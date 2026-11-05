"""Every model and tool dispatch inside the loop goes through the root's limits and admission."""

import asyncio
import json
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

REPAIRABLE = PLAN_REJECTIONS | {"invalid_arguments"}
STOPPING = frozenset({"plan_revisions_limit"})
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
    role: str
    profile: str
    wire_id: str
    worst_case_micro_usd: int


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
    ) -> None:
        super().__init__()
        self._connection = connection
        self._scope = scope
        self._limits = limits
        self._route = route
        self._sleep = sleep
        self._slot_wait_seconds = slot_wait_seconds
        self._lock = asyncio.Lock()

    async def _guard(self) -> float:
        """Before each new dispatch: still the owner, still running, and time left."""
        refusal = await ownership_refusal(self._connection, self._scope)
        if refusal is not None:
            raise LoopStopped(refusal)
        remaining = self._limits.active_seconds - await active_seconds_used(
            self._connection, self._scope.run_id
        )
        if remaining <= 0:
            raise LoopStopped("active_time_limit")
        return remaining

    async def _repair(self, code: str) -> None:
        try:
            await consume(self._connection, self._scope.run_id, "repairs", self._limits.repairs)
        except LimitReached:
            raise LoopStopped(code) from None

    async def _admitted_call(
        self, request: Any, handler: Any, remaining: float
    ) -> tuple[Any, bool]:
        run_id = self._scope.run_id
        limit: list[LimitReached] = []
        replies: list[Any] = []

        async def dispatch(_: Any) -> ModelOutput:
            try:
                await consume(self._connection, run_id, "model_calls", self._limits.model_calls)
            except LimitReached as reached:
                limit.append(reached)
                raise ProviderFailure(FailureClass.OTHER) from None
            token = _ADMITTED.set(True)
            try:
                response = await handler(request)
            except ProviderFailure:
                raise
            except Exception as error:
                status = getattr(error, "status_code", None)
                failure = (
                    classify_status(status)
                    if isinstance(status, int)
                    else FailureClass.UNCERTAIN_ACCEPTANCE
                )
                raise ProviderFailure(failure) from None
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
            "select model_calls from app_private.run_usage where run_id = %s", (run_id,)
        )
        used = (await cursor.fetchone())[0]
        admission_request = AdmissionRequest(
            workspace_id=self._scope.workspace_id,
            root_run_id=run_id,
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
            if limit:
                raise LoopStopped(limit[0].code) from None
            raise LoopStopped(failure.failure.value) from None
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
                    self._scope.run_id,
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
