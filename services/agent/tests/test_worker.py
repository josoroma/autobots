"""The worker process's entry point and its step composition, without a database. Split from
test_worker_inference.py by module (PTST-04)."""

import asyncio

import psycopg
import pytest

from autobots.operations import worker


def test_the_switch_needs_its_configuration_rather_than_starting_half_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTOBOTS_CONFIG_ROOT", raising=False)
    with pytest.raises(SystemExit, match="AUTOBOTS_CONFIG_ROOT"):
        worker.inference_from_environment("postgresql://unused", object(), None, None)
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", "/nonexistent")
    with pytest.raises(SystemExit, match="service key"):
        worker.inference_from_environment("postgresql://unused", None, None, None)


def test_a_failing_first_step_does_not_starve_the_second() -> None:
    async def broken(_: object) -> bool:
        raise RuntimeError("arranged")

    async def working(_: object) -> bool:
        return True

    async def go() -> bool:
        return await worker.both(broken, working)(None)

    assert asyncio.run(go()) is True


def test_losing_the_database_still_reaches_the_serve_loop() -> None:
    async def lost(_: object) -> bool:
        raise psycopg.OperationalError("arranged")

    async def working(_: object) -> bool:
        raise AssertionError("no second step on a lost connection")

    async def go() -> bool:
        return await worker.both(lost, working)(None)

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(go())


def test_a_relative_configuration_root_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", "relative/path")
    with pytest.raises(SystemExit, match="absolute"):
        worker.inference_from_environment("postgresql://unused", object(), None, None)


def test_both_steps_run_and_either_one_counts_as_work() -> None:
    calls: list[str] = []

    def step(name: str, worked: bool) -> worker.Step:
        async def inner(_: object) -> bool:
            calls.append(name)
            return worked

        return inner

    async def run_both(first: bool, second: bool) -> bool:
        return await worker.both(step("first", first), step("second", second))(None)

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
