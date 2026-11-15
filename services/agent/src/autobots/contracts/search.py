"""PRD-Studio SR-01: typed search results within one workspace. Titles are public labels only."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import LAX_CONTRACT

SearchKind = Literal["run", "expert", "workflow", "tool"]


class SearchResult(BaseModel):
    model_config = LAX_CONTRACT

    kind: SearchKind
    id: str = Field(min_length=1, max_length=100)
    title: str
    # A run's state, or a tool's ID. Null for Experts and workflows.
    detail: str | None
    # Where the result opens in the app.
    href: str = Field(pattern=r"^/[a-z]+/[A-Za-z0-9_-]+$")


class SearchResults(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    query: str
    results: list[SearchResult]
