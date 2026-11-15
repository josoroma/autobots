"""A tool call resolved once, with no database: grant, registration, qualification, arguments and
path grants, in that order, then the call's identity (PTOL-02, SP-013).

The operation ID binds an approval to its effect and names the receipt, so its value is pinned.
"""

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

import pytest
from pydantic import BaseModel

from autobots.application.tool_definitions import ToolDefinition, ToolRegistry, ToolScope
from autobots.application.tool_gateway import Call, Refused, _hash, _operation_id, resolve
from autobots.contracts.file_tools import ReadRunFileInput
from autobots.contracts.tools import CalculateInput, CalculateOutput
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import OperationClass

WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
RUN = UUID("b0000000-0000-4000-8000-000000000002")
SCOPE = ToolScope(WORKSPACE, RUN, 3, {"calculate_x": 2})
ARGUMENTS = {"operation": "sum", "values": [1, 2]}
# The values of today's identity rule, which an approval, a receipt and a tool use record.
ARGUMENT_HASH = "268f9d982d17e412e15a12822688fd2cbc1339202b9431f8e2f73d98038b2cff"
OPERATION = "4f612f83b94c381030f813b6ad826913592c7c76479d6cf12f759e95ab5f7bae"
OPERATION_IN_ITEM = "9c12c0da7cf0b55ca507e671864f5d12fc6ace837ac80a408e8a1a1f9e337302"


async def _handler(_: object, __: object) -> CalculateOutput:
    return CalculateOutput(result=1)


def _tool(
    operation_class: OperationClass = OperationClass.REVERSIBLE_INTERNAL_WRITE,
    *,
    tool_id: str = "calculate_x",
    version: int = 2,
    input_model: type[BaseModel] = CalculateInput,
    resources: Callable[[BaseModel], tuple[str, ...]] = lambda _: (),
    qualified: Callable[[], bool] | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        version=version,
        description="x",
        input_model=input_model,
        output_model=CalculateOutput,
        operation_class=operation_class,
        handler=_handler,
        resources=resources,
        qualified=qualified,
    )


def _registry(*tools: ToolDefinition) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_the_operation_id_is_pinned() -> None:
    """The identity is the run, the foreach item if any, the tool, its version and the hash of the
    parsed arguments. Changing any of it would orphan every stored approval and receipt."""
    parsed = CalculateInput.model_validate(ARGUMENTS)
    assert _hash(parsed) == ARGUMENT_HASH
    assert _operation_id(SCOPE, _tool(), parsed) == OPERATION
    assert _operation_id(replace(SCOPE, instance="item#1"), _tool(), parsed) == OPERATION_IN_ITEM


def test_a_resolved_call_carries_the_pinned_identity() -> None:
    tool = _tool()
    call = resolve(_registry(tool), SCOPE, "calculate_x", ARGUMENTS)
    assert isinstance(call, Call)
    assert call.tool is tool
    assert call.parsed == CalculateInput(operation="sum", values=[1.0, 2.0])
    assert (call.argument_hash, call.operation_id) == (ARGUMENT_HASH, OPERATION)
    in_item = resolve(_registry(tool), replace(SCOPE, instance="item#1"), "calculate_x", ARGUMENTS)
    assert isinstance(in_item, Call) and in_item.operation_id == OPERATION_IN_ITEM


def test_arguments_that_parse_alike_are_one_operation() -> None:
    """The hash is of the parsed arguments, so `1` and `1.0` name the same operation."""
    registry = _registry(_tool())
    floats = resolve(registry, SCOPE, "calculate_x", {"operation": "sum", "values": [1.0, 2.0]})
    assert isinstance(floats, Call) and floats.operation_id == OPERATION


def test_a_registered_tool_the_scope_does_not_grant_is_refused() -> None:
    registry = _registry(_tool(tool_id="save_x", version=1))
    assert resolve(registry, SCOPE, "save_x", {}) == Refused(GatewayCode.TOOL_NOT_GRANTED)


def test_a_granted_version_that_is_not_registered_is_refused() -> None:
    registry = _registry(_tool(version=1))
    assert resolve(registry, SCOPE, "calculate_x", ARGUMENTS) == Refused(
        GatewayCode.TOOL_NOT_REGISTERED
    )


def test_an_executor_whose_qualification_was_withdrawn_is_refused_before_its_arguments() -> None:
    """AB-02, checked at each call. Its arguments still parse for the call's record (TU-04)."""
    qualified = [True]
    tool = _tool(OperationClass.ARBITRARY_EXECUTION, qualified=lambda: qualified[0])
    registry = _registry(tool)
    qualified[0] = False
    refused = resolve(registry, SCOPE, "calculate_x", ARGUMENTS)
    assert refused == Refused(
        GatewayCode.CAPABILITY_DISABLED, tool, CalculateInput.model_validate(ARGUMENTS)
    )
    invalid = resolve(registry, SCOPE, "calculate_x", {"operation": "sum", "values": []})
    assert invalid == Refused(GatewayCode.CAPABILITY_DISABLED, tool)


@pytest.mark.parametrize(
    "arguments",
    [
        {"operation": "sum", "values": []},
        {"operation": "median", "values": [1]},
        {"operation": "sum", "values": [1], "extra": 1},
        {"operation": "sum", "values": [float("inf")]},
        None,
        "sum 1 2",
    ],
)
def test_invalid_arguments_are_refused_with_the_tool_named(arguments: object) -> None:
    tool = _tool()
    assert resolve(_registry(tool), SCOPE, "calculate_x", arguments) == Refused(
        GatewayCode.INVALID_ARGUMENTS, tool
    )


@pytest.mark.parametrize(
    ("path", "resolved"),
    [("outputs/a.md", True), ("outputs/../.env", False), ("notes/a.md", False)],
)
def test_a_path_outside_the_grants_is_refused_after_parsing(path: str, resolved: bool) -> None:
    tool = _tool(
        OperationClass.READ_ONLY,
        tool_id="read_x",
        version=1,
        input_model=ReadRunFileInput,
        resources=lambda arguments: (getattr(arguments, "path", ""),),
    )
    scope = replace(SCOPE, tools={"read_x": 1}, paths=("outputs",))
    result = resolve(_registry(tool), scope, "read_x", {"path": path})
    if resolved:
        assert isinstance(result, Call) and result.parsed == ReadRunFileInput(path=path)
    else:
        assert result == Refused(
            GatewayCode.RESOURCE_NOT_GRANTED, tool, ReadRunFileInput.model_validate({"path": path})
        )
