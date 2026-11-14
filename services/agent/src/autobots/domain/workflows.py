"""The documented workflow subset and its validation, PRD 7.3. Pure, and reachable by any caller.

A graph is data. Whatever wrote it, a person or a model, it passes through here before it can be
published, and nothing about who wrote it changes what is accepted.
"""

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MAX_FOREACH_ITEMS = 100
# PRD-Studio WF-06: IR version 2 adds an optional `label` to each node. A graph with no
# `ir_version` is version 1, which stays valid and hashes exactly as it always did.
IR_VERSIONS = frozenset({1, 2})
LABELLED_IR_VERSION = 2
TRANSFORMS = frozenset({"identity", "upper", "lower", "length", "sum", "to_string"})
PREDICATES = frozenset({"equals", "not_equals", "greater_than", "less_than", "contains"})


@dataclass(frozen=True)
class BlockSpec:
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    required: frozenset[str]
    many_inputs: frozenset[str] = frozenset()


BLOCKS: Mapping[str, Mapping[int, BlockSpec]] = {
    "input": {1: BlockSpec({}, {"value": "config"}, frozenset())},
    "output": {1: BlockSpec({"value": "json"}, {}, frozenset({"value"}))},
    "transform": {1: BlockSpec({"value": "json"}, {"value": "json"}, frozenset({"value"}))},
    "condition": {
        1: BlockSpec({"value": "json"}, {"true": "json", "false": "json"}, frozenset({"value"}))
    },
    "foreach": {1: BlockSpec({"items": "list"}, {"item": "config_item"}, frozenset({"items"}))},
    "join": {
        1: BlockSpec(
            {"value": "json"}, {"items": "list"}, frozenset({"value"}), frozenset({"value"})
        )
    },
    "read": {1: BlockSpec({"path": "string"}, {"content": "string"}, frozenset({"path"}))},
    "artifact": {
        1: BlockSpec({"content": "string"}, {"artifact_id": "string"}, frozenset({"content"}))
    },
    "approval": {1: BlockSpec({"value": "json"}, {"value": "json"}, frozenset({"value"}))},
    "agent": {1: BlockSpec({"goal": "string"}, {"result": "json"}, frozenset({"goal"}))},
}
INPUT_TYPES = frozenset({"string", "number", "boolean", "json", "list"})


@dataclass(frozen=True)
class GraphError:
    code: str
    node: str | None = None
    port: str | None = None


def _compatible(source: str, target: str) -> bool:
    return target == "json" or source == target


TRANSFORM_OUTPUTS = {
    "upper": "string",
    "lower": "string",
    "to_string": "string",
    "length": "number",
    "sum": "number",
}
# Pass their input through unchanged, so what follows can rely on its type.
PASS_THROUGH = frozenset({"approval", "condition"})


def _resolved_type(
    nodes: Mapping[str, Mapping[str, Any]],
    specs: Mapping[str, BlockSpec],
    feeds: Mapping[str, tuple[str, str]],
    name: str,
    port: str,
    seen: frozenset[str] = frozenset(),
) -> str:
    node = nodes[name]
    passes_along = node["block"] in PASS_THROUGH or (
        node["block"] == "transform" and node.get("config", {}).get("operation") == "identity"
    )
    if passes_along and name in feeds and name not in seen:
        source, source_port = feeds[name]
        return _resolved_type(nodes, specs, feeds, source, source_port, seen | {name})
    if node["block"] == "transform":
        return TRANSFORM_OUTPUTS.get(str(node.get("config", {}).get("operation")), "json")
    return _output_type(node, port, specs[name])


def _output_type(node: Mapping[str, Any], port: str, spec: BlockSpec) -> str:
    declared = spec.outputs[port]
    config = node.get("config", {})
    if declared == "config":
        return str(config.get("type", "json"))
    return str(config.get("item_type", "json")) if declared == "config_item" else declared


