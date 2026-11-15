"""Stored JSON documents as records, apart from the contracts that write them (refactor plan R-52,
PDOM-01).

A record is the storage format of one jsonb document. It ignores fields it doesn't know and holds
no request bounds, so a contract can change without a saved version failing to read. Each carries
a version: a document without `record_version` is version 1, and version 1 is written without it,
so stored bytes and receipt fingerprints stay as they were (Decision 0029 F9). Another version is
refused until a reader for it exists. The application maps each record to and from its public
contract explicitly.
"""

from collections.abc import Mapping
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PlainSerializer, PlainValidator

from autobots.domain.routines import (
    DEFAULT_TIMEZONE,
    DailyTrigger,
    IntervalTrigger,
    SavedTrigger,
    UnscheduledTrigger,
    saved_trigger,
    wall_clock,
)

LENIENT = ConfigDict(frozen=True, extra="ignore")


class StoredRecord(BaseModel):
    model_config = LENIENT

    record_version: Literal[1] = 1

    def document(self) -> dict[str, object]:
        """The JSON to store. Version 1 leaves its version out, as absent means 1."""
        return self.model_dump(mode="json", exclude={"record_version"})

    def stored(self) -> str:
        return self.model_dump_json(exclude={"record_version"})


class ExpertConfigRecord(StoredRecord):
    """`public.expert_versions.config`. Without `tool_groups` before US-14.2."""

    purpose: str = ""
    instructions: str = ""
    tools: tuple[str, ...] = ()
    tool_groups: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    role_bindings: Mapping[str, str] = Field(default_factory=dict)


def _trigger(value: object) -> SavedTrigger:
    """Parsed once on read, accepting every form a saved version holds (domain/routines.py)."""
    if isinstance(value, IntervalTrigger | DailyTrigger | UnscheduledTrigger):
        return value
    if not isinstance(value, Mapping):
        # A ValueError, which pydantic reports as a validation error, where a TypeError escapes.
        raise ValueError("a trigger is a mapping")
    return saved_trigger(value)


def _trigger_document(trigger: SavedTrigger) -> dict[str, object]:
    """As routines always stored a trigger: its kind and the one field that kind uses."""
    if isinstance(trigger, IntervalTrigger):
        return {"kind": "interval", "minutes": trigger.minutes}
    if isinstance(trigger, UnscheduledTrigger):
        return {"kind": "daily", "time": trigger.time}
    return {"kind": "daily", "time": wall_clock(trigger)}


StoredTrigger = Annotated[
    SavedTrigger, PlainValidator(_trigger), PlainSerializer(_trigger_document, return_type=dict)
]


class RoutineTargetRecord(BaseModel):
    model_config = LENIENT

    kind: Literal["expert", "workflow"]
    id: UUID
    # Only a published version is ever saved (PRD-Studio WF-02).
    version: int


class RoutineConfigRecord(StoredRecord):
    """`public.routine_versions.config`. A routine with no target or trigger can't run, so those
    two are required; the rest default as the contract always did."""

    target: RoutineTargetRecord
    trigger: StoredTrigger
    timezone: str = DEFAULT_TIMEZONE
    goal: str = ""
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    tools: tuple[str, ...] | None = None
    limit_micro_usd: int = 1_000_000
    overlap: Literal["skip"] = "skip"


class RequiredArtifactRecord(BaseModel):
    model_config = LENIENT

    name: str
    must_contain: tuple[str, ...] = ()


class GoalSpecRecord(StoredRecord):
    """`app_private.goal_specs.spec`. Without `required_artifacts` before US-4.8, and without
    `instructions` before US-5.1."""

    objective: str
    original_request: str
    criteria: Mapping[str, str]
    allowed_tools: Mapping[str, int]
    allowed_paths: tuple[str, ...]
    required_artifacts: tuple[RequiredArtifactRecord, ...] = ()
    instructions: str = ""


class PlanTaskRecord(StoredRecord):
    """One task of `app_private.plan_versions.tasks`, a JSON list, unchanged since US-4.3."""

    id: str
    title: str
    depends_on: tuple[str, ...] = ()
    criteria: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    expected_evidence: str


def read_expert_config(stored: object) -> ExpertConfigRecord:
    return ExpertConfigRecord.model_validate(stored)


def read_routine_config(stored: object) -> RoutineConfigRecord:
    return RoutineConfigRecord.model_validate(stored)


def read_goal_spec(stored: object) -> GoalSpecRecord:
    return GoalSpecRecord.model_validate(stored)


def read_plan_tasks(stored: object) -> list[PlanTaskRecord]:
    if not isinstance(stored, list):
        raise TypeError("a stored plan is a list of tasks")
    return [PlanTaskRecord.model_validate(task) for task in stored]
