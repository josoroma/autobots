"""Readiness over typed inputs and immutable emissions, PRD 7.3. Pure, so it can be tested alone.

A repeated node gets one instance per iteration, written `node#iteration`. Its outputs are emissions
keyed by that instance and port, so one iteration can't overwrite another's.
"""

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

TERMINAL = frozenset({"succeeded", "failed", "skipped", "blocked"})


class BlockFailed(Exception):
    """A typed reason this instance failed. Nothing about its inputs is hidden by this."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def run_transform(operation: str, value: Any) -> Any:
    try:
        if operation == "identity":
            return value
        if operation == "upper":
            return str(_text(value)).upper()
        if operation == "lower":
            return str(_text(value)).lower()
        if operation == "length":
            return len(value)
        if operation == "sum":
            return sum(value)
        if operation == "to_string":
            return str(value)
    except TypeError:
        raise BlockFailed("transform_input_invalid") from None
    raise BlockFailed("transform_operation_unknown")


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise BlockFailed("transform_input_invalid")
    return value


def run_predicate(predicate: str, value: Any, operand: Any) -> bool:
    try:
        if predicate == "equals":
            return bool(value == operand)
        if predicate == "not_equals":
            return bool(value != operand)
        if predicate == "greater_than":
            return bool(value > operand)
        if predicate == "less_than":
            return bool(value < operand)
        if predicate == "contains":
            return operand in value
    except TypeError:
        raise BlockFailed("condition_input_invalid") from None
    raise BlockFailed("condition_invalid")


@dataclass(frozen=True)
class Step:
    """A node instance whose fate is now decided from its inputs."""

    key: str
    node_id: str
    iteration: int | None
    decision: str
    inputs: Mapping[str, Any]


@dataclass(frozen=True)
class GraphShape:
    nodes: Mapping[str, Mapping[str, Any]]
    links_to: Mapping[str, list[Mapping[str, str]]]
    order: list[str]
    owner: Mapping[str, str]


def shape_of(graph: Mapping[str, Any]) -> GraphShape:
    nodes = {node["id"]: node for node in graph["nodes"]}
    links_to: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    successors: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = dict.fromkeys(nodes, 0)
    for link in graph["links"]:
        links_to[link["target"]].append(link)
        successors[link["source"]].append(link["target"])
        incoming[link["target"]] += 1
    ready = deque(name for name, count in incoming.items() if count == 0)
    order: list[str] = []
    while ready:
        current = ready.popleft()
        order.append(current)
        for target in successors[current]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    owner: dict[str, str] = {}
    for name, node in nodes.items():
        if node["block"] != "foreach":
            continue
        pending = deque(successors[name])
        while pending:
            current = pending.popleft()
            if nodes[current]["block"] == "join" or current in owner:
                continue
            owner[current] = name
            pending.extend(successors[current])
    return GraphShape(nodes, links_to, order, owner)


def instance_key(node_id: str, iteration: int | None) -> str:
    return node_id if iteration is None else f"{node_id}#{iteration}"


def _source_value(
    shape: GraphShape,
    link: Mapping[str, str],
    iteration: int | None,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> tuple[str, Any]:
    """`waiting`, `blocked`, `skipped` or `ready` with its value. Not taken isn't failed."""
    source = link["source"]
    in_same_iteration = shape.owner.get(source) is not None and iteration is not None
    key = instance_key(source, iteration if in_same_iteration else None)
    status = statuses.get(key)
    if status is None or status not in TERMINAL:
        return "waiting", None
    if status in {"failed", "blocked"}:
        return "blocked", None
    if status == "skipped":
        return "skipped", None
    is_item = shape.nodes[source]["block"] == "foreach"
    sequence = iteration if is_item and iteration is not None else 0
    found = (key, link["source_port"], sequence)
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
            inputs[link["target_port"]] = value
    key = instance_key(node_id, iteration)
    if "blocked" in states:
        return Step(key, node_id, iteration, "blocked", {})
    if "waiting" in states:
        return None
    if "skipped" in states:
        return Step(key, node_id, iteration, "skipped", {})
    return Step(key, node_id, iteration, "run", inputs)


def _decide_join(
    shape: GraphShape,
    node_id: str,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> Step | None:
    """Waits for every iteration. A skipped one contributes nothing, and a failed one blocks it."""
    links = shape.links_to.get(node_id, [])
    foreach = next(
        (shape.owner[link["source"]] for link in links if link["source"] in shape.owner), None
    )
    if foreach is None:
        foreach = next(link["source"] for link in links)
    if statuses.get(foreach) not in TERMINAL:
        return None
    if statuses[foreach] != "succeeded":
        return Step(node_id, node_id, None, "blocked", {})
    count = sum(1 for (key, port, _) in emissions if key == foreach and port == "item")
    collected: list[Any] = []
    for iteration in range(count):
        for link in links:
            state, value = _source_value(shape, link, iteration, statuses, emissions)
            if state == "waiting":
                return None
            if state == "blocked":
                return Step(node_id, node_id, None, "blocked", {})
            if state == "ready":
                collected.append(value)
    return Step(node_id, node_id, None, "run", {"value": collected})


def next_steps(
    shape: GraphShape,
    statuses: Mapping[str, str],
    emissions: Mapping[tuple[str, str, int], Any],
) -> list[Step]:
    """Every instance that can be decided now, in a stable order. Empty means nothing can move."""
    steps: list[Step] = []
    for node_id in shape.order:
        block = shape.nodes[node_id]["block"]
        if block == "join":
            if statuses.get(node_id) not in TERMINAL:
                step = _decide_join(shape, node_id, statuses, emissions)
                if step is not None:
                    steps.append(step)
            continue
        foreach = shape.owner.get(node_id)
        if foreach is None:
            if statuses.get(node_id) not in TERMINAL:
                step = _decide(shape, node_id, None, statuses, emissions)
                if step is not None:
                    steps.append(step)
            continue
        if statuses.get(foreach) != "succeeded":
            if statuses.get(foreach) in {"failed", "blocked", "skipped"}:
                key = instance_key(node_id, None)
                if statuses.get(key) not in TERMINAL:
                    steps.append(Step(key, node_id, None, "blocked", {}))
            continue
        count = sum(1 for (key, port, _) in emissions if key == foreach and port == "item")
        for iteration in range(count):
            if statuses.get(instance_key(node_id, iteration)) in TERMINAL:
                continue
            step = _decide(shape, node_id, iteration, statuses, emissions)
            if step is not None:
                steps.append(step)
    return steps


def unsettled_nodes(shape: GraphShape, statuses: Mapping[str, str]) -> list[str]:
    """What should have an outcome and doesn't. A foreach body has none when it had no items."""
    missing = [
        name
        for name in shape.nodes
        if name not in shape.owner and statuses.get(name) not in TERMINAL
    ]
    open_instances = [key for key, status in statuses.items() if status not in TERMINAL]
    return sorted({*missing, *open_instances})