def _config_errors(node: Mapping[str, Any]) -> list[GraphError]:  # noqa: PLR0911 - baseline 2026-11-14, shrink only (STD-06)
    block, config, name = node["block"], node.get("config", {}), node["id"]
    if block == "input" and config.get("type") not in INPUT_TYPES:
        return [GraphError("input_type_invalid", name)]
    if block == "transform" and config.get("operation") not in TRANSFORMS:
        return [GraphError("transform_operation_unknown", name)]
    if block == "condition":
        if config.get("predicate") not in PREDICATES or "operand" not in config:
            return [GraphError("condition_invalid", name)]
    if block == "foreach":
        bound = config.get("max_items")
        if not isinstance(bound, int) or isinstance(bound, bool) or bound < 1:
            return [GraphError("foreach_bound_required", name)]
        if bound > MAX_FOREACH_ITEMS:
            return [GraphError("foreach_bound_too_large", name)]
        if config.get("item_type", "json") not in INPUT_TYPES:
            return [GraphError("foreach_item_type_invalid", name)]
    if block == "artifact" and not str(config.get("path", "")).startswith("outputs/"):
        return [GraphError("artifact_path_invalid", name)]
    if block == "agent" and not config.get("expert_id"):
        return [GraphError("agent_expert_required", name)]
    return []


def _has_cycle(names: list[str], successors: Mapping[str, set[str]]) -> bool:
    incoming: dict[str, int] = dict.fromkeys(names, 0)
    for targets in successors.values():
        for target in targets:
            incoming[target] += 1
    ready = deque(name for name, count in incoming.items() if count == 0)
    seen = 0
    while ready:
        current = ready.popleft()
        seen += 1
        for target in successors.get(current, ()):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    return seen != len(names)


def _iteration_errors(
    nodes: Mapping[str, Mapping[str, Any]], successors: Mapping[str, set[str]]
) -> list[GraphError]:
    """Iteration is bounded and explicit: every path out of a foreach goes through one join."""
    errors: list[GraphError] = []
    in_region: set[str] = set()
    joins_seen: dict[str, set[str]] = {}
    regions: dict[str, set[str]] = {}
    for name, node in nodes.items():
        if node["block"] != "foreach":
            continue
        region: set[str] = set()
        found_join = False
        pending = deque(successors.get(name, ()))
        while pending:
            current = pending.popleft()
            block = nodes[current]["block"]
            if block == "join":
                found_join = True
                joins_seen.setdefault(current, set()).add(name)
                continue
            if block == "foreach":
                errors.append(GraphError("nested_foreach", current))
                continue
            if current in region:
                continue
            region.add(current)
            following = successors.get(current, set())
            if block == "output" or not following:
                errors.append(GraphError("iteration_boundary_crossed", current))
            pending.extend(following)
        if not found_join:
            errors.append(GraphError("foreach_without_join", name))
        in_region |= region
        regions[name] = region
    # Iterations are collected by position, so two lists can't feed one join without losing items.
    errors.extend(
        GraphError("join_multiple_foreach", name)
        for name, sources in joins_seen.items()
        if len(sources) > 1
    )
    # Iteration is counted from a join's first link, so an outside link could empty the result.
    for join, sources in joins_seen.items():
        allowed = {node for source in sources for node in (source, *regions.get(source, ()))}
        if any(join in following and name not in allowed for name, following in successors.items()):
            errors.append(GraphError("join_mixed_sources", join))
    errors.extend(
        GraphError("join_outside_foreach", name)
        for name, node in nodes.items()
        if node["block"] == "join" and name not in joins_seen
    )
    return errors


def ir_normalized(graph: Mapping[str, Any]) -> dict[str, Any]:
    """As stored and hashed. An absent label or IR version is left out, so a version 1 graph is
    unchanged, and a graph whose nodes carry labels is stored at IR version 2."""
    plain = dict(graph)
    plain["nodes"] = [
        {key: value for key, value in node.items() if not (key == "label" and value is None)}
        for node in graph.get("nodes", [])
    ]
    if plain.get("ir_version") is None:
        plain.pop("ir_version", None)
        if any("label" in node for node in plain["nodes"]):
            plain["ir_version"] = LABELLED_IR_VERSION
    return plain


