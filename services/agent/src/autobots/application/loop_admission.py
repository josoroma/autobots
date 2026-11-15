"""Every model and tool dispatch inside a goal loop goes through the root's limits and admission:
SP-008, PRD-Model-Providers MP-07 and MP-08, and Decision 0022's streaming decision.

`LoopAdmission` guards each dispatch (still the owner, still running, time left), admits and
reserves each model call, bounds it, classifies its failure, settles it, compacts the model's view
and counts each tool dispatch. The framework's requests reach it as a `ModelCall`, which only says
how big it is and how to send it, so nothing here depends on an agent framework:
adapters/loop_middleware.py is the LangChain side (refactor plan R-62, PADP-08 and PADP-09).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Protocol
from uuid import UUID

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage

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
from autobots.application.loop_policy import (
    REPAIR_NOTE,
    DispatchStopped,
    LoopStopped,
    past_known_price,
    reservation_for,
    uncertain_call_fields,
)
from autobots.application.model_admission import (
    AdmissionRefused,
    AdmissionRequest,
    AttemptAlreadySettled,
    ModelAdmission,
    NoInferenceSlot,
    ReplyFacts,
    Ticket,
)
from autobots.application.model_attempts import (
    UNCERTAIN,
    FailureClass,
    ModelOutput,
    ProviderFailure,
    RetryPolicy,
    call_with_policy,
)
from autobots.application.run_usage import (
    LimitReached,
    RootLimits,
    active_seconds_used,
    consume,
    model_calls_used,
)
from autobots.application.runs import ancestors_running, current_status
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ownership_refusal
from autobots.contracts.plans import GoalSpec
from autobots.domain.models import ModelRoute
from autobots.domain.runs import INTERRUPTING
from autobots.domain.stops import REPAIRABLE, STOPPING, StopCode, repair_limit

# Written through the standard logger, as STD-01 keeps this layer from importing
# operations/logs.py; that module's formatter renders the record and its conventions apply.
logger = logging.getLogger("autobots.worker")

CHECK_SECONDS = 1.0

_ADMITTED: ContextVar[bool] = ContextVar("autobots_model_call_admitted", default=False)
_INVOCATION: ContextVar[UUID | None] = ContextVar("autobots_model_invocation", default=None)

# Before each dispatch: raises `LoopStopped` to refuse it, and otherwise returns the run's seconds
# left. `LoopAdmission`'s default reads ownership, run status and active time from the database.
Guard = Callable[[], Awaitable[float]]


class PromptParts(Protocol):
    """What sizing a model request reads: its messages, its system message and its tools."""

    @property
    def messages(self) -> Sequence[BaseMessage]: ...

    @property
    def system_message(self) -> BaseMessage | None: ...

    @property
    def tools(self) -> Sequence[object]: ...


class ModelReply(Protocol):
    """A model's answer to one request, its last message the reply."""

    @property
    def result(self) -> Sequence[BaseMessage]: ...


class ModelCall[S: ModelReply](Protocol):
    """One model request as the framework holds it: an upper bound on its prompt in bytes, which
    raises `UnicodeEncodeError` for text no provider can read, and how to send it."""

    def prompt_bytes(self) -> int: ...

    async def send(self) -> S: ...


class ReplyReader(Protocol):
    """How the framework's reply and failures read, from the reply alone."""

    def output(self, reply: ModelReply) -> ModelOutput: ...

    def facts(self, reply: ModelReply) -> ReplyFacts: ...

    def cut_off(self, reply: ModelReply) -> bool: ...

    def failure(self, error: Exception) -> ProviderFailure: ...


class AdmittingLoop(Protocol):
    """The loop whose tool call is running, so a tool's own model calls go through its admission."""

    async def admitted[Q: PromptParts, S: ModelReply](
        self, request: Q, handler: Callable[[Q], Awaitable[S]], route: ModelRoute
    ) -> tuple[S, bool]: ...


# Set by the loop around each tool call it dispatches. browse_trial.py and its disposable check set
# it directly, through loop_middleware's name for it.
ACTIVE_LOOP: ContextVar[AdmittingLoop | None] = ContextVar("autobots_loop", default=None)


@contextmanager
def admitted_scope() -> Iterator[None]:
    """Model calls inside it are admitted, so `AdmittedModel` answers them. `LoopAdmission` opens
    one around each dispatch it admitted, and nothing else in production does."""
    token = _ADMITTED.set(True)
    try:
        yield
    finally:
        _ADMITTED.reset(token)


def model_call_admitted() -> bool:
    return _ADMITTED.get()


