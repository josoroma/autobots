"""The canonical run state machine from SP-010, and the domain view of a run."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from autobots.domain.errors import FixedRefusal


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
# R-11: the other sets derive from RunStatus and TERMINAL, so a new status changes one place.
NEEDS_YOU = frozenset({RunStatus.WAITING_APPROVAL, RunStatus.WAITING_INPUT})
IN_PROGRESS = frozenset(RunStatus) - TERMINAL - NEEDS_YOU
# A run in one of these has stopped, or is stopping, so a model call in it ends early.
INTERRUPTING = TERMINAL | {RunStatus.CANCELLING}

# The tables here are read-only, as domain/models.py's are (PDOM-20).
NORMAL_EXITS: Final[Mapping[RunStatus, frozenset[RunStatus]]] = MappingProxyType(
    {
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
)


def can_transition(current: RunStatus, following: RunStatus) -> bool:
    """A terminal run never moves. Cancellation is valid from every nonterminal state."""
    if current in TERMINAL:
        return False
    if following in {RunStatus.CANCELLING, RunStatus.CANCELLED}:
        return current is not RunStatus.CANCELLING or following is RunStatus.CANCELLED
    return following in NORMAL_EXITS[current]


class Actor(StrEnum):
    """Who applies a command (SP-010). `SYSTEM` is neither a person nor the run's leased worker: a
    parent's cancel or resume reaching its child, a parent's settlement cancelling a child that
    cascade missed, or an approval's expiry pausing its run (Decision 0029 F5)."""

    USER = "user"
    WORKER = "worker"
    SYSTEM = "system"


class RunCommand(StrEnum):
    SUBMIT_INPUT = "submit_input"
    DECIDE_APPROVAL = "decide_approval"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    CLAIM = "claim"
    REQUEST_INPUT = "request_input"
    REQUEST_APPROVAL = "request_approval"
    VERIFY = "verify"
    REPAIR = "repair"
    COMPLETE = "complete"
    FAIL = "fail"
    FINISH_CANCEL = "finish_cancel"
    SUSPEND = "suspend"


class CommandRefused(FixedRefusal):
    """This actor can't do this in the run's current state. Nothing changes. The argument says
    why, internally; a response shows only the code."""

    code = "transition_refused"


_USER = frozenset({Actor.USER})
_WORKER = frozenset({Actor.WORKER})
_USER_OR_SYSTEM = frozenset({Actor.USER, Actor.SYSTEM})
# Exactly who may apply each command, as SP-010's command table states it. A completion can never
# come from a person, and the system applies only cancel, pause and resume (Decision 0029 F5).
ACTORS: Final[Mapping[RunCommand, frozenset[Actor]]] = MappingProxyType(
    {
        RunCommand.SUBMIT_INPUT: _USER,
        RunCommand.DECIDE_APPROVAL: _USER,
        RunCommand.PAUSE: _USER_OR_SYSTEM,
        RunCommand.RESUME: _USER_OR_SYSTEM,
        RunCommand.CANCEL: _USER_OR_SYSTEM,
        RunCommand.CLAIM: _WORKER,
        RunCommand.REQUEST_INPUT: _WORKER,
        RunCommand.REQUEST_APPROVAL: _WORKER,
        RunCommand.VERIFY: _WORKER,
        RunCommand.REPAIR: _WORKER,
        RunCommand.COMPLETE: _WORKER,
        RunCommand.FAIL: _WORKER,
        RunCommand.FINISH_CANCEL: _WORKER,
        RunCommand.SUSPEND: _WORKER,
    }
)
# What each command moves to. A cancel isn't here: it reaches cancelling or cancelled, by what is
# still open.
TARGETS: Final[Mapping[RunCommand, RunStatus]] = MappingProxyType(
    {
        RunCommand.SUBMIT_INPUT: RunStatus.QUEUED,
        RunCommand.DECIDE_APPROVAL: RunStatus.QUEUED,
        RunCommand.PAUSE: RunStatus.PAUSED,
        RunCommand.RESUME: RunStatus.QUEUED,
        RunCommand.CLAIM: RunStatus.RUNNING,
        RunCommand.REQUEST_INPUT: RunStatus.WAITING_INPUT,
        RunCommand.REQUEST_APPROVAL: RunStatus.WAITING_APPROVAL,
        RunCommand.VERIFY: RunStatus.VERIFYING,
        RunCommand.REPAIR: RunStatus.RUNNING,
        RunCommand.COMPLETE: RunStatus.SUCCEEDED,
        RunCommand.FAIL: RunStatus.FAILED,
        RunCommand.FINISH_CANCEL: RunStatus.CANCELLED,
        RunCommand.SUSPEND: RunStatus.PAUSED,
    }
)
# The states each command can start from, where the target alone doesn't say. Without its source a
# claim of a verifying run would reach running, as a repair does.
COMMAND_SOURCES: Final[Mapping[RunCommand, frozenset[RunStatus]]] = MappingProxyType(
    {
        RunCommand.SUBMIT_INPUT: frozenset({RunStatus.WAITING_INPUT}),
        RunCommand.DECIDE_APPROVAL: frozenset({RunStatus.WAITING_APPROVAL}),
        RunCommand.RESUME: frozenset({RunStatus.PAUSED}),
        RunCommand.CLAIM: frozenset({RunStatus.QUEUED}),
        RunCommand.REPAIR: frozenset({RunStatus.VERIFYING}),
        RunCommand.FINISH_CANCEL: frozenset({RunStatus.CANCELLING}),
    }
)


