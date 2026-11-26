"""A run's files as its tools read and write them, PRD-Tool-Catalog and SP-013: the latest version
of one path or of every path, the version one operation wrote, and a new version under this
attempt's lease. tools.py, code_tools.py and the remote-file adapter go through here, so run-file
storage has one reader and one writer (PTOL-11). The readback by operation ID is the proof that a
write committed; without its row, nothing was saved.
"""

import hashlib
from dataclasses import dataclass

from autobots.application.sql import one, optional_row
from autobots.application.tool_definitions import ToolContext, ToolFailed
from autobots.application.worker_leases import hold_lease
from autobots.persistence.rows import RunFileRow


@dataclass(frozen=True)
class RunFile:
    """One version of a run file."""

    version: int
    sha256: str
    content: str
    media_type: str


_COLUMNS = "version, sha256, content, media_type"


def run_file_of(row: RunFileRow) -> RunFile:
    return RunFile(row.version, row.sha256, row.content, row.media_type)


async def latest(context: ToolContext, path: str) -> RunFile:
    """The latest version of this run's file at `path`, or `file_not_found`."""
    row = await optional_row(
        context.connection,
        RunFileRow,
        f"select {_COLUMNS} from app_private.run_files "
        "where run_id = %s and path = %s order by version desc limit 1",
        (context.scope.run_id, path),
    )
    if row is None:
        raise ToolFailed("file_not_found")
    return run_file_of(row)


async def latest_contents(context: ToolContext) -> dict[str, str]:
    """Each of this run's paths with its latest version's content."""
    cursor = await context.connection.execute(
        "select distinct on (path) path, content from app_private.run_files "
        "where run_id = %s order by path, version desc",
        (context.scope.run_id,),
    )
    return {path: content for path, content in await cursor.fetchall()}


async def by_operation(context: ToolContext) -> RunFile | None:
    """The version this attempt's operation saved through `write`, or None. That write commits
    under a unique operation ID in one transaction, so no row means nothing was saved, and a
    readback can say so without SQL of its own (PADP-13, XMOD-02)."""
    row = await optional_row(
        context.connection,
        RunFileRow,
        f"select {_COLUMNS} from app_private.run_files where operation_id = %s",
        (context.operation_id,),
    )
    return None if row is None else run_file_of(row)


async def _locked(context: ToolContext, path: str) -> None:
    """Inside a write's transaction: the lease, then a lock that serializes writers to this path,
    so two writes can't take one version and an add reads the version it extends."""
    if path.startswith("inputs/"):
        raise ToolFailed("inputs_read_only")
    await hold_lease(context.connection, context.scope)
    await context.connection.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"{context.scope.run_id}|{path}",),
    )


async def write(context: ToolContext, path: str, content: str, media_type: str) -> tuple[int, str]:
    """A new version of a run file under this attempt's operation ID, fenced by the lease. Its
    version and digest. `inputs/` is read-only."""
    async with context.connection.transaction():
        await _locked(context, path)
        (version,) = await one(
            context.connection,
            "select coalesce(max(version), 0) + 1 from app_private.run_files "
            "where run_id = %s and path = %s",
            (context.scope.run_id, path),
        )
        return await _insert(context, path, version, content, media_type)


async def append(context: ToolContext, path: str, content: str, limit: int) -> tuple[RunFile, int]:
    """`content` added to the end of the latest version, as the next one under this attempt's
    operation ID, read and written under one lock (Decision 0040 P1, P2). A missing file starts
    empty, as Markdown. The new version and the length of its whole content. Past `limit`
    characters it is refused `file_too_large`, and nothing is written."""
    async with context.connection.transaction():
        await _locked(context, path)
        row = await optional_row(
            context.connection,
            RunFileRow,
            f"select {_COLUMNS} from app_private.run_files "
            "where run_id = %s and path = %s order by version desc limit 1",
            (context.scope.run_id, path),
        )
        before = RunFile(0, "", "", "text/markdown") if row is None else run_file_of(row)
        whole = before.content + content
        if len(whole) > limit:
            raise ToolFailed("file_too_large")
        version, digest = await _insert(context, path, before.version + 1, whole, before.media_type)
    return RunFile(version, digest, whole, before.media_type), len(whole)


async def _insert(
    context: ToolContext, path: str, version: int, content: str, media_type: str
) -> tuple[int, str]:
    digest = hashlib.sha256(content.encode()).hexdigest()
    await context.connection.execute(
        "insert into app_private.run_files (run_id, path, version, content, sha256, "
        "media_type, operation_id) values (%s, %s, %s, %s, %s, %s, %s)",
        (
            context.scope.run_id,
            path,
            version,
            content,
            digest,
            media_type,
            context.operation_id,
        ),
    )
    return version, digest
