"""The tool rules that need no database."""

import hashlib
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from autobots.adapters.tool_registry import build_registry
from autobots.application.approvals import requesting_agent, scope_hash, scope_snapshot
from autobots.application.tool_definitions import (
    APPROVAL_POLICY_VERSION,
    ApprovalPolicy,
    ToolDefinition,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tools import first_grants
from autobots.contracts.tools import CalculateInput, CalculateOutput
from autobots.domain.tools import OperationClass, path_granted


async def _handler(_: object, __: object) -> CalculateOutput:
    return CalculateOutput(result=1)


def _tool(operation_class: OperationClass, retries: int = 0) -> ToolDefinition:
    return ToolDefinition(
        tool_id="x",
        version=1,
        description="x",
        input_model=CalculateInput,
        output_model=CalculateOutput,
        operation_class=operation_class,
        handler=_handler,
        retries=retries,
    )


def test_arbitrary_execution_cannot_be_registered() -> None:
    with pytest.raises(ValueError, match="arbitrary execution"):
        ToolRegistry().register(_tool(OperationClass.ARBITRARY_EXECUTION))


def test_an_effect_cannot_declare_blind_retries() -> None:
    with pytest.raises(ValueError, match="never retried"):
        ToolRegistry().register(_tool(OperationClass.REVERSIBLE_INTERNAL_WRITE, retries=1))


def test_a_version_registers_once() -> None:
    registry = ToolRegistry()
    registry.register(_tool(OperationClass.PURE))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_tool(OperationClass.PURE))


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("outputs/a.md", True),
        ("outputs", True),
        ("outputs/deep/a.md", True),
        ("outputsx/a.md", False),
        ("../outputs/a.md", False),
        ("outputs/../a.md", False),
        ("outputs//a.md", False),
        ("outputs/./a.md", False),
        ("/outputs/a.md", False),
        ("outputs\\a.md", False),
        ("outputs/\x00", False),
        ("", False),
        (".env", False),
    ],
)
def test_paths_need_an_explicit_grant(path: str, allowed: bool) -> None:
    assert path_granted(path, ("outputs",)) is allowed


def test_no_grants_means_no_path() -> None:
    assert not path_granted("a.md", ())


def test_a_catalog_shows_only_grants_and_no_handler() -> None:
    from uuid import uuid4

    scope = ToolScope(uuid4(), uuid4(), 1, {"calculate": 1})
    catalog = ToolGateway(build_registry(None)).registry.catalog(scope)
    assert [tool["name"] for tool in catalog] == ["calculate"]
    assert set(catalog[0]) == {"name", "version", "description", "input_schema"}


def test_the_first_tool_set_is_small_and_has_no_shell() -> None:
    assert set(first_grants()) == {"calculate", "read_run_file", "save_artifact"}


def test_calculate_refuses_extra_fields_and_non_finite_values() -> None:
    with pytest.raises(ValidationError):
        CalculateInput.model_validate({"operation": "sum", "values": [1], "extra": 1})
    with pytest.raises(ValidationError):
        CalculateInput.model_validate({"operation": "sum", "values": [float("inf")]})


MARKED = "This tool is marked to wait for a person, so policy holds each call."
EXTERNAL = "This tool changes something outside this Mac, so policy holds each call for a person."


def _sums(arguments: CalculateInput) -> bool:
    return arguments.operation == "sum"


# Each approval policy a tool can declare.
DECLARED: dict[str, ApprovalPolicy] = {
    "plain": ApprovalPolicy(),
    "marked": ApprovalPolicy(always=True),
    "by_action": ApprovalPolicy(when=_sums),
    "marked_and_by_action": ApprovalPolicy(always=True, when=_sums),
}


def test_the_approval_policy_version_names_these_rules() -> None:
    """Decision 0015. Changing the condition, a rule, its text or the catalog's label fails here
    until the version changes too. Each row is (label, held for a matching call, held for another
    call, rule, reason text), for every operation class and every declared policy (PTOL-04)."""
    matching = CalculateInput(operation="sum", values=[1])
    other = CalculateInput(operation="mean", values=[1])
    table = {}
    for kind in OperationClass:
        for name, chosen in DECLARED.items():
            policy = replace(_tool(kind), approval=chosen).approval
            table[kind.value, name] = (
                policy.label(kind),
                policy.applies(kind, matching),
                policy.applies(kind, other),
                policy.rule(kind),
                policy.reason_text(kind),
            )
    # A consequential external write is held on every call, whatever else is declared.
    external = ("always", True, True, "consequential_external_write", EXTERNAL)
    declared = {
        "plain": ("never", False, False, "tool_marked", MARKED),
        "marked": ("always", True, True, "tool_marked", MARKED),
        "by_action": ("by_action", True, False, "action_marked", MARKED),
        "marked_and_by_action": ("always", True, True, "tool_marked", MARKED),
    }
    assert (APPROVAL_POLICY_VERSION, table) == (
        "approval-policy/2",
        {
            (kind.value, name): (
                external if kind is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE else row
            )
            for kind in OperationClass
            for name, row in declared.items()
        },
    )
    own = ApprovalPolicy(reason="Own.")
    assert own.reason_text(OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE) == "Own."
    snapshot = scope_snapshot({"b": 2, "a": 1}, ("outputs",))
    assert snapshot == {"tools": {"b": 2, "a": 1}, "paths": ["outputs"]}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert digest == scope_hash({"a": 1, "b": 2}, ["outputs"])
    assert requesting_agent(None, None) == {"kind": "coordinator"}


def test_the_catalog_shows_the_label_the_gateway_holds_by() -> None:
    """Decision 0026 C9: the Tools page's approval label is the gateway's own rule."""
    from autobots.application.tool_catalog import describe

    for kind in OperationClass:
        for chosen in DECLARED.values():
            tool = replace(_tool(kind), tool_id="held_x", approval=chosen)
            assert describe(tool, {}).approval == tool.approval.label(kind)
