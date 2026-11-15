"""The lifecycle every pass under a lease shares: its settings and result, a keeper that holds the
lease while it works, and finishing the run through the canonical transitions (SP-010, SP-012).

The goal loop and the workflow runner both build on it, and neither imports the other: the goal loop
passes its own drive function to the workflow runner, which drives its agent steps' children with it
(PPRD-02, R-33).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

import psycopg

from autobots.application.bounded import stop_task
from autobots.application.compaction import CompactionPolicy
from autobots.application.plans import load_goal, plan_view
from autobots.application.recovery import classify_interrupted, outstanding
from autobots.application.run_usage import RootLimits, discount_sleep, usage_view
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.tool_gateway import ToolDefinition
from autobots.application.worker_leases import (
    DEFAULT_LEASE_SECONDS,
    Lease,
    WakeClock,
    claim_run,
    heartbeat,
    revive_lease,
)
from autobots.contracts.plans import GoalSpec
from autobots.domain.models import ModelRoute
from autobots.domain.repetition import Repeated
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus
from autobots.domain.stops import (
    COMMANDS,
    UNMAPPED,
    Disposition,
    PassOutcome,
    StopCode,
    disposition_of,
)

# STD-01 keeps this module from importing `autobots.operations.logs`, so it writes that module's
# record with its own logger: `logger.log(level, event, extra={"fields": {...}})`.
logger = logging.getLogger("autobots.worker")
WAKE_LOOK_SECONDS = 1.0


@dataclass(frozen=True)
class LoopConfig:
    route: ModelRoute
    limits: RootLimits = RootLimits()  # noqa: RUF009 - frozen, so sharing the default is safe.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    slot_wait_seconds: float = 30.0
    object_store: Any = None
    tools: tuple[ToolDefinition, ...] = ()
    compaction: CompactionPolicy = CompactionPolicy()  # noqa: RUF009 - frozen, so sharing is safe.
    heartbeat_seconds: float = 20.0
    model_call_seconds: float = 120.0
    lease_seconds: float = DEFAULT_LEASE_SECONDS
    # Why this job can't dispatch, known before it reserves anything. A cancel or a verification
    # that needs no model still goes first, so it's checked with the route, not at claim.
    refusal: str | None = None


@dataclass(frozen=True)
class LoopResult:
    """What really happened, whatever the model said at the end."""

    outcome: PassOutcome
    code: str | None
    run_status: str | None
    plan_version: int | None
    completed: tuple[str, ...]
    remaining: tuple[str, ...]
    uncovered_criteria: tuple[str, ...]
    usage: dict[str, Any]


# How a claimed lease is driven: (connection, database URL, lease, model factory, config). The goal
# loop passes its own, so the workflow runner drives an agent step's child without importing it.
Drive = Callable[[Any, str, Lease, Callable[[], Any], LoopConfig], Awaitable[LoopResult]]


class Rows(Protocol):
    # Rows stay untyped until the SQL boundary is typed (R-54).
    async def fetchone(self) -> tuple[Any, ...] | None: ...
    async def fetchall(self) -> list[tuple[Any, ...]]: ...


class Connection(Protocol):
    """The worker's psycopg connection, as far as finishing a pass uses it."""

    async def execute(self, query: str, params: tuple[object, ...], /) -> Rows: ...
    def transaction(self) -> AbstractAsyncContextManager[object]: ...


async def _row(connection: Connection, query: str, params: tuple[object, ...]) -> tuple[Any, ...]:
    """The row a query about a run this worker holds finds. A missing one is a named defect."""
    row = await (await connection.execute(query, params)).fetchone()
    if row is None:
        raise LookupError(f"no row: {query}")
    return row


async def run_status(connection: Connection, lease: Lease) -> str:
    status: str = (
        await _row(connection, "select status from public.runs where id = %s", (lease.run_id,))
    )[0]
    return status


async def result_of(
    connection: Connection,
    lease: Lease,
    goal: GoalSpec,
    outcome: PassOutcome,
    code: str | None,
    status: str | None,
) -> LoopResult:
    """The pass's result as it is stored: the plan's progress and the run's usage, read now."""
    view = await plan_view(connection, lease.run_id, goal)
    return LoopResult(
        outcome,
        code,
        status,
        view.version,
        view.completed,
        view.remaining,
        view.uncovered_criteria,
        await usage_view(connection, lease.run_id),
    )


