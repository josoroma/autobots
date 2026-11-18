"""The LangChain side of the goal loop's admission (refactor plan R-62, PADP-09, PADP-16, XTYP-11).

Here are the model that answers only inside an admitted dispatch, the streamed reply, how a request
is sized and a reply read, and a thin `LoopMiddleware` that hands each model and tool call to
application/loop_admission.py, where the admission, budget, compaction and stop policy live.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
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
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command
from pydantic import ConfigDict

from autobots.adapters.model_replies import (
    charged,
    failure_without_status,
    finished,
    retry_after,
)
from autobots.adapters.result_stream import current_tap
from autobots.adapters.tool_middleware import gateway_code
from autobots.application.compaction import CompactionPolicy
from autobots.application.loop_admission import (
    ACTIVE_LOOP,
    Guard,
    LoopAdmission,
    LoopSettings,
    ModelReply,
    PromptParts,
    active_middleware,
    model_call_admitted,
)
from autobots.application.loop_policy import LoopStopped, UnadmittedModelCall
from autobots.application.model_admission import ModelAdmission, ReplyFacts
from autobots.application.model_attempts import (
    FailureClass,
    ModelOutput,
    ProviderFailure,
    classify_status,
)
from autobots.application.run_usage import RootLimits
from autobots.application.sql import SqlConnection
from autobots.application.tool_definitions import ToolScope
from autobots.contracts.plans import GoalSpec
from autobots.domain.models import MODEL_CALL_SECONDS, ModelRoute

# LoopStopped, UnadmittedModelCall and ModelRoute are imported from here by the disposable checks;
# `_MIDDLEWARE` is the loop's ContextVar, which browse_trial.py and
# tests/db/checks/browse_goal_check.py set by this name; `_charged` is the settlement
# tests/test_reported_charges.py pins under that name (R-22).
__all__ = [
    "MAX_FACT_CHARS",
    "MAX_FACT_NAMES",
    "AdmittedModel",
    "LoopMiddleware",
    "LoopStopped",
    "ModelRoute",
    "UnadmittedModelCall",
    "reply_facts",
    "request_bytes",
]
_MIDDLEWARE = ACTIVE_LOOP
_charged = charged

MAX_FACT_CHARS = 100
MAX_FACT_NAMES = 20


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
        if not model_call_admitted():
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


def request_bytes(request: PromptParts) -> int:
    """An upper bound on the prompt's tokens, at about one per byte, as no tokenizer is pinned.

    It counts what compaction doesn't: the system prompt and the tools' schemas.
    """
    total = 0
    for message in [request.system_message, *request.messages]:
        if message is not None:
            calls = getattr(message, "tool_calls", None) or []
            total += len(
                json.dumps([message.content, calls], default=str, ensure_ascii=False).encode()
            )
    return total + len(
        json.dumps(list(request.tools), default=_tool_text, ensure_ascii=False).encode()
    )


def _tool_text(tool: Any) -> Any:
    try:
        return convert_to_openai_tool(tool)
    except (TypeError, ValueError, AttributeError):
        return str(tool)


def _count(value: object) -> int | None:
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


def _message(reply: ModelReply) -> AIMessage:
    """The reply's last message. A reply arrived, so one that isn't a model's message may still
    have been charged, and stays uncertain."""
    message = reply.result[-1]
    if not isinstance(message, AIMessage):
        raise ProviderFailure(FailureClass.UNCERTAIN_ACCEPTANCE, reason="reply_not_a_model_message")
    return message


class _Replies:
    """How a LangChain reply and an SDK failure read, for application/loop_admission.py."""

    def output(self, reply: ModelReply) -> ModelOutput:
        message = _message(reply)
        return ModelOutput(
            text=str(message.content),
            complete=finished(message),
            charged_micro_usd=charged(message),
        )

    def facts(self, reply: ModelReply) -> ReplyFacts:
        return reply_facts(_message(reply))

    def cut_off(self, reply: ModelReply) -> bool:
        return reply.result[-1].response_metadata.get("finish_reason") == "length"

    def failure(self, error: Exception) -> ProviderFailure:
        """Any failure of a model call, classified by its status or, without one, by whether the
        connection ever opened (MP-08)."""
        status = getattr(error, "status_code", None)
        kind = classify_status(status) if isinstance(status, int) else failure_without_status(error)
        return ProviderFailure(kind, retry_after=retry_after(error))


_REPLIES = _Replies()


@dataclass(frozen=True)
class _Call[Q: PromptParts, S: ModelReply]:
    """One framework request and the handler that sends it, as the admission sees a model call."""

    request: Q
    handler: Callable[[Q], Awaitable[S]]

    def prompt_bytes(self) -> int:
        return request_bytes(self.request)

    async def send(self) -> S:
        return await self.handler(self.request)


class LoopMiddleware(AgentMiddleware[Any, Any]):
    """Hands every model and tool call of a Deep Agents loop to the run's `LoopAdmission`.

    List it before `GatewayMiddleware`, so it is the outer of the two: the gateway's middleware
    answers every tool call, and its `ToolMessage` carries the gateway's code, which this reads.
    """

    def __init__(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
        self,
        connection: SqlConnection,
        scope: ToolScope,
        limits: RootLimits,
        route: ModelRoute,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        slot_wait_seconds: float = 30.0,
        model_call_seconds: float = MODEL_CALL_SECONDS,
        goal: GoalSpec | None = None,
        compaction: CompactionPolicy | None = None,
        summary_route: ModelRoute | None = None,
        guard: Guard | None = None,
        admission: Callable[[], ModelAdmission] | None = None,
    ) -> None:
        super().__init__()
        settings = LoopSettings(
            sleep=sleep,
            slot_wait_seconds=slot_wait_seconds,
            model_call_seconds=model_call_seconds,
            goal=goal,
            compaction=compaction or CompactionPolicy(),
            summary_route=summary_route,
        )
        # Production passes neither `guard` nor `admission`, so every dispatch checks the database
        # and settles in the ledger. Tests pass in-memory ones (PTST-01).
        self._loop = LoopAdmission(
            connection, scope, limits, route, _REPLIES, settings, guard, admission
        )
        # The SDK may run a reply's tool calls at once, and these share one connection.
        self._lock = asyncio.Lock()

    async def guard(self) -> float:
        """The check each new dispatch makes: still the owner, still running, and the seconds
        left."""
        return await self._loop.guard()

    async def admitted[Q: PromptParts, S: ModelReply](
        self, request: Q, handler: Callable[[Q], Awaitable[S]], route: ModelRoute
    ) -> tuple[S, bool]:
        """One admitted call on another of the run's frozen routes, as browsing makes them.

        A stop here stops the loop too, once the tool call that made it returns.
        """
        return await self._loop.nested(_Call(request, handler), route)

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        await self._loop.guard()

        def summarize(messages: list[AnyMessage]) -> _Call[ModelRequest[Any], ModelResponse[Any]]:
            return _Call(request.override(messages=messages, tools=[]), handler)

        compacted = request.override(messages=await self._loop.compact(request.messages, summarize))

        def again(note: str) -> _Call[ModelRequest[Any], ModelResponse[Any]]:
            return _Call(
                compacted.override(messages=[*compacted.messages, HumanMessage(note)]), handler
            )

        return await self._loop.turn(_Call(compacted, handler), again)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage:
        async def run() -> ToolMessage:
            with active_middleware(self):
                reply = await handler(request)
            if not isinstance(reply, ToolMessage):
                raise TypeError("the gateway's middleware answers every tool call with a message")
            return reply

        async with self._lock:
            return await self._loop.tool_dispatch(run, gateway_code)
