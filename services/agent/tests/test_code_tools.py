"""US-14.11: the code tools' search over files, and their names, without a database."""

import pytest

from autobots.application.code_tools import CODE_TOOLS, search
from autobots.application.tool_gateway import ToolFailed
from autobots.contracts.code_tools import SearchFilesInput

FILES = {
    "inputs/app.py": "import os\n\ndef main():\n    return os.getcwd()\n",
    "inputs/util.py": "def helper():\n    return 1\n# main is elsewhere\n",
    "outputs/notes.md": "main points\n" + "x" * 900 + " main\n",
}


def run(**arguments: object) -> object:
    return search(FILES, SearchFilesInput.model_validate(arguments))


def test_content_matches_with_context_from_run_files_only() -> None:
    found = run(pattern=r"def \w+", context=1)
    assert [(m.path, m.line_number, m.content) for m in found.matches] == [  # type: ignore[attr-defined]
        ("inputs/app.py", 3, "def main():"),
        ("inputs/util.py", 1, "def helper():"),
    ]
    first = found.matches[0]  # type: ignore[attr-defined]
    assert (first.before, first.after) == ([""], ["    return os.getcwd()"])


def test_prefix_glob_modes_paging_and_caps() -> None:
    assert run(pattern="main", path="inputs/", output_mode="count").total_count == 2  # type: ignore[attr-defined]
    only = run(pattern="main", output_mode="files_only")
    assert only.files == ["inputs/app.py", "inputs/util.py", "outputs/notes.md"]  # type: ignore[attr-defined]
    assert run(pattern="main", file_glob="*.md").total_count == 2  # type: ignore[attr-defined]
    page = run(pattern="main", limit=2, offset=1)
    assert len(page.matches) == 2 and page.total_count == 4 and page.truncated is True  # type: ignore[attr-defined]
    first = run(pattern="main", limit=1)
    assert first.truncated is True  # type: ignore[attr-defined]
    long_line = [m for m in run(pattern="x{10}").matches]  # type: ignore[attr-defined]
    assert len(long_line[0].content) == 500
    named = run(pattern=r"util", target="files")
    assert named.files == ["inputs/util.py"]  # type: ignore[attr-defined]


def test_an_uncompilable_pattern_is_invalid_pattern() -> None:
    with pytest.raises(ToolFailed) as failed:
        run(pattern="(unclosed")
    assert str(failed.value) == "invalid_pattern"


def test_names_never_match_the_sdks_file_tools() -> None:
    sdk = {"read_file", "write_file", "edit_file", "grep", "glob", "ls", "execute"}
    assert not sdk & {tool.tool_id for tool in CODE_TOOLS}


@pytest.mark.parametrize(
    "arguments",
    [
        {"pattern": ""},
        {"pattern": "a", "context": 6},
        {"pattern": "a", "limit": 201},
        {"pattern": "a" * 201},
    ],
)
def test_ceilings_are_in_the_schema(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SearchFilesInput.model_validate(arguments)
