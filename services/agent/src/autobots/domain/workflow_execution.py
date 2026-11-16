"""Readiness over typed inputs and immutable emissions, PRD 7.3. Pure, so it can be tested alone.

A repeated node gets one instance per iteration, written `node#iteration`. Its outputs are emissions
keyed by that instance and port, so one iteration can't overwrite another's. The blocks that need no
tool run here too, so the runner and the golden-graph tests share one copy of them (PTST-10).
"""

from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Literal, NamedTuple

from autobots.domain import runs
from autobots.domain.runs import RunStatus
from autobots.domain.workflows import (
    PREDICATES,
    TRANSFORMS,
    Block,
    BlockConfig,
    ConditionConfig,
    ForeachConfig,
    Link,
    Node,
    TransformConfig,
    parse_link,
    parse_node,
    topological_order,
)


class InstanceStatus(StrEnum):
    """A saved node instance's status, as workflow_node_instances' check constraint holds it
    (migration 20261105000019)."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


TERMINAL = frozenset(
    {
        InstanceStatus.SUCCEEDED,
        InstanceStatus.FAILED,
        InstanceStatus.SKIPPED,
        InstanceStatus.BLOCKED,
    }
)
# What readiness decides for an instance: it runs, or it settles without running.
Decision = Literal["run", "skipped", "blocked"]


class UnsavedStatus(StrEnum):
    """What an execution shows for an instance with no saved row yet (`unsaved_status`)."""

    NOT_RUN = "not_run"
    WAITING = "waiting"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    STOPPED_HERE = "stopped_here"


class BlockFailed(Exception):
    """A typed reason this instance failed. Nothing about its inputs is hidden by this."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def run_transform(operation: str, value: object) -> object:
    """Workflow values are untyped JSON, so a transform given the wrong kind fails with its code."""
    transform = TRANSFORMS.get(operation)
    if transform is None:
        raise BlockFailed("transform_operation_unknown")
    try:
        return transform.apply(value)
    except TypeError:
        raise BlockFailed("transform_input_invalid") from None


def run_predicate(predicate: str, value: object, operand: object) -> bool:
    rule = PREDICATES.get(predicate)
    if rule is None:
        raise BlockFailed("condition_invalid")
    try:
        return rule(value, operand)
    except TypeError:
        raise BlockFailed("condition_input_invalid") from None


@dataclass(frozen=True)
class Step:
    """A node instance whose fate is now decided from its inputs."""

    key: str
    node_id: str
    iteration: int | None
    decision: Decision
    inputs: Mapping[str, Any]


class Emission(NamedTuple):
    """One output of an instance: its port, its position on that port, and its value."""

    port: str
    sequence: int
    value: object


def typed_config[C](config: BlockConfig, kind: type[C]) -> C:
    """A validated node's configuration as its block's. Validation makes another impossible."""
    if not isinstance(config, kind):
        raise BlockFailed("unknown_block")
    return config


def _input(_config: BlockConfig, step: Step, inputs: Mapping[str, object]) -> list[Emission]:
    return [Emission("value", 0, inputs[step.node_id])]


def _output(_config: BlockConfig, step: Step, _inputs: Mapping[str, object]) -> list[Emission]:
    return [Emission("value", 0, step.inputs.get("value"))]


def _join(_config: BlockConfig, step: Step, _inputs: Mapping[str, object]) -> list[Emission]:
    return [Emission("items", 0, step.inputs.get("value"))]


def _transform(config: BlockConfig, step: Step, _inputs: Mapping[str, object]) -> list[Emission]:
    operation = typed_config(config, TransformConfig).operation
    return [Emission("value", 0, run_transform(operation, step.inputs.get("value")))]


def _condition(config: BlockConfig, step: Step, _inputs: Mapping[str, object]) -> list[Emission]:
    rule = typed_config(config, ConditionConfig)
    value = step.inputs.get("value")
    taken = run_predicate(rule.predicate, value, rule.operand)
    return [Emission("true" if taken else "false", 0, value)]


def _foreach(config: BlockConfig, step: Step, _inputs: Mapping[str, object]) -> list[Emission]:
    bound = typed_config(config, ForeachConfig).max_items
    items = step.inputs["items"]
    if len(items) > bound:
        raise BlockFailed("foreach_over_bound")
    return [Emission("item", index, item) for index, item in enumerate(items)]


# A block's configuration, its decided step and the execution's inputs, to what it emits.
PureBlock = Callable[[BlockConfig, Step, Mapping[str, object]], list[Emission]]
# The blocks that need no tool. The tool-backed rest are workflow_runner.TOOL_BLOCKS, and together
# the two cover BLOCKS exactly (tests/test_workflow_block_rules.py, PPRD-06).
PURE_BLOCKS: Mapping[Block, PureBlock] = MappingProxyType(
    {
        Block.INPUT: _input,
        Block.OUTPUT: _output,
        Block.JOIN: _join,
        Block.TRANSFORM: _transform,
        Block.CONDITION: _condition,
        Block.FOREACH: _foreach,
    }
)


