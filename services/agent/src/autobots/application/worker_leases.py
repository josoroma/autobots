"""Job ownership by database time and a rising generation, SP-012."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol
from uuid import UUID

from autobots.application.runs import LeaseLost, record_transition
from autobots.domain.runs import RunStatus

DEFAULT_LEASE_SECONDS = 60.0
# Over this between the two clocks is a sleep, and not a busy Mac.
SLEEP_GAP_SECONDS = 20.0
# Long enough for Docker's VM to correct its clock, which it did late in the first real sleep.
WAKE_WINDOW_SECONDS = 300.0
# A pass that raises an exception no handler classifies is retried after each delay in turn, and
# the bound's consecutive failure suspends its run instead (Decision 0028 E4, SP-012).
FAILURE_BOUND: Final = 3
RETRY_DELAYS_SECONDS: Final = (30.0, 60.0)
# The longest stored type, as the column's check bounds it (20261114000055_run_job_failures.sql).
FAILURE_TYPE_LIMIT: Final = 200
_OUTSIDE_A_NAME = re.compile(r"[^A-Za-z0-9_.<>]")


class WakeClock:
    """A monotonic clock stops while a Mac sleeps, and the wall clock doesn't, US-11.10.

    So this sees a real sleep, in this process. SIGSTOP or a hung worker stops neither clock apart.
    """

    def __init__(
        self,
        wall: Callable[[], float] = time.time,
        mono: Callable[[], float] = time.monotonic,
    ) -> None:
        self._wall = wall
        self._mono = mono
        self._last_wall = wall()
        self._last_mono = mono()
        self._woke_at: float | None = None

    def check(self) -> float:
        """The seconds asleep since the last check, or 0 if this wasn't a sleep."""
        wall, mono = self._wall(), self._mono()
        gap = (wall - self._last_wall) - (mono - self._last_mono)
        self._last_wall, self._last_mono = wall, mono
        if gap <= SLEEP_GAP_SECONDS:
            return 0.0
        self._woke_at = mono
        return gap

    def just_woke(self) -> bool:
        return self._woke_at is not None and self._mono() - self._woke_at < WAKE_WINDOW_SECONDS


@dataclass(frozen=True)
class Lease:
    run_id: UUID
    workspace_id: UUID
    generation: int
    worker_id: str
    attempts: int
    run_status: str

    @property
    def thread_id(self) -> str:
        return str(self.run_id)


class LeaseHolder(Protocol):
    """A claim on one run at one generation, such as a `Lease` or a tool call's scope."""

    @property
    def run_id(self) -> UUID: ...

    @property
    def generation(self) -> int: ...


async def hold_lease(connection: Any, holder: LeaseHolder) -> None:
    """Inside a write's transaction. The share lock serializes it against a new claim."""
    cursor = await connection.execute(
        "select 1 from app_private.run_jobs where run_id = %s and generation = %s "
        "and status = 'claimed' and lease_expires_at > clock_timestamp() for share",
        (holder.run_id, holder.generation),
    )
    if await cursor.fetchone() is None:
        raise LeaseLost("this worker no longer owns the run")


async def generation_alive(connection: Any, run_id: str, generation: int) -> bool:
    """Whether the run's job is still claimed at `generation` with an unexpired lease by database
    time, and the run is running. The browser sweeper keeps a session only while this holds, by the
    run and generation its container is labelled with (BX-04, PADP-13)."""
    cursor = await connection.execute(
        "select 1 from app_private.run_jobs j join public.runs r on r.id = j.run_id "
        "where j.run_id::text = %s and j.generation = %s and j.status = 'claimed' "
        "and j.lease_expires_at > clock_timestamp() and r.status = 'running'",
        (run_id, generation),
    )
    return await cursor.fetchone() is not None


async def is_held(connection: Any) -> bool:
    """A restored instance holds all its work until a person releases it."""
    cursor = await connection.execute("select 1 from app_private.installation_holds limit 1")
    return await cursor.fetchone() is not None


