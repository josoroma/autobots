"""Code tools over the run's own files, US-14.11 and Decision 0017 C7 and Q8.

Pure Python over `app_private.run_files`: no shell, no binary and no host path. `search_files` takes
the latest version of each file the scope's path grants cover. Writes go under `outputs/` only, as
new versions with an operation ID, like `save_artifact`. A patch is exact string replacement: an
absent `old_string`, or one found more than once without `replace_all`, writes nothing.
"""

import json
from collections.abc import Mapping

from autobots.application import code_search
from autobots.application.bounded import BoundExceeded, ChildFailed, run_module
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolFailed
from autobots.application.tools import write_run_file
from autobots.contracts.code_tools import (
    CodeFileWritten,
    NumberedLine,
    PatchCodeFileInput,
    ReadCodeFileInput,
    ReadCodeFileOutput,
    SearchFilesInput,
    SearchFilesOutput,
    WriteCodeFileInput,
)
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass, path_granted

LINE_CHARACTERS = 2000
# Under the tool's 10 s gateway timeout, so the child is stopped before the gateway gives up.
SEARCH_SECONDS = 8.0


def search(files: Mapping[str, str], arguments: SearchFilesInput) -> SearchFilesOutput:
    """The search in this process, unbounded. Pure, so it is tested without a run."""
    try:
        return code_search.search(files, arguments)
    except code_search.InvalidPattern:
        raise ToolFailed("invalid_pattern") from None


async def bounded_search(
    files: Mapping[str, str], arguments: SearchFilesInput, seconds: float = SEARCH_SECONDS
) -> SearchFilesOutput:
    """The search in a child interpreter that is killed after `seconds` (R-20)."""
    request = {"files": dict(files), "arguments": arguments.model_dump(mode="json")}
    try:
        reply = await run_module(code_search.__name__, json.dumps(request).encode("utf-8"), seconds)
        answer = json.loads(reply)
    except BoundExceeded:
        raise ToolFailed("search_timeout") from None
    except (ChildFailed, ValueError):
        # A read-only search that ended without an answer had no effect.
        raise ToolFailed("search_failed") from None
    if answer.get("error") == "invalid_pattern":
        raise ToolFailed("invalid_pattern")
    return SearchFilesOutput.model_validate(answer["output"])


async def _latest_files(context: ToolContext) -> dict[str, str]:
    cursor = await context.connection.execute(
        "select distinct on (path) path, content from app_private.run_files "
        "where run_id = %s order by path, version desc",
        (context.scope.run_id,),
    )
    return {
        path: content
        for path, content in await cursor.fetchall()
        if path_granted(path, context.scope.paths)
    }


async def _search(arguments: SearchFilesInput, context: ToolContext) -> SearchFilesOutput:
    files = await _latest_files(context)
    # A pattern holds the interpreter lock while it matches, so a thread can't be stopped and the
    # event loop would stall with it. A child process is stopped on time (R-20, PTOL-01).
    return await bounded_search(files, arguments)