@dataclass(frozen=True)
class GraphShape:
    nodes: Mapping[str, Node]
    links_to: Mapping[str, list[Link]]
    order: list[str]
    owner: Mapping[str, str]


def _owners(nodes: Mapping[str, Node], successors: Mapping[str, list[str]]) -> dict[str, str]:
    """The foreach each repeated step belongs to. Unlike validation's region walk
    (domain/workflows.py `_foreach_region`), it reports nothing: it runs on a validated graph, where
    each region has one foreach and ends at its join."""
    owner: dict[str, str] = {}
    for name, node in nodes.items():
        if node.block is not Block.FOREACH:
            continue
        pending = deque(successors.get(name, ()))
        while pending:
            current = pending.popleft()
            if nodes[current].block is Block.JOIN or current in owner:
                continue
            owner[current] = name
            pending.extend(successors.get(current, ()))
    return owner


def shape_of(graph: Mapping[str, Any]) -> GraphShape:
    """A validated graph as its runner reads it: typed nodes, the links into each node, one run
    order and each repeated step's foreach. A node validation would refuse raises."""
    nodes = {node["id"]: parse_node(node) for node in graph["nodes"]}
    links_to: dict[str, list[Link]] = defaultdict(list)
    successors: dict[str, list[str]] = defaultdict(list)
    for item in graph["links"]:
        link = parse_link(item)
        links_to[link.target].append(link)
        successors[link.source].append(link.target)
    # A validated graph has no cycle, so nothing is left unordered.
    order, _ = topological_order(list(nodes), successors)
    return GraphShape(nodes, links_to, order, _owners(nodes, successors))


def instance_key(node_id: str, iteration: int | None) -> str:
    return node_id if iteration is None else f"{node_id}#{iteration}"


def parse_instance_key(key: str) -> tuple[str, int | None]:
    """The node and iteration an instance key names, as `instance_key` writes them (PPRD-10)."""
    node_id = key.split("#")[0]
    return node_id, int(key.split("#")[1]) if "#" in key else None