def next_status(
    current: RunStatus, command: RunCommand, actor: Actor, *, has_active_work: bool = False
) -> RunStatus | None:
    """The status a command moves to, or None when cancelling an already-cancelling run."""
    if actor not in ACTORS[command]:
        raise CommandRefused("this actor cannot issue that command")
    if command is RunCommand.CANCEL:
        if current is RunStatus.CANCELLING:
            return None
        if current in TERMINAL:
            if current is RunStatus.CANCELLED:
                return None
            raise CommandRefused("a finished run cannot be cancelled")
        return RunStatus.CANCELLING if has_active_work else RunStatus.CANCELLED
    target = TARGETS[command]
    sources = COMMAND_SOURCES.get(command)
    if current in TERMINAL or (sources is not None and current not in sources):
        raise CommandRefused("that is not allowed in the current state")
    if not can_transition(current, target):
        raise CommandRefused("that is not allowed in the current state")
    return target


class JobStatus(StrEnum):
    """A run's job: waiting for a claim, held by a worker's lease, or no worker's (SP-012)."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    DONE = "done"


@dataclass(frozen=True)
class LockedJob:
    """A run's job as the transaction that moves the run read it under its row lock. A run with no
    job row reads as no status and no generation."""

    status: JobStatus | None
    generation: int | None
    # Whether its lease is unexpired by database time.
    live: bool

    @property
    def live_claim(self) -> bool:
        return self.status is JobStatus.CLAIMED and self.live

    def held_by(self, generation: int) -> bool:
        """Whether the worker at `generation` still owns the run (SP-012)."""
        return self.live_claim and self.generation == generation


def job_status_after(following: RunStatus, actor: Actor, job: LockedJob) -> JobStatus | None:
    """What a transition to `following` does to the run's job, or None to leave it as it is.

    A queued run waits for a claim. A run running or verifying stays with its lease holder. A run
    being cancelled stays with a live owner, which settles it, and is queued for a worker to settle
    otherwise. A pause by a person or the system leaves a live owner its job: it sees the pause at
    its next check, saves its step and lets go. In any other state no worker owns the run
    (PRUN-06, SP-012).
    """
    if following is RunStatus.QUEUED:
        return JobStatus.QUEUED
    if following in {RunStatus.RUNNING, RunStatus.VERIFYING}:
        return None
    if following is RunStatus.CANCELLING:
        return None if job.live_claim else JobStatus.QUEUED
    if following is RunStatus.PAUSED and actor is not Actor.WORKER and job.live_claim:
        return None
    return JobStatus.DONE


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
    version: int = 1
