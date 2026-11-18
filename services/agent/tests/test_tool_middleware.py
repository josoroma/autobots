"""The gateway middleware: the only route to a tool inside a Deep Agents loop (refactor plan R-62,
PADP-16 and PADP-18). The model sees granted tools only, every call is answered by the gateway, and
the SDK's own tool bodies never run. tests/db/checks/tool_gateway_check.py runs it inside a real
agent.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import cast
from uuid import uuid4

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from pydantic import BaseModel

from autobots.adapters.tool_middleware import GatewayMiddleware, gateway_code, visible_tools
from autobots.application.tool_definitions import (
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.domain.tools import OperationClass, ToolOutcome
from sql_fakes import ScriptedConnection

SCOPE = ToolScope(uuid4(), uuid4(), 1, {"granted": 1})
CONNECTION = ScriptedConnection()


class Note(BaseModel):
    text: str


class Saved(BaseModel):
    ok: bool


async def save(arguments: Note, _: ToolContext) -> Saved:
    return Saved(ok=bool(arguments.text))


def definition(tool_id: str) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        version=1,
        description=f"The {tool_id} tool.",
        input_model=Note,
        output_model=Saved,
        operation_class=OperationClass.READ_ONLY,
        handler=save,
    )


@dataclass(frozen=True)
class Gateway(ToolGateway):
    """Answers each call with `result` and records it, so the middleware is all that runs."""

    result: ToolResult
    calls: list[tuple[object, ToolScope, str, object]] = field(default_factory=list)
    active: list[int] = field(default_factory=list)

    async def execute(
        self, connection: object, scope: ToolScope, name: str, arguments: object
    ) -> ToolResult:
        self.active.append(1)
        assert len(self.active) == 1, "two calls shared the connection at once"
        await asyncio.sleep(0)
        self.calls.append((connection, scope, name, arguments))
        self.active.pop()
        return self.result


SUCCEEDED = ToolResult(ToolOutcome.SUCCEEDED, output={"ok": True}, operation_id="o-1")


def gateway(result: ToolResult = SUCCEEDED) -> Gateway:
    registry = ToolRegistry()
    registry.register(definition("granted"))
    registry.register(definition("other"))
    return Gateway(registry, result)


def tool_call(name: str = "granted", call_id: str = "call-1") -> ToolCallRequest:
    call = ToolCall(name=name, args={"text": "hello"}, id=call_id, type="tool_call")
    # The middleware reads only the call; the runtime is the graph's, absent outside one.
    return ToolCallRequest(tool_call=call, tool=None, state={}, runtime=cast(ToolRuntime, None))


async def never(_: ToolCallRequest) -> ToolMessage:
    raise AssertionError("the SDK's tool body ran")


def named(name: str) -> BaseTool:
    async def body(text: str) -> str:
        return text

    return StructuredTool.from_function(coroutine=body, name=name, description=name)


@pytest.mark.asyncio
async def test_the_model_sees_granted_tools_only() -> None:
    middleware = GatewayMiddleware(gateway(), CONNECTION, SCOPE)
    seen: list[ModelRequest] = []

    async def model(request: ModelRequest) -> ModelResponse:
        seen.append(request)
        return ModelResponse(result=[AIMessage("done")])

    request = ModelRequest(
        model=GenericFakeChatModel(messages=iter([])),
        messages=[],
        tools=[named("granted"), named("other"), named("write_file")],
    )
    await middleware.awrap_model_call(request, model)
    [sent] = seen
    assert [getattr(tool, "name", None) for tool in sent.tools] == ["granted"]


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (ToolResult(ToolOutcome.SUCCEEDED, output={"ok": True}, operation_id="o-1"), "success"),
        (ToolResult(ToolOutcome.DENIED, "tool_not_granted"), "error"),
        (ToolResult(ToolOutcome.FAILED, "github_refused_422", operation_id="o-2"), "error"),
    ],
)
@pytest.mark.asyncio
async def test_every_tool_call_is_answered_by_the_gateway(result: ToolResult, status: str) -> None:
    answering = gateway(result)
    middleware = GatewayMiddleware(answering, CONNECTION, SCOPE)
    reply = await middleware.awrap_tool_call(tool_call(), never)
    assert isinstance(reply, ToolMessage)
    assert reply.content == result.for_model()
    assert (reply.tool_call_id, reply.name, reply.status) == ("call-1", "granted", status)
    assert answering.calls == [(CONNECTION, SCOPE, "granted", {"text": "hello"})]
    assert json.loads(str(reply.content))["outcome"] == result.outcome.value
    # The loop's middleware reads the code from the artifact, which the model never sees.
    code = None if result.code is None else str(result.code)
    assert reply.artifact == {"outcome": result.outcome.value, "code": code}
    assert gateway_code(reply) == code


@pytest.mark.asyncio
async def test_calls_made_at_once_take_turns_on_the_connection() -> None:
    answering = gateway()
    middleware = GatewayMiddleware(answering, CONNECTION, SCOPE)

    async def both() -> None:
        await asyncio.gather(
            middleware.awrap_tool_call(tool_call(call_id="a"), never),
            middleware.awrap_tool_call(tool_call(call_id="b"), never),
        )

    await both()
    assert len(answering.calls) == 2


def test_there_is_no_synchronous_route_to_a_tool() -> None:
    answering = gateway()
    reply = GatewayMiddleware(answering, CONNECTION, SCOPE).wrap_tool_call(
        tool_call(), lambda _: pytest.fail("the SDK's tool body ran")
    )
    assert (reply.status, reply.content) == ("error", "synchronous tool calls are not available")
    assert answering.calls == []


@pytest.mark.asyncio
async def test_the_sdk_sees_granted_names_and_schemas_and_their_bodies_refuse() -> None:
    tools = visible_tools(gateway(), SCOPE)
    assert [tool.name for tool in tools] == ["granted"]
    assert tools[0].args_schema is Note
    with pytest.raises(RuntimeError, match="through the gateway only"):
        await tools[0].ainvoke({"text": "hello"})


@pytest.mark.parametrize("artifact", [None, "code", {"outcome": "succeeded"}])
def test_a_reply_the_gateway_didnt_make_is_a_defect(artifact: object) -> None:
    """The middlewares' order matters: the loop's must wrap the gateway's (PADP-16)."""
    reply = ToolMessage(content="{}", artifact=artifact, tool_call_id="c", name="granted")
    with pytest.raises(TypeError):
        gateway_code(reply)
