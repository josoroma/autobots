"""`append_to_file`, Decision 0040 P1 and P2: text added to the end of a run file as a new version.
Nothing here reaches a database. The lock, concurrent adds and the readback after a crash are in
tests/db/checks/append_to_file_check.py.
"""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.application.tools import APPEND_TO_FILE
from autobots.contracts.file_tools import AppendToFileInput
from autobots.domain.execution import TOOL_VERSIONS
from autobots.domain.tools import EXPERT_TOOLS, GENERAL_TOOLS, LOOP_TOOL_GRANTS
from sql_fakes import Row, RuledConnection

LEASED: tuple[str, list[Row]] = ("for share", [(1,)])
LOCK: tuple[str, list[Row]] = ("pg_advisory_xact_lock", [(None,)])
INSERT: tuple[str, list[Row]] = ("insert into app_private.run_files", [])


def add(content: str, latest: list[Row]) -> tuple[Any, list[tuple[str, Any]]]:
    """One add over a file whose latest version is `latest` (none when empty), and what it wrote."""
    connection = RuledConnection(LEASED, LOCK, ("order by version desc", latest), INSERT)
    scope = ToolScope(uuid4(), uuid4(), 1, {"append_to_file": 1}, ("outputs",))
    context = ToolContext(connection, scope, "operation-1")
    arguments = AppendToFileInput(path="outputs/notes.md", content=content)

    async def call() -> Any:  # noqa: ANN401 - the tool's output, or its refusal's code
        try:
            return await APPEND_TO_FILE.handler(arguments, context)
        except ToolFailed as refused:
            return str(refused)

    output = asyncio.run(call())
    return output, [s for s in connection.statements if "insert into" in s[0]]


def row(content: str, version: int = 3, media_type: str = "text/plain") -> Row:
    return {"version": version, "sha256": "a" * 64, "content": content, "media_type": media_type}


def test_a_missing_file_is_created_as_markdown() -> None:
    output, [(_, written)] = add("# First\n\n", [])
    assert written[2:4] == (1, "# First\n\n") and written[5:] == ("text/markdown", "operation-1")
    assert (output.version, output.characters, output.sha256) == (1, 9, written[4])


def test_an_add_goes_to_the_end_and_keeps_the_files_media_type() -> None:
    output, [(_, written)] = add("second\n", [row("first\n")])
    assert written[2:4] == (4, "first\nsecond\n") and written[5] == "text/plain"
    assert (output.path, output.version, output.characters) == ("outputs/notes.md", 4, 13)


def test_past_the_limit_nothing_is_written() -> None:
    output, written = add("x" * 10, [row("y" * 255_995)])
    assert (output, written) == ("file_too_large", [])


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": "notes.md", "content": "x"},
        {"path": "inputs/notes.md", "content": "x"},
        {"path": "outputs/notes.md", "content": ""},
        {"path": "outputs/notes.md", "content": "x" * 256_001},
    ],
)
def test_only_text_for_a_file_under_outputs(arguments: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AppendToFileInput.model_validate(arguments)


def test_only_an_expert_grants_it_and_its_receipt_is_read_back() -> None:
    assert EXPERT_TOOLS["append_to_file"] == TOOL_VERSIONS["append_to_file"] == 1
    assert "append_to_file" not in GENERAL_TOOLS and "append_to_file" not in LOOP_TOOL_GRANTS
    assert APPEND_TO_FILE.reconcile is not None and APPEND_TO_FILE.safe_to_repeat
    assert APPEND_TO_FILE.resources(AppendToFileInput(path="outputs/a.md", content="x")) == (
        "outputs/a.md",
    )
    assert "content" not in APPEND_TO_FILE.public_input_fields
