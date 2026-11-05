"""Golden graphs and every typed refusal, with no database."""

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from autobots.application.run_projection import public_text
from autobots.application.tool_gateway import ToolScope
from autobots.application.workflow_runner import _run_block, _Stop, _tool
from autobots.domain.workflow_execution import BlockFailed, GraphShape, Step, unsettled_nodes
from autobots.domain.workflows import (
    MAX_FOREACH_ITEMS,
    _iteration_errors,
    block_versions,
    graph_hash,
    input_errors,
    validate_graph,
)


def node(name: str, block: str, **config: Any) -> dict[str, Any]:
    return {"id": name, "block": block, "version": 1, "config": config}


def link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def simple() -> dict[str, Any]:
    return {
        "nodes": [
            node("in", "input", type="string"),
            node("up", "transform", operation="upper"),
            node("out", "output"),
        ],
        "links": [link("in", "value", "up", "value"), link("up", "value", "out", "value")],
    }


def loop() -> dict[str, Any]:
    return {
        "nodes": [
            node("in", "input", type="list"),
            node("each", "foreach", max_items=10),
            node("up", "transform", operation="upper"),
            node("all", "join"),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "each", "items"),
            link("each", "item", "up", "value"),
            link("up", "value", "all", "value"),
            link("all", "items", "out", "value"),
        ],
    }


def branch() -> dict[str, Any]:
    return {
        "nodes": [
            node("in", "input", type="number"),
            node("if", "condition", predicate="greater_than", operand=3),
            node("big", "output"),
            node("small", "output"),
        ],
        "links": [
            link("in", "value", "if", "value"),
            link("if", "true", "big", "value"),
            link("if", "false", "small", "value"),
        ],
    }


def codes(graph: dict[str, Any]) -> list[str]:
    return [error.code for error in validate_graph(graph)]


@pytest.mark.parametrize("graph", [simple(), loop(), branch()])
def test_the_documented_subset_validates(graph: dict[str, Any]) -> None:
    assert validate_graph(graph) == []


def test_every_documented_block_is_available() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="string"),
            node("read", "read"),
            node("save", "artifact", path="outputs/a.md"),
            node("ok", "approval"),
            node("ask", "agent", expert_id="e"),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "read", "path"),
            link("read", "content", "save", "content"),
            link("save", "artifact_id", "ok", "value"),
            link("in", "value", "ask", "goal"),
            link("ok", "value", "out", "value"),
        ],
    }
    assert validate_graph(graph) == []


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda g: g["nodes"].append(node("in", "input", type="string")), "duplicate_node"),
        (lambda g: g["nodes"].append(node("x", "shell")), "unknown_block"),
        (
            lambda g: g["nodes"].append({**node("x", "input", type="json"), "version": 9}),
            "unknown_block_version",
        ),
        (lambda g: g["links"].append(link("ghost", "value", "out", "value")), "unknown_node"),
        (lambda g: g["links"].append(link("in", "nope", "out", "value")), "unknown_port"),
        (lambda g: g["links"].append(link("in", "value", "out", "nope")), "unknown_port"),
        (lambda g: g["links"].append(link("in", "value", "out", "value")), "input_linked_twice"),
        (lambda g: g["links"].pop(), "required_input_unlinked"),
        (lambda g: g["nodes"][0]["config"].update(type="shell"), "input_type_invalid"),
        (lambda g: g["nodes"][1]["config"].update(operation="eval"), "transform_operation_unknown"),
    ],
)
def test_typed_errors(change: Any, code: str) -> None:
    graph = simple()
    change(graph)
    assert code in codes(graph)


def test_types_must_match_across_a_link() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="number"),
            node("each", "foreach", max_items=2),
            node("all", "join"),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "each", "items"),
            link("each", "item", "all", "value"),
            link("all", "items", "out", "value"),
        ],
    }
    assert codes(graph) == ["link_type_mismatch"]


