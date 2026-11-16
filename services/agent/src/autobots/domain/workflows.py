"""The documented workflow subset and its validation, PRD 7.3. Pure, and reachable by any caller.

A graph is data. Whatever wrote it, a person or a model, it passes through here before it can be
published, and nothing about who wrote it changes what is accepted. Validation and hashing read the
stored, normalized dict; a validated graph's runner reads it as typed `Node`s and `Link`s (PDOM-09).
"""

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

MAX_FOREACH_ITEMS = 100
# PRD-Studio WF-06: IR version 2 adds an optional `label` to each node. A graph with no
# `ir_version` is version 1, which stays valid and hashes exactly as it always did.
IR_VERSIONS = frozenset({1, 2})
LABELLED_IR_VERSION = 2


class Block(StrEnum):
    """Each block kind of the documented subset. The stored graph keeps the kind as its text."""

    INPUT = "input"
    OUTPUT = "output"
    TRANSFORM = "transform"
    CONDITION = "condition"
    FOREACH = "foreach"
    JOIN = "join"
    READ = "read"
    ARTIFACT = "artifact"
    APPROVAL = "approval"
    AGENT = "agent"


def _text(value: object) -> str:
    """Upper and lower read text only, so anything else is the wrong input."""
    if not isinstance(value, str):
        raise TypeError(type(value).__name__)
    return value


@dataclass(frozen=True)
class Transform:
    """A transform's output type, which validation checks links against, and what it computes. A
    `TypeError` from `apply` is the wrong input (workflow_execution.run_transform)."""

    output_type: str
    apply: Callable[[Any], object]


# One table per vocabulary: validation reads the names, link checks the output types, and execution
# applies them, so a name that validates always runs (PDOM-12).
TRANSFORMS: Mapping[str, Transform] = MappingProxyType(
    {
        "identity": Transform("json", lambda value: value),
        "upper": Transform("string", lambda value: _text(value).upper()),
        "lower": Transform("string", lambda value: _text(value).lower()),
        "length": Transform("number", len),
        "sum": Transform("number", sum),
        "to_string": Transform("string", str),
    }
)
PREDICATES: Mapping[str, Callable[[Any, Any], bool]] = MappingProxyType(
    {
        "equals": lambda value, operand: bool(value == operand),
        "not_equals": lambda value, operand: bool(value != operand),
        "greater_than": lambda value, operand: bool(value > operand),
        "less_than": lambda value, operand: bool(value < operand),
        "contains": lambda value, operand: operand in value,
    }
)


@dataclass(frozen=True)
class BlockSpec:
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    required: frozenset[str]
    many_inputs: frozenset[str] = frozenset()


BLOCKS: Mapping[str, Mapping[int, BlockSpec]] = {
    Block.INPUT: {1: BlockSpec({}, {"value": "config"}, frozenset())},
    Block.OUTPUT: {1: BlockSpec({"value": "json"}, {}, frozenset({"value"}))},
    Block.TRANSFORM: {1: BlockSpec({"value": "json"}, {"value": "json"}, frozenset({"value"}))},
    Block.CONDITION: {
        1: BlockSpec({"value": "json"}, {"true": "json", "false": "json"}, frozenset({"value"}))
    },
    Block.FOREACH: {1: BlockSpec({"items": "list"}, {"item": "config_item"}, frozenset({"items"}))},
    Block.JOIN: {
        1: BlockSpec(
            {"value": "json"}, {"items": "list"}, frozenset({"value"}), frozenset({"value"})
        )
    },
    Block.READ: {1: BlockSpec({"path": "string"}, {"content": "string"}, frozenset({"path"}))},
    Block.ARTIFACT: {
        1: BlockSpec({"content": "string"}, {"artifact_id": "string"}, frozenset({"content"}))
    },
    Block.APPROVAL: {1: BlockSpec({"value": "json"}, {"value": "json"}, frozenset({"value"}))},
    Block.AGENT: {1: BlockSpec({"goal": "string"}, {"result": "json"}, frozenset({"goal"}))},
}
INPUT_TYPES = frozenset({"string", "number", "boolean", "json", "list"})


