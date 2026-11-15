"""A pass that raises an exception no handler classifies is recorded and bounded, with no database
(Decision 0028 E4, SP-012, PRUN-14, XERR-10).

The job keeps the count of consecutive failed passes and the last one's module-qualified type,
never its message. Below the bound it is requeued after 30 s, then 60 s; the third consecutive
failure suspends the run with `worker_failed` through `apply_command`, so it is paused and
resumable. A completed pass resets the count, and so does a person's resume. Cancellation is a
BaseException, so it propagates with nothing recorded.
"""

import asyncio
import contextlib
import json
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from autobots.application import goal_loop, run_lifecycle, runs
from autobots.application.run_lifecycle import (
    FailureEnding,
    LoopConfig,
    LoopResult,
    PassFailure,
    record_failure,
)
from autobots.application.runs import LeaseLost, TransitionResult
from autobots.application.worker_leases import (
    FAILURE_BOUND,
    FAILURE_TYPE_LIMIT,
    RETRY_DELAYS_SECONDS,
    Lease,
    failure_type,
    retry_delay,
)
from autobots.domain.models import ModelRoute
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus
from autobots.domain.stops import PassOutcome, StopCode
from autobots.operations.logs import JsonFormatter

MIGRATION = (
    Path(__file__).resolve().parents[3] / "supabase/migrations/20261114000055_run_job_failures.sql"
)
LEASE = Lease(uuid4(), uuid4(), 3, "worker", 1, "running")
SECRET = "sk-or-planted-in-a-message"


class ArrangedDefect(Exception):
    """A defect that no handler in the pass classifies."""


@dataclass
class Job:
    """What the job's columns hold before a failure is recorded."""

    generation: int = LEASE.generation
    status: str = "claimed"
    failed_attempts: int = 0
    last_failure_type: str | None = None
    delay: float | None = None


@dataclass
class Database:
    """The worker's connection as recording a failure uses it: one job and its run, every
    statement, and whether a transaction was open for each write."""

    job: Job = field(default_factory=Job)
    run_status: RunStatus = RunStatus.RUNNING
    statements: list[tuple[str, tuple[object, ...], bool]] = field(default_factory=list)
    stop_reasons: list[object] = field(default_factory=list)
    depth: int = 0
    answer: tuple[object, ...] | None = None

    def _fenced(self, values: tuple[object, ...]) -> bool:
        return (
            self.job.status == "claimed"
            and values[-2] == LEASE.run_id
            and values[-1] == self.job.generation
        )

    async def execute(self, statement: str, values: tuple[object, ...] = ()) -> "Database":
        self.statements.append((statement, tuple(values), self.depth > 0))
        self.answer = None
        if statement.startswith("update app_private.run_jobs j set failed_attempts"):
            if self._fenced(values):
                self.job.failed_attempts += 1
                self.job.last_failure_type = str(values[0])
                self.answer = (self.job.failed_attempts, self.run_status.value)
        elif statement.startswith("update app_private.run_jobs set status = 'queued'"):
            if self._fenced(values):
                self.job.status, self.job.delay = "queued", float(str(values[0]))
        elif statement.startswith("update app_private.run_jobs set status = 'done'"):
            if self._fenced(values):
                self.job.status = "done"
        elif statement.startswith("select version from public.runs"):
            self.answer = (4,)
        elif "stop_reason" in statement:
            self.stop_reasons.append(values[1])
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.answer

    async def fetchall(self) -> list[tuple[object, ...]]:
        return []

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.depth += 1
        try:
            yield None
        finally:
            self.depth -= 1

    def job_writes(self) -> list[tuple[str, tuple[object, ...], bool]]:
        return [item for item in self.statements if item[0].startswith("update app_private.run_")]


@dataclass
class Transitions:
    """Each `apply_command` the recording applied, and a refusal to raise instead."""

    applied: list[dict[str, object]] = field(default_factory=list)
    refusal: Exception | None = None


def _record(
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    error: Exception,
    transitions: Transitions | None = None,
) -> PassFailure:
    """`record_failure` against the arranged job, its transition behaving as `apply_command` does
    under its row locks: a suspension leaves the run paused and its job done."""
    transitions = transitions or Transitions()

    async def apply_command(connection: object, **fields: object) -> TransitionResult:
        assert database.depth > 0, "the suspension commits with the count"
        transitions.applied.append(fields)
        if transitions.refusal is not None:
            raise transitions.refusal
        database.run_status, database.job.status = RunStatus.PAUSED, "done"
        return TransitionResult(LEASE.run_id, 5, RunStatus.PAUSED.value, True)

    monkeypatch.setattr(run_lifecycle, "apply_command", apply_command)
    return asyncio.run(record_failure(database, LEASE, error))