def test_arbitrary_cycles_are_rejected() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="json"),
            node("a", "transform", operation="identity"),
            node("b", "condition", predicate="equals", operand=1),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "a", "value"),
            link("a", "value", "b", "value"),
            link("b", "true", "a", "value"),
            link("b", "false", "out", "value"),
        ],
    }
    errors = codes(graph)
    assert "cycle_not_supported" in errors or "input_linked_twice" in errors
    graph["links"][0] = link("in", "value", "out", "value")
    graph["links"].pop(3)
    assert codes(graph) == ["cycle_not_supported"]


@pytest.mark.parametrize(
    ("config", "code"),
    [
        ({}, "foreach_bound_required"),
        ({"max_items": 0}, "foreach_bound_required"),
        ({"max_items": True}, "foreach_bound_required"),
        ({"max_items": MAX_FOREACH_ITEMS + 1}, "foreach_bound_too_large"),
    ],
)
def test_iteration_is_bounded(config: dict[str, Any], code: str) -> None:
    graph = loop()
    graph["nodes"][1]["config"] = config
    assert codes(graph) == [code]


def test_an_iteration_needs_its_join() -> None:
    graph = loop()
    graph["nodes"] = [item for item in graph["nodes"] if item["id"] != "all"]
    graph["links"] = [
        link("in", "value", "each", "items"),
        link("each", "item", "up", "value"),
        link("up", "value", "out", "value"),
    ]
    found = codes(graph)
    assert "foreach_without_join" in found and "iteration_boundary_crossed" in found


def test_iterations_do_not_nest_yet() -> None:
    graph = loop()
    graph["nodes"][1]["config"]["item_type"] = "list"
    graph["nodes"].append(node("inner", "foreach", max_items=2))
    graph["links"][1] = link("each", "item", "inner", "items")
    graph["links"].append(link("inner", "item", "up", "value"))
    assert "nested_foreach" in codes(graph)


def test_a_declared_item_type_is_checked_across_links() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="list"),
            node("each", "foreach", max_items=2, item_type="number"),
            node("save", "artifact", path="outputs/a.md"),
            node("all", "join"),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "each", "items"),
            link("each", "item", "save", "content"),
            link("save", "artifact_id", "all", "value"),
            link("all", "items", "out", "value"),
        ],
    }
    assert codes(graph) == ["link_type_mismatch"]
    graph["nodes"][1]["config"]["item_type"] = "string"
    assert codes(graph) == []


def test_a_join_needs_an_iteration() -> None:
    graph = simple()
    graph["nodes"].append(node("all", "join"))
    graph["links"][1] = link("up", "value", "all", "value")
    graph["links"].append(link("all", "items", "out", "value"))
    assert codes(graph) == ["join_outside_foreach"]


def test_a_graph_needs_an_output() -> None:
    graph = {"nodes": [node("in", "input", type="json")], "links": []}
    assert codes(graph) == ["output_required"]


def test_hash_is_stable_and_names_block_versions() -> None:
    first, second = simple(), simple()
    second["links"].reverse()
    assert graph_hash(first) == graph_hash(simple())
    assert graph_hash(first) != graph_hash(second)
    assert block_versions(first)["up"] == "transform@1"


def test_execution_inputs_match_their_types() -> None:
    graph = simple()
    assert input_errors(graph, {"in": "text"}) == []
    assert [e.code for e in input_errors(graph, {})] == ["input_missing"]
    assert [e.code for e in input_errors(graph, {"in": 5})] == ["input_type_mismatch"]
    assert "input_unknown" in [e.code for e in input_errors(graph, {"in": "a", "extra": 1})]


def test_two_foreach_regions_cannot_feed_one_join() -> None:
    nodes = {
        "left": {"block": "foreach"},
        "right": {"block": "foreach"},
        "gather": {"block": "join"},
    }
    successors = {"left": {"gather"}, "right": {"gather"}}
    errors = _iteration_errors(nodes, successors)
    assert [(error.code, error.node) for error in errors] == [("join_multiple_foreach", "gather")]


