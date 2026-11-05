"""Makes the gateway the only route to a tool inside a Deep Agents loop.

The SDK adds file, shell and subagent tools of its own. Hiding them from the model is not enough, so
this answers every tool call from the gateway, and the SDK's own tool bodies never run.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool

from autobots.application.tool_gateway import ToolGateway, ToolScope
from autobots.domain.tools import ToolOutcome


class GatewayMiddleware(AgentMiddleware[Any, Any]):
    def __init__(self, gateway: ToolGateway, connection: Any, scope: ToolScope) -> None:
        super().__init__()
        self._gateway = gateway
        self._connection = connection
        self._scope = scope

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        """The model sees granted tools only, whatever the SDK attached."""
        granted = [
            tool for tool in request.tools if getattr(tool, "name", None) in self._scope.tools
        ]
        return await handler(request.override(tools=granted))

    async def awrap_tool_call(
        self, request: Any, handler: Callable[[Any], Awaitable[Any]]
    ) -> ToolMessage:
        call = request.tool_call
        result = await self._gateway.execute(
            self._connection, self._scope, call["name"], call["args"]
        )
        return ToolMessage(
            content=result.for_model(),
            tool_call_id=call["id"],
            name=call["name"],
            status="success" if result.outcome is ToolOutcome.SUCCEEDED else "error",
        )

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> ToolMessage:
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

    async def refuse(**_: Any) -> str:
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
