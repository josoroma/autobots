"""The catalog, derived from the registry the worker runs, PRD-Tool-Catalog TC-01 to TC-05.

Discovery never grants: this view lists every tool, and only a run's scope decides what it may call.
Availability is computed per request from configuration and never stored. The registry comes from
the composition edge (adapters/tool_registry.py), as a parameter, so this module builds none and
needs no stand-in resources (XMOD-01, PTOL-08).
"""

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from autobots.application.tool_definitions import ToolDefinition, ToolRegistry
from autobots.contracts.tools import (
    FieldDescriptor,
    GrantSiteName,
    KeyRequirementView,
    ToolCatalog,
    ToolDescriptor,
    ToolGroupDescriptor,
    ToolGuideView,
    ToolLimits,
)
from autobots.domain.errors import FixedRefusal
from autobots.domain.tool_catalog import (
    GROUP_TITLES,
    PLANNED_TOOLS,
    SIDE_EFFECTS,
    KeyRequirement,
    PlannedTool,
    ToolAvailability,
    grant_sites,
    key_availability,
)
from autobots.domain.tool_guides import TOOL_GUIDES
from autobots.domain.tools import WORKFLOW_TOOLS

_SCHEMA_KEYS = (
    "enum",
    "const",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "default",
)


def _type(schema: Mapping[str, Any], definitions: Mapping[str, Any]) -> str:
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " | ".join(_type(option, definitions) for option in schema["anyOf"])
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    kind = schema.get("type", "any")
    if kind == "array":
        return f"{_type(schema.get('items', {}), definitions)}[]"
    return str(kind)


def _fields(
    schema: Mapping[str, Any], direction: str, public: tuple[str, ...]
) -> list[FieldDescriptor]:
    """Top-level fields, then one level into nested objects, so a screen can show every input."""
    definitions = schema.get("$defs", {})
    fields: list[FieldDescriptor] = []

    def walk(node: Mapping[str, Any], prefix: str, top: str | None, depth: int) -> None:
        required = set(node.get("required", ()))
        for name, value in node.get("properties", {}).items():
            path = f"{prefix}{name}"
            root = top or name
            fields.append(
                FieldDescriptor(
                    path=path,
                    direction=direction,  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal
                    type=_type(value, definitions),
                    required=name in required,
                    description=value.get("description"),
                    constraints={key: value[key] for key in _SCHEMA_KEYS if key in value},
                    public=root in public,
                )
            )
            target = value.get("items", value) if value.get("type") == "array" else value
            if "$ref" in target and depth < 2:
                nested = definitions.get(str(target["$ref"]).rsplit("/", 1)[-1], {})
                suffix = "[]." if value.get("type") == "array" else "."
                walk(nested, f"{path}{suffix}", root, depth + 1)

    walk(schema, "", None, 0)
    return fields


def _key_source(
    requirement: KeyRequirement, environ: Mapping[str, str]
) -> Literal["settings", "environment"]:
    """`settings` when the workspace saved the key (PK-04). A `KeySources` view says so, and
    a plain environment means the key is in the environment."""
    sources = getattr(environ, "sources", {})
    found = {sources.get(variable, "environment") for variable in requirement.variables}
    return "settings" if "settings" in found else "environment"


class MissingGuide(LookupError):
    """TG-01: every tool needs a guide. Raised with the tool's id, so a test names it."""


NOT_DESCRIBED = "Not described yet."


def has_guide(tool_id: str) -> bool:
    found = TOOL_GUIDES.get(tool_id)
    return found is not None and all(text.strip() for text in (found.what, found.when, found.why))


def require_guides(tool_ids: Iterable[str]) -> None:
    """TG-01's test: raises naming the first tool without a full guide."""
    for tool_id in tool_ids:
        if not has_guide(tool_id):
            raise MissingGuide(tool_id)


def guide_for(tool_id: str) -> ToolGuideView:
    """A shipped tool always has one, by the test above. A test fixture's tool reads as not yet
    described, so a fixture never breaks the catalog it is checked through."""
    if not has_guide(tool_id):
        return ToolGuideView(what=NOT_DESCRIBED, when=NOT_DESCRIBED, why=NOT_DESCRIBED)
    found = TOOL_GUIDES[tool_id]
    return ToolGuideView(what=found.what, when=found.when, why=found.why)


def describe(tool: ToolDefinition, environ: Mapping[str, str]) -> ToolDescriptor:
    input_schema = tool.input_model.model_json_schema()
    output_schema = tool.output_model.model_json_schema()
    availability, reason = key_availability(tool.key_requirement, environ)
    requirement = tool.key_requirement
    return ToolDescriptor(
        tool_id=tool.tool_id,
        guide=guide_for(tool.tool_id),
        version=tool.version,
        title=tool.title or tool.tool_id,
        description=tool.description,
        group=tool.group.value,
        provider=tool.provider.value,
        operation_class=tool.operation_class.value,
        side_effects=SIDE_EFFECTS[tool.operation_class].value,
        network=tool.network,
        cost_class=tool.cost_class.value,
        cost_note=tool.cost_note,
        key_requirement=(
            KeyRequirementView(
                credential=requirement.credential,
                variables=list(requirement.variables),
                scopes=list(requirement.scopes),
                source=(
                    _key_source(requirement, environ)
                    if availability is ToolAvailability.AVAILABLE
                    else None
                ),
            )
            if requirement
            else None
        ),
        # The gateway's own rule, so the label can't disagree with what it holds (PTOL-04).
        approval=tool.approval.label(tool.operation_class),
        input_schema=input_schema,
        output_schema=output_schema,
        fields=[
            *_fields(input_schema, "input", tool.public_input_fields),
            *_fields(output_schema, "output", tool.public_output_fields),
        ],
        limits=ToolLimits(
            timeout_seconds=float(tool.timeout_seconds),
            retries=tool.retries,
            max_output_bytes=tool.max_output_bytes,
        ),
        grantable_to=cast(list[GrantSiteName], grant_sites(tool.tool_id, WORKFLOW_TOOLS)),
        registered=True,
        availability=availability.value,
        availability_reason=reason,
    )


