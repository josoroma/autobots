"""The narrow first tool set: a calculation, a read and an artifact save. Nothing else exists."""

import hashlib

from autobots.application.tool_gateway import (
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolRegistry,
    hold_lease,
)
from autobots.contracts.tools import (
    CalculateInput,
    CalculateOutput,
    ReadRunFileInput,
    ReadRunFileOutput,
    SaveArtifactInput,
    SaveArtifactOutput,
)
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass


async def _calculate(arguments: CalculateInput, _: ToolContext) -> CalculateOutput:
    values = arguments.values
    results = {
        "sum": sum(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }
    return CalculateOutput(result=results[arguments.operation])


async def _read(arguments: ReadRunFileInput, context: ToolContext) -> ReadRunFileOutput:
    cursor = await context.connection.execute(
        "select version, content, sha256 from app_private.run_files "
        "where run_id = %s and path = %s order by version desc limit 1",
        (context.scope.run_id, arguments.path),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ToolFailed("file_not_found")
    return ReadRunFileOutput(path=arguments.path, version=row[0], content=row[1], sha256=row[2])


async def _existing_save(
    arguments: SaveArtifactInput, context: ToolContext
) -> SaveArtifactOutput | None:
    cursor = await context.connection.execute(
        "select version, sha256 from app_private.run_files where operation_id = %s",
        (context.operation_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return SaveArtifactOutput(path=arguments.path, version=row[0], sha256=row[1])


async def _save(arguments: SaveArtifactInput, context: ToolContext) -> SaveArtifactOutput:
    if arguments.path.startswith("inputs/"):
        raise ToolFailed("inputs_read_only")
    digest = hashlib.sha256(arguments.content.encode()).hexdigest()
    async with context.connection.transaction():
        await hold_lease(context.connection, context.scope)
        # Serializes writers to this path, so two saves can't take one version.
        await context.connection.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"{context.scope.run_id}|{arguments.path}",),
        )
        cursor = await context.connection.execute(
            "select coalesce(max(version), 0) + 1 from app_private.run_files "
            "where run_id = %s and path = %s",
            (context.scope.run_id, arguments.path),
        )
        version = (await cursor.fetchone())[0]
        await context.connection.execute(
            "insert into app_private.run_files (run_id, path, version, content, sha256, "
            "media_type, operation_id) values (%s, %s, %s, %s, %s, %s, %s)",
            (
                context.scope.run_id,
                arguments.path,
                version,
                arguments.content,
                digest,
                arguments.media_type,
                context.operation_id,
            ),
        )
    return SaveArtifactOutput(path=arguments.path, version=version, sha256=digest)


CALCULATE = ToolDefinition(
    tool_id="calculate",
    title="Calculate",
    group=ToolGroup.GENERAL,
    public_input_fields=("operation",),
    public_output_fields=("result",),
    version=1,
    description="Sum, mean, minimum or maximum of a list of numbers.",
    input_model=CalculateInput,
    output_model=CalculateOutput,
    operation_class=OperationClass.PURE,
    handler=_calculate,
    timeout_seconds=2.0,
    retries=1,
)
READ_RUN_FILE = ToolDefinition(
    tool_id="read_run_file",
    title="File Read",
    group=ToolGroup.FILES,
    public_input_fields=("path",),
    public_output_fields=("path", "version", "sha256"),
    version=1,
    description="Read the latest version of a file belonging to this run.",
    input_model=ReadRunFileInput,
    output_model=ReadRunFileOutput,
    operation_class=OperationClass.READ_ONLY,
    handler=_read,
    timeout_seconds=5.0,
    retries=1,
    resources=lambda arguments: (arguments.path,),
)
SAVE_ARTIFACT = ToolDefinition(
    tool_id="save_artifact",
    title="Save file",
    group=ToolGroup.FILES,
    public_input_fields=("path", "media_type"),
    public_output_fields=("path", "version", "sha256"),
    version=1,
    description="Save a file for this run as a new version.",
    input_model=SaveArtifactInput,
    output_model=SaveArtifactOutput,
    operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
    handler=_save,
    timeout_seconds=5.0,
    resources=lambda arguments: (arguments.path,),
    reconcile=_existing_save,
    # One transaction with a unique operation ID: if the row isn't there, it never happened.
    safe_to_repeat=True,
)


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT):
        registry.register(tool)
    return registry


def first_grants() -> dict[str, int]:
    return {"calculate": 1, "read_run_file": 1, "save_artifact": 1}
