"""The worker process: `python -m autobots.operations.worker`.

`serve` owns liveness, drain and reconnection for whatever step it's given. The entry point here
gives it maintenance only: no model client exists in this process until inference is qualified
(US-3.4), so it never claims a job, and says so in its heartbeat. Local Operations reports queued
work as waiting for an inference worker instead of showing it as moving.
"""

import asyncio
import logging
import os
import secrets
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg
from pydantic import SecretStr

from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.api.main import provider_context_from_environment
from autobots.application.approvals import expire_due
from autobots.application.provider_settings import ProviderSettings
from autobots.application.retention import apply_all
from autobots.application.routines import evaluate_routines
from autobots.operations.logs import configure_logging, forbid_remote_tracing, log_event

logger = logging.getLogger("autobots.worker")
Step = Callable[[Any], Awaitable[bool]]


@dataclass
class WorkerConfig:
    worker_id: str
    database_url: str
    claims_inference: bool = False
    idle_seconds: float = 2.0
    beat_seconds: float = 10.0
    drain_seconds: float = 30.0


@dataclass
class _Status:
    state: str = "running"
    changed: asyncio.Event = field(default_factory=asyncio.Event)


async def _write_beat(connection: Any, config: WorkerConfig, state: str) -> None:
    await connection.execute(
        "insert into app_private.worker_heartbeats (worker_id, state, claims_inference) "
        "values (%s, %s, %s) on conflict (worker_id) do update set state = excluded.state, "
        "beat_at = clock_timestamp(), claims_inference = excluded.claims_inference",
        (config.worker_id, state, config.claims_inference),
    )


async def _beat(config: WorkerConfig, status: _Status) -> None:
    """On its own connection, so a long step can't make a live worker look dead."""
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                config.database_url, autocommit=True
            ) as connection:
                while True:
                    await _write_beat(connection, config, status.state)
                    status.changed.clear()
                    try:
                        async with asyncio.timeout(config.beat_seconds):
                            await status.changed.wait()
                    except TimeoutError:
                        pass
        except psycopg.OperationalError as error:
            log_event(logger, "worker.heartbeat_lost", logging.WARNING, error=type(error).__name__)
            await asyncio.sleep(min(config.beat_seconds, 2.0))


async def _pause(stop: asyncio.Event, seconds: float) -> None:
    try:
        async with asyncio.timeout(seconds):
            await stop.wait()
    except TimeoutError:
        pass


async def _run_step(
    step: Step, connection: Any, stop: asyncio.Event, config: WorkerConfig, status: _Status
) -> bool:
    """One step, given until drain ends once a stop arrives. Cut short, its lease just expires."""
    task: asyncio.Future[Any] = asyncio.ensure_future(step(connection))
    waiter: asyncio.Future[Any] = asyncio.ensure_future(stop.wait())
    try:
        await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        waiter.cancel()
    if not task.done():
        status.state = "draining"
        status.changed.set()
        log_event(logger, "worker.draining", worker=config.worker_id, seconds=config.drain_seconds)
        await asyncio.wait({task}, timeout=config.drain_seconds)
    if not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        log_event(logger, "worker.drain_cut_short", logging.WARNING, worker=config.worker_id)
        return False
    return bool(task.result())


async def serve(config: WorkerConfig, step: Step, stop: asyncio.Event) -> None:
    """Until `stop`: no new step starts after it, and the last beat says this worker has stopped."""
    status = _Status()
    beat = asyncio.create_task(_beat(config, status))
    log_event(
        logger, "worker.started", worker=config.worker_id, claims_inference=config.claims_inference
    )
    try:
        while not stop.is_set():
            try:
                async with await psycopg.AsyncConnection.connect(
                    config.database_url, autocommit=True
                ) as connection:
                    while not stop.is_set():
                        try:
                            worked = await _run_step(step, connection, stop, config, status)
                        except psycopg.OperationalError:
                            raise
                        except Exception as error:
                            log_event(
                                logger,
                                "worker.step_failed",
                                logging.ERROR,
                                error=type(error).__name__,
                            )
                            worked = False
                        if not worked:
                            await _pause(stop, config.idle_seconds)
            except psycopg.OperationalError as error:
                log_event(
                    logger, "worker.database_lost", logging.WARNING, error=type(error).__name__
                )
                await _pause(stop, config.idle_seconds)
    finally:
        beat.cancel()
        await asyncio.gather(beat, return_exceptions=True)
        try:
            async with await psycopg.AsyncConnection.connect(
                config.database_url, autocommit=True
            ) as connection:
                await _write_beat(connection, config, "stopped")
        except psycopg.OperationalError as error:
            # The stack may be stopping too. The stale heartbeat reads as absent anyway.
            log_event(logger, "worker.last_beat_lost", logging.WARNING, error=type(error).__name__)
        log_event(logger, "worker.stopped", worker=config.worker_id)


def install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signal_number, stop.set)


def maintenance_step(
    credential_check: Callable[[Any, UUID], Awaitable[str]],
    store: Any,
    retention_seconds: float = 3600,
) -> Step:
    """Expired approvals, due routines and declared retention, each safe from many workers."""
    last_retention: list[float] = []

    async def step(connection: Any) -> bool:
        await expire_due(connection)

        async def check(workspace_id: UUID) -> str:
            return await credential_check(connection, workspace_id)

        admitted = await evaluate_routines(connection, check)
        now = asyncio.get_running_loop().time()
        if not last_retention or now - last_retention[0] >= retention_seconds:
            last_retention[:] = [now]
            await apply_all(connection, store)
        return admitted > 0

    return step


async def no_credential(_: Any, __: UUID) -> str:
    """With no provider context, nothing unattended starts. The code matches a missing key."""
    return "credentials_required"


def credential_check_from_environment() -> Callable[[Any, UUID], Awaitable[str]]:
    # The same context the API uses, so a routine and a person see one answer about a key.
    context = provider_context_from_environment()
    if context is None:
        return no_credential

    async def check(connection: Any, workspace_id: UUID) -> str:
        return await ProviderSettings(connection, context).run_intent(workspace_id)

    return check


async def main() -> None:
    forbid_remote_tracing(os.environ)
    configure_logging()
    url = os.environ.get("AUTOBOTS_DATABASE_URL", "")
    if not url:
        raise SystemExit("AUTOBOTS_DATABASE_URL is required")
    base, key = (
        os.environ.get("AUTOBOTS_SUPABASE_URL", ""),
        os.environ.get("AUTOBOTS_SERVICE_ROLE_KEY", ""),
    )
    store = SupabaseObjectStore(base, SecretStr(key)) if base and key else None
    config = WorkerConfig(
        worker_id=f"{os.uname().nodename}-{os.getpid()}-{secrets.token_hex(3)}",
        database_url=url,
        drain_seconds=float(os.environ.get("AUTOBOTS_WORKER_DRAIN_SECONDS", "30")),
    )
    stop = asyncio.Event()
    install_signal_handlers(stop)
    await serve(config, maintenance_step(credential_check_from_environment(), store), stop)


if __name__ == "__main__":
    asyncio.run(main())