def test_a_workflow_nothing_can_move_is_not_finished() -> None:
    shape = GraphShape(
        nodes={
            "each": {"block": "foreach"},
            "body": {"block": "transform"},
            "gather": {"block": "join"},
            "end": {"block": "output"},
        },
        links_to={},
        order=["each", "body", "gather", "end"],
        owner={"body": "each"},
    )
    settled = {"each": "succeeded", "gather": "succeeded", "end": "succeeded"}
    assert unsettled_nodes(shape, settled) == []
    assert unsettled_nodes(shape, {"each": "succeeded"}) == ["end", "gather"]
    assert unsettled_nodes(shape, {**settled, "body#0": "running"}) == ["body#0"]


def test_a_word_containing_the_key_prefix_is_shown_as_written() -> None:
    assert public_text("a risk-free change") == "a risk-free change"
    assert public_text("key sk-or-v1-abcdef") == "key [redacted]"


def test_a_join_cannot_mix_a_foreach_with_an_outside_source() -> None:
    nodes = {
        "in": {"block": "input"},
        "each": {"block": "foreach"},
        "gather": {"block": "join"},
    }
    successors = {"in": {"each", "gather"}, "each": {"gather"}}
    codes = [error.code for error in _iteration_errors(nodes, successors)]
    assert codes == ["join_mixed_sources"]


def test_a_stopped_agent_node_runs_again_instead_of_failing() -> None:
    class Stopped:
        def __init__(self, code: str) -> None:
            self.code = code

        async def execute(self, *_: Any) -> Any:
            return SimpleNamespace(code=self.code, outcome=SimpleNamespace(value="failed"))

    for code in ("assignment_lost", "assignment_busy", "run_not_running", "run_not_found"):
        with pytest.raises(_Stop):
            asyncio.run(_tool(Stopped(code), None, None, "t", {}))  # type: ignore[arg-type]
    with pytest.raises(BlockFailed):
        asyncio.run(_tool(Stopped("tool_failed"), None, None, "t", {}))  # type: ignore[arg-type]


def _chain(first: dict[str, Any], *rest: tuple[dict[str, Any], str, str]) -> dict[str, Any]:
    nodes, links, previous, port = [first], [], first["id"], "value"
    for item, in_port, out_port in rest:
        nodes.append(item)
        links.append(link(previous, port, item["id"], in_port))
        previous, port = item["id"], out_port
    nodes.append(node("out", "output"))
    links.append(link(previous, port, "out", "value"))
    return {"nodes": nodes, "links": links}


def test_an_approval_can_guard_an_effect_and_keeps_its_inputs_type() -> None:
    graph = _chain(
        node("in", "input", type="string"),
        (node("ok", "approval"), "value", "value"),
        (node("save", "artifact", path="outputs/a.md"), "content", "artifact_id"),
    )
    assert validate_graph(graph) == []


def test_to_string_can_feed_an_artifact() -> None:
    graph = _chain(
        node("in", "input", type="number"),
        (node("text", "transform", operation="to_string"), "value", "value"),
        (node("save", "artifact", path="outputs/a.md"), "content", "artifact_id"),
    )
    assert validate_graph(graph) == []


def test_a_json_value_still_cant_reach_a_string_input_through_an_approval() -> None:
    graph = _chain(
        node("in", "input", type="json"),
        (node("ok", "approval"), "value", "value"),
        (node("save", "artifact", path="outputs/a.md"), "content", "artifact_id"),
    )
    assert [error.code for error in validate_graph(graph)] == ["link_type_mismatch"]


def test_equal_foreach_items_are_separate_operations() -> None:
    seen: list[Any] = []

    class Recording:
        async def execute(self, _: Any, scope: Any, name: str, arguments: Any) -> Any:
            seen.append(scope.instance)
            return SimpleNamespace(
                code=None,
                outcome=SimpleNamespace(value="succeeded"),
                output={"outcome": "succeeded"},
            )

    scope = ToolScope(workspace_id=uuid4(), run_id=uuid4(), generation=1, tools={})
    agent = node("a", "agent", expert_id=str(uuid4()))
    for iteration in (0, 1):
        step = Step(f"a#{iteration}", "a", iteration, "run", {"goal": "x"})
        asyncio.run(_run_block(Recording(), None, scope, agent, step, {}))  # type: ignore[arg-type]
    assert seen == ["a#0", "a#1"]
