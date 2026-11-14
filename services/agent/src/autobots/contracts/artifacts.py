"""Artifact tool and API contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier
from autobots.contracts.tools import TOOL_CONTRACT


class PublishArtifact(BaseModel):
    """The version makes the operation identity follow the content, not only the path."""

    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    version: int = Field(ge=1)


class PublishedArtifact(BaseModel):
    model_config = TOOL_CONTRACT

    artifact_id: str
    name: str
    sha256: str
    size_bytes: int


class ArtifactSummary(BaseModel):
    """It never holds a storage path."""

    # Not strict, since it is built from database values.

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Identifier
    run_id: Identifier
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: Literal["published", "missing"]


class ArtifactList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    artifacts: list[ArtifactSummary]
