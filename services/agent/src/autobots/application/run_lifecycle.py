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


async def _holds_lease(connection: Connection, lease: Lease) -> bool:
    cursor = await connection.execute(
        "select 1 from app_private.run_jobs where run_id = %s and generation = %s "
        "and status = 'claimed' and lease_expires_at > clock_timestamp()",
        (lease.run_id, lease.generation),
    )
    return await cursor.fetchone() is not None


def _disposition(lease: Lease, code: str | None) -> Disposition:
    """The table's disposition. A code missing from it suspends the run, so it stays resumable, and
    the warning names the code so that it can join the table (Decision 0028 E3, SP-010)."""
    disposition = disposition_of(code)
    if disposition is None:
        logger.log(
            logging.WARNING,
            "worker.stop_code_unmapped",
            extra={"fields": {"run": str(lease.run_id), "code": code}},
        )
        return UNMAPPED
    return disposition


async def finish(
    connection: Connection, lease: Lease, goal: GoalSpec, stop_code: str | None
) -> LoopResult:
    """Ends a pass through the canonical transitions, whatever stopped it (SP-010).

    A run being cancelled finishes cancelling: the worker that still holds the lease settles its
    children, classifies what is in flight and writes `cancelled`, while one that lost the lease
    writes nothing. Otherwise a pass with no code and an unfinished plan stops as `plan_missing` or
    `plan_incomplete`, and the code's disposition picks the command. The transition commits with
    its stop reason in one transaction under the lease's generation, and a refused one is reported
    as `lease_lost` (SP-012).
    """
    view = await plan_view(connection, lease.run_id, goal)
    code = stop_code
    # Whatever stopped this pass, a run being cancelled finishes that. Anything else is refused.
    if (
        code != StopCode.LEASE_LOST
        and await run_status(connection, lease) == RunStatus.CANCELLING.value
    ):
        # Settling classifies what's in flight, so a worker that lost the run must not start it.
        code = (
            StopCode.RUN_NOT_RUNNING
            if await _holds_lease(connection, lease)
            else StopCode.LEASE_LOST
        )
    if code is None and not view.finished:
        code = StopCode.PLAN_MISSING if view.version is None else StopCode.PLAN_INCOMPLETE
    command: RunCommand | None
    if (
        code == StopCode.RUN_NOT_RUNNING
        and await run_status(connection, lease) == RunStatus.CANCELLING.value
    ):
        # This worker still owns it, and it is the one who settles the cancellation.
        retry_at = await settle_children(connection, lease)
        if retry_at is not None:
            await connection.execute(
                "update app_private.run_jobs set status = 'queued', lease_owner = null, "
                "lease_expires_at = null, available_at = %s "
                "where run_id = %s and generation = %s and status = 'claimed'",
                (retry_at, lease.run_id, lease.generation),
            )
            return await result_of(
                connection,
                lease,
                goal,
                PassOutcome.WAITING,
                StopCode.CHILDREN_SETTLING,
                RunStatus.CANCELLING.value,
            )
        await classify_interrupted(connection, lease.run_id, lease.generation + 1)
        left = await outstanding(connection, lease.run_id)
        code = (
            StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES
            if left.uncertain_calls or left.unknown_effects
            else StopCode.CANCELLED
        )
        command = RunCommand.FINISH_CANCEL
    else:
        disposition = _disposition(lease, code)
        command = COMMANDS.get(disposition)
        if (
            disposition is Disposition.RELEASE
            and code == StopCode.RUN_NOT_RUNNING
            and await run_status(connection, lease) == RunStatus.PAUSED.value
        ):
            # Stopped at a safe boundary. The run waits for a resume with nobody holding it.
            await connection.execute(
                "update app_private.run_jobs set status = 'done', lease_owner = null, "
                "lease_expires_at = null where run_id = %s and generation = %s "
                "and status = 'claimed'",
                (lease.run_id, lease.generation),
            )
    status = None
    if command is not None:
        version = (
            await _row(connection, "select version from public.runs where id = %s", (lease.run_id,))
        )[0]
        try:
            # The reason commits with the transition, so a worker that lost the run writes nothing.
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
            status = result.status
        except (LeaseLost, VersionConflict, CommandRefused):
            code = StopCode.LEASE_LOST
    outcome = (
        PassOutcome.CANDIDATE
        if code is None
        else PassOutcome.WAITING
        if code == StopCode.APPROVAL_PENDING
        else PassOutcome.LOST
        if disposition_of(code) is Disposition.RELEASE
        else PassOutcome.STOPPED
    )
    return await result_of(connection, lease, goal, outcome, code, status)