class LeaseKeeper:
    """Holds one lease on its own connection, since the loop's may be mid-transaction or waiting on
    a model (SP-012).

    It looks every second for a Mac having slept, as a lease runs out during any sleep longer than
    it. Right after one, it beats every look too, because Docker's clock can jump again later
    (US-11.10).
    """

    def __init__(
        self, database_url: str, lease: Lease, config: LoopConfig, clock: WakeClock | None = None
    ) -> None:
        self.database_url = database_url
        self.lease = lease
        self.config = config
        self.wake = clock or WakeClock()
        self.look_seconds = min(WAKE_LOOK_SECONDS, config.heartbeat_seconds)
        self.since_beat = 0.0
        self.undiscounted = 0.0
        self.failures = Repeated()

    async def run(self) -> None:
        """Looks until the lease is lost for good. A dropped connection or any other failure is
        counted and retried, and the first look after it beats."""
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self.database_url, autocommit=True
                ) as connection:
                    while True:
                        await asyncio.sleep(self.look_seconds)
                        if not await self.look(connection):
                            return
            except Exception as error:  # noqa: BLE001 - a dropped connection or any other failure is counted and retried
                # A sleep can drop this connection, among other things.
                if self.failures.failed():
                    logger.log(
                        logging.WARNING,
                        "worker.keeper_reconnecting",
                        extra={"fields": {"error": error, "failures": self.failures.count}},
                    )
                await asyncio.sleep(self.look_seconds)
                # An outage used up lease time with no beat, so the first look after it beats.
                self.since_beat = self.config.heartbeat_seconds

    async def look(self, connection: Connection) -> bool:
        """One look, after its wait: a sleep since the last look is noticed, the lease beats when a
        beat is due or the Mac just woke, a lease that ran out during a sleep is revived, and the
        sleep comes off the active time. False once the lease is lost for good."""
        self.since_beat += self.look_seconds
        slept = self.wake.check()
        if slept:
            logger.log(logging.INFO, "worker.woke", extra={"fields": {"seconds": round(slept, 1)}})
            self.undiscounted += slept
        if self.since_beat >= self.config.heartbeat_seconds or self.wake.just_woke():
            self.since_beat = 0.0
            try:
                await heartbeat(connection, self.lease, lease_seconds=self.config.lease_seconds)
            except LeaseLost:
                if not self.wake.just_woke():
                    return False
                try:
                    await revive_lease(
                        connection, self.lease, lease_seconds=self.config.lease_seconds
                    )
                except LeaseLost:
                    return False
                logger.log(
                    logging.INFO,
                    "worker.lease_revived",
                    extra={"fields": {"generation": self.lease.generation}},
                )
        # After the beat, so a discount that keeps failing can't lose the lease.
        if self.undiscounted:
            await discount_sleep(connection, self.lease, self.undiscounted)
            self.undiscounted = 0.0
        self.failures.cleared()
        return True


@asynccontextmanager
async def lease_heartbeat(
    database_url: str, lease: Lease, config: LoopConfig, clock: WakeClock | None = None
) -> AsyncIterator[None]:
    """A `LeaseKeeper` holds the lease while the block runs. On the way out its task is cancelled
    and awaited, so its connection is closed before the pass goes on, and a cancellation of the
    block's own caller still propagates (PRUN-15, DH-06)."""
    task = asyncio.create_task(LeaseKeeper(database_url, lease, config, clock).run())
    try:
        yield
    finally:
        await stop_task(task)


async def _cancel_stray_child(connection: Connection, lease: Lease, child: UUID) -> str:
    status, version = await _row(
        connection, "select status, version from public.runs where id = %s", (child,)
    )
    try:
        result = await apply_command(
            connection,
            workspace_id=lease.workspace_id,
            run_id=child,
            command=RunCommand.CANCEL,
            actor=Actor.USER,
            expected_version=version,
        )
    except (CommandRefused, VersionConflict):
        # It moved under us. The parent stays queued and looks again.
        return str(status)
    return str(result.status)