@dataclass(frozen=True)
class GraphError:
    code: str
    node: str | None = None
    port: str | None = None


def _compatible(source: str, target: str) -> bool:
    return target == "json" or source == target


# Pass their input through unchanged, so what follows can rely on its type.
PASS_THROUGH = frozenset({Block.APPROVAL, Block.CONDITION})


# Each block's configuration, typed once from the graph's mapping (refactor plan R-52, XTYP-08).
# The graph IR stays the stored format; these are what readers take from it.
@dataclass(frozen=True)
class InputConfig:
    type: str


@dataclass(frozen=True)
class TransformConfig:
    operation: str


@dataclass(frozen=True)
class ConditionConfig:
    predicate: str
    operand: object


@dataclass(frozen=True)
class ForeachConfig:
    max_items: int
    item_type: str


@dataclass(frozen=True)
class ArtifactConfig:
    path: str


@dataclass(frozen=True)
class AgentConfig:
    expert_id: str


@dataclass(frozen=True)
class PlainConfig:
    """output, join, read and approval, which read no configuration."""


BlockConfig = (
    InputConfig
    | TransformConfig
    | ConditionConfig
    | ForeachConfig
    | ArtifactConfig
    | AgentConfig
    | PlainConfig
)


def _named(value: object, names: Collection[str]) -> str | None:
    """`value` if it is one of `names`. A draft can hold any JSON there, such as a list."""
    return value if isinstance(value, str) and value in names else None


def _input(config: Mapping[str, Any]) -> BlockConfig | str:
    kind = _named(config.get("type"), INPUT_TYPES)
    return InputConfig(kind) if kind is not None else "input_type_invalid"


def _transform(config: Mapping[str, Any]) -> BlockConfig | str:
    operation = _named(config.get("operation"), TRANSFORMS)
    return TransformConfig(operation) if operation is not None else "transform_operation_unknown"


def _condition(config: Mapping[str, Any]) -> BlockConfig | str:
    predicate = _named(config.get("predicate"), PREDICATES)
    if predicate is None or "operand" not in config:
        return "condition_invalid"
    return ConditionConfig(predicate, config["operand"])


def _foreach(config: Mapping[str, Any]) -> BlockConfig | str:
    bound = config.get("max_items")
    if not isinstance(bound, int) or isinstance(bound, bool) or bound < 1:
        return "foreach_bound_required"
    if bound > MAX_FOREACH_ITEMS:
        return "foreach_bound_too_large"
    item_type = _named(config.get("item_type", "json"), INPUT_TYPES)
    return ForeachConfig(bound, item_type) if item_type is not None else "foreach_item_type_invalid"


def _artifact(config: Mapping[str, Any]) -> BlockConfig | str:
    path = str(config.get("path", ""))
    return ArtifactConfig(path) if path.startswith("outputs/") else "artifact_path_invalid"


def _agent(config: Mapping[str, Any]) -> BlockConfig | str:
    expert_id = config.get("expert_id")
    return AgentConfig(str(expert_id)) if expert_id else "agent_expert_required"


_CONFIGS: Mapping[str, Callable[[Mapping[str, Any]], BlockConfig | str]] = {
    Block.INPUT: _input,
    Block.TRANSFORM: _transform,
    Block.CONDITION: _condition,
    Block.FOREACH: _foreach,
    Block.ARTIFACT: _artifact,
    Block.AGENT: _agent,
}


def block_config(node: Mapping[str, Any]) -> BlockConfig | GraphError:
    """A node's configuration, typed, or the node-level error validation reports for it."""
    if node["block"] not in BLOCKS:
        return GraphError("unknown_block", node["id"])
    parse = _CONFIGS.get(node["block"])
    if parse is None:
        return PlainConfig()
    config = node.get("config", {})
    # A configuration that isn't an object holds none of its block's keys.
    parsed = parse(config if isinstance(config, Mapping) else {})
    return GraphError(parsed, node["id"]) if isinstance(parsed, str) else parsed