async def _latest(context: ToolContext, path: str) -> tuple[int, str]:
    cursor = await context.connection.execute(
        "select version, content from app_private.run_files where run_id = %s and path = %s "
        "order by version desc limit 1",
        (context.scope.run_id, path),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ToolFailed("file_not_found")
    return row[0], row[1]


async def _read(arguments: ReadCodeFileInput, context: ToolContext) -> ReadCodeFileOutput:
    version, content = await _latest(context, arguments.path)
    lines = content.splitlines()
    end = arguments.offset + arguments.limit
    return ReadCodeFileOutput(
        path=arguments.path,
        version=version,
        lines=[
            NumberedLine(number=index + 1, text=code_search.cut(lines[index], LINE_CHARACTERS))
            for index in range(arguments.offset, min(end, len(lines)))
        ],
        total_lines=len(lines),
        truncated=end < len(lines)
        or any(len(line) > LINE_CHARACTERS for line in lines[arguments.offset : end]),
    )


async def _write(arguments: WriteCodeFileInput, context: ToolContext) -> CodeFileWritten:
    version, digest = await write_run_file(context, arguments.path, arguments.content, "text/plain")
    return CodeFileWritten(path=arguments.path, version=version, sha256=digest)


async def _patch(arguments: PatchCodeFileInput, context: ToolContext) -> CodeFileWritten:
    _, content = await _latest(context, arguments.path)
    count = content.count(arguments.old_string)
    if count == 0:
        raise ToolFailed("old_string_not_found")
    if count > 1 and not arguments.replace_all:
        raise ToolFailed("old_string_ambiguous")
    patched = content.replace(
        arguments.old_string, arguments.new_string, -1 if arguments.replace_all else 1
    )
    version, digest = await write_run_file(context, arguments.path, patched, "text/plain")
    return CodeFileWritten(
        path=arguments.path,
        version=version,
        sha256=digest,
        replacements=count if arguments.replace_all else 1,
    )


async def _written(
    arguments: WriteCodeFileInput | PatchCodeFileInput, context: ToolContext
) -> CodeFileWritten | None:
    """A crash after the write committed: the row under this operation ID says so."""
    cursor = await context.connection.execute(
        "select version, sha256 from app_private.run_files where operation_id = %s",
        (context.operation_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return CodeFileWritten(path=arguments.path, version=row[0], sha256=row[1])


SEARCH_FILES = ToolDefinition(
    tool_id="search_files",
    version=1,
    title="Search files",
    description=(
        "Search this run's files by regular expression: lines with optional context, matching "
        "files, or a count, with paging. Use it instead of a terminal search; there is no shell."
    ),
    input_model=SearchFilesInput,
    output_model=SearchFilesOutput,
    operation_class=OperationClass.READ_ONLY,
    handler=_search,
    timeout_seconds=10.0,
    max_output_bytes=600_000,
    group=ToolGroup.CODE,
    public_input_fields=(
        "pattern",
        "target",
        "path",
        "file_glob",
        "output_mode",
        "limit",
        "offset",
    ),
    public_output_fields=("total_count", "truncated"),
)
READ_CODE_FILE = ToolDefinition(
    tool_id="read_code_file",
    version=1,
    title="Read file",
    description="Read a file of this run as numbered lines, from a line offset, with paging.",
    input_model=ReadCodeFileInput,
    output_model=ReadCodeFileOutput,
    operation_class=OperationClass.READ_ONLY,
    handler=_read,
    timeout_seconds=5.0,
    retries=1,
    max_output_bytes=1_000_000,
    resources=lambda arguments: (arguments.path,),
    group=ToolGroup.CODE,
    public_input_fields=("path", "offset", "limit"),
    public_output_fields=("path", "version", "total_lines", "truncated"),
)
WRITE_CODE_FILE = ToolDefinition(
    tool_id="write_code_file",
    version=1,
    title="Write file",
    description="Write a file under outputs/ as a new version.",
    input_model=WriteCodeFileInput,
    output_model=CodeFileWritten,
    operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
    handler=_write,
    timeout_seconds=5.0,
    resources=lambda arguments: (arguments.path,),
    reconcile=_written,
    safe_to_repeat=True,
    group=ToolGroup.CODE,
    public_input_fields=("path",),
    public_output_fields=("path", "version", "sha256"),
)
PATCH_CODE_FILE = ToolDefinition(
    tool_id="patch_code_file",
    version=1,
    title="Patch file",
    description=(
        "Replace an exact string in a file under outputs/, once, or everywhere with replace_all. "
        "A string that isn't there, or is there more than once without replace_all, changes "
        "nothing."
    ),
    input_model=PatchCodeFileInput,
    output_model=CodeFileWritten,
    operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
    handler=_patch,
    timeout_seconds=5.0,
    resources=lambda arguments: (arguments.path,),
    reconcile=_written,
    safe_to_repeat=True,
    group=ToolGroup.CODE,
    public_input_fields=("path", "replace_all"),
    public_output_fields=("path", "version", "sha256", "replacements"),
)
CODE_TOOLS = (SEARCH_FILES, READ_CODE_FILE, WRITE_CODE_FILE, PATCH_CODE_FILE)