def _source_value(
    shape: GraphShape,
    link: Link,
    iteration: int | None,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> tuple[str, Any]:
    """`waiting`, `blocked`, `skipped` or `ready` with its value. Not taken isn't failed."""
    source = link.source
    in_same_iteration = shape.owner.get(source) is not None and iteration is not None
    key = instance_key(source, iteration if in_same_iteration else None)
    status = statuses.get(key)
    if status is None or status not in TERMINAL:
        return "waiting", None
    if status in {InstanceStatus.FAILED, InstanceStatus.BLOCKED}:
        return "blocked", None
    if status == InstanceStatus.SKIPPED:
        return "skipped", None
    is_item = shape.nodes[source].block is Block.FOREACH
    sequence = iteration if is_item and iteration is not None else 0
    found = (key, link.source_port, sequence)
    return ("ready", emissions[found]) if found in emissions else ("skipped", None)


def _decide(
    shape: GraphShape,
    node_id: str,
    iteration: int | None,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> Step | None:
    inputs: dict[str, Any] = {}
    states = []
    for link in shape.links_to.get(node_id, []):
        state, value = _source_value(shape, link, iteration, statuses, emissions)
        states.append(state)
        if state == "ready":
            inputs[link.target_port] = value
    key = instance_key(node_id, iteration)
    if "blocked" in states:
        return Step(key, node_id, iteration, "blocked", {})
    if "waiting" in states:
        return None
    if "skipped" in states:
        return Step(key, node_id, iteration, "skipped", {})
    return Step(key, node_id, iteration, "run", inputs)


def _item_count(emissions: Mapping[tuple[str, str, int], Any], foreach: str) -> int:
    """How many items a finished foreach emitted, so how many iterations each step has."""
    return sum(1 for (key, port, _) in emissions if key == foreach and port == "item")


def _decide_join(
    shape: GraphShape,
    node_id: str,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> Step | None:
    """Waits for every iteration. A skipped one contributes nothing, and a failed one blocks it."""
    links = shape.links_to.get(node_id, [])
    foreach = next((shape.owner[link.source] for link in links if link.source in shape.owner), None)
    if foreach is None:
        foreach = next(link.source for link in links)
    if statuses.get(foreach) not in TERMINAL:
        return None
    if statuses[foreach] != InstanceStatus.SUCCEEDED:
        return Step(node_id, node_id, None, "blocked", {})
    collected: list[Any] = []
    for iteration in range(_item_count(emissions, foreach)):
        for link in links:
            state, value = _source_value(shape, link, iteration, statuses, emissions)
            if state == "waiting":
                return None
            if state == "blocked":
                return Step(node_id, node_id, None, "blocked", {})
            if state == "ready":
                collected.append(value)
    return Step(node_id, node_id, None, "run", {"value": collected})


def _decided(step: Step | None) -> list[Step]:
    return [] if step is None else [step]


def _foreach_body_steps(
    shape: GraphShape,
    node_id: str,
    foreach: str,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> list[Step]:
    """One instance per item once its foreach succeeded. If it didn't, the step is blocked once."""
    if statuses.get(foreach) != InstanceStatus.SUCCEEDED:
        unrun = {InstanceStatus.FAILED, InstanceStatus.BLOCKED, InstanceStatus.SKIPPED}
        key = instance_key(node_id, None)
        if statuses.get(foreach) in unrun and statuses.get(key) not in TERMINAL:
            return [Step(key, node_id, None, "blocked", {})]
        return []
    steps: list[Step] = []
    for iteration in range(_item_count(emissions, foreach)):
        if statuses.get(instance_key(node_id, iteration)) not in TERMINAL:
            steps += _decided(_decide(shape, node_id, iteration, statuses, emissions))
    return steps


def _steps_for(
    shape: GraphShape,
    node_id: str,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> list[Step]:
    foreach = shape.owner.get(node_id)
    if foreach is not None and shape.nodes[node_id].block is not Block.JOIN:
        return _foreach_body_steps(shape, node_id, foreach, statuses, emissions)
    if statuses.get(node_id) in TERMINAL:
        return []
    if shape.nodes[node_id].block is Block.JOIN:
        return _decided(_decide_join(shape, node_id, statuses, emissions))
    return _decided(_decide(shape, node_id, None, statuses, emissions))


def next_steps(
    shape: GraphShape,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> list[Step]:
    """Every instance that can be decided now, in a stable order. Empty means nothing can move."""
    return [
        step for node_id in shape.order for step in _steps_for(shape, node_id, statuses, emissions)
    ]


def unsettled_nodes(shape: GraphShape, statuses: Mapping[str, str]) -> list[str]:
    """What should have an outcome and doesn't. A foreach body has none when it had no items."""
    missing = [
        name
        for name in shape.nodes
        if name not in shape.owner and statuses.get(name) not in TERMINAL
    ]
    open_instances = [key for key, status in statuses.items() if status not in TERMINAL]
    return sorted({*missing, *open_instances})


@dataclass(frozen=True)
class InstanceState:
    """A node instance as an execution shows it: saved, or derived from the graph and the run."""

    key: str
    node_id: str
    iteration: int | None
    status: str
    error_code: str | None


def unsaved_status(
    key: str, current: str | None, run_status: RunStatus, approval_pending: bool
) -> UnsavedStatus:
    """An instance with no row is waiting, or not run once its run ended. The one in progress
    started, so on an ended run its effect may have happened: it shows where the run stopped."""
    if key != current:
        return UnsavedStatus.NOT_RUN if run_status in runs.TERMINAL else UnsavedStatus.WAITING
    if run_status is RunStatus.WAITING_APPROVAL or approval_pending:
        return UnsavedStatus.WAITING_APPROVAL
    if run_status is RunStatus.RUNNING:
        return UnsavedStatus.RUNNING
    return UnsavedStatus.WAITING if run_status is RunStatus.QUEUED else UnsavedStatus.STOPPED_HERE


def instance_states(
    saved: Sequence[InstanceState],
    node_ids: Sequence[str],
    current: str | None,
    run_status: RunStatus,
    approval_pending: bool,
) -> list[InstanceState]:
    """Every saved instance, each node not started yet, and the instance in progress when it has
    no row, in graph order and then by iteration. That comes from the graph, not a stored guess."""
    started = {item.node_id for item in saved}
    settled = {item.key for item in saved}
    in_progress = parse_instance_key(current) if current else None
    states = list(saved)
    for node_id in node_ids:
        if node_id in started or (in_progress is not None and node_id == in_progress[0]):
            continue
        status = unsaved_status(node_id, current, run_status, approval_pending)
        states.append(InstanceState(node_id, node_id, None, status, None))
    if current and in_progress is not None and current not in settled:
        # An iteration is keyed apart from its node, so it's added by what's running.
        node_id, iteration = in_progress
        status = unsaved_status(current, current, run_status, approval_pending)
        states.append(InstanceState(current, node_id, iteration, status, None))
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    states.sort(key=lambda item: (order[item.node_id], item.iteration or 0))
    return states
