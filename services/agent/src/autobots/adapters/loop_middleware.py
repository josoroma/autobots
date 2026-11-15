"""Every model and tool dispatch inside the loop goes through the root's limits and admission."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    InvalidToolCall,
    ToolCall,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.messages.tool import invalid_tool_call as make_invalid_tool_call
from langchain_core.messages.tool import tool_call as make_tool_call
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from autobots.adapters.model_replies import (
    charged,
    failure_without_status,
    finished,
    retry_after,
)
from autobots.adapters.models.catalog import RESERVED_PROMPT_TOKENS
from autobots.adapters.result_stream import current_tap
from autobots.application.compaction import (
    CompactionPolicy,
    StoredSummary,
    latest_summary,
    offload_large,
    safe_split,
    state_block,
    store_summary,
    summary_request,
    summary_text,
    total_chars,
)
from autobots.application.model_admission import (
    AdmissionRefused,
    AdmissionRequest,
    AttemptAlreadySettled,
    ModelAdmission,
    NoInferenceSlot,
    ReplyFacts,
)
from autobots.application.model_attempts import (
    UNCERTAIN,
    FailureClass,
    ModelOutput,
    ProviderFailure,
    RetryPolicy,
    call_with_policy,
    classify_status,
)
from autobots.application.run_usage import (
    LimitReached,
    RootLimits,
    active_seconds_used,
    consume,
    model_calls_used,
)
from autobots.application.runs import ancestors_running, current_status
from autobots.application.tool_gateway import ToolScope, ownership_refusal
from autobots.contracts.plans import GoalSpec

# Defined in the domain, so the run lifecycle uses it without importing this adapter (R-33).
# Re-exported for this module's users.
from autobots.domain.models import ModelRoute as ModelRoute
from autobots.domain.runs import INTERRUPTING
from autobots.domain.stops import REPAIRABLE, STOPPING, StopCode, repair_limit
from autobots.operations.logs import log_event

logger = logging.getLogger("autobots.worker")

CHECK_SECONDS = 1.0
MAX_FACT_CHARS = 100
MAX_FACT_NAMES = 20

_ADMITTED: ContextVar[bool] = ContextVar("autobots_model_call_admitted", default=False)
_INVOCATION: ContextVar[UUID | None] = ContextVar("autobots_model_invocation", default=None)
_MIDDLEWARE: ContextVar["LoopMiddleware | None"] = ContextVar("autobots_loop", default=None)
REPAIR_NOTE = "Your last reply was cut off, so none of it was used. Reply again, more briefly."
# Before each dispatch: raises `LoopStopped` to refuse it, and otherwise returns the run's seconds
# left. `LoopMiddleware`'s default reads ownership, run status and active time from the database.
Guard = Callable[[], Awaitable[float]]
# The settlement `tests/test_reported_charges.py` pins under this name (R-22).
_charged = charged


@contextmanager
def admitted_scope() -> Iterator[None]:
    """Model calls inside it are admitted, so `AdmittedModel` answers them. The middleware opens one
    around each dispatch it admitted, and nothing else in production does."""
    token = _ADMITTED.set(True)
    try:
        yield
    finally:
        _ADMITTED.reset(token)


@contextmanager
def active_middleware(middleware: "LoopMiddleware") -> Iterator[None]:
    """`current_middleware` returns this loop inside it, as it does during the loop's tool calls."""
    token = _MIDDLEWARE.set(middleware)
    try:
        yield
    finally:
        _MIDDLEWARE.reset(token)


def current_middleware() -> "LoopMiddleware | None":
    """The loop whose tool call is running, so a tool's own model calls go through its admission."""
    return _MIDDLEWARE.get()


def current_invocation() -> UUID | None:
    """The ledger row of the attempt being dispatched, or None outside one."""
    return _INVOCATION.get()


