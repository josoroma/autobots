"""Makes the gateway the only route to a tool inside a Deep Agents loop.

The SDK adds file, shell and subagent tools of its own. Hiding them from the model is not enough, so
this answers every tool call from the gateway, and the SDK's own tool bodies never run.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from autobots.application.tool_gateway import ToolGateway, ToolResult, ToolScope
from autobots.domain.tools import ToolOutcome


def _message(call_id: str | None, name: str, result: ToolResult) -> ToolMessage:
    """What the model reads is `for_model()`. The artifact, which the model never sees, carries the
    outcome and code for the loop's middleware, so it needn't parse the model's text (PADP-16)."""
    return ToolMessage(
        content=result.for_model(),
        # Plain strings, as a checkpoint keeps the message.
        artifact={
            "outcome": result.outcome.value,
            "code": None if result.code is None else str(result.code),
        },
        tool_call_id=call_id,
        name=name,
        status="success" if result.outcome is ToolOutcome.SUCCEEDED else "error",
    )


def gateway_code(message: ToolMessage) -> str | None:
    """The gateway's code on a reply this middleware made, or None for a call without one."""
    artifact = message.artifact
    if not isinstance(artifact, dict) or "code" not in artifact:
        raise TypeError("the reply wasn't made by the gateway's middleware")
    code = artifact["code"]
    return None if code is None else str(code)


class GatewayMiddleware(AgentMiddleware[Any, Any]):
    """Answers every tool call from the gateway. List it after `LoopMiddleware`, which reads the
    code this tags each reply with."""

    def __init__(self, gateway: ToolGateway, connection: object, scope: ToolScope) -> None:
        super().__init__()
        self._gateway = gateway
        self._connection = connection
        self._scope = scope
        # The SDK may run a reply's tool calls at once, and these share one connection.
        self._lock = asyncio.Lock()

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        """The model sees granted tools only, whatever the SDK attached."""
        granted = [
            tool for tool in request.tools if getattr(tool, "name", None) in self._scope.tools
        ]
        return await handler(request.override(tools=granted))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage:
        call = request.tool_call
        async with self._lock:
            result = await self._gateway.execute(
                self._connection, self._scope, call["name"], call["args"]
            )
        return _message(call["id"], call["name"], result)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage:
        """There is no synchronous route to a tool."""
        call = request.tool_call
        return ToolMessage(
            content="synchronous tool calls are not available",
            tool_call_id=call["id"],
            name=call["name"],
            status="error",
        )


def visible_tools(gateway: ToolGateway, scope: ToolScope) -> list[BaseTool]:
    """Names and schemas for the SDK. Their bodies refuse, since the middleware answers first."""

    async def refuse(**_: object) -> str:
        raise RuntimeError("tools run through the gateway only")

    tools: list[BaseTool] = []
    for name, version in sorted(scope.tools.items()):
        tool = gateway.registry.get(name, version)
        if tool is not None:
            tools.append(
                StructuredTool.from_function(
                    coroutine=refuse,
                    name=name,
                    description=tool.description,
                    args_schema=tool.input_model,
                )
            )
    return tools
