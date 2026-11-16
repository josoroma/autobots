"""The order in which `validate_graph` reports each phase's errors is observable behavior: the
editor lists them as returned (PDOM-10). These graphs fail in every way a phase can, and each
expected list was captured from `validate_graph` before it was split by phase (refactor plan R-63).
"""

from typing import Any

from autobots.domain.workflows import GraphError, validate_graph


def node(name: str, block: str, version: int = 1, **config: object) -> dict[str, Any]:
    return {"id": name, "block": block, "version": version, "config": config}


def link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def test_node_level_errors_keep_their_order() -> None:
    """Labels first, then duplicates, then each distinct node's block, version or configuration,
    in the order the nodes were first listed. A duplicate's last copy is the one checked."""
    graph = {
        "ir_version": 1,
        "nodes": [
            {**node("a", "transform", operation="eval"), "label": "First"},
            node("b", "shell"),
            node("c", "input", version=9, type="string"),
            {**node("d", "foreach"), "label": "Fourth"},
            node("b", "input", type="nope"),
            node("e", "artifact", path="inputs/x.md"),
            node("f", "agent"),
            node("g", "condition", predicate="equals"),
            node("h", "foreach", max_items=500),
            node("i", "foreach", max_items=2, item_type="shell"),
            node("a", "transform", operation="upper"),
            node("j", "output"),
        ],
        "links": [link("ghost", "value", "j", "value")],
    }
    assert validate_graph(graph) == [
        GraphError("label_needs_ir_version_2", "a"),
        GraphError("label_needs_ir_version_2", "d"),
        GraphError("duplicate_node", "b"),
        GraphError("duplicate_node", "a"),
        GraphError("input_type_invalid", "b"),
        GraphError("unknown_block_version", "c"),
        GraphError("foreach_bound_required", "d"),
        GraphError("artifact_path_invalid", "e"),
        GraphError("agent_expert_required", "f"),
        GraphError("condition_invalid", "g"),
        GraphError("foreach_bound_too_large", "h"),
        GraphError("foreach_item_type_invalid", "i"),
    ]


def test_link_level_errors_keep_their_order() -> None:
    """Each link in turn, then inputs linked twice, then unlinked required inputs by node and port,
    then a missing output and a missing input."""
    graph = {
        "nodes": [
            node("t", "transform", operation="upper"),
            node("u", "transform", operation="length"),
            node("save", "artifact", path="outputs/a.md"),
            node("j", "join"),
        ],
        "links": [
            link("ghost", "value", "t", "value"),
            link("t", "value", "phantom", "value"),
            link("t", "nope", "u", "value"),
            link("t", "value", "u", "nope"),
            link("u", "value", "save", "content"),
            link("t", "value", "save", "content"),
            link("u", "value", "j", "value"),
            link("t", "value", "j", "value"),
        ],
    }
    assert validate_graph(graph) == [
        GraphError("unknown_node", "ghost"),
        GraphError("unknown_node", "phantom"),
        GraphError("unknown_port", "t", "nope"),
        GraphError("unknown_port", "u", "nope"),
        GraphError("link_type_mismatch", "save", "content"),
        GraphError("input_linked_twice", "save", "content"),
        GraphError("required_input_unlinked", "t", "value"),
        GraphError("required_input_unlinked", "u", "value"),
        GraphError("output_required"),
        GraphError("input_required"),
    ]


def test_an_unknown_ir_version_is_the_only_error() -> None:
    graph = {"ir_version": 7, "nodes": [node("b", "shell"), node("b", "shell")], "links": []}
    assert validate_graph(graph) == [GraphError("unknown_ir_version")]


def test_a_cycle_is_reported_alone_before_iteration_rules() -> None:
    """A foreach with no join would fail iteration, but the cycle is the only error reported."""
    graph = {
        "nodes": [
            node("in", "input", type="list"),
            node("y", "transform", operation="identity"),
            node("z", "transform", operation="identity"),
            node("each", "foreach", max_items=3),
            node("out", "output"),
        ],
        "links": [
            link("in", "value", "each", "items"),
            link("z", "value", "y", "value"),
            link("y", "value", "z", "value"),
            link("in", "value", "out", "value"),
        ],
    }
    assert validate_graph(graph) == [GraphError("cycle_not_supported")]
    graph["links"] = [link("in", "value", "each", "items"), link("in", "value", "out", "value")]
    graph["nodes"] = [item for item in graph["nodes"] if item["id"] not in {"y", "z"}]
    assert validate_graph(graph) == [GraphError("foreach_without_join", "each")]
