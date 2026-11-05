"""Expert, session and routing contracts, PRD 8.2 and 11.2."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier
from autobots.domain.models import ModelProfileId

VIEW = ConfigDict(extra="forbid", frozen=True)


class ExpertConfig(BaseModel):
    """Not strict, so JSON strings become enums. Unknown fields and values are still refused."""

    model_config = VIEW

    purpose: str = Field(default="", max_length=1000)
    instructions: str = Field(default="", max_length=20000)
    tools: list[str] = Field(default_factory=list, max_length=20)
    skills: list[str] = Field(default_factory=list, max_length=50)
    role_bindings: dict[str, ModelProfileId] = Field(default_factory=dict)


class ExpertCreate(BaseModel):
    model_config = VIEW

    name: str = Field(min_length=1, max_length=100)
    config: ExpertConfig


class ExpertRevision(BaseModel):
    model_config = VIEW

    expected_version: int = Field(ge=1)
    config: ExpertConfig


class ExpertVersionView(BaseModel):
    model_config = VIEW

    version: int
    config: ExpertConfig


class ExpertView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    name: str
    latest_version: int
    versions: list[ExpertVersionView]


class ExpertList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    experts: list[ExpertView]


class SessionExpert(BaseModel):
    model_config = VIEW

    expert_id: Identifier
    version: int | None = None


class SessionCreate(BaseModel):
    model_config = VIEW

    kind: Literal["direct", "coordinator"]
    experts: list[SessionExpert] = Field(min_length=1, max_length=20)


class RouteOption(BaseModel):
    """What a user sees before starting work. Nothing beyond this is granted."""

    model_config = VIEW

    expert_id: Identifier
    name: str
    version: int
    purpose: str
    tools: list[str]
    role_bindings: dict[str, str]


class SessionView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    kind: Literal["direct", "coordinator"]
    options: list[RouteOption]