async def _claim(
    connection: Any, condition: str, values: tuple[Any, ...], worker_id: str, lease_seconds: float
) -> Lease | None:
    if await is_held(connection):
        return None
    async with connection.transaction():
        cursor = await connection.execute(
            "select j.run_id, j.workspace_id, r.status, r.version "
            "from app_private.run_jobs j join public.runs r on r.id = j.run_id "
            f"where {condition} and r.status <> 'paused' "
            "and j.available_at <= clock_timestamp() and (j.status = 'queued' or "
            "(j.status = 'claimed' and j.lease_expires_at <= clock_timestamp())) "
            "order by j.available_at limit 1 for update of j skip locked",
            values,
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        run_id, workspace_id, status, version = row
        cursor = await connection.execute(
            "update app_private.run_jobs set status = 'claimed', generation = generation + 1, "
            "attempts = attempts + 1, lease_owner = %s, "
            "lease_expires_at = clock_timestamp() + make_interval(secs => %s) "
            "where run_id = %s returning generation, attempts",
            (worker_id, lease_seconds, run_id),
        )
        generation, attempts = await cursor.fetchone()
        await connection.execute(
            "update public.runs set lease_generation = %s, checkpoint_thread_id = %s where id = %s",
            (generation, str(run_id), run_id),
        )
        if status == RunStatus.QUEUED.value:
            await record_transition(connection, run_id, status, RunStatus.RUNNING.value, version)
            status = RunStatus.RUNNING.value
    return Lease(run_id, workspace_id, generation, worker_id, attempts, status)


async def claim_next(
    connection: Any, *, worker_id: str, lease_seconds: float = DEFAULT_LEASE_SECONDS
) -> Lease | None:
    """Take one eligible job: queued, or held by an owner whose lease has expired.

    A child's job is left to its parent, which runs it and reads its result.
    """
    return await _claim(connection, "r.parent_run_id is null", (), worker_id, lease_seconds)


async def claim_run(
    connection: Any, run_id: UUID, *, worker_id: str, lease_seconds: float = DEFAULT_LEASE_SECONDS
) -> Lease | None:
    return await _claim(connection, "j.run_id = %s", (run_id,), worker_id, lease_seconds)


async def revive_lease(
    connection: Any, lease: Lease, *, lease_seconds: float = DEFAULT_LEASE_SECONDS
) -> None:
    """After a real sleep only: its own worker takes back a lease that ran out while nobody ran.

    Anyone who claimed it raised the generation, so this fails for them and fencing is unchanged. A
    reply that came back through the sleep is then used, instead of being paid for a second time.
    """
    cursor = await connection.execute(
        "update app_private.run_jobs "
        "set lease_expires_at = clock_timestamp() + make_interval(secs => %s) "
        "where run_id = %s and generation = %s and status = 'claimed' and lease_owner = %s "
        "returning run_id",
        (lease_seconds, lease.run_id, lease.generation, lease.worker_id),
    )
    if await cursor.fetchone() is None:
        raise LeaseLost("this worker no longer owns the run")


async def heartbeat(
    connection: Any, lease: Lease, *, lease_seconds: float = DEFAULT_LEASE_SECONDS
) -> None:
    """Extends a live lease only. An expired one can't come back, even if nobody took it yet."""
    cursor = await connection.execute(
        "update app_private.run_jobs "
        "set lease_expires_at = clock_timestamp() + make_interval(secs => %s) "
        "where run_id = %s and generation = %s and status = 'claimed' "
        "and lease_expires_at > clock_timestamp() returning run_id",
        (lease_seconds, lease.run_id, lease.generation),
    )
    if await cursor.fetchone() is None:
        raise LeaseLost("this worker no longer owns the run")


def retry_delay(failed_attempts: int) -> float | None:
    """Seconds before a job whose pass failed `failed_attempts` consecutive times may be claimed
    again, or None at the bound, where its run is suspended instead (Decision 0028 E4)."""
    if failed_attempts >= FAILURE_BOUND:
        return None
    return RETRY_DELAYS_SECONDS[max(failed_attempts, 1) - 1]


def failure_type(error: BaseException) -> str:
    """A failure's module-qualified type, as `run_jobs.last_failure_type` keeps it: never its
    message, which can hold a key or a provider's reply (Decision 0028 E4). Anything outside a
    name becomes `_`, and it is cut to the column's bound, so the column's check always passes."""
    kind = type(error)
    name = _OUTSIDE_A_NAME.sub("_", f"{kind.__module__}.{kind.__qualname__}")
    return name[:FAILURE_TYPE_LIMIT]


async def count_failure(connection: Any, lease: Lease, kind: str) -> tuple[int, str] | None:
    """Adds a failed pass to the job this lease claims, with its type, and returns the consecutive
    count and the run's status. None when the lease's generation no longer holds a claimed job, so
    a worker that lost the run records nothing (SP-012). The row stays locked until its caller's
    transaction ends."""
    cursor = await connection.execute(
        "update app_private.run_jobs j set failed_attempts = j.failed_attempts + 1, "
        "last_failure_type = %s from public.runs r where r.id = j.run_id "
        "and j.run_id = %s and j.generation = %s and j.status = 'claimed' "
        "returning j.failed_attempts, r.status",
        (kind, lease.run_id, lease.generation),
    )
    row = await cursor.fetchone()
    return None if row is None else (int(row[0]), str(row[1]))


async def release(connection: Any, lease: Lease, delay_seconds: float) -> None:
    """Requeues the job this lease claims, claimable again `delay_seconds` from now by database
    time. The lease's generation fences it."""
    await connection.execute(
        "update app_private.run_jobs set status = 'queued', lease_owner = null, "
        "lease_expires_at = null, available_at = clock_timestamp() + make_interval(secs => %s) "
        "where run_id = %s and generation = %s and status = 'claimed'",
        (delay_seconds, lease.run_id, lease.generation),
    )


async def let_go(connection: Any, lease: Lease) -> None:
    """Ends this lease's claim on a run a person paused. Their resume queues the job again."""
    await connection.execute(
        "update app_private.run_jobs set status = 'done', lease_owner = null, "
        "lease_expires_at = null where run_id = %s and generation = %s and status = 'claimed'",
        (lease.run_id, lease.generation),
    )


async def reset_failures(connection: Any, lease: Lease) -> None:
    """A pass under this lease completed, so the job's consecutive failures start again from none
    (Decision 0028 E4). The generation fences it, so a later claim keeps a count of its own."""
    await connection.execute(
        "update app_private.run_jobs set failed_attempts = 0 "
        "where run_id = %s and generation = %s and failed_attempts <> 0",
        (lease.run_id, lease.generation),
    )
