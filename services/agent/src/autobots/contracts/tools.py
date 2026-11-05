"""Versioned input and output contracts for the narrow tool set."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TOOL_CONTRACT = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
MAX_FILE_CHARACTERS = 256_000


class CalculateInput(BaseModel):
    model_config = TOOL_CONTRACT

    operation: Literal["sum", "mean", "min", "max"]
    values: list[float] = Field(min_length=1, max_length=1000)


class CalculateOutput(BaseModel):
    model_config = TOOL_CONTRACT

    result: float


class ReadRunFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)


class ReadRunFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    content: str
    sha256: str


class SaveArtifactInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=MAX_FILE_CHARACTERS)
    media_type: Literal["text/plain", "text/markdown", "application/json"] = "text/markdown"


class SaveArtifactOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str