def test_the_bound_is_three_consecutive_failures_with_a_30_then_60_second_backoff() -> None:
    assert FAILURE_BOUND == 3
    assert RETRY_DELAYS_SECONDS == (30.0, 60.0)
    assert len(RETRY_DELAYS_SECONDS) == FAILURE_BOUND - 1
    assert [retry_delay(count) for count in (1, 2, 3, 4)] == [30.0, 60.0, None, None]


def test_the_stored_type_is_module_qualified_and_never_the_message() -> None:
    def local() -> Exception:
        class Inner(Exception):
            pass

        return Inner(SECRET)

    assert failure_type(RuntimeError(SECRET)) == "builtins.RuntimeError"
    assert failure_type(ArrangedDefect(SECRET)) == f"{__name__}.ArrangedDefect"
    nested = failure_type(local())
    assert nested.endswith(".local.<locals>.Inner") and SECRET not in nested
    long = type("A" * 300, (Exception,), {})
    assert len(failure_type(long())) == FAILURE_TYPE_LIMIT
    odd = type("Odd", (Exception,), {"__module__": "weird module-é"})
    assert failure_type(odd()) == "weird_module__.Odd"


def test_every_stored_type_passes_the_columns_check() -> None:
    """The migration's check refuses anything but a qualified name, so no message can be stored,
    and every name `failure_type` builds passes it, so recording a failure can't fail on it."""
    sql = MIGRATION.read_text()
    found = re.search(r"last_failure_type ~ '([^']+)'", sql)
    assert found is not None
    pattern = re.compile(found.group(1))
    odd = type("Odd", (Exception,), {"__module__": "weird module-é"})
    long = type("A" * 300, (Exception,), {})
    for error in (RuntimeError(SECRET), ArrangedDefect(), long(), odd()):
        assert pattern.fullmatch(failure_type(error)), failure_type(error)
    assert not pattern.fullmatch("builtins.RuntimeError: " + SECRET)
    assert f"{{1,{FAILURE_TYPE_LIMIT}}}" in found.group(1)


def test_a_first_and_second_failure_requeue_the_job_after_30_then_60_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database()
    transitions = Transitions()
    first = _record(monkeypatch, database, ArrangedDefect(SECRET), transitions)
    assert first == PassFailure(FailureEnding.RETRY, 1, 30.0)
    assert (database.job.status, database.job.delay) == ("queued", 30.0)
    assert database.job.last_failure_type == f"{__name__}.ArrangedDefect"
    # The next claim, for which the same lease stands in.
    database.job.status = "claimed"
    second = _record(monkeypatch, database, ArrangedDefect(SECRET), transitions)
    assert second == PassFailure(FailureEnding.RETRY, 2, 60.0)
    assert (database.job.failed_attempts, database.job.delay) == (2, 60.0)
    assert transitions.applied == [] and database.stop_reasons == []


def test_the_third_consecutive_failure_suspends_the_run_with_worker_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(job=Job(failed_attempts=2))
    transitions = Transitions()
    failure = _record(monkeypatch, database, ArrangedDefect(SECRET), transitions)
    assert failure == PassFailure(FailureEnding.SUSPENDED, 3)
    [applied] = transitions.applied
    assert applied["command"] is RunCommand.SUSPEND
    assert applied["actor"] is Actor.WORKER
    assert applied["generation"] == LEASE.generation
    assert database.stop_reasons == [StopCode.WORKER_FAILED]
    # Paused and resumable, its job done: nothing requeues it.
    assert (database.run_status, database.job.status) == (RunStatus.PAUSED, "done")
    assert not [item for item in database.statements if "status = 'queued'" in item[0]]


def test_a_worker_that_lost_the_run_records_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    for job in (Job(generation=LEASE.generation + 1), Job(status="done")):
        database = Database(job=job)
        transitions = Transitions()
        failure = _record(monkeypatch, database, ArrangedDefect(SECRET), transitions)
        assert failure == PassFailure(FailureEnding.LOST)
        assert (database.job.failed_attempts, database.job.last_failure_type) == (0, None)
        assert len(database.job_writes()) == 1 and transitions.applied == []


def test_a_run_a_person_paused_lets_its_job_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """Below the bound or at it: the person's pause stands, and their resume queues the job."""
    for count in (0, 2):
        database = Database(job=Job(failed_attempts=count), run_status=RunStatus.PAUSED)
        transitions = Transitions()
        failure = _record(monkeypatch, database, ArrangedDefect(), transitions)
        assert failure == PassFailure(FailureEnding.LET_GO, count + 1)
        assert database.job.status == "done" and transitions.applied == []


