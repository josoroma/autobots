"""Inputs and outputs of the run file tools, US-14.9 and PRD-Tool-Catalog "File tools". Text only;
content never becomes a public field."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import MAX_FILE_CHARACTERS, TOOL_CONTRACT
from autobots.contracts.tool_fields import GuardedUrl, OutputPath, RunFilePath

TextMediaType = Literal["text/plain", "text/markdown", "application/json", "text/csv"]


class ReadRunFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: RunFilePath


class ReadRunFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    content: str
    sha256: str


class ReadRunFileV2Input(BaseModel):
    model_config = TOOL_CONTRACT

    path: RunFilePath
    offset: int = Field(default=0, ge=0, description="The first line to return, from 0.")
    limit: int | None = Field(
        default=None, ge=1, le=20_000, description="How many lines. Left out, to the end."
    )


class ReadRunFileV2Output(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    media_type: str
    sha256: str
    content: str
    offset: int
    total_lines: int
    truncated: bool


class ReadCsvInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: RunFilePath
    delimiter: Literal[",", ";", "\t", "|"] = ","
    has_header: bool = True
    max_rows: int = Field(default=100, ge=1, le=500)
    columns: list[str] = Field(default_factory=list, max_length=50)


class CsvColumn(BaseModel):
    model_config = TOOL_CONTRACT

    name: str
    inferred_type: Literal["integer", "number", "boolean", "date", "string", "empty"]


class ReadCsvOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    columns: list[CsvColumn]
    rows: list[list[str]]
    row_count: int
    truncated: bool


class SaveArtifactInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: RunFilePath
    content: str = Field(max_length=MAX_FILE_CHARACTERS)
    media_type: Literal["text/plain", "text/markdown", "application/json"] = "text/markdown"


class SaveArtifactOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str


class StoreRemoteFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    url: GuardedUrl
    path: OutputPath


class StoreRemoteFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str
    size_bytes: int
    media_type: TextMediaType
