"""The worker process's entry point and its step composition, without a database. Split from
test_worker_inference.py by module (PTST-04)."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import cast

import psycopg
import pytest

from autobots.application.artifacts import PingableObjectStore
from autobots.application.readiness import MalformedSetting
from autobots.application.sql import SqlParams
from autobots.operations import worker
from sql_fakes import ScriptedConnection, ScriptedRows

URL = "postgresql://unused"


def test_the_switch_needs_its_configuration_rather_than_starting_half_ready() -> None:
    with pytest.raises(MalformedSetting, match="AUTOBOTS_CONFIG_ROOT"):
        worker.inference_from_environment(
            {}, URL, cast("PingableObjectStore", object()), None, None
        )
    environ = {"AUTOBOTS_CONFIG_ROOT": "/nonexistent"}
    with pytest.raises(MalformedSetting, match="service key"):
        worker.inference_from_environment(environ, URL, None, None, None)


def test_a_failing_first_step_does_not_starve_the_second() -> None:
    async def broken(_: object) -> bool:
        raise RuntimeError("arranged")

    async def working(_: object) -> bool:
        return True

    async def go() -> bool:
        return await worker.both(broken, working)(ScriptedConnection())

    assert asyncio.run(go()) is True


def test_losing_the_database_still_reaches_the_serve_loop() -> None:
    async def lost(_: object) -> bool:
        raise psycopg.OperationalError("arranged")

    async def working(_: object) -> bool:
        raise AssertionError("no second step on a lost connection")

    async def go() -> bool:
        return await worker.both(lost, working)(ScriptedConnection())

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(go())


def test_a_relative_configuration_root_refuses_to_start() -> None:
    environ = {"AUTOBOTS_CONFIG_ROOT": "relative/path"}
    with pytest.raises(MalformedSetting, match="absolute"):
        worker.inference_from_environment(
            environ, URL, cast("PingableObjectStore", object()), None, None
        )


def test_both_steps_run_and_either_one_counts_as_work() -> None:
    calls: list[str] = []

    def step(name: str, worked: bool) -> worker.Step:
        async def inner(_: object) -> bool:
            calls.append(name)
            return worked

        return inner

    async def run_both(first: bool, second: bool) -> bool:
        return await worker.both(step("first", first), step("second", second))(ScriptedConnection())

    assert asyncio.run(run_both(False, True)) is True
    assert calls == ["first", "second"]
    assert asyncio.run(run_both(True, False)) is True
    assert asyncio.run(run_both(False, False)) is False


def test_the_entry_point_gives_the_inference_step_the_stop_its_signals_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stop that lands during maintenance keeps the next paid job from starting, so the step
    has to watch the event the signal handlers set (PTST-08)."""
    seen: dict[str, object] = {}
    source = object()

    def inference_step(
        config: worker.WorkerConfig, given: object, store: object, stop: asyncio.Event | None
    ) -> worker.Step:
        seen.update(config=config, source=given, store=store, stop=stop)

        async def step(_: object) -> bool:
            return False

        return step

    async def serve(config: worker.WorkerConfig, step: worker.Step, stop: asyncio.Event) -> None:
        seen.update(served=stop)

    monkeypatch.setenv("AUTOBOTS_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv(worker.INFERENCE_SWITCH, "enabled")
    for name in ("AUTOBOTS_SUPABASE_URL", "AUTOBOTS_CONFIG_ROOT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(worker, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker, "inference_from_environment", lambda *_: source)
    monkeypatch.setattr(worker, "inference_step", inference_step)
    monkeypatch.setattr(worker, "install_signal_handlers", lambda stop: seen.update(signals=stop))
    monkeypatch.setattr(worker, "serve", serve)
    asyncio.run(worker.main())
    assert isinstance(seen["stop"], asyncio.Event)
    assert seen["stop"] is seen["signals"] is seen["served"]
    assert seen["source"] is source and seen["store"] is None
    config = seen["config"]
    assert isinstance(config, worker.WorkerConfig) and config.claims_inference


def test_the_entry_point_hands_the_live_environment_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never a copy, so a key is resolved again for each attempt (model-gateway rule)."""
    import os

    given: list[object] = []

    def inference(environ: object, *_rest: object) -> object:
        given.append(environ)
        return object()

    async def serve(*_args: object, **_options: object) -> None:
        return None

    monkeypatch.setenv("AUTOBOTS_DATABASE_URL", URL)
    monkeypatch.setenv(worker.INFERENCE_SWITCH, "enabled")
    monkeypatch.setattr(worker, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker, "inference_from_environment", inference)
    monkeypatch.setattr(worker, "install_signal_handlers", lambda _stop: None)
    monkeypatch.setattr(worker, "serve", serve)
    asyncio.run(worker.main())
    assert given == [os.environ] and given[0] is os.environ


@pytest.mark.parametrize(
    ("settings", "said"),
    [
        ({}, "ERROR: set AUTOBOTS_DATABASE_URL"),
        (
            {"AUTOBOTS_DATABASE_URL": URL, "AUTOBOTS_WORKER_DRAIN_SECONDS": "soon"},
            "ERROR: AUTOBOTS_WORKER_DRAIN_SECONDS must be a number of seconds",
        ),
        (
            {"AUTOBOTS_DATABASE_URL": URL, "AUTOBOTS_WORKER_INFERENCE": "enabled"},
            "ERROR: AUTOBOTS_WORKER_INFERENCE needs an absolute AUTOBOTS_CONFIG_ROOT",
        ),
    ],
)
def test_a_setting_it_cant_start_with_stops_it_before_it_serves_with_exit_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    settings: dict[str, str],
    said: str,
) -> None:
    """POPS-14: not configured is exit 2, as for every entry point, and only the name is said."""

    async def never(*_args: object, **_options: object) -> None:
        raise AssertionError("it must stop before it serves")

    for name in (
        "AUTOBOTS_DATABASE_URL",
        "AUTOBOTS_WORKER_DRAIN_SECONDS",
        "AUTOBOTS_WORKER_INFERENCE",
        "AUTOBOTS_CONFIG_ROOT",
        "AUTOBOTS_MIN_FREE_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(worker, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker, "serve", never)
    with pytest.raises(SystemExit) as stopped:
        asyncio.run(worker.main())
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert error.startswith(said) and "soon" not in error and URL not in error


def test_the_drain_is_read_once_with_its_default() -> None:
    assert worker.worker_config({"AUTOBOTS_DATABASE_URL": URL}).drain_seconds == 30.0
    read = worker.worker_config(
        {"AUTOBOTS_DATABASE_URL": URL, "AUTOBOTS_WORKER_DRAIN_SECONDS": "0"}
    )
    assert (read.database_url, read.drain_seconds, read.claims_inference) == (URL, 0.0, False)


# The serve loop over a fake database (POPS-19)


class FakeDatabase:
    """Hands out connections, after refusing the first `failures`, and keeps each heartbeat state
    written, in order."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.opened = 0
        self.beats: list[str] = []

    async def connect(self, _url: str) -> "FakeConnection":
        self.opened += 1
        if self.failures:
            self.failures -= 1
            raise psycopg.OperationalError("arranged")
        return FakeConnection(self)


class FakeConnection:
    autocommit = True

    def __init__(self, database: FakeDatabase) -> None:
        self.database = database

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def commit(self) -> None:
        return None

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        if "worker_heartbeats" in query and isinstance(params, Sequence):
            self.database.beats.append(str(params[1]))
        return ScriptedRows()


def quick_config(drain_seconds: float = 30.0) -> worker.WorkerConfig:
    return worker.WorkerConfig(
        "fixture-worker", URL, idle_seconds=0.01, beat_seconds=0.01, drain_seconds=drain_seconds
    )


def test_a_lost_database_is_reconnected_and_the_last_beat_says_stopped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    database = FakeDatabase(failures=1)
    ran: list[object] = []

    async def go() -> None:
        stop = asyncio.Event()

        async def step(connection: object) -> bool:
            ran.append(connection)
            stop.set()
            return True

        await worker.serve(quick_config(), step, stop, connect=database.connect)

    caplog.set_level("INFO", logger="autobots.worker")
    asyncio.run(go())
    events = [record.getMessage() for record in caplog.records]
    assert "worker.database_lost" in events and events[-1] == "worker.stopped"
    assert len(ran) == 1 and isinstance(ran[0], FakeConnection)
    assert database.beats[-1] == "stopped"
    # The refused one, the serve loop's, at least one heartbeat's, and the last beat's.
    assert database.opened >= 4


def test_a_step_still_running_when_the_drain_ends_is_cut_short(
    caplog: pytest.LogCaptureFixture,
) -> None:
    status = worker._Status()

    async def slow(_connection: object) -> bool:
        await asyncio.sleep(10)
        return True

    async def go() -> bool:
        stop = asyncio.Event()
        stop.set()
        return await worker._run_step(
            slow, ScriptedConnection(), stop, quick_config(drain_seconds=0.01), status
        )

    caplog.set_level("INFO", logger="autobots.worker")
    assert asyncio.run(go()) is False
    assert status.state == "draining"
    events = [record.getMessage() for record in caplog.records]
    assert events == ["worker.draining", "worker.drain_cut_short"]


def test_a_step_that_ends_within_the_drain_keeps_its_result() -> None:
    status = worker._Status()

    async def quick(_connection: object) -> bool:
        await asyncio.sleep(0.01)
        return True

    async def go() -> bool:
        stop = asyncio.Event()
        stop.set()
        return await worker._run_step(
            quick, ScriptedConnection(), stop, quick_config(drain_seconds=5), status
        )

    assert asyncio.run(go()) is True