@contextmanager
def active_middleware(loop: AdmittingLoop) -> Iterator[None]:
    """`current_middleware` returns this loop inside it, as it does during the loop's tool calls."""
    token = ACTIVE_LOOP.set(loop)
    try:
        yield
    finally:
        ACTIVE_LOOP.reset(token)


def current_middleware() -> AdmittingLoop | None:
    """The loop whose tool call is running, or None outside one."""
    return ACTIVE_LOOP.get()


def current_invocation() -> UUID | None:
    """The ledger row of the attempt being dispatched, or None outside one."""
    return _INVOCATION.get()


@dataclass(frozen=True)
class LoopSettings:
    """How long a loop waits and what it compacts toward. Production passes the worker's; tests
    pass an instant `sleep`."""

    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    slot_wait_seconds: float = 30.0
    model_call_seconds: float = 120.0
    goal: GoalSpec | None = None
    compaction: CompactionPolicy = field(default_factory=CompactionPolicy)
    summary_route: ModelRoute | None = None


@dataclass
class _Attempted[S: ModelReply]:
    """The last attempt of one admitted call: its ledger row and the reply it got, if any."""

    ticket: Ticket | None = None
    reply: S | None = None


@dataclass
class LoopAdmission:
    """One run's admission for its loop. `guard` and `admission` default to the database's and the
    ledger's; tests pass in-memory ones through them (PTST-01)."""

    connection: object
    scope: ToolScope
    limits: RootLimits
    route: ModelRoute
    replies: ReplyReader
    settings: LoopSettings = field(default_factory=LoopSettings)
    guard_with: Guard | None = None
    admission: Callable[[], ModelAdmission] | None = None
    # A stop a tool's own model call met, so the loop stops too once that tool call returns.
    inner_stop: str | None = field(default=None, init=False)

    async def guard(self) -> float:
        """Before each new dispatch: still the owner, still running, and the seconds left."""
        if self.guard_with is not None:
            return await self.guard_with()
        refusal = await ownership_refusal(self.connection, self.scope)
        if refusal is not None:
            raise LoopStopped(refusal)
        parent = self.scope.parent_run_id
        if parent is not None and not await ancestors_running(self.connection, parent):
            raise LoopStopped(StopCode.PARENT_NOT_RUNNING)
        remaining = self.limits.active_seconds - await active_seconds_used(
            self.connection, self.scope.budget_run_id
        )
        if remaining <= 0:
            raise LoopStopped(StopCode.ACTIVE_TIME_LIMIT)
        return remaining

    async def repair(self, code: str) -> None:
        try:
            await consume(self.connection, self.scope.budget_run_id, "repairs", self.limits.repairs)
        except LimitReached:
            raise LoopStopped(code) from None

    async def turn[S: ModelReply](
        self, call: ModelCall[S], again: Callable[[str], ModelCall[S]]
    ) -> S:
        """The loop's own model call. Being cut off is worth a shorter try, asked with `again`, as
        long as repairs remain; a provider's own stop wouldn't change."""
        current = call
        while True:
            reply, output = await self._with_slot(current)
            if output.complete:
                return reply
            if not self.replies.cut_off(reply):
                raise LoopStopped(FailureClass.INCOMPLETE_OUTPUT.value)
            await self.repair(FailureClass.INCOMPLETE_OUTPUT.value)
            current = again(REPAIR_NOTE)

    async def nested[S: ModelReply](self, call: ModelCall[S], route: ModelRoute) -> tuple[S, bool]:
        """One admitted call on another of the run's frozen routes, as browsing makes them.

        A stop here stops the loop too, once the tool call that made it returns.
        """
        try:
            reply, output = await self._with_slot(call, route)
        except LoopStopped as stopped:
            self.inner_stop = stopped.code
            raise
        return reply, output.complete

    async def tool_dispatch[T](
        self, run: Callable[[], Awaitable[T]], code_of: Callable[[T], str | None]
    ) -> T:
        """One tool call: the run still owned and a dispatch counted first, then the gateway's code
        read for a stop or a repair. A stop a nested model call met wins."""
        await self.guard()
        try:
            await consume(
                self.connection,
                self.scope.budget_run_id,
                "tool_dispatches",
                self.limits.tool_dispatches,
            )
        except LimitReached as reached:
            raise LoopStopped(reached.code) from None
        self.inner_stop = None
        reply = await run()
        if self.inner_stop is not None:
            raise LoopStopped(self.inner_stop)
        code = code_of(reply)
        if code in STOPPING:
            raise LoopStopped(code)
        if code in REPAIRABLE:
            await self.repair(repair_limit(code))
        return reply

    async def compact[S: ModelReply](
        self, messages: list[AnyMessage], summarize: Callable[[list[AnyMessage]], ModelCall[S]]
    ) -> list[AnyMessage]:
        """The model's view of `messages`, within the compaction budget. Only the view changes, and
        under budget it is the messages as they came, with large tool results offloaded."""
        try:
            return await self._compacted(messages, summarize)
        except LimitReached as reached:
            raise LoopStopped(reached.code) from None

    async def _compacted[S: ModelReply](
        self, messages: list[AnyMessage], summarize: Callable[[list[AnyMessage]], ModelCall[S]]
    ) -> list[AnyMessage]:
        run_id, policy, goal = self.scope.run_id, self.settings.compaction, self.settings.goal
        view: list[AnyMessage] = await offload_large(self.connection, run_id, messages, policy)
        if total_chars(view) <= policy.context_chars or goal is None:
            return view
        previous = await latest_summary(self.connection, run_id)
        covered = previous.covers if previous else 0
        block = await state_block(self.connection, run_id, goal)
        recent = view[covered:]
        lead: list[AnyMessage] = [HumanMessage(block)]
        if previous:
            lead.append(AIMessage(summary_text(previous)))
        if total_chars([*lead, *recent]) > policy.context_chars:
            cut = safe_split(view, policy.keep_recent)
            if cut > covered:
                previous = await self._summarize(view, previous, covered, cut, summarize)
                recent = view[cut:]
                lead = [HumanMessage(block), AIMessage(summary_text(previous))]
        return [*lead, *recent]

    async def _summarize[S: ModelReply](
        self,
        view: list[AnyMessage],
        previous: StoredSummary | None,
        covered: int,
        cut: int,
        summarize: Callable[[list[AnyMessage]], ModelCall[S]],
    ) -> StoredSummary:
        """Under the run's frozen summarizer role, through admission like any other call."""
        route = self.settings.summary_route
        if route is None:
            raise LoopStopped(StopCode.ROUTE_NOT_BOUND)
        earlier = view[covered:cut]
        asked = summarize([HumanMessage(summary_request(earlier, previous))])
        _, output = await self._with_slot(asked, route)
        if not output.complete:
            raise LoopStopped(StopCode.COMPACTION_FAILED)
        return await store_summary(
            self.connection,
            self.scope.run_id,
            covers=cut,
            summary=output.text,
            earlier=earlier,
            previous=previous,
            role=route.role,
            profile=route.profile,
        )

    async def _with_slot[S: ModelReply](
        self, call: ModelCall[S], route: ModelRoute | None = None
    ) -> tuple[S, ModelOutput]:
        """One admitted call. A busy slot is waited out, and any other refusal stops the loop."""
        waited = 0.0
        while True:
            remaining = await self.guard()
            try:
                return await self._admitted_call(call, remaining, route or self.route)
            except NoInferenceSlot:
                if waited >= self.settings.slot_wait_seconds:
                    raise LoopStopped(NoInferenceSlot.code) from None
                waited += 1.0
                await self.settings.sleep(1.0)
            except AdmissionRefused as refused:
                raise LoopStopped(refused.code) from None

    async def _admission_request[S: ModelReply](
        self, route: ModelRoute, call: ModelCall[S]
    ) -> AdmissionRequest:
        """What the ledger reserves for this call: the route's worst case, and more for a request
        larger than that assumes. One that could reach a price nothing reserves isn't sent."""
        used = await model_calls_used(self.connection, self.scope.budget_run_id)
        try:
            prompt_bytes = call.prompt_bytes()
        except UnicodeEncodeError:
            # A lone surrogate is no text a provider can read, so nothing is reserved or sent.
            raise LoopStopped(StopCode.REQUEST_UNENCODABLE) from None
        if past_known_price(route, prompt_bytes):
            raise LoopStopped(FailureClass.COST_UNAVAILABLE.value)
        return AdmissionRequest(
            workspace_id=self.scope.workspace_id,
            root_run_id=self.scope.budget_run_id,
            run_id=self.scope.run_id,
            role=route.role,
            profile=route.profile,
            wire_id=route.wire_id,
            attempt=used + 1,
            worst_case_micro_usd=reservation_for(route, prompt_bytes),
        )

    async def _admitted_call[S: ModelReply](
        self, call: ModelCall[S], remaining: float, route: ModelRoute
    ) -> tuple[S, ModelOutput]:
        attempted: _Attempted[S] = _Attempted()
        request = await self._admission_request(route, call)
        policy = RetryPolicy(
            deadline=datetime.now(UTC) + timedelta(seconds=remaining), sleep=self.settings.sleep
        )
        ledger = self.admission() if self.admission is not None else ModelAdmission(self.connection)
        try:
            output = await call_with_policy(
                ledger, request, partial(self._dispatch, attempted, call), policy
            )
        except DispatchStopped as stopped:
            raise LoopStopped(stopped.code) from None
        except ProviderFailure as failure:
            raise LoopStopped(failure.failure.value) from None
        except AttemptAlreadySettled:
            # Recovery classified this call while it was out. Its charge is late evidence. Any other
            # error is a defect and propagates (PADP-11).
            await self._reconcile_late_charge(ledger, attempted)
            raise LoopStopped(StopCode.LEASE_LOST) from None
        ticket, reply = attempted.ticket, attempted.reply
        if ticket is None or reply is None:
            raise RuntimeError("a call settled without its attempt and reply")
        # Settled by now, so this can't change what the call cost or whether it counted.
        await ledger.record_reply(ticket.invocation_id, self.replies.facts(reply))
        return reply, output

    async def _reconcile_late_charge[S: ModelReply](
        self, ledger: ModelAdmission, attempted: _Attempted[S]
    ) -> None:
        if attempted.reply is None or attempted.ticket is None:
            return
        late = self.replies.output(attempted.reply).charged_micro_usd
        if late is not None:
            await ledger.reconcile(attempted.ticket.invocation_id, late, source="provider")

    async def _dispatch[S: ModelReply](
        self, attempted: _Attempted[S], call: ModelCall[S], ticket: Ticket
    ) -> ModelOutput:
        """Every attempt, including a retry after its backoff. Until the call is sent, a refusal
        closes the reservation as never accepted."""
        attempted.ticket = ticket
        try:
            await self.guard()
        except LoopStopped as stop:
            raise DispatchStopped(FailureClass.OTHER, stop.code) from None
        try:
            await consume(
                self.connection, self.scope.budget_run_id, "model_calls", self.limits.model_calls
            )
        except LimitReached as reached:
            raise DispatchStopped(FailureClass.OTHER, reached.code) from None
        with admitted_scope():
            invocation = _INVOCATION.set(ticket.invocation_id)
            try:
                reply = await self._bounded(call)
            except ProviderFailure as failure:
                if failure.failure in UNCERTAIN:
                    self._log_uncertain(
                        ticket.invocation_id, failure.failure, failure, failure.reason
                    )
                raise
            except Exception as error:  # noqa: BLE001 - any failure of a model call becomes a classified ProviderFailure
                classified = self.replies.failure(error)
                if classified.failure in UNCERTAIN:
                    self._log_uncertain(ticket.invocation_id, classified.failure, error, None)
                raise classified from None
            finally:
                _INVOCATION.reset(invocation)
        attempted.reply = reply
        return self.replies.output(reply)

    async def _bounded[S: ModelReply](self, call: ModelCall[S]) -> S:
        """A hung call can't hold a run. Ending it proves nothing about what the provider did.

        Only a cancel interrupts. A pause waits for a safe boundary, and a worker that lost its
        lease still waits, because the reply is the only evidence of what the call cost.
        """
        task = asyncio.ensure_future(call.send())
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=CHECK_SECONDS)
                if done:
                    return task.result()
                if loop.time() - started >= self.settings.model_call_seconds:
                    raise ProviderFailure(
                        FailureClass.UNCERTAIN_ACCEPTANCE, reason="call_time_limit"
                    )
                if await current_status(self.connection, self.scope.run_id) in INTERRUPTING:
                    raise DispatchStopped(
                        FailureClass.UNCERTAIN_ACCEPTANCE,
                        StopCode.RUN_NOT_RUNNING,
                        reason="run_interrupted",
                    )
        finally:
            if not task.done():
                task.cancel()

    def _log_uncertain(
        self, invocation: UUID, failure: FailureClass, error: BaseException, reason: str | None
    ) -> None:
        """Why a call's outcome is unknown, so a person ruling on it has more than the class."""
        fields = uncertain_call_fields(error)
        if reason is not None:
            fields["reason"] = reason
        logger.warning(
            "worker.call_uncertain",
            extra={
                "fields": {
                    "invocation": str(invocation),
                    "run": str(self.scope.run_id),
                    "failure": failure.value,
                    **fields,
                }
            },
        )