async def settle_children(connection: Connection, lease: Lease) -> datetime | None:
    """A cancelled parent's children finish too, and their open assignments close.

    Returns when to try again, if a child still has a live owner. A parent that finished without it
    would leave nothing able to settle that child, as `claim_next` leaves children to their parent.
    """
    cursor = await connection.execute(
        "select a.id, a.child_run_id, r.status from app_private.assignments a "
        "join public.runs r on r.id = a.child_run_id "
        "where a.parent_run_id = %s and a.status = 'open'",
        (lease.run_id,),
    )
    terminal = {RunStatus.CANCELLED.value, RunStatus.FAILED.value, RunStatus.SUCCEEDED.value}
    retry_at: datetime | None = None
    for assignment_id, child, status in await cursor.fetchall():
        if status != RunStatus.CANCELLING.value and status not in terminal:
            # Admitted as the cancel landed, so the cascade missed it. Nothing else would reach it.
            status = await _cancel_stray_child(connection, lease, child)
        if status not in terminal:
            child_lease = await claim_run(connection, child, worker_id=lease.worker_id)
            settled = None
            if child_lease is not None:
                settled = await finish(
                    connection,
                    child_lease,
                    await load_goal(connection, child),
                    StopCode.RUN_NOT_RUNNING,
                )
            if settled is None or settled.run_status not in terminal:
                # Still owned, or it has children of its own to wait for.
                moment = (
                    await _row(
                        connection,
                        "select greatest(available_at, coalesce(lease_expires_at, available_at), "
                        "clock_timestamp() + interval '5 seconds') "
                        "from app_private.run_jobs where run_id = %s",
                        (child,),
                    )
                )[0]
                retry_at = moment if retry_at is None else max(retry_at, moment)
                continue
        outcome = (
            await _row(connection, "select status from public.runs where id = %s", (child,))
        )[0]
        await connection.execute(
            "update app_private.assignments set status = 'finished', outcome = %s, "
            "finished_at = now() where id = %s",
            (outcome, assignment_id),
        )
    return retry_at


@dataclass(frozen=True)
class Observed:
    """What `decide` reads, read once as a pass ends: the run's status and whether this worker
    still holds its lease, from one statement so the two agree, and its plan's state (PRUN-03)."""

    status: RunStatus
    holds_lease: bool
    plan_version: int | None
    plan_finished: bool


class Ending(StrEnum):
    """The step `finish` takes once it has decided."""

    # Not this worker's to write: another owner, a person or a pending approval has the run.
    LEAVE = "leave"
    # A person paused the run: its job is done, and the run waits for a resume, held by nobody.
    LET_GO = "let_go"
    # A run being cancelled: settle its children, classify what is in flight, then FINISH_CANCEL.
    SETTLE = "settle"
    # Apply the command, with the code as its stop reason.
    TRANSITION = "transition"


@dataclass(frozen=True)
class Decision:
    """How a pass ends: the step, the code it ends with, the command a transition or settlement
    applies, and whether the code was missing from the table, which its caller logs (Decision 0028
    E3)."""

    ending: Ending
    code: str | None
    command: RunCommand | None = None
    unmapped: bool = False


def decide(code: str | None, observed: Observed) -> Decision:
    """How a pass that stopped with `code` ends, from one observation of its run (SP-010, SP-012).

    A lost lease writes nothing. A run being cancelled is settled by the worker that holds its
    lease, whatever stopped the pass, and by nobody else, since settling classifies what is in
    flight. Otherwise a pass with no code and an unfinished plan stops as `plan_missing` or
    `plan_incomplete`. A run a person paused waits for a resume: its job is let go as
    `run_not_running` when the pass stopped with that code, or with a code whose command the paused
    run would refuse while this worker holds the lease (R-34). Any other code's disposition picks
    its command, or none, and `apply_command` re-validates it under its row locks.
    """
    if code == StopCode.LEASE_LOST:
        return Decision(Ending.LEAVE, StopCode.LEASE_LOST)
    if observed.status is RunStatus.CANCELLING:
        if observed.holds_lease:
            return Decision(Ending.SETTLE, StopCode.RUN_NOT_RUNNING, RunCommand.FINISH_CANCEL)
        return Decision(Ending.LEAVE, StopCode.LEASE_LOST)
    if code is None and not observed.plan_finished:
        code = StopCode.PLAN_MISSING if observed.plan_version is None else StopCode.PLAN_INCOMPLETE
    known = disposition_of(code)
    command = COMMANDS.get(UNMAPPED if known is None else known)
    if observed.status is RunStatus.PAUSED and (
        code == StopCode.RUN_NOT_RUNNING or (command is not None and observed.holds_lease)
    ):
        return Decision(Ending.LET_GO, StopCode.RUN_NOT_RUNNING, unmapped=known is None)
    if command is None:
        return Decision(Ending.LEAVE, code)
    return Decision(Ending.TRANSITION, code, command, unmapped=known is None)


def outcome_of(code: str | None) -> PassOutcome:
    """What a pass that ended with `code` reports beside it."""
    if code is None:
        return PassOutcome.CANDIDATE
    if code == StopCode.APPROVAL_PENDING:
        return PassOutcome.WAITING
    if disposition_of(code) is Disposition.RELEASE:
        return PassOutcome.LOST
    return PassOutcome.STOPPED


