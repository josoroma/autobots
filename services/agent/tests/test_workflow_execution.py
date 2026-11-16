"""Readiness and emission identity as pure functions, run to completion over golden graphs.

The golden runs use the runner's own pure block rules (domain PURE_BLOCKS), so a change to a port,
an emission's position or the foreach bound shows here too (PTST-10).
"""

from typing import Any

import pytest

from autobots.domain.workflow_execution import (
    PURE_BLOCKS,
    BlockFailed,
    next_steps,
    run_predicate,
    run_transform,
    shape_of,
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


def run(graph: dict[str, Any], inputs: dict[str, Any]) -> tuple[dict[str, str], dict[Any, Any]]:
    """The runner's decisions and pure block rules, with emissions kept in plain dictionaries."""
    shape = shape_of(graph)
    statuses: dict[str, str] = {}
    emissions: dict[Any, Any] = {}
    for _ in range(100):
        steps = next_steps(shape, statuses, emissions)
        if not steps:
            return statuses, emissions
        for step in steps:
            if step.decision != "run":
                statuses[step.key] = step.decision
                continue
            data = shape.nodes[step.node_id]
            try:
                emitted = PURE_BLOCKS[data.block](data.config, step, inputs)
            except BlockFailed:
                statuses[step.key] = "failed"
                continue
            for port, sequence, value in emitted:
                emissions[(step.key, port, sequence)] = value
            statuses[step.key] = "succeeded"
    raise AssertionError("did not settle")


def loop(*body: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            node("in", "input", type="list"),
            node("each", "foreach", max_items=10),
            *body,
            node("all", "join"),
            node("out", "output"),
        ],
        "links": [link("in", "value", "each", "items"), link("all", "items", "out", "value")],
    }


def upper_loop() -> dict[str, Any]:
    graph = loop(node("up", "transform", operation="upper"))
    graph["links"] += [link("each", "item", "up", "value"), link("up", "value", "all", "value")]
    return graph


def test_each_iteration_has_its_own_instance_and_emission() -> None:
    statuses, emissions = run(upper_loop(), {"in": ["a", "b", "c"]})
    assert emissions[("up#0", "value", 0)] == "A"
    assert emissions[("up#1", "value", 0)] == "B"
    assert emissions[("up#2", "value", 0)] == "C"
    assert emissions[("each", "item", 1)] == "b"
    assert emissions[("out", "value", 0)] == ["A", "B", "C"]
    assert statuses["up#2"] == "succeeded"


def test_an_empty_list_joins_to_nothing_and_still_finishes() -> None:
    statuses, emissions = run(upper_loop(), {"in": []})
    assert emissions[("out", "value", 0)] == []
    assert "up#0" not in statuses


def test_a_branch_not_taken_is_skipped_rather_than_failed_or_waiting() -> None:
    graph = {
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
    statuses, emissions = run(graph, {"in": 5})
    assert statuses["big"] == "succeeded"
    assert statuses["small"] == "skipped"
    assert emissions[("big", "value", 0)] == 5


def test_a_failure_blocks_what_depends_on_it_and_nothing_else() -> None:
    graph = {
        "nodes": [
            node("in", "input", type="json"),
            node("bad", "transform", operation="upper"),
            node("after", "transform", operation="identity"),
            node("good", "transform", operation="identity"),
            node("out", "output"),
            node("other", "output"),
        ],
        "links": [
            link("in", "value", "bad", "value"),
            link("bad", "value", "after", "value"),
            link("after", "value", "out", "value"),
            link("in", "value", "good", "value"),
            link("good", "value", "other", "value"),
        ],
    }
    statuses, _ = run(graph, {"in": 5})
    assert statuses["bad"] == "failed"
    assert statuses["after"] == "blocked"
    assert statuses["out"] == "blocked"
    assert statuses["other"] == "succeeded"


def test_a_filter_inside_an_iteration_skips_only_that_iteration() -> None:
    graph = loop(node("if", "condition", predicate="greater_than", operand=2))
    graph["links"] += [link("each", "item", "if", "value"), link("if", "true", "all", "value")]
    statuses, emissions = run(graph, {"in": [1, 3, 2, 5]})
    assert emissions[("out", "value", 0)] == [3, 5]
    assert statuses["all"] == "succeeded"


def test_a_list_over_the_foreach_bound_fails_it_and_blocks_what_follows() -> None:
    graph = upper_loop()
    graph["nodes"][1]["config"]["max_items"] = 2
    statuses, emissions = run(graph, {"in": ["a", "b", "c"]})
    assert statuses == {
        "in": "succeeded",
        "each": "failed",
        "up": "blocked",
        "all": "blocked",
        "out": "blocked",
    }
    assert not any(key == "each" for key, _, _ in emissions)


def test_a_failed_iteration_blocks_the_join() -> None:
    statuses, _ = run(upper_loop(), {"in": ["a", 5]})
    assert statuses["up#0"] == "succeeded"
    assert statuses["up#1"] == "failed"
    assert statuses["all"] == "blocked"
    assert statuses["out"] == "blocked"


def test_a_join_waits_for_the_last_iteration() -> None:
    shape = shape_of(upper_loop())
    statuses = {"in": "succeeded", "each": "succeeded", "up#0": "succeeded"}
    emissions = {
        ("in", "value", 0): ["a", "b"],
        ("each", "item", 0): "a",
        ("each", "item", 1): "b",
        ("up#0", "value", 0): "A",
    }
    keys = [step.key for step in next_steps(shape, statuses, emissions)]
    assert keys == ["up#1"]


def test_a_saved_instance_is_never_decided_again() -> None:
    shape = shape_of(upper_loop())
    statuses, emissions = run(upper_loop(), {"in": ["a"]})
    assert next_steps(shape, statuses, emissions) == []


@pytest.mark.parametrize(
    ("operation", "value", "expected"),
    [("upper", "a", "A"), ("lower", "A", "a"), ("length", [1, 2], 2), ("sum", [1, 2], 3)],
)
def test_transforms(operation: str, value: Any, expected: Any) -> None:
    assert run_transform(operation, value) == expected


def test_transforms_and_predicates_fail_with_a_code_on_bad_input() -> None:
    with pytest.raises(BlockFailed):
        run_transform("sum", ["a", 1])
    with pytest.raises(BlockFailed):
        run_transform("upper", 5)
    with pytest.raises(BlockFailed):
        run_predicate("greater_than", "a", 1)
