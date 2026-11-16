"""The `publish_artifact` tool: a run publishes one of its own saved files as a verified private
artifact (PRD 9.1, LM-05). Tool definitions sit apart from the services they call, so the registry
composes them without the services depending on it (Decision 0029 F12, PPRD-15).
"""

from autobots.application.artifacts import ObjectStore, publish
from autobots.application.sql import optional_row
from autobots.application.tool_definitions import (
    RuntimeUnbound,
    ToolContext,
    ToolDefinition,
    ToolFailed,
)
from autobots.contracts.artifacts import PublishArtifact, PublishedArtifact
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import PUBLISH_ARTIFACT_TOOL, OperationClass
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
