"""`cronjob` v1's input and output, Decision 0026 C1 and C8, PRD-Tool-Catalog CJ-01 to CJ-04.

The schedule is typed for the model rather than a free mapping, and becomes a routine trigger.
Each action takes only its own fields, so a call can't carry anything its action ignores.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from autobots.contracts.primitives import Identifier
from autobots.contracts.tools import TOOL_CONTRACT
from autobots.domain.routines import MAX_INTERVAL_MINUTES

CronjobAction = Literal["list", "create", "update", "pause", "resume", "run", "remove"]
# Per occurrence, as the Routines API's default: a scheduled task can't spend more than US$1.
MAX_LIMIT_MICRO_USD = 1_000_000


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


class CronjobTask(BaseModel):
    """What a routine starts, and when. An Expert's goal, or a published workflow version."""

    model_config = TOOL_CONTRACT

    target_kind: Literal["expert", "workflow"]
    target_id: Identifier
    target_version: int = Field(ge=1)
    schedule: CronjobSchedule
    timezone: str = Field(default="America/Costa_Rica", min_length=1, max_length=64)
    goal: str = Field(default="", max_length=20_000)
    inputs: dict[str, str | int | float | bool] = Field(default_factory=dict)
    tools: list[str] | None = Field(default=None, max_length=64)
    limit_micro_usd: int = Field(default=MAX_LIMIT_MICRO_USD, ge=0, le=MAX_LIMIT_MICRO_USD)


_FIELDS: dict[str, set[str]] = {
    "list": set(),
    "create": {"name", "task"},
    "update": {"routine_id", "expected_version", "task"},
    "pause": {"routine_id"},
    "resume": {"routine_id"},
    "run": {"routine_id"},
    "remove": {"routine_id"},
}


class CronjobInput(BaseModel):
    model_config = TOOL_CONTRACT

    action: CronjobAction
    routine_id: Identifier | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_version: int | None = Field(default=None, ge=1)
    task: CronjobTask | None = None

    @model_validator(mode="after")
    def _fields_for_action(self) -> Self:
        given = {name for name in ("routine_id", "name", "expected_version", "task")}
        given = {name for name in given if getattr(self, name) is not None}
        if given != _FIELDS[self.action]:
            needed = ", ".join(sorted(_FIELDS[self.action])) or "nothing else"
            raise ValueError(f"{self.action} takes {needed}")
        return self


class CronjobRoutine(BaseModel):
    model_config = TOOL_CONTRACT

    routine_id: Identifier
    name: str
    enabled: bool
    latest_version: int


class CronjobOutput(BaseModel):
    """`status` is `listed`, `saved`, `paused`, `resumed`, `removed`, or for `run` one of
    `admitted`, `skipped_overlap` and `blocked`, with `reason` saying why it wasn't admitted."""

    model_config = TOOL_CONTRACT

    action: CronjobAction
    status: str
    routine_id: Identifier | None = None
    version: int | None = None
    run_id: Identifier | None = None
    reason: str | None = None
    routines: list[CronjobRoutine] | None = None
