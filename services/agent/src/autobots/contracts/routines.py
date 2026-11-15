"""Routine contracts, PRD 10.4. A version states everything a scheduled run gets.

The Routines API and the `cronjob` tool share one schedule and one timezone (Decision 0026 C5). A
saved version is read back through its stored record (persistence/records.py) and shown as
`RoutineConfigView`, so an older version keeps reading while requests stay strict.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from autobots.contracts.primitives import (
    LAX_CONTRACT,
    TOOL_CONTRACT,
    Flag,
    Identifier,
    MicroUsd,
    UtcTimestamp,
    Version,
)
from autobots.domain.routines import DEFAULT_TIMEZONE, MAX_INTERVAL_MINUTES

# An IANA zone's name. The routine service checks that the zone exists, and refuses one that
# doesn't with `timezone_unknown`, for either caller (Decision 0026 C5).
IanaTimezone = Annotated[str, Field(min_length=1, max_length=64)]
# routine_occurrences.status, as its check constraint allows (tests/test_contract_vocabularies.py).
OccurrenceStatus = Literal["admitted", "missed", "skipped_overlap", "blocked"]
OCCURRENCE_STATUSES: tuple[OccurrenceStatus, ...] = get_args(OccurrenceStatus)


# Named for the tool that introduced it: the name is the title in `cronjob` v1's input schema, which
# must not change (Decision 0026 C1).
class CronjobSchedule(BaseModel):
    """Every `minutes`, or `daily` at a wall-clock `time` (`HH:MM`) in the routine's timezone."""

    model_config = TOOL_CONTRACT

    kind: Literal["interval", "daily"]
    minutes: int | None = Field(default=None, ge=1, le=MAX_INTERVAL_MINUTES)
    time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.kind == "interval" and (self.minutes is None or self.time is not None):
            raise ValueError("an interval takes minutes only")
        if self.kind == "daily" and (self.time is None or self.minutes is not None):
            raise ValueError("a daily schedule takes a time only")
        return self


class RoutineTarget(BaseModel):
    model_config = LAX_CONTRACT

    kind: Literal["expert", "workflow"]
    id: Identifier
    # "draft" is accepted here only to be refused with `draft_not_runnable` (PRD-Studio WF-02).
    version: Version | Literal["draft"]


class RoutineConfig(BaseModel):
    """A version as a request sets it."""

    model_config = LAX_CONTRACT

    target: RoutineTarget
    trigger: CronjobSchedule
    timezone: IanaTimezone = DEFAULT_TIMEZONE
    goal: str = Field(default="", max_length=20000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] | None = None
    # Per run, with no cap of its own for a person's routine: admission caps each run at the
    # workspace's run limit. The cronjob tool caps its own at US$1 (Decision 0029 F2).
    limit_micro_usd: MicroUsd = 1_000_000
    # The sources' default. Nothing else is offered yet.
    overlap: Literal["skip"] = "skip"

    @field_validator("trigger", mode="before")
    @classmethod
    def _whole_minutes(cls, value: object) -> object:
        """An interval is a JSON integer, as the Routines API always required: lax validation
        would read `true` as 1 minute, or "15" as 15."""
        if isinstance(value, Mapping):
            minutes = value.get("minutes")
            if minutes is not None and (isinstance(minutes, bool) or not isinstance(minutes, int)):
                raise ValueError("minutes is a whole number")
        return value


class RoutineCreate(BaseModel):
    model_config = LAX_CONTRACT

    name: str = Field(min_length=1, max_length=100)
    config: RoutineConfig


class RoutineRevision(BaseModel):
    model_config = LAX_CONTRACT

    expected_version: Version
    config: RoutineConfig


class RoutineEnabled(BaseModel):
    model_config = LAX_CONTRACT

    enabled: Flag


class RoutineScheduleView(BaseModel):
    """A saved schedule as it runs: every `minutes`, or `daily` at the wall-clock `time` its
    occurrences use. That is `HH:MM`, with seconds and any fraction only for an older version saved
    with them, such as `07:30:45`. `time` is null for an older daily version whose stored time isn't
    text, which never runs."""

    model_config = LAX_CONTRACT

    kind: Literal["interval", "daily"]
    minutes: int | None
    time: str | None


class RoutineConfigView(BaseModel):
    """A saved version, read from its stored record."""

    model_config = LAX_CONTRACT

    target: RoutineTarget
    trigger: RoutineScheduleView
    timezone: str
    goal: str
    inputs: dict[str, Any]
    tools: list[str] | None
    limit_micro_usd: MicroUsd
    overlap: Literal["skip"]


class OccurrenceView(BaseModel):
    model_config = LAX_CONTRACT

    occurrence_time: UtcTimestamp
    routine_version: int
    status: OccurrenceStatus
    reason: str | None
    run_id: Identifier | None


class RoutineView(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    id: Identifier
    name: str
    enabled: bool
    latest_version: int
    config: RoutineConfigView
    occurrences: list[OccurrenceView]


class RoutineList(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    routines: list[RoutineView]
