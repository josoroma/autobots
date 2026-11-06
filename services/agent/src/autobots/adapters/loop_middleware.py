"""Every model and tool dispatch inside the loop goes through the root's limits and admission."""

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from autobots.adapters.models.catalog import RESERVED_PROMPT_TOKENS
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
    ModelAdmission,
    NoInferenceSlot,
    ReplyFacts,
)
from autobots.application.model_attempts import (
    FailureClass,
    ModelOutput,
    ProviderFailure,
    RetryPolicy,
    call_with_policy,
    classify_status,
)
from autobots.application.plans import PLAN_REJECTIONS
from autobots.application.run_usage import LimitReached, RootLimits, active_seconds_used, consume
from autobots.application.tool_gateway import ToolScope, ownership_refusal
from autobots.contracts.plans import GoalSpec

CHECK_SECONDS = 1.0
INCOMPLETE_FINISHES = frozenset({"length", "error", "content_filter"})
INTERRUPTING = frozenset({"cancelling", "cancelled", "failed", "succeeded"})
MAX_FACT_CHARS = 100
MAX_FACT_NAMES = 20

REPAIRABLE = PLAN_REJECTIONS | {"invalid_arguments", "route_not_granted", "scope_expansion_denied"}
STOPPING = frozenset(
    {
        "plan_revisions_limit",
        "assignment_paused",
        "assignment_lost",
        "assignment_busy",
        "approval_pending",
        "outcome_unknown",
        # N-15: its result is unknown, so nothing should build on it.
        "output_too_large",
    }
)
_ADMITTED: ContextVar[bool] = ContextVar("autobots_model_call_admitted", default=False)
_INVOCATION: ContextVar[UUID | None] = ContextVar("autobots_model_invocation", default=None)
REPAIR_NOTE = "Your last reply was cut off, so none of it was used. Reply again, more briefly."


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
        message = await target.ainvoke(messages, stop=stop, **kwargs)
        return ChatResult(generations=[ChatGeneration(message=message)])


@dataclass(frozen=True)
class ModelRoute:
    """A worker takes this from the run's frozen policy. `run_goal` refuses one that differs."""

    role: str
    profile: str
    wire_id: str
    worst_case_micro_usd: int
    # For a request larger than the worst case already assumes. Zero where no price is known.
    input_per_million_micro_usd: int = 0
    # Where a higher rate starts, past the size assumed. Nothing is reserved at that rate.
    tier_from_tokens: int | None = None


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


def _retry_after(error: Exception) -> float | None:
    # The SDK's errors carry `headers`. Other clients' errors carry them on `response`.
    headers = (
        getattr(error, "headers", None)
        or getattr(getattr(error, "response", None), "headers", None)
        or {}
    )
    try:
        seconds = float(str(headers.get("retry-after")))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _charged(message: AIMessage) -> int | None:
    cost = message.response_metadata.get("cost")
    return None if cost is None else round(float(cost) * 1_000_000)


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


def _finished(message: AIMessage) -> bool:
    """A reply cut off or stopped by the provider is never run, whatever it appears to hold."""
    return message.response_metadata.get("finish_reason") not in INCOMPLETE_FINISHES


def _failure_without_status(error: Exception) -> FailureClass:
    """A connection that never opened carried nothing. Anything else may have been accepted."""
    if isinstance(error, httpx.ConnectError | httpx.ConnectTimeout):
        return FailureClass.NETWORK_BEFORE_ACCEPTANCE
    return FailureClass.UNCERTAIN_ACCEPTANCE


class LoopMiddleware(AgentMiddleware[Any, Any]):
    def __init__(
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

    async def _guard(self) -> float:
        """Before each new dispatch: still the owner, still running, and time left."""
        refusal = await ownership_refusal(self._connection, self._scope)
        if refusal is not None:
            raise LoopStopped(refusal)
        if self._scope.parent_run_id is not None:
            cursor = await self._connection.execute(
                "with recursive up as (select id, parent_run_id, status from public.runs "
                "where id = %s union all select r.id, r.parent_run_id, r.status "
                "from public.runs r join up u on r.id = u.parent_run_id) "
                "select count(*) from up where status <> 'running'",
                (self._scope.parent_run_id,),
            )
            if (await cursor.fetchone())[0]:
                raise LoopStopped("parent_not_running")
        remaining = self._limits.active_seconds - await active_seconds_used(
            self._connection, self._scope.budget_run_id
        )
        if remaining <= 0:
            raise LoopStopped("active_time_limit")
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
                    raise ProviderFailure(FailureClass.UNCERTAIN_ACCEPTANCE)
                cursor = await self._connection.execute(
                    "select status from public.runs where id = %s", (self._scope.run_id,)
                )
                row = await cursor.fetchone()
                if row is not None and row[0] in INTERRUPTING:
                    stopped.append("run_not_running")
                    raise ProviderFailure(FailureClass.UNCERTAIN_ACCEPTANCE)
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
            raise LoopStopped("route_not_bound")
        earlier = view[covered:cut]
        asked = request.override(
            messages=[HumanMessage(summary_request(earlier, previous))], tools=[]
        )
        response, complete = await self._with_slot(asked, handler, route)
        if not complete:
            raise LoopStopped("compaction_failed")
        text = str(response.result[-1].content)
        return await store_summary(
            self._connection,
            self._scope.run_id,
            cut,
            text,
            earlier,
            previous,
            route.role,
            route.profile,
        )

    async def _admitted_call(
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
            token = _ADMITTED.set(True)
            invocation = _INVOCATION.set(ticket.invocation_id)
            try:
                response = await self._bounded(handler, request, stopped)
            except ProviderFailure:
                raise
            except Exception as error:
                status = getattr(error, "status_code", None)
                failure = (
                    classify_status(status)
                    if isinstance(status, int)
                    else _failure_without_status(error)
                )
                raise ProviderFailure(failure, retry_after=_retry_after(error)) from None
            finally:
                _INVOCATION.reset(invocation)
                _ADMITTED.reset(token)
            message = response.result[-1]
            replies.append(response)
            return ModelOutput(
                text=str(message.content),
                complete=_finished(message),
                charged_micro_usd=_charged(message),
            )

        cursor = await self._connection.execute(
            "select model_calls from app_private.run_usage where run_id = %s", (budget,)
        )
        used = (await cursor.fetchone())[0]
        prompt_bytes = request_bytes(request)
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
        try:
            output = await call_with_policy(
                ModelAdmission(self._connection), admission_request, dispatch, policy
            )
        except ProviderFailure as failure:
            if stopped:
                raise LoopStopped(stopped[0]) from None
            if limit:
                raise LoopStopped(limit[0].code) from None
            raise LoopStopped(failure.failure.value) from None
        except ValueError:
            # Recovery classified this call while it was out. Its charge is late evidence.
            charged = _charged(replies[-1].result[-1]) if replies else None
            if charged is not None and last_ticket:
                await ModelAdmission(self._connection).reconcile(
                    last_ticket[-1].invocation_id, charged, source="provider"
                )
            raise LoopStopped("lease_lost") from None
        # Settled by now, so this can't change what the call cost or whether it counted.
        await ModelAdmission(self._connection).record_reply(
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
            reply = await handler(request)
            code = json.loads(reply.content).get("code")
            if code in STOPPING or code in {"lease_lost", "run_not_running"}:
                raise LoopStopped(code)
            if code in REPAIRABLE:
                await self._repair(f"repair_limit:{code}")
            message: ToolMessage = reply
            return message