def validate_graph(graph: Mapping[str, Any]) -> list[GraphError]:  # noqa: C901, PLR0912 - baseline 2026-11-14, shrink only (STD-06)
    """Typed errors, all at once where they can be found. An empty list means publishable."""
    errors: list[GraphError] = []
    version = graph.get("ir_version", 1)
    if version not in IR_VERSIONS:
        return [GraphError("unknown_ir_version")]
    if version < LABELLED_IR_VERSION:
        errors.extend(
            GraphError("label_needs_ir_version_2", node["id"])
            for node in graph.get("nodes", [])
            if node.get("label") is not None
        )
    nodes: dict[str, Mapping[str, Any]] = {}
    for node in graph.get("nodes", []):
        if node["id"] in nodes:
            errors.append(GraphError("duplicate_node", node["id"]))
        nodes[node["id"]] = node
    specs: dict[str, BlockSpec] = {}
    for name, node in nodes.items():
        versions = BLOCKS.get(node["block"])
        if versions is None:
            errors.append(GraphError("unknown_block", name))
            continue
        spec = versions.get(node["version"])
        if spec is None:
            errors.append(GraphError("unknown_block_version", name))
            continue
        specs[name] = spec
        errors.extend(_config_errors(node))
    if errors:
        return errors
    linked: dict[tuple[str, str], int] = defaultdict(int)
    successors: dict[str, set[str]] = defaultdict(set)
    feeds = {
        link["target"]: (link["source"], link["source_port"])
        for link in graph.get("links", [])
        if link["target_port"] == "value"
        and link["source"] in nodes
        and link["target"] in nodes
        and link["source_port"] in specs[link["source"]].outputs
    }
    for link in graph.get("links", []):
        source, target = link["source"], link["target"]
        if source not in nodes or target not in nodes:
            errors.append(GraphError("unknown_node", source if source not in nodes else target))
            continue
        if link["source_port"] not in specs[source].outputs:
            errors.append(GraphError("unknown_port", source, link["source_port"]))
            continue
        if link["target_port"] not in specs[target].inputs:
            errors.append(GraphError("unknown_port", target, link["target_port"]))
            continue
        kind = _resolved_type(nodes, specs, feeds, source, link["source_port"])
        wanted = specs[target].inputs[link["target_port"]]
        if not _compatible(kind, wanted):
            errors.append(GraphError("link_type_mismatch", target, link["target_port"]))
        linked[(target, link["target_port"])] += 1
        successors[source].add(target)
    for (target, port), count in linked.items():
        if count > 1 and port not in specs[target].many_inputs:
            errors.append(GraphError("input_linked_twice", target, port))
    for name, spec in specs.items():
        errors.extend(
            GraphError("required_input_unlinked", name, port)
            for port in sorted(spec.required)
            if (name, port) not in linked
        )
    if not any(node["block"] == "output" for node in nodes.values()):
        errors.append(GraphError("output_required"))
    if not any(node["block"] == "input" for node in nodes.values()):
        errors.append(GraphError("input_required"))
    if errors:
        return errors
    if _has_cycle(list(nodes), successors):
        return [GraphError("cycle_not_supported")]
    return _iteration_errors(nodes, successors)


def step_order(graph: Mapping[str, Any]) -> list[str]:
    """Node IDs in the order the graph runs them: each after everything that feeds it, and ties
    in the order the nodes are listed. A node in an unsupported cycle keeps its listed place."""
    names = [node["id"] for node in graph.get("nodes", [])]
    waiting: dict[str, int] = dict.fromkeys(names, 0)
    successors: dict[str, list[str]] = defaultdict(list)
    for link in graph.get("links", []):
        if link.get("source") in waiting and link.get("target") in waiting:
            successors[link["source"]].append(link["target"])
            waiting[link["target"]] += 1
    ordered: list[str] = []
    ready = deque(name for name in names if waiting[name] == 0)
    while ready:
        name = ready.popleft()
        ordered.append(name)
        for target in successors[name]:
            waiting[target] -= 1
            if waiting[target] == 0:
                ready.append(target)
    return ordered + [name for name in names if name not in ordered]


def canonical(graph: Mapping[str, Any]) -> str:
    return json.dumps(graph, sort_keys=True, separators=(",", ":"))


def graph_hash(graph: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(graph).encode()).hexdigest()


def block_versions(graph: Mapping[str, Any]) -> dict[str, str]:
    return {node["id"]: f"{node['block']}@{node['version']}" for node in graph["nodes"]}


def input_errors(graph: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[GraphError]:
    """An execution binds values to the graph's input nodes, of the declared types."""
    declared = {
        node["id"]: node.get("config", {}).get("type", "json")
        for node in graph["nodes"]
        if node["block"] == "input"
    }
    errors = [GraphError("input_missing", name) for name in declared if name not in inputs]
    errors.extend(GraphError("input_unknown", name) for name in inputs if name not in declared)
    python_types: dict[str, tuple[type, ...]] = {
        "string": (str,),
        "number": (int, float),
        "boolean": (bool,),
        "list": (list,),
    }
    for name, kind in declared.items():
        if name not in inputs or kind == "json":
            continue
        value = inputs[name]
        valid = isinstance(value, python_types[kind]) and not (
            kind == "number" and isinstance(value, bool)
        )
        if not valid:
            errors.append(GraphError("input_type_mismatch", name))
    return errors
