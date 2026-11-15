"""Staged publication. A database commit and an upload aren't one operation, SP-013 and LM-05."""

import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol
from uuid import UUID, uuid4

from autobots.application.runs import append_event
from autobots.application.tool_definitions import (
    RuntimeUnbound,
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolScope,
)
from autobots.application.tool_gateway import hold_lease
from autobots.contracts.artifacts import PublishArtifact, PublishedArtifact
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass

MEDIA_TYPES = frozenset({"text/plain", "text/markdown", "application/json"})
MAX_ARTIFACT_BYTES = 1_000_000
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class ObjectStore(Protocol):
    async def put(self, path: str, content: bytes, media_type: str) -> bool: ...
    async def get(self, path: str) -> bytes | None: ...
    async def remove(self, path: str) -> None: ...
    async def names(self, prefix: str) -> list[str]: ...


class ArtifactUnavailable(Refusal):
    """Not this workspace's, not published, gone or altered. The caller gets no bytes."""

    kinds = MappingProxyType({"artifact_not_found": RefusalKind.NOT_FOUND})


def object_path(workspace_id: UUID, run_id: UUID, operation_id: str, name: str) -> str:
    return f"{workspace_id}/{run_id}/{operation_id}-{name}"


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def _publish_row(
    connection: Any, artifact_id: UUID, run_id: UUID, name: str, digest: str
) -> None:
    await connection.execute(
        "update public.artifacts set status = 'published', published_at = now() where id = %s",
        (artifact_id,),
    )
    await append_event(
        connection,
        run_id,
        {
            "type": "artifact.published",
            "artifact_id": str(artifact_id),
            "name": name,
            "sha256": digest,
        },
    )


async def publish(
    connection: Any,
    store: ObjectStore,
    scope: ToolScope,
    *,
    operation_id: str,
    name: str,
    media_type: str,
    content: bytes,
) -> PublishedArtifact:
    """Stage, upload, read back and compare, and only then publish under the current lease."""
    if not _NAME.fullmatch(name):
        raise ToolFailed("artifact_name_invalid")
    if media_type not in MEDIA_TYPES:
        raise ToolFailed("artifact_type_refused")
    if len(content) > MAX_ARTIFACT_BYTES:
        raise ToolFailed("artifact_too_large")
    digest = _digest(content)
    path = object_path(scope.workspace_id, scope.run_id, operation_id, name)
    await connection.execute(
        "insert into public.artifacts (id, workspace_id, run_id, operation_id, name, object_path, "
        "media_type, size_bytes, sha256, status) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'staged') "
        "on conflict (operation_id) do nothing",
        (
            uuid4(),
            scope.workspace_id,
            scope.run_id,
            operation_id,
            name,
            path,
            media_type,
            len(content),
            digest,
        ),
    )
    cursor = await connection.execute(
        "select id, status from public.artifacts where operation_id = %s", (operation_id,)
    )
    artifact_id, status = await cursor.fetchone()
    result = PublishedArtifact(
        artifact_id=str(artifact_id), name=name, sha256=digest, size_bytes=len(content)
    )
    if status == "published":
        return result
    await store.put(path, content, media_type)
    stored = await store.get(path)
    if stored is None or _digest(stored) != digest:
        await connection.execute(
            "update public.artifacts set status = 'failed' where id = %s", (artifact_id,)
        )
        raise ToolFailed("artifact_hash_mismatch")
    async with connection.transaction():
        await hold_lease(connection, scope)
        await _publish_row(connection, artifact_id, scope.run_id, name, digest)
    return result


@dataclass(frozen=True)
class ReconcileReport:
    """What recovery found. Anything in `incomplete` was promised and can't be delivered."""

    published: tuple[str, ...] = ()
    incomplete: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    orphans_removed: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.incomplete and not self.missing


async def _still_owner(connection: Any, owner: ToolScope | None) -> None:
    """A worker's recovery stops at the moment it loses the run. An operator passes no owner."""
    if owner is not None:
        await hold_lease(connection, owner)


