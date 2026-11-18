"""The artifact tools. `publish_artifact`: a run publishes one of its own saved files as a verified
private artifact (PRD 9.1, LM-05). `read_artifact`: a run reads a published text artifact of its
workspace, so a workflow's next step can read an earlier step's work (Decision 0034 A1 to A4). Tool
definitions sit apart from the services they call, so the registry composes them without the
services depending on it (Decision 0029 F12, PPRD-15).
"""

import hashlib
from uuid import UUID

from autobots.application.artifacts import ArtifactUnavailable, ObjectStore, publish, read_artifact
from autobots.application.sql import optional_row
from autobots.application.tool_definitions import (
    RuntimeUnbound,
    ToolContext,
    ToolDefinition,
    ToolFailed,
)
from autobots.application.tools import line_page
from autobots.contracts.artifacts import PublishArtifact, PublishedArtifact
from autobots.contracts.file_tools import ReadArtifactInput, ReadArtifactOutput
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import PUBLISH_ARTIFACT_TOOL, READ_ARTIFACT_TOOL, OperationClass
from autobots.persistence.rows import PublishedArtifactRow


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
        row = await optional_row(
            context.connection,
            PublishedArtifactRow,
            "select id, name, sha256, size_bytes from public.artifacts "
            "where operation_id = %s and status = 'published'",
            (context.operation_id,),
        )
        if row is None:
            return None
        return PublishedArtifact(
            artifact_id=str(row.id), name=row.name, sha256=row.sha256, size_bytes=row.size_bytes
        )

    return ToolDefinition(
        tool_id=PUBLISH_ARTIFACT_TOOL,
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


# What `publish_artifact` saves (`_media_type`), and so what `read_artifact` reads
# (Decision 0034 A1).
TEXT_MEDIA_TYPES = frozenset({"text/markdown", "text/plain", "application/json"})


def read_tool(store: ObjectStore | None) -> ToolDefinition:
    """The workspace comes from the run's scope, never from the arguments, and a refusal carries no
    content (Decision 0034 A2). With no store, as the catalog describes it, a call refuses before
    anything is read."""

    async def run(arguments: ReadArtifactInput, context: ToolContext) -> ReadArtifactOutput:
        if store is None:
            raise RuntimeUnbound
        try:
            artifact_id = UUID(arguments.artifact_id)
        except ValueError:
            raise ToolFailed("artifact_not_found") from None
        try:
            name, media_type, stored = await read_artifact(
                context.connection, store, context.scope.workspace_id, artifact_id
            )
        except ArtifactUnavailable as refused:
            raise ToolFailed(refused.code) from None
        if media_type not in TEXT_MEDIA_TYPES:
            raise ToolFailed("artifact_not_text")
        try:
            text = stored.decode()
        except UnicodeDecodeError:
            raise ToolFailed("artifact_not_text") from None
        page = line_page(text, arguments.offset, arguments.limit)
        return ReadArtifactOutput(
            artifact_id=str(artifact_id),
            name=name,
            media_type=media_type,
            sha256=hashlib.sha256(stored).hexdigest(),
            size_bytes=len(stored),
            content=page.content,
            offset=arguments.offset,
            total_lines=page.total_lines,
            truncated=page.truncated,
        )

    return ToolDefinition(
        tool_id=READ_ARTIFACT_TOOL,
        title="Artifact Read",
        group=ToolGroup.FILES,
        public_input_fields=("artifact_id", "offset", "limit"),
        public_output_fields=(
            "artifact_id",
            "name",
            "media_type",
            "sha256",
            "size_bytes",
            "total_lines",
            "truncated",
        ),
        version=1,
        description=(
            "Read a published text artifact of this workspace by its ID, optionally from a line "
            "offset for a number of lines. Says its media type, total lines and whether it was cut."
        ),
        input_model=ReadArtifactInput,
        output_model=ReadArtifactOutput,
        operation_class=OperationClass.READ_ONLY,
        handler=run,
        timeout_seconds=10.0,
        retries=1,
        # No resources: they are run-file paths under the scope's path grant, and an artifact ID
        # isn't one. The workspace scope is the grant here (Decision 0034 A2).
        max_output_bytes=1_000_000,
    )
