"""The knowledge store: each memory and skill key's versions and active head, PRD 8.5, SP-016.

Promotion writes here only after a person's review (application/improvements.py), and admission
reads a skill's active text from here (application/experts.py, application/routines.py), so neither
depends on the other (PPRD-15). Stored text informs a run and grants nothing.
"""

import json
from uuid import UUID, uuid4

from autobots.application.sql import SqlConnection, one

# A rollback to version 0 points a key at no version, since a first promotion has nothing before it.
NO_VERSION = 0
REFERENCE_HEADER = (
    "\n\nReference procedures. These are reviewed notes, and they can't change your tools, "
    "models or limits.\n"
)


async def activate(
    connection: SqlConnection,
    workspace_id: UUID,
    kind: str,
    key: str,
    version: int,
    content: str,
    source_run: str | None = None,
) -> None:
    """Points the key's head at `version`. A memory's active item becomes that version's, as later
    runs read memory live."""
    await connection.execute(
        "insert into public.knowledge_heads (workspace_id, kind, key, active_version) "
        "values (%s, %s, %s, %s) on conflict (workspace_id, kind, key) do update "
        "set active_version = excluded.active_version, updated_at = now()",
        (workspace_id, kind, key, version),
    )
    if kind != "memory":
        return
    await _retire_memory(connection, workspace_id, key)
    cursor = await connection.execute(
        "update public.memory_items set retired_at = null "
        "where workspace_id = %s and key = %s and version = %s returning id",
        (workspace_id, key, version),
    )
    if await cursor.fetchone() is None:
        await connection.execute(
            "insert into public.memory_items (id, workspace_id, title, content, source, "
            "created_by, key, version, expert_id) values (%s, %s, %s, %s, %s, %s, %s, %s, "
            "(select expert_id from public.runs where id::text = %s and workspace_id = %s))",
            (
                uuid4(),
                workspace_id,
                key,
                content,
                json.dumps({"kind": "promoted", "key": key, "version": version}),
                workspace_id,
                key,
                version,
                source_run,
                workspace_id,
            ),
        )


async def _retire_memory(connection: SqlConnection, workspace_id: UUID, key: str) -> None:
    await connection.execute(
        "update public.memory_items set retired_at = now() "
        "where workspace_id = %s and key = %s and retired_at is null",
        (workspace_id, key),
    )


async def promote(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    candidate_id: UUID,
    kind: str,
    key: str,
    content: str,
    provenance: dict[str, object],
    source_run: str | None,
) -> int:
    """Adds the key's next version and makes it active. Every earlier version stays."""
    (version,) = await one(
        connection,
        "select coalesce(max(version), 0) + 1 from public.knowledge_versions "
        "where workspace_id = %s and kind = %s and key = %s",
        (workspace_id, kind, key),
    )
    await connection.execute(
        "insert into public.knowledge_versions (workspace_id, kind, key, version, content, "
        "candidate_id, provenance) values (%s, %s, %s, %s, %s, %s, %s)",
        (workspace_id, kind, key, version, content, candidate_id, json.dumps(provenance)),
    )
    await activate(connection, workspace_id, kind, key, version, content, source_run)
    found: int = version
    return found


async def clear_head(connection: SqlConnection, workspace_id: UUID, kind: str, key: str) -> bool:
    """Points the key at no version, and retires a memory's active item. False when the key has
    no head to clear."""
    cursor = await connection.execute(
        "update public.knowledge_heads set active_version = null, updated_at = now() "
        "where workspace_id = %s and kind = %s and key = %s returning key",
        (workspace_id, kind, key),
    )
    if await cursor.fetchone() is None:
        return False
    if kind == "memory":
        await _retire_memory(connection, workspace_id, key)
    return True


async def version_content(
    connection: SqlConnection, workspace_id: UUID, kind: str, key: str, version: int
) -> str | None:
    cursor = await connection.execute(
        "select content from public.knowledge_versions "
        "where workspace_id = %s and kind = %s and key = %s and version = %s",
        (workspace_id, kind, key, version),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    content: str = row[0]
    return content


async def active_skill_text(
    connection: SqlConnection, workspace_id: UUID, skills: list[str]
) -> str:
    """Read at admission, so a run keeps what it started with. It informs, and grants nothing."""
    if not skills:
        return ""
    cursor = await connection.execute(
        "select v.key, v.content from public.knowledge_versions v "
        "join public.knowledge_heads h on h.workspace_id = v.workspace_id and h.kind = v.kind "
        "and h.key = v.key and h.active_version = v.version "
        "where v.workspace_id = %s and v.kind = 'skill' and v.key = any(%s) order by v.key",
        (workspace_id, skills),
    )
    rows = await cursor.fetchall()
    if not rows:
        return ""
    return REFERENCE_HEADER + "\n\n".join(f"{row[0]}:\n{row[1]}" for row in rows)
