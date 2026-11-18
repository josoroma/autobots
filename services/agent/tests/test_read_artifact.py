"""`read_artifact`: a published text artifact of the run's workspace, read by its ID in pages of
lines (Decision 0034 A1 to A4, PRD-Tool-Catalog FI-02). The SQL and the object store are checked on
a disposable database (tests/db/checks/artifact_check.py)."""

import hashlib
from uuid import UUID, uuid4

import pytest

from autobots.adapters.tool_registry import catalog, tool_definitions
from autobots.application import artifact_tool
from autobots.application.artifacts import ArtifactUnavailable
from autobots.application.tool_definitions import RuntimeUnbound, ToolContext, ToolFailed, ToolScope
from autobots.application.tool_uses import is_metered
from autobots.contracts.file_tools import ReadArtifactInput, ReadArtifactOutput
from autobots.domain.tools import EXPERT_TOOLS, LOOP_TOOL_GRANTS, OperationClass

WORKSPACE = UUID("00000000-0000-4000-8000-000000000001")
ARTIFACT = "00000000-0000-4000-8000-0000000000aa"
DOCUMENT = b"# Deep agents\n\nLine two [S-01]\nLine three\n"
Stored = tuple[str, str, bytes]


class Reader:
    """A stand-in for `artifacts.read_artifact` that records where it looked."""

    def __init__(self, answer: Stored | ArtifactUnavailable) -> None:
        self.answer = answer
        self.seen: list[tuple[UUID, UUID]] = []

    async def __call__(
        self, _connection: object, _store: object, workspace: UUID, artifact: UUID
    ) -> Stored:
        self.seen.append((workspace, artifact))
        if isinstance(self.answer, ArtifactUnavailable):
            raise self.answer
        return self.answer


def context() -> ToolContext:
    scope = ToolScope(WORKSPACE, uuid4(), 1, {"read_artifact": 1})
    # The reader is replaced, so nothing touches the connection.
    return ToolContext(connection=object(), scope=scope, operation_id=None)  # type: ignore[arg-type]  # see above


async def read(
    monkeypatch: pytest.MonkeyPatch,
    reader: Reader,
    arguments: ReadArtifactInput,
    store: object | None = None,
) -> ReadArtifactOutput:
    monkeypatch.setattr(artifact_tool, "read_artifact", reader)
    tool = artifact_tool.read_tool(object() if store is None else store)  # type: ignore[arg-type]  # the store is only passed through
    result = await tool.handler(arguments, context())
    assert isinstance(result, ReadArtifactOutput)
    return result


@pytest.mark.asyncio
async def test_a_published_markdown_artifact_is_read_whole_from_the_runs_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = Reader(("content.md", "text/markdown", DOCUMENT))
    result = await read(monkeypatch, reader, ReadArtifactInput(artifact_id=ARTIFACT))
    assert reader.seen == [(WORKSPACE, UUID(ARTIFACT))]
    assert (result.artifact_id, result.name, result.media_type) == (
        ARTIFACT,
        "content.md",
        "text/markdown",
    )
    assert (result.sha256, result.size_bytes) == (
        hashlib.sha256(DOCUMENT).hexdigest(),
        len(DOCUMENT),
    )
    assert (result.content, result.offset, result.total_lines, result.truncated) == (
        DOCUMENT.decode(),
        0,
        4,
        False,
    )


@pytest.mark.asyncio
async def test_it_pages_by_lines_as_read_run_file_does(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = Reader(("c.md", "text/markdown", DOCUMENT))
    arguments = ReadArtifactInput(artifact_id=ARTIFACT, offset=2, limit=1)
    result = await read(monkeypatch, reader, arguments)
    assert (result.content, result.offset, result.total_lines, result.truncated) == (
        "Line two [S-01]\n",
        2,
        4,
        True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (ArtifactUnavailable("artifact_not_found"), "artifact_not_found"),
        (ArtifactUnavailable("artifact_missing"), "artifact_missing"),
        (("shot.png", "image/png", b"\x89PNG"), "artifact_not_text"),
        (("data.json", "application/json", b"\xff\xfe"), "artifact_not_text"),
    ],
    ids=["not_found", "missing", "image", "undecodable"],
)
async def test_each_refusal_has_its_code_and_no_content(
    monkeypatch: pytest.MonkeyPatch, answer: Stored | ArtifactUnavailable, code: str
) -> None:
    with pytest.raises(ToolFailed) as refused:
        await read(monkeypatch, Reader(answer), ReadArtifactInput(artifact_id=ARTIFACT))
    assert str(refused.value) == code


@pytest.mark.asyncio
async def test_an_id_that_isnt_one_is_not_found_without_a_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = Reader(("x.md", "text/markdown", b"x"))
    with pytest.raises(ToolFailed, match="artifact_not_found"):
        await read(monkeypatch, reader, ReadArtifactInput(artifact_id="z" * 36))
    assert reader.seen == []


@pytest.mark.asyncio
async def test_without_a_store_it_refuses_before_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = Reader(("x.md", "text/markdown", b"x"))
    monkeypatch.setattr(artifact_tool, "read_artifact", reader)
    with pytest.raises(RuntimeUnbound):
        await artifact_tool.read_tool(None).handler(
            ReadArtifactInput(artifact_id=ARTIFACT), context()
        )
    assert reader.seen == []


def test_it_is_an_expert_only_read_only_files_tool() -> None:
    tool = next(item for item in tool_definitions(None) if item.tool_id == "read_artifact")
    assert (tool.version, tool.group, tool.operation_class) == (
        1,
        "files",
        OperationClass.READ_ONLY,
    )
    assert (tool.network, tool.key_requirement, is_metered(tool)) == (False, None, False)
    # An artifact ID isn't a run-file path, so the scope's path grant never refuses it.
    assert tool.resources(ReadArtifactInput(artifact_id=ARTIFACT)) == ()
    assert EXPERT_TOOLS["read_artifact"] == 1
    assert "read_artifact" not in LOOP_TOOL_GRANTS
    described = next(
        item for item in catalog().catalog({}).tools if item.tool_id == "read_artifact"
    )
    assert (described.side_effects, described.approval, described.network) == (
        "none",
        "never",
        False,
    )
    assert described.key_requirement is None
    assert "expert" in described.grantable_to
