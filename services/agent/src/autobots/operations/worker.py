"""The worker process: `python -m autobots.operations.worker`.

`serve` owns liveness, drain and reconnection for whatever step it's given. By default the entry
point gives it maintenance only, so it never claims a job and says so in its heartbeat. Local
Operations reports queued work as waiting for an inference worker instead of showing it as moving.

`AUTOBOTS_WORKER_INFERENCE=enabled` adds the inference step, which sends real, billed OpenRouter
requests for any queued run once a key exists. Nothing turns it on by default, because it spends
real money. No environment value selects another endpoint, model or fake. The
HTTP client does honor the usual proxy variables, as any client on this Mac would.

What it reads from the environment is built by `composition.py`, as the API's is. A setting it can't
start with stops it before it serves, exit 2 with the variable named (POPS-14).
"""

import asyncio
import logging
import os
import secrets
import signal
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID

import psycopg

from autobots.adapters.tool_registry import build_registry, catalog
from autobots.application.approvals import expire_due
from autobots.application.artifacts import PingableObjectStore
from autobots.application.bounded import stop_task
from autobots.application.goal_loop import UNBOUND
from autobots.application.provider_settings import CatalogFetcher, ConnectionReadiness
from autobots.application.readiness import (
    LentConnection,
    MalformedSetting,
    ReadinessSettings,
    first_blocking,
    installation_conditions,
)
from autobots.application.retention import apply_all
from autobots.application.routines import evaluate_routines
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.sql import CommittingConnection, SqlConnection
from autobots.application.tool_catalog import Catalog
from autobots.application.worker_inference import CatalogCache, InferenceSource
from autobots.application.worker_leases import is_held
from autobots.domain.repetition import Repeated
from autobots.logs import configure_logging, forbid_remote_tracing, log_event
from autobots.operations.composition import (
    CONFIG_ROOT,
    DATABASE_URL,
    STORAGE_URL,
    credential_check,
    object_store,
    provider_context,
    require,
    seconds,
    stop_unconfigured,
)
from autobots.operations.job_dispatch import process_next

logger = logging.getLogger("autobots.worker")
Step = Callable[[CommittingConnection], Awaitable[bool]]
# Opens one autocommit connection; the serve loop, its heartbeat and its last beat each use one.
Connect = Callable[[str], Awaitable[AbstractAsyncContextManager[CommittingConnection]]]
INFERENCE_SWITCH = "AUTOBOTS_WORKER_INFERENCE"
DRAIN_SECONDS = "AUTOBOTS_WORKER_DRAIN_SECONDS"
DEFAULT_DRAIN_SECONDS = 30.0


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


async def _write_beat(connection: SqlConnection, config: WorkerConfig, state: str) -> None:
    await connection.execute(
        "insert into app_private.worker_heartbeats (worker_id, state, claims_inference) "
        "values (%s, %s, %s) on conflict (worker_id) do update set state = excluded.state, "
        "beat_at = clock_timestamp(), claims_inference = excluded.claims_inference",
        (config.worker_id, state, config.claims_inference),
    )


async def connect_database(url: str) -> psycopg.AsyncConnection[Any]:
    return await psycopg.AsyncConnection.connect(url, autocommit=True)


async def _beat(config: WorkerConfig, status: _Status, connect: Connect) -> None:
    """On its own connection, so a long step can't make a live worker look dead."""
    lost = Repeated()
    while True:
        try:
            async with await connect(config.database_url) as connection:
                while True:
                    await _write_beat(connection, config, status.state)
                    lost.cleared()
                    status.changed.clear()
                    try:
                        async with asyncio.timeout(config.beat_seconds):
                            await status.changed.wait()
                    except TimeoutError:
                        pass
        except Exception as error:  # noqa: BLE001 - a lost heartbeat is logged without its message and retried
            # Retried every 2 s while the database is away, so only some attempts are logged.
            if lost.failed():
                log_event(
                    logger,
                    "worker.heartbeat_lost",
                    logging.WARNING,
                    error=error,
                    failures=lost.count,
                )
            await asyncio.sleep(min(config.beat_seconds, 2.0))


async def _pause(stop: asyncio.Event, seconds: float) -> None:
    try:
        async with asyncio.timeout(seconds):
            await stop.wait()
    except TimeoutError:
        pass


