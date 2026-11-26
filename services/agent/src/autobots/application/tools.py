"""Built-in local tools: a calculation, run-file reads and writes, CSV reads, artifact saves and
adding to a file (Decision 0040).
Each reads and writes run files through run_files.py (PTOL-11)."""

import csv
import io
import re
from dataclasses import dataclass
from typing import Literal

from autobots.application import run_files
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.file_tools import (
    AppendToFileInput,
    AppendToFileOutput,
    CsvColumn,
    ReadCsvInput,
    ReadCsvOutput,
    ReadRunFileInput,
    ReadRunFileOutput,
    ReadRunFileV2Input,
    ReadRunFileV2Output,
    SaveArtifactInput,
    SaveArtifactOutput,
)
from autobots.contracts.primitives import MAX_FILE_CHARACTERS
from autobots.contracts.tools import CalculateInput, CalculateOutput
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
    found = await run_files.latest(context, arguments.path)
    return ReadRunFileOutput(
        path=arguments.path, version=found.version, content=found.content, sha256=found.sha256
    )


async def _existing_save(
    arguments: SaveArtifactInput, context: ToolContext
) -> SaveArtifactOutput | None:
    found = await run_files.by_operation(context)
    if found is None:
        return None
    return SaveArtifactOutput(path=arguments.path, version=found.version, sha256=found.sha256)


async def _save(arguments: SaveArtifactInput, context: ToolContext) -> SaveArtifactOutput:
    version, digest = await run_files.write(
        context, arguments.path, arguments.content, arguments.media_type
    )
    return SaveArtifactOutput(path=arguments.path, version=version, sha256=digest)


# read_run_file version 2 returns at most this many characters, and says when it cut.
READ_CHARACTERS = 200_000


@dataclass(frozen=True)
class LinePage:
    content: str
    total_lines: int
    truncated: bool


def line_page(text: str, offset: int, limit: int | None) -> LinePage:
    """Lines `offset` to `offset + limit` of `text`, at most READ_CHARACTERS of them.
    `read_run_file` version 2 and `read_artifact` page alike (Decision 0034 A1)."""
    lines = text.splitlines(keepends=True)
    end = len(lines) if limit is None else offset + limit
    chosen = "".join(lines[offset:end])
    cut = chosen[:READ_CHARACTERS]
    return LinePage(cut, len(lines), end < len(lines) or len(cut) < len(chosen))


async def _read_v2(arguments: ReadRunFileV2Input, context: ToolContext) -> ReadRunFileV2Output:
    found = await run_files.latest(context, arguments.path)
    page = line_page(found.content, arguments.offset, arguments.limit)
    return ReadRunFileV2Output(
        path=arguments.path,
        version=found.version,
        media_type=found.media_type,
        sha256=found.sha256,
        content=page.content,
        offset=arguments.offset,
        total_lines=page.total_lines,
        truncated=page.truncated,
    )


