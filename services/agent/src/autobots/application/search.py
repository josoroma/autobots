"""PRD-Studio SR-01: one search over the workspace's runs by goal, and Experts, workflows and
tools by name. Each SQL read names the workspace, so nothing from another workspace can match.
The tool catalog is the same for every workspace on this install."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from autobots.application.tool_catalog import Catalog

PER_KIND = 5


@dataclass(frozen=True)
class Hit:
    kind: str
    id: str
    title: str
    detail: str | None


def _pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def search(
    connection: Any, workspace_id: UUID, query: str, environ: Mapping[str, str], catalog: Catalog
) -> list[Hit]:
    """Up to five of each kind, runs newest first and the rest by name. Tools come from `catalog`,
    the composition edge's (XMOD-01)."""
    pattern = _pattern(query)
    hits: list[Hit] = []
    cursor = await connection.execute(
        "select id, goal_summary, status from public.runs where workspace_id = %s "
        "and goal_summary ilike %s escape '\\' order by created_at desc, id limit %s",
        (workspace_id, pattern, PER_KIND),
    )
    hits += [Hit("run", str(row[0]), str(row[1]), str(row[2])) for row in await cursor.fetchall()]
    for kind, table in (("expert", "public.experts"), ("workflow", "public.workflows")):
        cursor = await connection.execute(
            f"select id, name from {table} where workspace_id = %s "
            "and name ilike %s escape '\\' order by lower(name), id limit %s",
            (workspace_id, pattern, PER_KIND),
        )
        hits += [Hit(kind, str(row[0]), str(row[1]), None) for row in await cursor.fetchall()]
    needle = query.casefold()
    newest: dict[str, Any] = {}
    for item in catalog.descriptors(environ):
        if item.tool_id not in newest or item.version > newest[item.tool_id].version:
            newest[item.tool_id] = item
    tools = sorted(
        (
            item
            for item in newest.values()
            if needle in item.title.casefold() or needle in item.tool_id.casefold()
        ),
        key=lambda item: (item.title.casefold(), item.tool_id),
    )
    hits += [Hit("tool", item.tool_id, item.title, item.tool_id) for item in tools[:PER_KIND]]
    return hits