@dataclass(frozen=True)
class Node:
    """A validated graph's node, as its runner reads it."""

    id: str
    block: Block
    version: int
    config: BlockConfig
    label: str | None = None


@dataclass(frozen=True)
class Link:
    source: str
    source_port: str
    target: str
    target_port: str


def parse_node(node: Mapping[str, Any]) -> Node:
    """A node of a graph that validates. One validation would refuse raises with its code."""
    config = block_config(node)
    if isinstance(config, GraphError):
        raise ValueError(config.code)
    return Node(node["id"], Block(node["block"]), node["version"], config, node.get("label"))


def parse_link(link: Mapping[str, str]) -> Link:
    return Link(link["source"], link["source_port"], link["target"], link["target_port"])


def topological_order(
    names: Sequence[str], successors: Mapping[str, Iterable[str]]
) -> tuple[list[str], list[str]]:
    """Kahn's order: each name after every name that leads to it, ties in the order given. The
    second list is what a cycle leaves unordered, in the order given. An edge counts once for each
    time it appears, and one from or to a name not given is ignored. Validation's cycle check, the
    step order shown to people and the runner's order all use this one sort (PDOM-17)."""
    incoming = dict.fromkeys(names, 0)
    for source, targets in successors.items():
        for target in targets:
            if source in incoming and target in incoming:
                incoming[target] += 1
    ready = deque(name for name in names if incoming[name] == 0)
    ordered: list[str] = []
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for target in successors.get(current, ()):
            if target in incoming:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
    placed = set(ordered)
    return ordered, [name for name in names if name not in placed]


@dataclass(frozen=True)
class _Types:
    """What a link's source port carries, read through pass-through steps to what feeds them."""

    nodes: Mapping[str, Mapping[str, Any]]
    specs: Mapping[str, BlockSpec]
    configs: Mapping[str, BlockConfig]
    feeds: Mapping[str, tuple[str, str]]

    def of(self, name: str, port: str, seen: frozenset[str] = frozenset()) -> str:
        config = self.configs[name]
        passes_along = self.nodes[name]["block"] in PASS_THROUGH or (
            isinstance(config, TransformConfig) and config.operation == "identity"
        )
        if passes_along and name in self.feeds and name not in seen:
            source, source_port = self.feeds[name]
            return self.of(source, source_port, seen | {name})
        if isinstance(config, TransformConfig):
            return TRANSFORMS[config.operation].output_type
        return _output_type(config, port, self.specs[name])


def _output_type(config: BlockConfig, port: str, spec: BlockSpec) -> str:
    declared = spec.outputs[port]
    if declared == "config":
        return config.type if isinstance(config, InputConfig) else "json"
    if declared == "config_item":
        return config.item_type if isinstance(config, ForeachConfig) else "json"
    return declared


def _foreach_region(
    name: str, nodes: Mapping[str, Mapping[str, Any]], successors: Mapping[str, set[str]]
) -> tuple[set[str], list[str], list[GraphError]]:
    """The steps a foreach repeats, the joins that collect it as first reached, and what breaks the
    region. The runner's walk (workflow_execution.shape_of) only assigns each step its foreach: it
    runs after this check, which already refused nesting and paths that leave without a join."""
    errors: list[GraphError] = []
    region: set[str] = set()
    joins: list[str] = []
    pending = deque(successors.get(name, ()))
    while pending:
        current = pending.popleft()
        block = nodes[current]["block"]
        if block == Block.JOIN:
            if current not in joins:
                joins.append(current)
            continue
        if block == Block.FOREACH:
            errors.append(GraphError("nested_foreach", current))
            continue
        if current in region:
            continue
        region.add(current)
        following = successors.get(current, set())
        if block == Block.OUTPUT or not following:
            errors.append(GraphError("iteration_boundary_crossed", current))
        pending.extend(following)
    if not joins:
        errors.append(GraphError("foreach_without_join", name))
    return region, joins, errors


