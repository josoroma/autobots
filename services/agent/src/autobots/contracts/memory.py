"""Memory and evidence search, PRD 8.4. Every hit says where it came from."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier
from autobots.contracts.tools import TOOL_CONTRACT

VIEW = ConfigDict(extra="forbid", frozen=True)


class SearchMemory(BaseModel):
    model_config = TOOL_CONTRACT

    query: str = Field(min_length=1, max_length=500)


class SearchHit(BaseModel):
    model_config = VIEW

    kind: Literal["memory", "evidence"]
    title: str
    snippet: str
    source: dict[str, Any]


class SearchResults(BaseModel):
    model_config = VIEW

    hits: list[SearchHit]


class MemorySearchView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    hits: list[SearchHit]


class MemoryCreate(BaseModel):
    model_config = VIEW

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    # Only this Expert's runs can then find it. Without one, the whole workspace's can.
    expert_id: Identifier | None = None


class MemoryCreated(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: str


class ReadOffload(BaseModel):
    model_config = TOOL_CONTRACT

    offload_id: str = Field(min_length=36, max_length=36)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=4000, ge=1, le=4000)


class OffloadContent(BaseModel):
    model_config = TOOL_CONTRACT

    tool_name: str
    content: str
    sha256: str
    total_chars: int
    next_offset: int | None
