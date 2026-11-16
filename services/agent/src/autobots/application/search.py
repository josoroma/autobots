"""PRD-Studio SR-01: one search over the workspace's runs by goal, and Experts, workflows and
tools by name. Each SQL read names the workspace, so nothing from another workspace can match.
The tool catalog is the same for every workspace on this install."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from autobots.application.sql import SqlConnection, all_rows
from autobots.application.tool_catalog import Catalog, latest
from autobots.contracts.search import SearchKind
from autobots.persistence.rows import RunHitRow

PER_KIND = 5


@dataclass(frozen=True)
class Hit:
    kind: SearchKind
    id: str
    title: str
    detail: str | None


def _pattern(text: str) -> str:
    """`text` matched anywhere by ILIKE, its wildcards and escape character taken literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def search_workspace(
    connection: SqlConnection,
    workspace_id: UUID,
    query: str,
    environ: Mapping[str, str],
    catalog: Catalog,
) -> list[Hit]:
    """Up to five of each kind, runs newest first and the rest by name. Tools come from `catalog`,
    the composition edge's (XMOD-01)."""
    pattern = _pattern(query)
    hits: list[Hit] = []
    runs = await all_rows(
        connection,
        RunHitRow,
        "select id, goal_summary, status from public.runs where workspace_id = %s "
        "and goal_summary ilike %s escape '\\' order by created_at desc, id limit %s",
        (workspace_id, pattern, PER_KIND),
    )
    hits += [Hit("run", str(row.id), str(row.goal_summary), str(row.status)) for row in runs]
    named: tuple[tuple[SearchKind, str], ...] = (
        ("expert", "public.experts"),
        ("workflow", "public.workflows"),
    )
    for kind, table in named:
        cursor = await connection.execute(
            f"select id, name from {table} where workspace_id = %s "
            "and name ilike %s escape '\\' order by lower(name), id limit %s",
            (workspace_id, pattern, PER_KIND),
        )
        hits += [Hit(kind, str(row[0]), str(row[1]), None) for row in await cursor.fetchall()]
    needle = query.casefold()
    # Each tool's newest version, as the catalog lists it (PPRD-18).
    tools = sorted(
        (
            item
            for item in latest(catalog.descriptors(environ))
            if needle in item.title.casefold() or needle in item.tool_id.casefold()
        ),
        key=lambda item: (item.title.casefold(), item.tool_id),
    )
    hits += [Hit("tool", item.tool_id, item.title, item.tool_id) for item in tools[:PER_KIND]]
    return hits
