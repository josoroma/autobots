"""Routine contracts, PRD 10.4. A version states everything a scheduled run gets."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier

VIEW = ConfigDict(extra="forbid", frozen=True)


class RoutineTarget(BaseModel):
    model_config = VIEW

    kind: Literal["expert", "workflow"]
    id: Identifier
    # "draft" is accepted here only to be refused with `draft_not_runnable` (PRD-Studio WF-02).
    version: Annotated[int, Field(ge=1)] | Literal["draft"]


class RoutineConfig(BaseModel):
    model_config = VIEW

    target: RoutineTarget
    trigger: dict[str, Any]
    timezone: str = "America/Costa_Rica"
    goal: str = Field(default="", max_length=20000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] | None = None
    limit_micro_usd: int = Field(default=1_000_000, ge=0)
    # The sources' default. Nothing else is offered yet.
    overlap: Literal["skip"] = "skip"


class RoutineCreate(BaseModel):
    model_config = VIEW

    name: str = Field(min_length=1, max_length=100)
    config: RoutineConfig


class RoutineRevision(BaseModel):
    model_config = VIEW

    expected_version: int = Field(ge=1)
    config: RoutineConfig


class RoutineEnabled(BaseModel):
    model_config = VIEW

    enabled: bool


class OccurrenceView(BaseModel):
    model_config = VIEW

    occurrence_time: str
    routine_version: int
    status: str
    reason: str | None
    run_id: Identifier | None


class RoutineView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    name: str
    enabled: bool
    latest_version: int
    config: RoutineConfig
    occurrences: list[OccurrenceView]


class RoutineList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    routines: list[RoutineView]
