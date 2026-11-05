"""Every model and tool dispatch inside the loop goes through the root's limits and admission."""

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ConfigDict

from autobots.application.model_admission import (
    AdmissionRefused,
    AdmissionRequest,
    ModelAdmission,
    NoInferenceSlot,
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

CHECK_SECONDS = 1.0
INTERRUPTING = frozenset({"cancelling", "cancelled", "failed", "succeeded"})

REPAIRABLE = PLAN_REJECTIONS | {"invalid_arguments", "route_not_granted", "scope_expansion_denied"}
STOPPING = frozenset(
    {
        "plan_revisions_limit",
        "assignment_paused",
        "assignment_lost",
        "approval_pending",
        "outcome_unknown",
    }
)
_ADMITTED: ContextVar[bool] = ContextVar("autobots_model_call_admitted", default=False)
REPAIR_NOTE = "Your last reply was cut off, so none of it was used. Reply again, more briefly."


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


def _retry_after(error: Exception) -> float | None:
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    try:
        seconds = float(str(headers.get("retry-after")))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _charged(message: AIMessage) -> int | None:
    cost = message.response_metadata.get("cost")
    return None if cost is None else round(float(cost) * 1_000_000)


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
    ) -> None:
        super().__init__()
        self._connection = connection
        self._scope = scope
        self._limits = limits
        self._route = route
        self._sleep = sleep
        self._slot_wait_seconds = slot_wait_seconds
        self._model_call_seconds = model_call_seconds
        self._lock = asyncio.Lock()

    async def _guard(self) -> float:
        """Before each new dispatch: still the owner, still running, and time left."""
        refusal = await ownership_refusal(self._connection, self._scope)
        if refusal is not None:
            raise LoopStopped(refusal)
        if self._scope.parent_run_id is not None:
            cursor = await self._connection.execute(
                "select status from public.runs where id = %s", (self._scope.parent_run_id,)
            )
            if (await cursor.fetchone())[0] != "running":
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

    async def _admitted_call(
        self, request: Any, handler: Any, remaining: float
    ) -> tuple[Any, bool]:
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
            try:
                response = await self._bounded(handler, request, stopped)
            except ProviderFailure:
                raise
            except Exception as error:
                status = getattr(error, "status_code", None)
                failure = (
                    classify_status(status)
                    if isinstance(status, int)
                    else FailureClass.UNCERTAIN_ACCEPTANCE
                )
                raise ProviderFailure(failure, retry_after=_retry_after(error)) from None
            finally:
                _ADMITTED.reset(token)
            message = response.result[-1]
            replies.append(response)
            return ModelOutput(
                text=str(message.content),
                complete=message.response_metadata.get("finish_reason") != "length",
                charged_micro_usd=_charged(message),
            )

        cursor = await self._connection.execute(
            "select model_calls from app_private.run_usage where run_id = %s", (budget,)
        )
        used = (await cursor.fetchone())[0]
        admission_request = AdmissionRequest(
            workspace_id=self._scope.workspace_id,
            root_run_id=budget,
            run_id=run_id,
            role=self._route.role,
            profile=self._route.profile,
            wire_id=self._route.wire_id,
            attempt=used + 1,
            worst_case_micro_usd=self._route.worst_case_micro_usd,
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
                    last_ticket[-1].invocation_id, charged
                )
            raise LoopStopped("lease_lost") from None
        return replies[-1], output.complete

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        current = request
        waited = 0.0
        while True:
            remaining = await self._guard()
            try:
                response, complete = await self._admitted_call(current, handler, remaining)
            except NoInferenceSlot:
                if waited >= self._slot_wait_seconds:
                    raise LoopStopped(NoInferenceSlot.code) from None
                waited += 1.0
                await self._sleep(1.0)
                continue
            except AdmissionRefused as refused:
                raise LoopStopped(refused.code) from None
            if complete:
                return response
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