def _inferred(
    values: list[str],
) -> Literal["integer", "number", "boolean", "date", "string", "empty"]:
    present = [value.strip() for value in values if value.strip()]
    if not present:
        return "empty"
    checks: tuple[tuple[Literal["integer", "number", "boolean", "date"], str], ...] = (
        ("integer", r"[+-]?\d+"),
        ("number", r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?"),
        ("boolean", r"(?i:true|false)"),
        ("date", r"\d{4}-\d{2}-\d{2}"),
    )
    for name, pattern in checks:
        if all(re.fullmatch(pattern, value) for value in present):
            return name
    return "string"


async def _read_csv(arguments: ReadCsvInput, context: ToolContext) -> ReadCsvOutput:
    found = await run_files.latest(context, arguments.path)
    try:
        parsed = list(
            csv.reader(io.StringIO(found.content), delimiter=arguments.delimiter, strict=True)
        )
    except csv.Error:
        raise ToolFailed("csv_malformed") from None
    parsed = [row for row in parsed if row]
    if arguments.has_header and parsed:
        header, data = parsed[0], parsed[1:]
    else:
        width = max((len(row) for row in parsed), default=0)
        header, data = [f"column_{index + 1}" for index in range(width)], parsed
    wanted = arguments.columns or header
    if any(name not in header for name in wanted):
        raise ToolFailed("csv_column_unknown")
    keep = [header.index(name) for name in wanted]
    rows = [[row[index] if index < len(row) else "" for index in keep] for row in data]
    shown = rows[: arguments.max_rows]
    columns = [
        CsvColumn(name=name, inferred_type=_inferred([row[position] for row in rows]))
        for position, name in enumerate(wanted)
    ]
    return ReadCsvOutput(
        path=arguments.path,
        version=found.version,
        columns=columns,
        rows=shown,
        row_count=len(rows),
        truncated=len(rows) > len(shown),
    )


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
READ_RUN_FILE_V2 = ToolDefinition(
    tool_id="read_run_file",
    version=2,
    title="File Read",
    description=(
        "Read a file belonging to this run, optionally from a line offset for a number of lines. "
        "Says its media type, total lines and whether it was cut."
    ),
    input_model=ReadRunFileV2Input,
    output_model=ReadRunFileV2Output,
    operation_class=OperationClass.READ_ONLY,
    handler=_read_v2,
    timeout_seconds=5.0,
    retries=1,
    max_output_bytes=1_000_000,
    resources=lambda arguments: (arguments.path,),
    group=ToolGroup.FILES,
    public_input_fields=("path", "offset", "limit"),
    public_output_fields=("path", "version", "media_type", "sha256", "total_lines", "truncated"),
)
READ_CSV = ToolDefinition(
    tool_id="read_csv",
    version=1,
    title="Read CSV",
    description="Read a CSV file of this run as columns with inferred types and rows, bounded.",
    input_model=ReadCsvInput,
    output_model=ReadCsvOutput,
    operation_class=OperationClass.READ_ONLY,
    handler=_read_csv,
    timeout_seconds=5.0,
    retries=1,
    max_output_bytes=1_000_000,
    resources=lambda arguments: (arguments.path,),
    group=ToolGroup.FILES,
    public_input_fields=("path", "delimiter", "has_header", "max_rows", "columns"),
    public_output_fields=("path", "version", "columns", "row_count", "truncated"),
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


async def _append(arguments: AppendToFileInput, context: ToolContext) -> AppendToFileOutput:
    found, characters = await run_files.append(
        context, arguments.path, arguments.content, MAX_FILE_CHARACTERS
    )
    return AppendToFileOutput(
        path=arguments.path, version=found.version, sha256=found.sha256, characters=characters
    )


async def _existing_append(
    arguments: AppendToFileInput, context: ToolContext
) -> AppendToFileOutput | None:
    """A crash after the add committed: the version under this operation ID says so (P2)."""
    found = await run_files.by_operation(context)
    if found is None:
        return None
    return AppendToFileOutput(
        path=arguments.path,
        version=found.version,
        sha256=found.sha256,
        characters=len(found.content),
    )


APPEND_TO_FILE = ToolDefinition(
    tool_id="append_to_file",
    title="Add to file",
    group=ToolGroup.FILES,
    public_input_fields=("path",),
    public_output_fields=("path", "version", "sha256", "characters"),
    version=1,
    description=(
        "Add text to the end of a file under outputs/ as a new version, creating it if it is "
        "missing. Use it to write a document longer than one reply, a section at a time."
    ),
    input_model=AppendToFileInput,
    output_model=AppendToFileOutput,
    operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
    handler=_append,
    timeout_seconds=5.0,
    resources=lambda arguments: (arguments.path,),
    reconcile=_existing_append,
    # One transaction with a unique operation ID: if the row isn't there, it never happened.
    safe_to_repeat=True,
)


def first_grants() -> dict[str, int]:
    return {"calculate": 1, "read_run_file": 1, "save_artifact": 1}