async def reconcile_run(
    connection: Any,
    store: ObjectStore,
    workspace_id: UUID,
    run_id: UUID,
    owner: ToolScope | None = None,
) -> ReconcileReport:
    """Compares rows to objects by hash, and assumes nothing about what committed.

    Objects are listed before rows are read. A row commits before its upload starts, so each
    listed object has a visible row, and another worker's fresh upload can't look like an orphan.
    """
    listed = await store.names(f"{workspace_id}/{run_id}")
    cursor = await connection.execute(
        "select id, name, object_path, sha256, status from public.artifacts "
        "where run_id = %s and workspace_id = %s",
        (run_id, workspace_id),
    )
    rows = await cursor.fetchall()
    published: list[str] = []
    incomplete: list[str] = []
    missing: list[str] = []
    for artifact_id, name, path, digest, status in rows:
        if status not in {"staged", "published"}:
            continue
        stored = await store.get(path)
        verified = stored is not None and _digest(stored) == digest
        if status == "staged" and verified:
            async with connection.transaction():
                await _still_owner(connection, owner)
                await _publish_row(connection, artifact_id, run_id, name, digest)
            published.append(name)
        elif status == "staged":
            async with connection.transaction():
                await _still_owner(connection, owner)
                await connection.execute(
                    "update public.artifacts set status = 'failed' where id = %s", (artifact_id,)
                )
            incomplete.append(name)
        elif not verified:
            async with connection.transaction():
                await _still_owner(connection, owner)
                await connection.execute(
                    "update public.artifacts set status = 'missing' where id = %s", (artifact_id,)
                )
                await append_event(
                    connection,
                    run_id,
                    {"type": "artifact.missing", "artifact_id": str(artifact_id), "name": name},
                )
            missing.append(name)
    known = {row[2] for row in rows}
    orphans = [path for path in listed if path not in known]
    for path in orphans:
        await _still_owner(connection, owner)
        await store.remove(path)
    return ReconcileReport(tuple(published), tuple(incomplete), tuple(missing), tuple(orphans))


async def list_artifacts(connection: Any, workspace_id: UUID, run_id: UUID) -> list[dict[str, Any]]:
    cursor = await connection.execute(
        "select id, run_id, name, media_type, size_bytes, sha256, status from public.artifacts "
        "where run_id = %s and workspace_id = %s and status in ('published', 'missing') "
        "order by created_at",
        (run_id, workspace_id),
    )
    names = ("id", "run_id", "name", "media_type", "size_bytes", "sha256", "status")
    return [dict(zip(names, row, strict=True)) for row in await cursor.fetchall()]


async def read_artifact(
    connection: Any, store: ObjectStore, workspace_id: UUID, artifact_id: UUID
) -> tuple[str, str, bytes]:
    """The workspace comes from the row, and bytes are checked against its hash before leaving."""
    cursor = await connection.execute(
        "select name, media_type, object_path, sha256, status from public.artifacts "
        "where id = %s and workspace_id = %s",
        (artifact_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None or row[4] == "staged" or row[4] == "failed":
        raise ArtifactUnavailable("artifact_not_found")
    name, media_type, path, digest, status = row
    if status != "published":
        raise ArtifactUnavailable("artifact_missing")
    stored = await store.get(path)
    if stored is None or _digest(stored) != digest:
        raise ArtifactUnavailable("artifact_missing")
    return name, media_type, stored


def _media_type(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    return "text/markdown" if path.endswith(".md") else "text/plain"


def publish_tool(store: ObjectStore | None) -> ToolDefinition:
    """Bytes come from this run's own saved file, never from arguments the model wrote out again.

    With no store, as the catalog describes it, a call refuses before anything is read or uploaded
    (XMOD-01)."""

    async def run(arguments: PublishArtifact, context: ToolContext) -> PublishedArtifact:
        if store is None:
            raise RuntimeUnbound
        if not arguments.path.startswith("outputs/"):
            raise ToolFailed("artifact_source_not_output")
        cursor = await context.connection.execute(
            "select content from app_private.run_files "
            "where run_id = %s and path = %s and version = %s",
            (context.scope.run_id, arguments.path, arguments.version),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ToolFailed("file_not_found")
        return await publish(
            context.connection,
            store,
            context.scope,
            operation_id=str(context.operation_id),
            name=arguments.path.rsplit("/", 1)[-1],
            media_type=_media_type(arguments.path),
            content=row[0].encode(),
        )

    async def found(arguments: PublishArtifact, context: ToolContext) -> PublishedArtifact | None:
        cursor = await context.connection.execute(
            "select id, name, sha256, size_bytes from public.artifacts "
            "where operation_id = %s and status = 'published'",
            (context.operation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return PublishedArtifact(
            artifact_id=str(row[0]), name=row[1], sha256=row[2], size_bytes=row[3]
        )

    return ToolDefinition(
        tool_id="publish_artifact",
        title="Publish artifact",
        group=ToolGroup.FILES,
        public_input_fields=("path", "version"),
        public_output_fields=("artifact_id", "name", "sha256", "size_bytes"),
        version=1,
        description="Publish a saved file of this run as a verified private artifact.",
        input_model=PublishArtifact,
        output_model=PublishedArtifact,
        operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
        handler=run,
        timeout_seconds=30.0,
        resources=lambda arguments: (arguments.path,),
        reconcile=found,
        safe_to_repeat=True,
    )
