"""Inputs and outputs of the code tools, PRD-Tool-Catalog "Code tools" and Decision 0017 C7 and Q8.

They work on the run's own files only. Their names never match the SDK's own file tools
(`read_file`, `write_file`, `edit_file`, `grep`, `glob`, `ls`), which the middleware hides by name.
"""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.tools import MAX_FILE_CHARACTERS, TOOL_CONTRACT

MATCH_CHARACTERS = 500


class SearchFilesInput(BaseModel):
    model_config = TOOL_CONTRACT

    pattern: str = Field(min_length=1, max_length=200, description="A regular expression.")
    target: Literal["content", "files"] = "content"
    path: str = Field(default="", max_length=500, description="Only paths starting with this.")
    file_glob: str | None = Field(default=None, max_length=100, description="Such as *.py.")
    output_mode: Literal["content", "files_only", "count"] = "content"
    context: int = Field(default=0, ge=0, le=5)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class SearchMatch(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    line_number: int
    content: str
    before: list[str] = Field(default_factory=list)
    after: list[str] = Field(default_factory=list)


class SearchFilesOutput(BaseModel):
    model_config = TOOL_CONTRACT

    matches: list[SearchMatch]
    files: list[str]
    total_count: int
    truncated: bool


class ReadCodeFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    offset: int = Field(default=0, ge=0, description="The first line, from 0.")
    limit: int = Field(default=400, ge=1, le=2000)


class NumberedLine(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    text: str


class ReadCodeFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    lines: list[NumberedLine]
    total_lines: int
    truncated: bool


class WriteCodeFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500, pattern=r"^outputs/")
    content: str = Field(max_length=MAX_FILE_CHARACTERS)


class PatchCodeFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500, pattern=r"^outputs/")
    old_string: str = Field(min_length=1, max_length=MAX_FILE_CHARACTERS)
    new_string: str = Field(max_length=MAX_FILE_CHARACTERS)
    replace_all: bool = False


class CodeFileWritten(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str
    replacements: int | None = None