def _iteration_errors(
    nodes: Mapping[str, Mapping[str, Any]], successors: Mapping[str, set[str]]
) -> list[GraphError]:
    """Iteration is bounded and explicit: every path out of a foreach goes through one join."""
    errors: list[GraphError] = []
    joins_seen: dict[str, set[str]] = {}
    regions: dict[str, set[str]] = {}
    for name, node in nodes.items():
        if node["block"] != Block.FOREACH:
            continue
        region, joins, region_errors = _foreach_region(name, nodes, successors)
        errors.extend(region_errors)
        for join in joins:
            joins_seen.setdefault(join, set()).add(name)
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
        if node["block"] == Block.JOIN and name not in joins_seen
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


def _label_errors(graph: Mapping[str, Any], version: int) -> list[GraphError]:
    if version >= LABELLED_IR_VERSION:
        return []
    return [
        GraphError("label_needs_ir_version_2", node["id"])
        for node in graph.get("nodes", [])
        if node.get("label") is not None
    ]


def _index_nodes(
    graph: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[GraphError]]:
    """Each node by its id, in the order ids are first listed, holding a repeated id's last copy."""
    nodes: dict[str, Mapping[str, Any]] = {}
    errors: list[GraphError] = []
    for node in graph.get("nodes", []):
        if node["id"] in nodes:
            errors.append(GraphError("duplicate_node", node["id"]))
        nodes[node["id"]] = node
    return nodes, errors


@dataclass(frozen=True)
class _Resolved:
    specs: dict[str, BlockSpec] = field(default_factory=dict)
    configs: dict[str, BlockConfig] = field(default_factory=dict)
    errors: list[GraphError] = field(default_factory=list)


def _resolve(nodes: Mapping[str, Mapping[str, Any]]) -> _Resolved:
    """Each node's block, version and configuration, or its node-level error, in node order."""
    resolved = _Resolved()
    for name, node in nodes.items():
        versions = BLOCKS.get(node["block"])
        if versions is None:
            resolved.errors.append(GraphError("unknown_block", name))
            continue
        spec = versions.get(node["version"])
        if spec is None:
            resolved.errors.append(GraphError("unknown_block_version", name))
            continue
        resolved.specs[name] = spec
        config = block_config(node)
        if isinstance(config, GraphError):
            resolved.errors.append(config)
        else:
            resolved.configs[name] = config
    return resolved


def _feeds(
    graph: Mapping[str, Any], nodes: Mapping[str, object], specs: Mapping[str, BlockSpec]
) -> dict[str, tuple[str, str]]:
    """What feeds each node's `value` input, for reading a type through pass-through steps."""
    return {
        link["target"]: (link["source"], link["source_port"])
        for link in graph.get("links", [])
        if link["target_port"] == "value"
        and link["source"] in nodes
        and link["target"] in nodes
        and link["source_port"] in specs[link["source"]].outputs
    }


@dataclass(frozen=True)
class _Wiring:
    errors: list[GraphError] = field(default_factory=list)
    linked: defaultdict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    successors: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def _wire(graph: Mapping[str, Any], types: _Types) -> _Wiring:
    """Each link's endpoints, ports and types, in link order."""
    wiring = _Wiring()
    nodes, specs = types.nodes, types.specs
    for link in graph.get("links", []):
        source, target = link["source"], link["target"]
        if source not in nodes or target not in nodes:
            wiring.errors.append(
                GraphError("unknown_node", source if source not in nodes else target)
            )
            continue
        if link["source_port"] not in specs[source].outputs:
            wiring.errors.append(GraphError("unknown_port", source, link["source_port"]))
            continue
        if link["target_port"] not in specs[target].inputs:
            wiring.errors.append(GraphError("unknown_port", target, link["target_port"]))
            continue
        kind = types.of(source, link["source_port"])
        if not _compatible(kind, specs[target].inputs[link["target_port"]]):
            wiring.errors.append(GraphError("link_type_mismatch", target, link["target_port"]))
        wiring.linked[(target, link["target_port"])] += 1
        wiring.successors[source].add(target)
    return wiring