async def _run_step(
    step: Step,
    connection: CommittingConnection,
    stop: asyncio.Event,
    config: WorkerConfig,
    status: _Status,
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
        await stop_task(task)
        log_event(logger, "worker.drain_cut_short", logging.WARNING, worker=config.worker_id)
        return False
    return bool(task.result())


async def serve(
    config: WorkerConfig, step: Step, stop: asyncio.Event, *, connect: Connect = connect_database
) -> None:
    """Until `stop`: no new step starts after it, and the last beat says this worker has stopped.

    A lost database is reconnected after `idle_seconds`. `connect` is for a check's fake database.
    """
    status = _Status()
    beat = asyncio.create_task(_beat(config, status, connect))
    log_event(
        logger, "worker.started", worker=config.worker_id, claims_inference=config.claims_inference
    )
    try:
        while not stop.is_set():
            try:
                async with await connect(config.database_url) as connection:
                    while not stop.is_set():
                        try:
                            worked = await _run_step(step, connection, stop, config, status)
                        except psycopg.OperationalError:
                            raise
                        except Exception as error:  # noqa: BLE001 - a failed step is logged without its message, and the worker keeps serving
                            log_event(logger, "worker.step_failed", logging.ERROR, error=error)
                            worked = False
                        if not worked:
                            await _pause(stop, config.idle_seconds)
            except psycopg.OperationalError as error:
                log_event(logger, "worker.database_lost", logging.WARNING, error=error)
                await _pause(stop, config.idle_seconds)
    finally:
        await stop_task(beat)
        try:
            async with await connect(config.database_url) as connection:
                await _write_beat(connection, config, "stopped")
        except psycopg.OperationalError as error:
            # The stack may be stopping too. The stale heartbeat reads as absent anyway.
            log_event(logger, "worker.last_beat_lost", logging.WARNING, error=error)
        log_event(logger, "worker.stopped", worker=config.worker_id)


def install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signal_number, stop.set)


@dataclass
class _Maintenance:
    """What the maintenance step remembers between passes."""

    last_retention: float | None = None
    # The refusal last logged while routines wait, so each change is logged once.
    said: str | None = None


def maintenance_step(
    credential_check: ConnectionReadiness,
    store: PingableObjectStore | None,
    readiness: ReadinessSettings,
    retention_seconds: float = 3600,
    *,
    catalog: Catalog,
) -> Step:
    """Expired approvals, due routines and declared retention, each safe from many workers.

    A restore hold stops all three (SP-018). Otherwise a routine is admission, so it waits on the
    gate a person's run passes (LM-07, Decision 0023 E2), and the refusing code is logged when it
    changes, and `catalog` refuses an occurrence whose tools are unavailable (PK-02). Retention
    doesn't wait: it removes content, and waits on Storage by itself.
    """
    state = _Maintenance()

    async def step(connection: CommittingConnection) -> bool:
        if await is_held(connection):
            return False
        await expire_due(connection)

        async def check(workspace_id: UUID) -> str:
            return await credential_check(connection, workspace_id)

        refused = first_blocking(
            await installation_conditions(LentConnection(connection), store, readiness)
        )
        admitted = 0
        if refused is None:
            admitted = await evaluate_routines(connection, check, catalog=catalog)
            state.said = None
        elif state.said != refused.code:
            state.said = refused.code
            log_event(logger, "worker.routines_waiting", logging.WARNING, reason=refused.code)
        now = asyncio.get_running_loop().time()
        if state.last_retention is None or now - state.last_retention >= retention_seconds:
            state.last_retention = now
            await apply_all(connection, store)
        return admitted > 0

    return step


def loop_config(store: PingableObjectStore | None) -> LoopConfig:
    """What every job's binder starts from: no route until the job's own policy binds one, and the
    tool set from the composition edge, so a pass runs what the catalog lists (XMOD-01, TC-01)."""
    return LoopConfig(route=UNBOUND, object_store=store, tool_set=build_registry)