class LoopStopped(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class UnadmittedModelCall(Exception):
    """The SDK tried to call the model on its own, such as to summarize."""


class AdmittedModel(BaseChatModel):
    """A model that only answers inside an admitted dispatch, so no SDK path can spend unseen."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    delegate: Any
    bound: Any = None

    @property
    def _llm_type(self) -> str:
        return "autobots-admitted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        return self.model_copy(update={"bound": self.delegate.bind_tools(tools, **kwargs)})

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **_: Any) -> Any:
        raise UnadmittedModelCall("synchronous model calls are not available")

    async def _agenerate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        if not _ADMITTED.get():
            raise UnadmittedModelCall("this model call was not admitted")
        target = self.bound if self.bound is not None else self.delegate
        message = await _streamed(target, messages, stop=stop, **kwargs)
        return ChatResult(generations=[ChatGeneration(message=message)])


async def _streamed(target: Any, messages: Any, **kwargs: Any) -> BaseMessage:
    """Decision 0022's streaming decision: every call streams, and the reply is the assembled
    message, so usage, cost and tool calls settle exactly as before. The result tap, when a run has
    one, sees each chunk. A stream that fails after its first chunk was accepted and may be
    charged, so it is `partial_stream`, which is reconciled rather than retried."""
    if not hasattr(target, "astream"):
        # A delegate that can only answer whole, such as a test double.
        message: BaseMessage = await target.ainvoke(messages, **kwargs)
        return message
    tap = current_tap()
    if tap is not None:
        tap.begin()
    assembled: Any = None
    try:
        async for chunk in target.astream(messages, **kwargs):
            assembled = chunk if assembled is None else assembled + chunk
            if tap is not None:
                await tap.feed(chunk)
    except ProviderFailure:
        raise
    except Exception:
        if assembled is not None:
            raise ProviderFailure(FailureClass.PARTIAL_STREAM) from None
        raise
    finally:
        if tap is not None:
            await tap.finish()
    if assembled is None:
        raise ProviderFailure(FailureClass.PARTIAL_STREAM)
    return _strictly_parsed(assembled)


def _strictly_parsed(assembled: Any) -> BaseMessage:
    """The assembled reply, with each tool call's arguments parsed as a whole reply's would be.
    Assembly repairs partial JSON, so a call cut off mid-argument would otherwise pass for a real
    one with truncated arguments. Here it stays an invalid tool call, as it is without streaming."""
    message = message_chunk_to_message(assembled)
    pieces = getattr(assembled, "tool_call_chunks", None) or []
    if not pieces or not isinstance(message, AIMessage):
        return message
    calls: list[ToolCall] = []
    invalid: list[InvalidToolCall] = []
    for piece in pieces:
        raw = piece.get("args") or ""
        try:
            arguments = json.loads(raw) if raw.strip() else {}
        except ValueError:
            arguments = None
        if isinstance(arguments, dict):
            # The factories set each call's `type`, which the tool node relies on.
            calls.append(
                make_tool_call(name=piece.get("name") or "", args=arguments, id=piece.get("id"))
            )
        else:
            invalid.append(
                make_invalid_tool_call(
                    name=piece.get("name"),
                    args=raw,
                    id=piece.get("id"),
                    error="the arguments are not a complete JSON object",
                )
            )
    return message.model_copy(update={"tool_calls": calls, "invalid_tool_calls": invalid})


def request_bytes(request: Any) -> int:
    """An upper bound on the prompt's tokens, at about one per byte, as no tokenizer is pinned.

    It counts what compaction doesn't: the system prompt and the tools' schemas.
    """
    total = 0
    for message in [getattr(request, "system_message", None), *getattr(request, "messages", ())]:
        if message is not None:
            calls = getattr(message, "tool_calls", None) or []
            total += len(
                json.dumps([message.content, calls], default=str, ensure_ascii=False).encode()
            )
    return total + len(
        json.dumps(
            getattr(request, "tools", None) or [], default=_tool_text, ensure_ascii=False
        ).encode()
    )


def _tool_text(tool: Any) -> Any:
    try:
        return convert_to_openai_tool(tool)
    except (TypeError, ValueError, AttributeError):
        return str(tool)


def reservation_for(route: ModelRoute, prompt_bytes: int) -> int:
    """The route's worst case, plus whatever this request has beyond the tokens that assumes."""
    excess = max(prompt_bytes - RESERVED_PROMPT_TOKENS, 0)
    return (
        route.worst_case_micro_usd
        + (excess * route.input_per_million_micro_usd + 999_999) // 1_000_000
    )


def past_known_price(route: ModelRoute, prompt_bytes: int) -> bool:
    """A token takes at least a byte, so a request this short can't reach the tier."""
    return route.tier_from_tokens is not None and prompt_bytes >= route.tier_from_tokens


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def reply_facts(message: AIMessage) -> ReplyFacts:
    """For diagnosing a stopped run. Tool names come from the model, so they're bounded here."""
    metadata = message.response_metadata
    usage: Any = message.usage_metadata or {}
    details = usage.get("output_token_details") or {}
    finish = metadata.get("finish_reason")
    return ReplyFacts(
        finish_reason=finish[:MAX_FACT_CHARS] if isinstance(finish, str) else None,
        input_tokens=_count(usage.get("input_tokens")),
        output_tokens=_count(usage.get("output_tokens")),
        reasoning_tokens=_count(details.get("reasoning")),
        tool_names=tuple(str(call["name"])[:MAX_FACT_CHARS] for call in message.tool_calls)[
            :MAX_FACT_NAMES
        ],
        invalid_tool_calls=len(message.invalid_tool_calls),
    )


def _type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def uncertain_call_fields(error: BaseException) -> dict[str, Any]:
    """Types and a status only. A message can carry a provider's reply or a connection string."""
    fields: dict[str, Any] = {"error_type": _type_name(error)}
    cause = error.__cause__ or error.__context__
    if cause is not None:
        fields["cause_type"] = _type_name(cause)
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        fields["status"] = status
    return fields


def _log_uncertain(
    invocation: UUID, run: UUID, failure: FailureClass, error: BaseException, reason: str | None
) -> None:
    """Why a call's outcome is unknown, so a person ruling on it has more than the class."""
    fields = uncertain_call_fields(error)
    if reason is not None:
        fields["reason"] = reason
    log_event(
        logger,
        "worker.call_uncertain",
        logging.WARNING,
        invocation=str(invocation),
        run=str(run),
        failure=failure.value,
        **fields,
    )


class LoopMiddleware(AgentMiddleware[Any, Any]):
    def __init__(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
        self,
        connection: Any,
        scope: ToolScope,
        limits: RootLimits,
        route: ModelRoute,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        slot_wait_seconds: float = 30.0,
        model_call_seconds: float = 120.0,
        goal: GoalSpec | None = None,
        compaction: CompactionPolicy | None = None,
        summary_route: ModelRoute | None = None,
        guard: Guard | None = None,
        admission: Callable[[], ModelAdmission] | None = None,
    ) -> None:
        super().__init__()
        self._connection = connection
        self._scope = scope
        self._limits = limits
        self._route = route
        self._sleep = sleep
        self._slot_wait_seconds = slot_wait_seconds
        self._model_call_seconds = model_call_seconds
        self._goal = goal
        self._compaction = compaction or CompactionPolicy()
        self._summary_route = summary_route
        self._lock = asyncio.Lock()
        self._inner_stop: str | None = None
        # Production passes neither, so every dispatch checks the database and settles in the
        # ledger. Tests pass in-memory ones to reach these paths without a database (PTST-01).
        self._guard: Guard = guard or self._owned_with_time_left
        self._admission: Callable[[], ModelAdmission] = admission or (
            lambda: ModelAdmission(connection)
        )

    async def _owned_with_time_left(self) -> float:
        """Before each new dispatch: still the owner, still running, and time left."""
        refusal = await ownership_refusal(self._connection, self._scope)
        if refusal is not None:
            raise LoopStopped(refusal)
        parent = self._scope.parent_run_id
        if parent is not None and not await ancestors_running(self._connection, parent):
            raise LoopStopped(StopCode.PARENT_NOT_RUNNING)
        remaining = self._limits.active_seconds - await active_seconds_used(
            self._connection, self._scope.budget_run_id
        )
        if remaining <= 0:
            raise LoopStopped(StopCode.ACTIVE_TIME_LIMIT)
        return remaining

    async def _bounded(self, handler: Any, request: Any, stopped: list[str]) -> Any:
        """A hung call can't hold a run. Ending it proves nothing about what the provider did.

        Only a cancel interrupts. A pause waits for a safe boundary, and a worker that lost its
        lease still waits, because the reply is the only evidence of what the call cost.
        """
        task = asyncio.ensure_future(handler(request))
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=CHECK_SECONDS)
                if done:
                    return task.result()
                if loop.time() - started >= self._model_call_seconds:
                    raise ProviderFailure(
                        FailureClass.UNCERTAIN_ACCEPTANCE, reason="call_time_limit"
                    )
                if await current_status(self._connection, self._scope.run_id) in INTERRUPTING:
                    stopped.append(StopCode.RUN_NOT_RUNNING)
                    raise ProviderFailure(
                        FailureClass.UNCERTAIN_ACCEPTANCE, reason="run_interrupted"
                    )
        finally:
            if not task.done():
                task.cancel()

    async def _repair(self, code: str) -> None:
        try:
            await consume(
                self._connection, self._scope.budget_run_id, "repairs", self._limits.repairs
            )
        except LimitReached:
            raise LoopStopped(code) from None

    async def _compacted(self, request: Any, handler: Any) -> Any:
        """Only the model's view changes. Under budget, the request goes out as it came."""
        run_id = self._scope.run_id
        policy = self._compaction
        view = await offload_large(self._connection, run_id, request.messages, policy)
        if total_chars(view) <= policy.context_chars or self._goal is None:
            return request.override(messages=view)
        previous = await latest_summary(self._connection, run_id)
        covered = previous.covers if previous else 0
        block = await state_block(self._connection, run_id, self._goal)
        recent = view[covered:]
        lead = [HumanMessage(block), *([AIMessage(summary_text(previous))] if previous else [])]
        if total_chars([*lead, *recent]) > policy.context_chars:
            cut = safe_split(view, policy.keep_recent)
            if cut > covered:
                previous = await self._summarize(request, handler, view, previous, covered, cut)
                recent = view[cut:]
                lead = [HumanMessage(block), AIMessage(summary_text(previous))]
        return request.override(messages=[*lead, *recent])

    async def _summarize(
        self,
        request: Any,
        handler: Any,
        view: list[Any],
        previous: StoredSummary | None,
        covered: int,
        cut: int,
    ) -> StoredSummary:
        """Under the run's frozen summarizer role, through admission like any other call."""
        route = self._summary_route
        if route is None:
            raise LoopStopped(StopCode.ROUTE_NOT_BOUND)
        earlier = view[covered:cut]
        asked = request.override(
            messages=[HumanMessage(summary_request(earlier, previous))], tools=[]
        )
        response, complete = await self._with_slot(asked, handler, route)
        if not complete:
            raise LoopStopped(StopCode.COMPACTION_FAILED)
        text = str(response.result[-1].content)
        return await store_summary(
            self._connection,
            self._scope.run_id,
            covers=cut,
            summary=text,
            earlier=earlier,
            previous=previous,
            role=route.role,
            profile=route.profile,
        )

    async def _admitted_call(  # noqa: PLR0915 - baseline 2026-11-14, shrink only (STD-06)
        self, request: Any, handler: Any, remaining: float, route: ModelRoute | None = None
    ) -> tuple[Any, bool]:
        chosen = route or self._route
        run_id = self._scope.run_id
        budget = self._scope.budget_run_id
        limit: list[LimitReached] = []
        stopped: list[str] = []
        replies: list[Any] = []
        last_ticket: list[Any] = []

        async def dispatch(ticket: Any) -> ModelOutput:
            last_ticket.append(ticket)
            # Every attempt, including a retry after its backoff. Nothing has been sent yet, so
            # the failure closes the reservation as never accepted.
            try:
                await self._guard()
            except LoopStopped as stop:
                stopped.append(stop.code)
                raise ProviderFailure(FailureClass.OTHER) from None
            try:
                await consume(self._connection, budget, "model_calls", self._limits.model_calls)
            except LimitReached as reached:
                limit.append(reached)
                raise ProviderFailure(FailureClass.OTHER) from None
            with admitted_scope():
                invocation = _INVOCATION.set(ticket.invocation_id)
                try:
                    response = await self._bounded(handler, request, stopped)
                except ProviderFailure as provider_failure:
                    if provider_failure.failure in UNCERTAIN:
                        _log_uncertain(
                            ticket.invocation_id,
                            run_id,
                            provider_failure.failure,
                            provider_failure,
                            provider_failure.reason,
                        )
                    raise
                except Exception as error:  # noqa: BLE001 - any failure of a model call becomes a classified ProviderFailure
                    status = getattr(error, "status_code", None)
                    failure = (
                        classify_status(status)
                        if isinstance(status, int)
                        else failure_without_status(error)
                    )
                    if failure in UNCERTAIN:
                        _log_uncertain(ticket.invocation_id, run_id, failure, error, None)
                    raise ProviderFailure(failure, retry_after=retry_after(error)) from None
                finally:
                    _INVOCATION.reset(invocation)
            message = response.result[-1]
            replies.append(response)
            return ModelOutput(
                text=str(message.content),
                complete=finished(message),
                charged_micro_usd=charged(message),
            )

        used = await model_calls_used(self._connection, budget)
        try:
            prompt_bytes = request_bytes(request)
        except UnicodeEncodeError:
            # A lone surrogate is no text a provider can read, so nothing is reserved or sent.
            raise LoopStopped(StopCode.REQUEST_UNENCODABLE) from None
        if past_known_price(chosen, prompt_bytes):
            raise LoopStopped(FailureClass.COST_UNAVAILABLE.value)
        admission_request = AdmissionRequest(
            workspace_id=self._scope.workspace_id,
            root_run_id=budget,
            run_id=run_id,
            role=chosen.role,
            profile=chosen.profile,
            wire_id=chosen.wire_id,
            attempt=used + 1,
            worst_case_micro_usd=reservation_for(chosen, prompt_bytes),
        )
        policy = RetryPolicy(
            deadline=datetime.now(UTC) + timedelta(seconds=remaining), sleep=self._sleep
        )
        ledger = self._admission()
        try:
            output = await call_with_policy(ledger, admission_request, dispatch, policy)
        except ProviderFailure as failure:
            if stopped:
                raise LoopStopped(stopped[0]) from None
            if limit:
                raise LoopStopped(limit[0].code) from None
            raise LoopStopped(failure.failure.value) from None
        except AttemptAlreadySettled:
            # Recovery classified this call while it was out. Its charge is late evidence. Any other
            # error is a defect and propagates (PADP-11).
            late = charged(replies[-1].result[-1]) if replies else None
            if late is not None and last_ticket:
                await ledger.reconcile(last_ticket[-1].invocation_id, late, source="provider")
            raise LoopStopped(StopCode.LEASE_LOST) from None
        # Settled by now, so this can't change what the call cost or whether it counted.
        await ledger.record_reply(
            last_ticket[-1].invocation_id, reply_facts(replies[-1].result[-1])
        )
        return replies[-1], output.complete

    async def _with_slot(
        self, request: Any, handler: Any, route: ModelRoute | None = None
    ) -> tuple[Any, bool]:
        """One admitted call. A busy slot is waited out, and any other refusal stops the loop."""
        waited = 0.0
        while True:
            remaining = await self._guard()
            try:
                return await self._admitted_call(request, handler, remaining, route)
            except NoInferenceSlot:
                if waited >= self._slot_wait_seconds:
                    raise LoopStopped(NoInferenceSlot.code) from None
                waited += 1.0
                await self._sleep(1.0)
            except AdmissionRefused as refused:
                raise LoopStopped(refused.code) from None

    async def admitted(
        self, request: Any, handler: Callable[[Any], Awaitable[Any]], route: ModelRoute
    ) -> tuple[Any, bool]:
        """One admitted call on another of the run's frozen routes, as browsing makes them.

        A stop here stops the loop too, once the tool call that made it returns.
        """
        try:
            return await self._with_slot(request, handler, route)
        except LoopStopped as stopped:
            self._inner_stop = stopped.code
            raise

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        await self._guard()
        try:
            request = await self._compacted(request, handler)
        except LimitReached as reached:
            raise LoopStopped(reached.code) from None
        current = request
        while True:
            response, complete = await self._with_slot(current, handler)
            if complete:
                return response
            # Being cut off is worth one shorter try. A provider's own stop wouldn't change.
            if response.result[-1].response_metadata.get("finish_reason") != "length":
                raise LoopStopped(FailureClass.INCOMPLETE_OUTPUT.value)
            await self._repair(FailureClass.INCOMPLETE_OUTPUT.value)
            current = request.override(messages=[*request.messages, HumanMessage(REPAIR_NOTE)])

    async def awrap_tool_call(
        self, request: Any, handler: Callable[[Any], Awaitable[Any]]
    ) -> ToolMessage:
        async with self._lock:
            await self._guard()
            try:
                await consume(
                    self._connection,
                    self._scope.budget_run_id,
                    "tool_dispatches",
                    self._limits.tool_dispatches,
                )
            except LimitReached as reached:
                raise LoopStopped(reached.code) from None
            self._inner_stop = None
            with active_middleware(self):
                reply = await handler(request)
            if self._inner_stop is not None:
                raise LoopStopped(self._inner_stop)
            code = json.loads(reply.content).get("code")
            if code in STOPPING:
                raise LoopStopped(code)
            if code in REPAIRABLE:
                await self._repair(repair_limit(code))
            message: ToolMessage = reply
            return message