def _arity_errors(
    linked: Mapping[tuple[str, str], int], specs: Mapping[str, BlockSpec]
) -> list[GraphError]:
    """Inputs linked more than they take, then required inputs left unlinked, by node and port."""
    errors = [
        GraphError("input_linked_twice", target, port)
        for (target, port), count in linked.items()
        if count > 1 and port not in specs[target].many_inputs
    ]
    for name, spec in specs.items():
        errors.extend(
            GraphError("required_input_unlinked", name, port)
            for port in sorted(spec.required)
            if (name, port) not in linked
        )
    return errors


def _presence_errors(nodes: Mapping[str, Mapping[str, Any]]) -> list[GraphError]:
    blocks = {node["block"] for node in nodes.values()}
    return [
        GraphError(code)
        for block, code in ((Block.OUTPUT, "output_required"), (Block.INPUT, "input_required"))
        if block not in blocks
    ]


def validate_graph(graph: Mapping[str, Any]) -> list[GraphError]:
    """Typed errors, all at once where they can be found. An empty list means publishable.

    Each phase runs only when the ones before it found nothing, and reports in a fixed order, which
    the editor shows as returned (tests/test_workflow_validation_order.py, PDOM-10)."""
    version = graph.get("ir_version", 1)
    if version not in IR_VERSIONS:
        return [GraphError("unknown_ir_version")]
    nodes, duplicates = _index_nodes(graph)
    resolved = _resolve(nodes)
    errors = [*_label_errors(graph, version), *duplicates, *resolved.errors]
    if errors:
        return errors
    types = _Types(nodes, resolved.specs, resolved.configs, _feeds(graph, nodes, resolved.specs))
    wiring = _wire(graph, types)
    errors = [
        *wiring.errors,
        *_arity_errors(wiring.linked, resolved.specs),
        *_presence_errors(nodes),
    ]
    if errors:
        return errors
    if topological_order(list(nodes), wiring.successors)[1]:
        return [GraphError("cycle_not_supported")]
    return _iteration_errors(nodes, wiring.successors)


def step_order(graph: Mapping[str, Any]) -> list[str]:
    """Node IDs in the order the graph runs them: each after everything that feeds it, and ties
    in the order the nodes are listed. A node in an unsupported cycle keeps its listed place."""
    names = [node["id"] for node in graph.get("nodes", [])]
    known = set(names)
    successors: dict[str, list[str]] = defaultdict(list)
    for link in graph.get("links", []):
        if link.get("source") in known and link.get("target") in known:
            successors[link["source"]].append(link["target"])
    ordered, unordered = topological_order(names, successors)
    return ordered + unordered


def agent_expert_of(node: Mapping[str, Any]) -> str | None:
    """The Expert an agent step names, or None for any other step, or one that names none. Only an
    agent step's configuration is read, so another step's draft value can't fail a preview."""
    if node["block"] != Block.AGENT:
        return None
    config = block_config(node)
    return config.expert_id if isinstance(config, AgentConfig) else None


def agent_expert_ids(graph: Mapping[str, Any]) -> list[str]:
    """The Experts a graph's agent steps name, in step order, once for each step (PPRD-10)."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    named = (agent_expert_of(nodes[name]) for name in step_order(graph))
    return [expert_id for expert_id in named if expert_id is not None]


def needs_model(graph: Mapping[str, Any]) -> bool:
    """Only an agent step calls a model, so a graph with none runs with no provider key."""
    return any(node["block"] == Block.AGENT for node in graph["nodes"])


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
        if node["block"] == Block.INPUT
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
