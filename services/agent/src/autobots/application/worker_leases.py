"""Job ownership by database time and a rising generation, SP-012."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from autobots.application.runs import LeaseLost, record_transition
from autobots.domain.runs import RunStatus

DEFAULT_LEASE_SECONDS = 60.0
# Over this between the two clocks is a sleep, and not a busy Mac.
SLEEP_GAP_SECONDS = 20.0
# Long enough for Docker's VM to correct its clock, which it did late in the first real sleep.
WAKE_WINDOW_SECONDS = 300.0


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
