"""Every block kind has exactly one runner, and the pure ones run with plain values (PPRD-06,
PDOM-12, PTST-10, refactor plan R-63).

A block that validates and publishes must also run, so the runner's two tables, the pure blocks in
the domain and the tool-backed blocks in workflow_runner.py, together cover BLOCKS exactly. Every
transform and predicate name that validation accepts also executes.
"""

from typing import Any

import pytest

from autobots.application.workflow_runner import TOOL_BLOCKS
from autobots.domain.workflow_execution import (
    PURE_BLOCKS,
    BlockFailed,
    Emission,
    Step,
    run_predicate,
    run_transform,
)
from autobots.domain.workflows import (
    BLOCKS,
    PREDICATES,
    TRANSFORMS,
    Block,
    ConditionConfig,
    ForeachConfig,
    PlainConfig,
    TransformConfig,
)


def step(node_id: str, **inputs: object) -> Step:
    return Step(node_id, node_id, None, "run", inputs)


def test_each_block_kind_has_exactly_one_runner() -> None:
    assert not set(PURE_BLOCKS) & set(TOOL_BLOCKS)
    assert set(PURE_BLOCKS) | set(TOOL_BLOCKS) == set(BLOCKS) == set(Block)


def test_the_pure_blocks_emit_on_their_ports() -> None:
    plain = PlainConfig()
    assert PURE_BLOCKS[Block.INPUT](plain, step("in"), {"in": 3}) == [Emission("value", 0, 3)]
    assert PURE_BLOCKS[Block.OUTPUT](plain, step("out", value=[1]), {}) == [
        Emission("value", 0, [1])
    ]
    assert PURE_BLOCKS[Block.JOIN](plain, step("all", value=[1, 2]), {}) == [
        Emission("items", 0, [1, 2])
    ]
    upper = TransformConfig("upper")
    assert PURE_BLOCKS[Block.TRANSFORM](upper, step("up", value="a"), {}) == [
        Emission("value", 0, "A")
    ]


@pytest.mark.parametrize(("value", "port"), [(5, "true"), (1, "false")])
def test_a_condition_passes_its_value_on_the_port_it_takes(value: int, port: str) -> None:
    rule = ConditionConfig("greater_than", 3)
    assert PURE_BLOCKS[Block.CONDITION](rule, step("if", value=value), {}) == [
        Emission(port, 0, value)
    ]


def test_a_foreach_emits_each_item_within_its_bound_and_fails_beyond_it() -> None:
    bound = ForeachConfig(max_items=2, item_type="json")
    assert PURE_BLOCKS[Block.FOREACH](bound, step("each", items=["a", "b"]), {}) == [
        Emission("item", 0, "a"),
        Emission("item", 1, "b"),
    ]
    with pytest.raises(BlockFailed) as failed:
        PURE_BLOCKS[Block.FOREACH](bound, step("each", items=[1, 2, 3]), {})
    assert failed.value.code == "foreach_over_bound"


EXAMPLES: dict[str, tuple[Any, Any]] = {
    "identity": ({"a": 1}, {"a": 1}),
    "upper": ("ab", "AB"),
    "lower": ("AB", "ab"),
    "length": ([1, 2, 3], 3),
    "sum": ([1, 2.5], 3.5),
    "to_string": (12, "12"),
}
OUTPUT_TYPES = {
    "identity": "json",
    "upper": "string",
    "lower": "string",
    "length": "number",
    "sum": "number",
    "to_string": "string",
}


@pytest.mark.parametrize("operation", sorted(TRANSFORMS))
def test_every_transform_that_validates_executes(operation: str) -> None:
    value, expected = EXAMPLES[operation]
    assert run_transform(operation, value) == expected
    assert TRANSFORMS[operation].output_type == OUTPUT_TYPES[operation]


def test_the_transform_examples_name_every_transform() -> None:
    assert set(EXAMPLES) == set(TRANSFORMS) == set(OUTPUT_TYPES)


@pytest.mark.parametrize(
    ("operation", "value"),
    [("upper", 5), ("lower", ["a"]), ("length", 3), ("sum", ["a", 1]), ("sum", None)],
)
def test_a_transform_of_the_wrong_input_fails_with_its_code(operation: str, value: object) -> None:
    with pytest.raises(BlockFailed) as failed:
        run_transform(operation, value)
    assert failed.value.code == "transform_input_invalid"


def test_an_unknown_transform_or_predicate_fails_with_its_code() -> None:
    with pytest.raises(BlockFailed) as failed:
        run_transform("eval", 1)
    assert failed.value.code == "transform_operation_unknown"
    with pytest.raises(BlockFailed) as failed:
        run_predicate("matches", 1, 1)
    assert failed.value.code == "condition_invalid"


PREDICATE_CASES: dict[str, list[tuple[Any, Any, bool]]] = {
    "equals": [(1, 1, True), ("a", "b", False)],
    "not_equals": [(1, 1, False), ("a", "b", True)],
    "greater_than": [(5, 3, True), (3, 5, False)],
    "less_than": [(3, 5, True), (5, 3, False)],
    "contains": [("abc", "b", True), ([1, 2], 3, False)],
}


@pytest.mark.parametrize("predicate", sorted(PREDICATES))
def test_every_predicate_that_validates_executes(predicate: str) -> None:
    for value, operand, expected in PREDICATE_CASES[predicate]:
        assert run_predicate(predicate, value, operand) is expected


def test_the_predicate_cases_name_every_predicate() -> None:
    assert set(PREDICATE_CASES) == set(PREDICATES)


@pytest.mark.parametrize(
    ("predicate", "value", "operand"), [("greater_than", "a", 1), ("contains", 5, 1)]
)
def test_a_predicate_of_the_wrong_input_fails_with_its_code(
    predicate: str, value: object, operand: object
) -> None:
    with pytest.raises(BlockFailed) as failed:
        run_predicate(predicate, value, operand)
    assert failed.value.code == "condition_input_invalid"
