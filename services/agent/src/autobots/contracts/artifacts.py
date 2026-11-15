"""Artifact tool and API contracts."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import LAX_CONTRACT, TOOL_CONTRACT, Identifier
from autobots.contracts.tool_fields import RunFilePath


class PublishArtifact(BaseModel):
    """The version makes the operation identity follow the content, not only the path."""

    model_config = TOOL_CONTRACT

    path: RunFilePath
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

    model_config = LAX_CONTRACT

    id: Identifier
    run_id: Identifier
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: Literal["published", "missing"]


class ArtifactList(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    artifacts: list[ArtifactSummary]