def inference_step(
    config: WorkerConfig,
    source: InferenceSource,
    store: PingableObjectStore | None,
    stop: asyncio.Event | None = None,
) -> Step:
    """Claims through `process_next`, and each job's own policy picks its route.

    A pass that raises an exception no handler classifies is recorded there and its retries are
    bounded, then the exception reaches `serve`, which logs `worker.step_failed` (Decision 0028 E4).
    """
    base = loop_config(store)

    async def step(connection: CommittingConnection) -> bool:
        # A stop can land during the maintenance before this, and a paid job shouldn't start then.
        if stop is not None and stop.is_set():
            return False
        result = await process_next(
            connection, config.database_url, config.worker_id, _unbound, base, bind=source.bind
        )
        return result is not None

    return step


def _unbound() -> NoReturn:
    raise RuntimeError("the job's binder chooses its model")


def both(first: Step, second: Step) -> Step:
    """Each runs on every pass, so a long job only delays maintenance, up to the job's own limit.

    A failing first step can't starve the second, since it may be stuck on one bad row forever.
    Losing the database still reaches `serve`, which reconnects.
    """

    async def step(connection: CommittingConnection) -> bool:
        try:
            worked = await first(connection)
        except psycopg.OperationalError:
            raise
        except Exception as error:  # noqa: BLE001 - a failed step is logged without its message, and the worker keeps serving
            log_event(logger, "worker.step_failed", logging.ERROR, error=error)
            worked = False
        return await second(connection) or worked

    return step


def inference_from_environment(
    environ: Mapping[str, str],
    database_url: str,
    store: PingableObjectStore | None,
    client_factory: Callable[[str], Any] | None,
    fetch_catalog: CatalogFetcher | None,
) -> InferenceSource:
    """Refuses to start half-configured, since a worker with no store can't verify any run."""
    context = provider_context(environ)
    if context is None or not Path(context.config_root).is_absolute():
        raise MalformedSetting(f"{INFERENCE_SWITCH} needs an absolute {CONFIG_ROOT}")
    if store is None:
        raise MalformedSetting(f"{INFERENCE_SWITCH} needs {STORAGE_URL} and the service key")
    if fetch_catalog is not None:
        context = replace(context, fetch_catalog=fetch_catalog)
    from autobots.adapters.browser_executor import BrowserExecutor

    # Used only while the executor reports qualified, which `bind` checks for each job.
    return InferenceSource(
        database_url,
        context,
        CatalogCache(context.fetch_catalog),
        client_factory,
        browser=BrowserExecutor(),
        store=store,
    )


def worker_config(environ: Mapping[str, str]) -> WorkerConfig:
    """Its identity, database and drain, read once at start. Inference is added only once its own
    configuration is complete, in `main`."""
    (url,) = require(environ, DATABASE_URL)
    drain = seconds(environ, DRAIN_SECONDS)
    return WorkerConfig(
        worker_id=f"{os.uname().nodename}-{os.getpid()}-{secrets.token_hex(3)}",
        database_url=url,
        drain_seconds=DEFAULT_DRAIN_SECONDS if drain is None else drain,
    )


async def main(
    *,
    client_factory: Callable[[str], Any] | None = None,
    fetch_catalog: CatalogFetcher | None = None,
) -> None:
    """The arguments are for a check's fake transport. Only Python can pass them, not a setting.

    Every setting is read before it serves, so a malformed one stops it at start, exit 2, instead
    of failing every pass. The environment stays the live mapping, so a key is resolved again for
    each attempt (model-gateway rule).
    """
    forbid_remote_tracing(os.environ)
    configure_logging()
    environ = os.environ
    source: InferenceSource | None = None
    try:
        config = worker_config(environ)
        readiness = ReadinessSettings.from_environment(environ)
        store = object_store(environ)
        if environ.get(INFERENCE_SWITCH) == "enabled":
            source = inference_from_environment(
                environ, config.database_url, store, client_factory, fetch_catalog
            )
    except MalformedSetting as error:
        stop_unconfigured(error)
    stop = asyncio.Event()
    # The composition edge's catalog, for the routines this process admits (XMOD-01).
    step = maintenance_step(credential_check(environ), store, readiness, catalog=catalog())
    if source is not None:
        config = replace(config, claims_inference=True)
        step = both(step, inference_step(config, source, store, stop))
    install_signal_handlers(stop)
    await serve(config, step, stop)


if __name__ == "__main__":
    asyncio.run(main())
