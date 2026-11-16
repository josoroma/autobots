"""Graph facts read once in the domain, with plain values: the one topological order, the Experts a
graph's agent steps name, whether it needs a model, and its execution shape (PPRD-10, PDOM-09,
PDOM-17, refactor plan R-63).
"""

from typing import Any

import pytest

from autobots.domain.workflow_execution import shape_of
from autobots.domain.workflows import (
    Block,
    Link,
    TransformConfig,
    agent_expert_ids,
    needs_model,
    topological_order,
)


def node(name: str, block: str, **config: object) -> dict[str, Any]:
    return {"id": name, "block": block, "version": 1, "config": config}


def link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def test_each_name_follows_what_leads_to_it_and_ties_keep_their_given_order() -> None:
    names = ["out", "write", "in", "research", "gate"]
    successors = {"in": ["research"], "research": ["write"], "write": ["gate"], "gate": ["out"]}
    assert topological_order(names, successors) == (["in", "research", "write", "gate", "out"], [])
    assert topological_order(["b", "a", "c"], {}) == (["b", "a", "c"], [])


def test_a_cycle_leaves_its_names_unordered_in_their_given_order() -> None:
    names = ["in", "y", "x", "out"]
    successors = {"in": {"x"}, "x": {"y"}, "y": {"x", "out"}}
    assert topological_order(names, successors) == (["in"], ["y", "x", "out"])


def test_a_repeated_edge_is_counted_once_for_each_time_it_appears() -> None:
    assert topological_order(["a", "b"], {"a": ["b", "b"]}) == (["a", "b"], [])


def test_an_edge_to_an_unknown_name_is_ignored() -> None:
    assert topological_order(["a"], {"a": ["ghost"], "ghost": ["a"]}) == (["a"], [])


def agents() -> dict[str, Any]:
    return {
        "nodes": [
            node("out", "output"),
            node("write", "agent", expert_id="e2"),
            node("in", "input", type="string"),
            node("research", "agent", expert_id="e1"),
            node("again", "agent", expert_id="e1"),
            node("blank", "agent", expert_id=""),
        ],
        "links": [
            link("in", "value", "research", "goal"),
            link("research", "result", "write", "goal"),
            link("write", "result", "again", "goal"),
            link("again", "result", "out", "value"),
        ],
    }


def test_agent_steps_name_their_experts_in_step_order() -> None:
    """One that names no Expert names none, as a draft may."""
    assert agent_expert_ids(agents()) == ["e1", "e2", "e1"]


def test_only_a_graph_with_an_agent_step_needs_a_model() -> None:
    assert needs_model(agents()) is True
    plain = {"nodes": [node("in", "input", type="string"), node("out", "output")], "links": []}
    assert needs_model(plain) is False


def test_the_execution_shape_reads_typed_nodes_links_order_and_foreach_owners() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="list"),
            node("each", "foreach", max_items=3),
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
    shape = shape_of(graph)
    assert shape.order == ["in", "each", "up", "all", "out"]
    assert shape.owner == {"up": "each"}
    assert shape.nodes["up"].block is Block.TRANSFORM
    assert shape.nodes["up"].config == TransformConfig("upper")
    assert shape.links_to["up"] == [Link("each", "item", "up", "value")]


def test_a_shape_refuses_a_node_its_validation_would_refuse() -> None:
    with pytest.raises(ValueError, match="unknown_block"):
        shape_of({"nodes": [node("x", "shell")], "links": []})