@pytest.mark.parametrize(
    "refusal",
    [CommandRefused("a person's command came first"), LeaseLost("the lease lapsed")],
    ids=["refused", "lapsed"],
)
def test_a_suspension_that_cant_apply_requeues_after_the_longest_backoff(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception
) -> None:
    """A lapsed lease can't apply a suspension, and a person's command can move the run first: the
    job is requeued after 60 s so that a later pass suspends the run."""
    database = Database(job=Job(failed_attempts=2))
    failure = _record(monkeypatch, database, ArrangedDefect(), Transitions(refusal=refusal))
    assert failure == PassFailure(FailureEnding.RETRY, 3, RETRY_DELAYS_SECONDS[-1])
    assert (database.job.status, database.job.delay) == ("queued", 60.0)
    assert database.stop_reasons == []


@pytest.mark.parametrize(
    ("settled", "expected"),
    [
        (StopCode.CANCELLED, PassFailure(FailureEnding.CANCELLED, 3)),
        (None, PassFailure(FailureEnding.RETRY, 3)),
    ],
    ids=["settled", "children_still_owned"],
)
def test_a_run_being_cancelled_settles_its_cancellation_at_the_bound(
    monkeypatch: pytest.MonkeyPatch, settled: str | None, expected: PassFailure
) -> None:
    """A run a person is cancelling can't be suspended, so at the bound its cancellation is settled
    as finish settles it, and the retries end (SP-010, SP-012). A child still owned elsewhere
    leaves the job requeued by the settlement, as finish's does."""
    database = Database(job=Job(failed_attempts=2), run_status=RunStatus.CANCELLING)
    settles: list[object] = []

    async def settle(connection: object, lease: object) -> str | None:
        settles.append(lease)
        return settled

    commands: list[object] = []

    async def transition(
        connection: object, lease: object, command: RunCommand, code: str | None
    ) -> tuple[str | None, str | None]:
        commands.append((command, code))
        return code, RunStatus.CANCELLED.value

    monkeypatch.setattr(run_lifecycle, "_settle", settle)
    monkeypatch.setattr(run_lifecycle, "_transition", transition)
    failure = asyncio.run(record_failure(database, LEASE, ArrangedDefect()))
    assert failure == expected
    assert settles == [LEASE]
    if settled is None:
        assert commands == []
    else:
        assert commands == [(RunCommand.FINISH_CANCEL, StopCode.CANCELLED)]


def test_every_job_write_keeps_the_generation_fence_in_one_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for arranged in (
        Database(),
        Database(job=Job(failed_attempts=2)),
        Database(run_status=RunStatus.PAUSED),
    ):
        _record(monkeypatch, arranged, ArrangedDefect())
        writes = arranged.job_writes()
        assert writes
        for statement, values, in_transaction in writes:
            assert "generation = %s and" in statement and "status = 'claimed'" in statement
            assert values[-2:] == (LEASE.run_id, LEASE.generation) and in_transaction


def test_the_log_names_the_run_and_the_error_type_and_never_its_message(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="autobots.worker"):
        _record(monkeypatch, Database(), ArrangedDefect(SECRET))
        _record(monkeypatch, Database(job=Job(failed_attempts=2)), ArrangedDefect(SECRET))
    retried, suspended = caplog.records
    assert (retried.levelno, suspended.levelno) == (logging.WARNING, logging.ERROR)
    lines = [json.loads(JsonFormatter().format(record)) for record in caplog.records]
    for line in lines:
        assert line["event"] == "run.pass_failed"
        assert line["error_type"] == f"{__name__}.ArrangedDefect"
        assert line["run"] == f"{str(LEASE.run_id)[:8]}…"
        assert SECRET not in json.dumps(line)
    first, third = lines
    assert (first["attempt"], first["ending"], first["retry_seconds"]) == (1, "retry", 30.0)
    assert (third["attempt"], third["ending"]) == (3, "suspended")
    assert "retry_seconds" not in third


RESULT = LoopResult(PassOutcome.STOPPED, "plan_missing", "failed", None, (), (), (), {})


@dataclass
class Dispatch:
    """`process_next` claiming LEASE, with its drive, recording and reset replaced: each failure
    it recorded and each lease whose count it reset."""

    recorded: list[tuple[Lease, BaseException]] = field(default_factory=list)
    reset: list[Lease] = field(default_factory=list)

    async def record(self, _: object, lease: Lease, error: Exception) -> PassFailure:
        self.recorded.append((lease, error))
        return PassFailure(FailureEnding.RETRY, 1, 30.0)

    async def reset_failures(self, _: object, lease: Lease) -> None:
        self.reset.append(lease)


