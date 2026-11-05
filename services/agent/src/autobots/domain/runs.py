"""The canonical run state machine from SP-010, and the domain view of a run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    VERIFYING = "verifying"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})

NORMAL_EXITS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.PAUSED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_INPUT,
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED,
            RunStatus.VERIFYING,
            RunStatus.FAILED,
        }
    ),
    RunStatus.WAITING_INPUT: frozenset({RunStatus.QUEUED, RunStatus.PAUSED}),
    RunStatus.WAITING_APPROVAL: frozenset({RunStatus.QUEUED, RunStatus.PAUSED}),
    RunStatus.PAUSED: frozenset({RunStatus.QUEUED}),
    RunStatus.VERIFYING: frozenset(
        {RunStatus.SUCCEEDED, RunStatus.RUNNING, RunStatus.FAILED, RunStatus.PAUSED}
    ),
    RunStatus.CANCELLING: frozenset({RunStatus.CANCELLED}),
}


def can_transition(current: RunStatus, following: RunStatus) -> bool:
    """A terminal run never moves. Cancellation is valid from every nonterminal state."""
    if current in TERMINAL:
        return False
    if following in {RunStatus.CANCELLING, RunStatus.CANCELLED}:
        return current is not RunStatus.CANCELLING or following is RunStatus.CANCELLED
    return following in NORMAL_EXITS[current]


@dataclass(frozen=True)
class Run:
    id: UUID
    workspace_id: UUID
    parent_run_id: UUID | None
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    spent_micro_usd: int
    reserved_micro_usd: int
    limit_micro_usd: int
    lease_generation: int
    checkpoint_thread_id: str | None