async def observe(connection: Connection, lease: Lease, goal: GoalSpec) -> Observed:
    """The run as `decide` needs it. Ownership is the lease's generation on a claimed job whose
    lease is live by database time, as `apply_command` checks it (SP-012)."""
    view = await plan_view(connection, lease.run_id, goal)
    status, holds = await _row(
        connection,
        "select r.status, exists (select 1 from app_private.run_jobs j where j.run_id = r.id "
        "and j.generation = %s and j.status = 'claimed' "
        "and j.lease_expires_at > clock_timestamp()) from public.runs r where r.id = %s",
        (lease.generation, lease.run_id),
    )
    return Observed(RunStatus(status), bool(holds), view.version, view.finished)


async def _settle(connection: Connection, lease: Lease) -> str | None:
    """Settles a run being cancelled: its children first, then what is in flight, classified with
    this owner's own receipts before FINISH_CANCEL (SP-010). Returns the code FINISH_CANCEL
    records, or None when a child still has a live owner, and the job is requeued until then."""
    retry_at = await settle_children(connection, lease)
    if retry_at is not None:
        await connection.execute(
            "update app_private.run_jobs set status = 'queued', lease_owner = null, "
            "lease_expires_at = null, available_at = %s "
            "where run_id = %s and generation = %s and status = 'claimed'",
            (retry_at, lease.run_id, lease.generation),
        )
        return None
    await classify_interrupted(connection, lease.run_id, lease.generation + 1)
    left = await outstanding(connection, lease.run_id)
    if left.uncertain_calls or left.unknown_effects:
        return StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES
    return StopCode.CANCELLED


async def _transition(
    connection: Connection, lease: Lease, command: RunCommand, code: str | None
) -> tuple[str | None, str | None]:
    """Applies `command` with `code` as its stop reason, in one transaction under the lease's
    generation, so a worker that lost the run writes neither (SP-012). The code the pass ends with
    and the status reached, which is None when nothing was written."""
    version = (
        await _row(connection, "select version from public.runs where id = %s", (lease.run_id,))
    )[0]
    try:
        async with connection.transaction():
            result = await apply_command(
                connection,
                workspace_id=lease.workspace_id,
                run_id=lease.run_id,
                command=command,
                actor=Actor.WORKER,
                expected_version=version,
                generation=lease.generation,
            )
            # A run can stop before its first segment, so the row may not exist yet.
            await connection.execute(
                "insert into app_private.run_usage (run_id, stop_reason) values (%s, %s) "
                "on conflict (run_id) do update set stop_reason = excluded.stop_reason",
                (lease.run_id, code),
            )
    except CommandRefused:
        # The run moved after `finish` looked, a person's pause or cancel say (R-34).
        return StopCode.COMMAND_REFUSED, None
    except (LeaseLost, VersionConflict):
        return StopCode.LEASE_LOST, None
    return code, result.status


async def finish(
    connection: Connection, lease: Lease, goal: GoalSpec, stop_code: str | None
) -> LoopResult:
    """Ends a pass through the canonical transitions, whatever stopped it (SP-010).

    It reads the run once into `Observed`, lets `decide` choose the step, then takes it. Each job
    write keeps the lease's generation and `status = 'claimed'` predicates. A transition commits
    with its stop reason in one transaction under the lease's generation; a refused one ends the
    pass as `command_refused`, and a lost lease or a moved version as `lease_lost` (SP-012).
    """
    decision = decide(stop_code, await observe(connection, lease, goal))
    if decision.unmapped:
        # A code missing from the table is decided as UNMAPPED, a suspension that leaves the run
        # resumable, and the warning names the code so that it can join the table (Decision 0028
        # E3, SP-010).
        logger.log(
            logging.WARNING,
            "worker.stop_code_unmapped",
            extra={"fields": {"run": str(lease.run_id), "code": stop_code}},
        )
    code = decision.code
    status: str | None = None
    if decision.ending is Ending.LET_GO:
        await connection.execute(
            "update app_private.run_jobs set status = 'done', lease_owner = null, "
            "lease_expires_at = null where run_id = %s and generation = %s "
            "and status = 'claimed'",
            (lease.run_id, lease.generation),
        )
    elif decision.ending is Ending.SETTLE:
        code = await _settle(connection, lease)
        if code is None:
            return await result_of(
                connection,
                lease,
                goal,
                PassOutcome.WAITING,
                StopCode.CHILDREN_SETTLING,
                RunStatus.CANCELLING.value,
            )
    if decision.command is not None:
        code, status = await _transition(connection, lease, decision.command, code)
    return await result_of(connection, lease, goal, outcome_of(code), code, status)