def _dispatch(
    monkeypatch: pytest.MonkeyPatch,
    drive: Callable[[], Awaitable[LoopResult]],
    bind: goal_loop.JobBinder | None = None,
) -> tuple[Dispatch, Callable[[], LoopResult | None]]:
    """The replaced `process_next`, and a call that runs it once."""
    seen = Dispatch()

    async def no(_: object) -> bool:
        return False

    async def yes(_: object) -> bool:
        return True

    async def nothing(_: object) -> None:
        return None

    async def claim(_: object, **__: object) -> Lease:
        return LEASE

    async def drive_lease(*_: object) -> LoopResult:
        return await drive()

    for name, value in {
        "is_held": no,
        "adapter_qualified": yes,
        "expire_due": nothing,
        "claim_next": claim,
        "drive_lease": drive_lease,
        "record_failure": seen.record,
        "reset_failures": seen.reset_failures,
    }.items():
        monkeypatch.setattr(goal_loop, name, value)
    config = LoopConfig(route=ModelRoute("executor", "openrouter_terra", "fixture/model", 1))

    def run() -> LoopResult | None:
        return asyncio.run(
            goal_loop.process_next(object(), "unused", "w", object, config, bind=bind)
        )

    return seen, run


def test_a_failed_pass_is_recorded_and_its_own_error_still_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker's serve loop still logs it as `worker.step_failed`, which qualifiers count."""
    error = ArrangedDefect(SECRET)

    async def drive() -> LoopResult:
        raise error

    seen, run = _dispatch(monkeypatch, drive)
    with pytest.raises(ArrangedDefect) as raised:
        run()
    assert raised.value is error
    assert seen.recorded == [(LEASE, error)] and seen.reset == []


def test_a_failing_binder_is_recorded_too(monkeypatch: pytest.MonkeyPatch) -> None:
    error = ArrangedDefect()

    async def drive() -> LoopResult:
        raise AssertionError("no drive after a failed bind")

    async def bind(*_: object) -> tuple[Callable[[], object], LoopConfig]:
        raise error

    seen, run = _dispatch(monkeypatch, drive, bind)
    with pytest.raises(ArrangedDefect):
        run()
    assert seen.recorded == [(LEASE, error)] and seen.reset == []


@pytest.mark.parametrize(
    "error",
    [asyncio.CancelledError(), LeaseLost("another owner")],
    ids=["cancelled", "lease-lost"],
)
def test_cancellation_and_a_lost_lease_propagate_with_nothing_recorded(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    """Cancellation is a BaseException (DH-06), and a lost lease is not this pass's defect: the
    next owner's generation fences it either way (SP-012)."""

    async def drive() -> LoopResult:
        raise error

    seen, run = _dispatch(monkeypatch, drive)
    with pytest.raises(type(error)):
        run()
    assert seen.recorded == [] and seen.reset == []


def test_a_completed_pass_resets_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def drive() -> LoopResult:
        return RESULT

    seen, run = _dispatch(monkeypatch, drive)
    assert run() is RESULT
    assert seen.reset == [LEASE] and seen.recorded == []


@dataclass
class Commands:
    """The connection `apply_command` uses, for one run in `status` whose job nobody holds."""

    status: RunStatus
    statements: list[str] = field(default_factory=list)
    answer: tuple[object, ...] | None = None

    async def execute(self, statement: str, values: tuple[object, ...] = ()) -> "Commands":
        self.statements.append(statement)
        self.answer = None
        if statement.startswith("select status, generation"):
            self.answer = ("done", 3, None)
        elif statement.startswith("select status, version"):
            self.answer = (self.status.value, 7)
        elif statement.startswith("select exists"):
            self.answer = (False,)
        elif statement.startswith("update public.runs set event_sequence"):
            self.answer = (2,)
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.answer

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield None


def _command(status: RunStatus, command: RunCommand) -> list[str]:
    database = Commands(status)
    asyncio.run(
        runs.apply_command(
            database,
            workspace_id=UUID(int=1),
            run_id=LEASE.run_id,
            command=command,
            actor=Actor.USER,
            expected_version=7,
        )
    )
    return [item for item in database.statements if "failed_attempts" in item]


def test_a_persons_resume_resets_the_count_and_their_pause_does_not() -> None:
    assert _command(RunStatus.PAUSED, RunCommand.RESUME) == [
        "update app_private.run_jobs set failed_attempts = 0 where run_id = %s"
    ]
    assert _command(RunStatus.RUNNING, RunCommand.PAUSE) == []
