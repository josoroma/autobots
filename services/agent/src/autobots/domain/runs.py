"""The canonical run state machine from SP-010, and the domain view of a run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
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


class Actor(StrEnum):
    USER = "user"
    WORKER = "worker"


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


# Who may issue each command, and what it moves to. A completion can never come from a user.
COMMANDS: dict[RunCommand, tuple[Actor, RunStatus]] = {
    RunCommand.SUBMIT_INPUT: (Actor.USER, RunStatus.QUEUED),
    RunCommand.DECIDE_APPROVAL: (Actor.USER, RunStatus.QUEUED),
    RunCommand.PAUSE: (Actor.USER, RunStatus.PAUSED),
    RunCommand.RESUME: (Actor.USER, RunStatus.QUEUED),
    RunCommand.CLAIM: (Actor.WORKER, RunStatus.RUNNING),
    RunCommand.REQUEST_INPUT: (Actor.WORKER, RunStatus.WAITING_INPUT),
    RunCommand.REQUEST_APPROVAL: (Actor.WORKER, RunStatus.WAITING_APPROVAL),
    RunCommand.VERIFY: (Actor.WORKER, RunStatus.VERIFYING),
    RunCommand.REPAIR: (Actor.WORKER, RunStatus.RUNNING),
    RunCommand.COMPLETE: (Actor.WORKER, RunStatus.SUCCEEDED),
    RunCommand.FAIL: (Actor.WORKER, RunStatus.FAILED),
    RunCommand.FINISH_CANCEL: (Actor.WORKER, RunStatus.CANCELLED),
    RunCommand.SUSPEND: (Actor.WORKER, RunStatus.PAUSED),
}
# The states each command can start from, where the target alone doesn't say.
COMMAND_SOURCES: dict[RunCommand, frozenset[RunStatus]] = {
    RunCommand.SUBMIT_INPUT: frozenset({RunStatus.WAITING_INPUT}),
    RunCommand.DECIDE_APPROVAL: frozenset({RunStatus.WAITING_APPROVAL}),
    RunCommand.RESUME: frozenset({RunStatus.PAUSED}),
    RunCommand.REPAIR: frozenset({RunStatus.VERIFYING}),
    RunCommand.FINISH_CANCEL: frozenset({RunStatus.CANCELLING}),
}


def next_status(
    current: RunStatus, command: RunCommand, actor: Actor, *, has_active_work: bool = False
) -> RunStatus | None:
    """The status a command moves to, or None when cancelling an already-cancelling run."""
    if command is RunCommand.CANCEL:
        if actor is not Actor.USER:
            raise CommandRefused("only a user cancels a run")
        if current is RunStatus.CANCELLING:
            return None
        if current in TERMINAL:
            if current is RunStatus.CANCELLED:
                return None
            raise CommandRefused("a finished run cannot be cancelled")
        return RunStatus.CANCELLING if has_active_work else RunStatus.CANCELLED
    owner, target = COMMANDS[command]
    if actor is not owner:
        raise CommandRefused("this actor cannot issue that command")
    sources = COMMAND_SOURCES.get(command)
    if current in TERMINAL or (sources is not None and current not in sources):
        raise CommandRefused("that is not allowed in the current state")
    if not can_transition(current, target):
        raise CommandRefused("that is not allowed in the current state")
    return target


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