def describe_planned(tool: PlannedTool) -> ToolDescriptor:
    empty: dict[str, Any] = {"type": "object", "properties": {}}
    return ToolDescriptor(
        tool_id=tool.tool_id,
        guide=guide_for(tool.tool_id),
        version=tool.version,
        title=tool.title,
        description=tool.description,
        group=tool.group.value,
        provider=tool.provider.value,
        operation_class=tool.operation_class.value,
        side_effects=SIDE_EFFECTS[tool.operation_class].value,
        network=True,
        cost_class="free_local",
        cost_note=None,
        key_requirement=None,
        approval="always",
        input_schema=empty,
        output_schema=empty,
        fields=[],
        limits=None,
        grantable_to=[],
        registered=False,
        availability=ToolAvailability.DISABLED_BY_POLICY.value,
        availability_reason=tool.reason,
    )


def all_descriptors(registry: ToolRegistry, environ: Mapping[str, str]) -> list[ToolDescriptor]:
    described = [describe(tool, environ) for tool in registry.definitions()]
    registered = {item.tool_id for item in described}
    described += [
        describe_planned(tool) for tool in PLANNED_TOOLS if tool.tool_id not in registered
    ]
    return sorted(described, key=lambda item: (item.tool_id, item.version))


def catalog_digest(descriptors: list[ToolDescriptor]) -> str:
    """Identifies the catalog itself, so availability and a key's source, which vary per install
    and workspace (PK-04), are left out."""
    left_out: Any = {
        "availability": True,
        "availability_reason": True,
        "key_requirement": {"source": True},
    }
    stable = [item.model_dump(mode="json", exclude=left_out) for item in descriptors]
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def latest(descriptors: list[ToolDescriptor]) -> list[ToolDescriptor]:
    newest: dict[str, ToolDescriptor] = {}
    for item in descriptors:
        if item.tool_id not in newest or item.version > newest[item.tool_id].version:
            newest[item.tool_id] = item
    return [newest[key] for key in sorted(newest)]


def tool_catalog(
    registry: ToolRegistry,
    environ: Mapping[str, str],
    *,
    group: str | None = None,
    availability: str | None = None,
    provider: str | None = None,
) -> ToolCatalog:
    descriptors = all_descriptors(registry, environ)
    digest = catalog_digest(descriptors)
    current = latest(descriptors)
    shown = [
        item
        for item in current
        if (group is None or item.group == group)
        and (availability is None or item.availability == availability)
        and (provider is None or item.provider == provider)
    ]
    groups = [
        ToolGroupDescriptor(
            group=name.value,
            title=title,
            description=text,
            tool_ids=[item.tool_id for item in current if item.group == name.value],
        )
        for name, (title, text) in GROUP_TITLES.items()
        if any(item.group == name.value for item in current)
    ]
    return ToolCatalog(schema_version=1, catalog_digest=digest, groups=groups, tools=shown)


class ToolsUnavailable(FixedRefusal):
    """A grant names a tool this install can't use now. Refused before any run exists (PK-02).
    The tools stay internal detail; a response names none."""

    code = "tool_unavailable"

    def __init__(self, tools: list[str]) -> None:
        super().__init__(", ".join(tools))
        self.tools = tools


@dataclass(frozen=True)
class Catalog:
    """The catalog over the registry the worker runs (TC-01), and what admission and Experts ask
    of it (PK-02). `registry` gives that registry for a workspace's Keys & vars view, so its
    browsing switch decides whether `browse_goal` is listed (Decision 0025 V6). The API and the
    worker take it from the composition edge and pass it in (XMOD-01)."""

    registry: Callable[[Mapping[str, str]], ToolRegistry]

    def descriptors(self, environ: Mapping[str, str]) -> list[ToolDescriptor]:
        return all_descriptors(self.registry(environ), environ)

    def catalog(
        self,
        environ: Mapping[str, str],
        *,
        group: str | None = None,
        availability: str | None = None,
        provider: str | None = None,
    ) -> ToolCatalog:
        return tool_catalog(
            self.registry(environ),
            environ,
            group=group,
            availability=availability,
            provider=provider,
        )

    def expert_groups(self, environ: Mapping[str, str]) -> dict[str, list[str]]:
        """What granting a whole group to an Expert means today: its tools an Expert may name."""
        groups: dict[str, list[str]] = {}
        for item in latest(self.descriptors(environ)):
            if "expert" in item.grantable_to:
                groups.setdefault(item.group, []).append(item.tool_id)
        return groups

    def unavailable(self, tool_ids: Iterable[str], environ: Mapping[str, str]) -> list[str]:
        """Named tools a grant can't use in this install: a missing key or a disabled class."""
        named = set(tool_ids)
        return [
            item.tool_id
            for item in latest(self.descriptors(environ))
            if item.tool_id in named and item.availability != ToolAvailability.AVAILABLE.value
        ]

    def require_available(self, tool_ids: Iterable[str], environ: Mapping[str, str]) -> None:
        """Raises ToolsUnavailable naming the tools `unavailable` finds."""
        missing = self.unavailable(tool_ids, environ)
        if missing:
            raise ToolsUnavailable(missing)
