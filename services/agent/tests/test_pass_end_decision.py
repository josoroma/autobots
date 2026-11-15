"""How a pass ends, with no database (PRUN-03, R-34, SP-010, SP-012).

`ROWS` lists each way a pass ends: the stop code, the run's status, whether this worker still holds
the lease and the plan's state, then the step `decide` chooses. The pure table is checked first;
then `finish` takes each row's step against a fake connection whose transition behaves as
`apply_command` does under its row locks: a lost lease is refused first, then any command the
canonical table refuses.
"""

import asyncio
import contextlib
import dataclasses
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from autobots.application import run_lifecycle
from autobots.application.plans import PlanView
from autobots.application.recovery import Outstanding
from autobots.application.run_lifecycle import Decision, Ending, Observed, decide, outcome_of
from autobots.application.runs import LeaseLost, TransitionResult, VersionConflict
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus, next_status
from autobots.domain.stops import (
    COMMANDS,
    DISPOSITION,
    SETTLEMENT,
    Disposition,
    GatewayCode,
    PassOutcome,
    StopCode,
    repair_limit,
)

GOAL = GoalSpec(
    objective="Write the report",
    original_request="Write the report",
    criteria={"c1": "the report exists"},
    allowed_tools={},
    allowed_paths=[],
)
LEASE = Lease(uuid4(), uuid4(), 3, "worker", 1, "running")
RETRY_AT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Row:
    """What stopped a pass and what `finish` saw, then the step it takes, the code it carries on
    with and the command a transition applies."""

    code: str | None
    status: RunStatus
    held: bool
    ending: str
    decided: str | None
    command: RunCommand | None = None
    plan: int | None = 1
    finished: bool = True
    unmapped: bool = False


ROWS: dict[str, Row] = {
    # A lost lease writes nothing, whatever the run's status.
    "lost lease": Row(StopCode.LEASE_LOST, RunStatus.RUNNING, False, "leave", StopCode.LEASE_LOST),
    "lost lease, run cancelling": Row(
        StopCode.LEASE_LOST, RunStatus.CANCELLING, True, "leave", StopCode.LEASE_LOST
    ),
    "lost lease, run paused": Row(
        StopCode.LEASE_LOST, RunStatus.PAUSED, True, "leave", StopCode.LEASE_LOST
    ),
    # A run being cancelled is settled by the worker holding its lease, whatever stopped the pass.
    "cancelling, owner, suspend code": Row(
        StopCode.BUDGET_EXCEEDED,
        RunStatus.CANCELLING,
        True,
        "settle",
        StopCode.RUN_NOT_RUNNING,
        RunCommand.FINISH_CANCEL,
    ),
    "cancelling, owner, no code and no plan": Row(
        None,
        RunStatus.CANCELLING,
        True,
        "settle",
        StopCode.RUN_NOT_RUNNING,
        RunCommand.FINISH_CANCEL,
        plan=None,
        finished=False,
    ),
    "cancelling, owner, run_not_running": Row(
        StopCode.RUN_NOT_RUNNING,
        RunStatus.CANCELLING,
        True,
        "settle",
        StopCode.RUN_NOT_RUNNING,
        RunCommand.FINISH_CANCEL,
    ),
    "cancelling, owner, approval_pending": Row(
        StopCode.APPROVAL_PENDING,
        RunStatus.CANCELLING,
        True,
        "settle",
        StopCode.RUN_NOT_RUNNING,
        RunCommand.FINISH_CANCEL,
    ),
    # The settlement replaces the code, so a code missing from the table is not consulted or logged.
    "cancelling, owner, unmapped code": Row(
        "made_up_stop",
        RunStatus.CANCELLING,
        True,
        "settle",
        StopCode.RUN_NOT_RUNNING,
        RunCommand.FINISH_CANCEL,
    ),
    # Settling classifies what's in flight, so a worker that lost the run must not start it.
    "cancelling, lost, suspend code": Row(
        StopCode.BUDGET_EXCEEDED, RunStatus.CANCELLING, False, "leave", StopCode.LEASE_LOST
    ),
    "cancelling, lost, run_not_running": Row(
        StopCode.RUN_NOT_RUNNING, RunStatus.CANCELLING, False, "leave", StopCode.LEASE_LOST
    ),
    # The plan decides a pass that nothing stopped.
    "running, no code, plan finished": Row(
        None, RunStatus.RUNNING, True, "transition", None, RunCommand.VERIFY
    ),
    "running, no code, no plan": Row(
        None,
        RunStatus.RUNNING,
        True,
        "transition",
        StopCode.PLAN_MISSING,
        RunCommand.FAIL,
        plan=None,
        finished=False,
    ),
    "running, no code, plan unfinished": Row(
        None,
        RunStatus.RUNNING,
        True,
        "transition",
        StopCode.PLAN_INCOMPLETE,
        RunCommand.FAIL,
        plan=2,
        finished=False,
    ),
    # Otherwise the code's disposition picks the command, and an unmapped code suspends (E3).
    "running, suspend code": Row(
        StopCode.BUDGET_EXCEEDED,
        RunStatus.RUNNING,
        True,
        "transition",
        StopCode.BUDGET_EXCEEDED,
        RunCommand.SUSPEND,
    ),
    "running, fail code": Row(
        StopCode.RATE_LIMITED,
        RunStatus.RUNNING,
        True,
        "transition",
        StopCode.RATE_LIMITED,
        RunCommand.FAIL,
    ),
    "running, spent repair": Row(
        repair_limit(GatewayCode.PLAN_CYCLE),
        RunStatus.RUNNING,
        True,
        "transition",
        repair_limit(GatewayCode.PLAN_CYCLE),
        RunCommand.FAIL,
    ),
    "running, unmapped code": Row(
        "made_up_stop",
        RunStatus.RUNNING,
        True,
        "transition",
        "made_up_stop",
        RunCommand.SUSPEND,
        unmapped=True,
    ),
    # A release code applies no command and writes nothing.
    "running, run_not_running": Row(
        StopCode.RUN_NOT_RUNNING, RunStatus.RUNNING, True, "leave", StopCode.RUN_NOT_RUNNING
    ),
    "running, run_not_found": Row(
        StopCode.RUN_NOT_FOUND, RunStatus.RUNNING, True, "leave", StopCode.RUN_NOT_FOUND
    ),
    # The approval gate moved the run to its wait and finished the job, so no lease is held.
    "waiting for approval": Row(
        StopCode.APPROVAL_PENDING,
        RunStatus.WAITING_APPROVAL,
        False,
        "leave",
        StopCode.APPROVAL_PENDING,
    ),
    # A person's pause: the run waits for a resume and its job is let go, with nobody holding it.
    "paused, run_not_running": Row(
        StopCode.RUN_NOT_RUNNING, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    # The job's write keeps its generation predicate, so a worker that lost the lease changes
    # nothing.
    "paused, run_not_running, lost": Row(
        StopCode.RUN_NOT_RUNNING, RunStatus.PAUSED, False, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, approval_pending": Row(
        StopCode.APPROVAL_PENDING, RunStatus.PAUSED, False, "leave", StopCode.APPROVAL_PENDING
    ),
    "paused, run_not_found": Row(
        StopCode.RUN_NOT_FOUND, RunStatus.PAUSED, True, "leave", StopCode.RUN_NOT_FOUND
    ),
    # A pause during an assignment or a tool call: the code's command would be refused, so the
    # owner lets the job go as run_not_running and the run stays paused and resumable (R-34).
    "paused, owner, assignment_paused": Row(
        StopCode.ASSIGNMENT_PAUSED, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, owner, parent_not_running": Row(
        StopCode.PARENT_NOT_RUNNING, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, owner, outcome_unknown": Row(
        StopCode.OUTCOME_UNKNOWN, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, owner, fail code": Row(
        StopCode.STEP_LIMIT, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, owner, no code, plan finished": Row(
        None, RunStatus.PAUSED, True, "let_go", StopCode.RUN_NOT_RUNNING
    ),
    "paused, owner, no code, no plan": Row(
        None,
        RunStatus.PAUSED,
        True,
        "let_go",
        StopCode.RUN_NOT_RUNNING,
        plan=None,
        finished=False,
    ),
    "paused, owner, unmapped code": Row(
        "made_up_stop",
        RunStatus.PAUSED,
        True,
        "let_go",
        StopCode.RUN_NOT_RUNNING,
        unmapped=True,
    ),
    # Without the lease the transition is left to apply_command, which refuses it as lease_lost.
    "paused, lost, suspend code": Row(
        StopCode.BUDGET_EXCEEDED,
        RunStatus.PAUSED,
        False,
        "transition",
        StopCode.BUDGET_EXCEEDED,
        RunCommand.SUSPEND,
    ),
    # Any other status is left to apply_command, which re-validates under its row locks.
    "verifying, suspend code": Row(
        StopCode.BUDGET_EXCEEDED,
        RunStatus.VERIFYING,
        True,
        "transition",
        StopCode.BUDGET_EXCEEDED,
        RunCommand.SUSPEND,
    ),
    "queued, lost, fail code": Row(
        StopCode.RATE_LIMITED,
        RunStatus.QUEUED,
        False,
        "transition",
        StopCode.RATE_LIMITED,
        RunCommand.FAIL,
    ),
}


def _observed(row: Row) -> Observed:
    return Observed(row.status, row.held, row.plan, row.finished)


RUNNING = Observed(RunStatus.RUNNING, True, 1, True)
EVERY_CODE: tuple[str | None, ...] = (
    None,
    *DISPOSITION,
    *SETTLEMENT,
    repair_limit(GatewayCode.PLAN_CYCLE),
    "made_up_stop",
)


@pytest.mark.parametrize("name", list(ROWS))
def test_decide_each_row(name: str) -> None:
    row = ROWS[name]
    assert decide(row.code, _observed(row)) == Decision(
        Ending(row.ending), row.decided, row.command, row.unmapped
    )


def test_every_known_code_on_a_running_run_takes_its_disposition() -> None:
    for code, disposition in DISPOSITION.items():
        command = COMMANDS.get(disposition)
        ending = Ending.LEAVE if command is None else Ending.TRANSITION
        assert decide(code, RUNNING) == Decision(ending, code, command), code


def test_every_code_on_a_run_being_cancelled_is_settled_by_its_owner_alone() -> None:
    for code in EVERY_CODE:
        if code == StopCode.LEASE_LOST:
            continue
        for plan, finished in ((None, False), (2, False), (1, True)):
            owner = Observed(RunStatus.CANCELLING, True, plan, finished)
            lost = Observed(RunStatus.CANCELLING, False, plan, finished)
            assert decide(code, owner) == Decision(
                Ending.SETTLE, StopCode.RUN_NOT_RUNNING, RunCommand.FINISH_CANCEL
            ), code
            assert decide(code, lost) == Decision(Ending.LEAVE, StopCode.LEASE_LOST), code


def test_a_lost_lease_writes_nothing_whatever_the_run_is() -> None:
    for status in RunStatus:
        for held in (True, False):
            observed = Observed(status, held, None, False)
            assert decide(StopCode.LEASE_LOST, observed) == Decision(
                Ending.LEAVE, StopCode.LEASE_LOST
            ), (status, held)


def test_a_paused_run_lets_go_of_every_code_whose_command_it_would_refuse() -> None:
    """R-34: with the lease held, the job is let go as run_not_running and the run stays paused.
    Without it, `apply_command` refuses the transition as a lost lease."""
    for code in EVERY_CODE:
        decided = decide(code, RUNNING)
        owner = decide(code, Observed(RunStatus.PAUSED, True, 1, True))
        lost = decide(code, Observed(RunStatus.PAUSED, False, 1, True))
        if code == StopCode.RUN_NOT_RUNNING:
            assert owner == lost == Decision(Ending.LET_GO, StopCode.RUN_NOT_RUNNING)
        elif decided.command is not None:
            assert owner == Decision(
                Ending.LET_GO, StopCode.RUN_NOT_RUNNING, unmapped=decided.unmapped
            ), code
            assert lost == decided, code
        else:
            assert owner == lost == decided, code


def test_only_a_transition_or_a_settlement_applies_a_command() -> None:
    statuses = (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.CANCELLING, RunStatus.VERIFYING)
    for code in EVERY_CODE:
        for status in statuses:
            for held in (True, False):
                decision = decide(code, Observed(status, held, 1, True))
                applies = decision.ending in {Ending.TRANSITION, Ending.SETTLE}
                assert (decision.command is not None) is applies, (code, status, held)


def test_an_observation_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        RUNNING.status = RunStatus.PAUSED  # type: ignore[misc]  # assigning is the failure tested


@pytest.mark.parametrize(
    ("code", "outcome"),
    [
        (None, PassOutcome.CANDIDATE),
        (StopCode.APPROVAL_PENDING, PassOutcome.WAITING),
        (StopCode.LEASE_LOST, PassOutcome.LOST),
        (StopCode.RUN_NOT_RUNNING, PassOutcome.LOST),
        (StopCode.RUN_NOT_FOUND, PassOutcome.LOST),
        (StopCode.COMMAND_REFUSED, PassOutcome.LOST),
        (StopCode.BUDGET_EXCEEDED, PassOutcome.STOPPED),
        (StopCode.RATE_LIMITED, PassOutcome.STOPPED),
        (repair_limit(GatewayCode.PLAN_CYCLE), PassOutcome.STOPPED),
        (StopCode.CANCELLED, PassOutcome.STOPPED),
        (StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES, PassOutcome.STOPPED),
        ("made_up_stop", PassOutcome.STOPPED),
    ],
)
def test_the_outcome_follows_the_code(code: str | None, outcome: PassOutcome) -> None:
    assert outcome_of(code) is outcome


def test_every_release_code_reports_the_pass_lost_but_a_pending_approval() -> None:
    for code, disposition in DISPOSITION.items():
        if disposition is Disposition.RELEASE and code != StopCode.APPROVAL_PENDING:
            assert outcome_of(code) is PassOutcome.LOST, code


@dataclass
class Database:
    """The connection `finish` uses: it answers from one arranged run and records each write, and
    whether a transaction was open when it ran."""

    status: RunStatus
    held: bool
    statements: list[str] = field(default_factory=list)
    writes: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)
    stop_reasons: list[tuple[object, bool]] = field(default_factory=list)
    in_transaction: bool = False
    answer: tuple[object, ...] | None = None

    async def execute(self, statement: str, values: tuple[object, ...] = ()) -> "Database":
        self.statements.append(statement)
        if statement.startswith("update app_private.run_jobs"):
            self.writes.append((statement, tuple(values)))
        if "stop_reason" in statement:
            self.stop_reasons.append((values[1], self.in_transaction))
        self.answer = self._answer(statement)
        return self

    def _answer(self, statement: str) -> tuple[object, ...] | None:
        if statement.startswith("select r.status"):
            return (self.status.value, self.held)
        # Separate status and ownership reads are answered too, so a `finish` that makes them again
        # fails the read-once test below rather than on a missing row.
        if statement.startswith("select status from public.runs"):
            return (self.status.value,)
        if statement.startswith("select 1 from app_private.run_jobs"):
            return (1,) if self.held else None
        if statement.startswith("select version from public.runs"):
            return (4,)
        return None

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.answer

    async def fetchall(self) -> list[tuple[object, ...]]:
        return []

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.in_transaction = True
        try:
            yield None
        finally:
            self.in_transaction = False


@dataclass
class Effects:
    """What `finish` did besides its own SQL: each transition it applied and each settlement
    step."""

    calls: list[tuple[object, ...]] = field(default_factory=list)
    refusal: Exception | None = None
    retry_at: datetime | None = None
    left: Outstanding = field(default_factory=lambda: Outstanding(0, 0))


def _finish(
    monkeypatch: pytest.MonkeyPatch,
    row: Row,
    effects: Effects | None = None,
) -> tuple[Database, Effects, run_lifecycle.LoopResult]:
    """`finish` on the arranged run. Its transition is refused as `apply_command` refuses it: a
    lost lease first, then a command the canonical table refuses, unless `effects.refusal` is
    arranged."""
    database = Database(row.status, row.held)
    effects = effects or Effects()

    async def plan_view(*_: object) -> PlanView:
        remaining = () if row.finished else ("t2",)
        return PlanView(row.plan, ("t1",), remaining, ())

    async def usage_view(*_: object) -> dict[str, object]:
        return {}

    async def apply_command(
        _: object,
        *,
        command: RunCommand,
        actor: Actor,
        expected_version: int,
        generation: int | None,
        **__: object,
    ) -> TransitionResult:
        effects.calls.append(("apply", command, generation, actor, database.in_transaction))
        if effects.refusal is not None:
            raise effects.refusal
        if not database.held:
            raise LeaseLost("this worker no longer owns the run")
        following = next_status(database.status, command, actor)
        assert following is not None
        return TransitionResult(LEASE.run_id, expected_version + 1, following.value, True)

    async def settle_children(*_: object) -> datetime | None:
        effects.calls.append(("settle_children",))
        return effects.retry_at

    async def classify_interrupted(_: object, run_id: object, generation: int) -> None:
        effects.calls.append(("classify_interrupted", run_id, generation))

    async def outstanding(*_: object) -> Outstanding:
        return effects.left

    monkeypatch.setattr(run_lifecycle, "plan_view", plan_view)
    monkeypatch.setattr(run_lifecycle, "usage_view", usage_view)
    monkeypatch.setattr(run_lifecycle, "apply_command", apply_command)
    monkeypatch.setattr(run_lifecycle, "settle_children", settle_children)
    monkeypatch.setattr(run_lifecycle, "classify_interrupted", classify_interrupted)
    monkeypatch.setattr(run_lifecycle, "outstanding", outstanding)
    result = asyncio.run(run_lifecycle.finish(database, LEASE, GOAL, row.code))
    return database, effects, result


def _released(database: Database, status: str) -> bool:
    """One job write, to `status`, fenced by this lease's generation and a claimed job."""
    if len(database.writes) != 1:
        return False
    statement, values = database.writes[0]
    return (
        f"set status = '{status}'" in statement
        and "generation = %s and status = 'claimed'" in statement
        and values[-2:] == (LEASE.run_id, LEASE.generation)
    )


@pytest.mark.parametrize("name", list(ROWS))
def test_finish_takes_each_rows_step(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    row = ROWS[name]
    database, effects, result = _finish(monkeypatch, row)
    applied = [call for call in effects.calls if call[0] == "apply"]
    if row.ending == "leave":
        assert not database.writes and not applied and not database.stop_reasons
        waits = row.decided == StopCode.APPROVAL_PENDING
        expected = PassOutcome.WAITING if waits else PassOutcome.LOST
        assert (result.outcome, result.code, result.run_status) == (expected, row.decided, None)
    elif row.ending == "let_go":
        assert _released(database, "done") and not applied and not database.stop_reasons
        assert (result.outcome, result.code, result.run_status) == (
            PassOutcome.LOST,
            StopCode.RUN_NOT_RUNNING,
            None,
        )
    elif row.ending == "settle":
        # Classified before FINISH_CANCEL, this owner's receipts included (SP-010).
        assert effects.calls == [
            ("settle_children",),
            ("classify_interrupted", LEASE.run_id, LEASE.generation + 1),
            ("apply", RunCommand.FINISH_CANCEL, LEASE.generation, Actor.WORKER, True),
        ]
        assert database.stop_reasons == [(StopCode.CANCELLED, True)] and not database.writes
        assert (result.outcome, result.code, result.run_status) == (
            PassOutcome.STOPPED,
            StopCode.CANCELLED,
            RunStatus.CANCELLED.value,
        )
    else:
        assert applied == [("apply", row.command, LEASE.generation, Actor.WORKER, True)]
        assert not database.writes
        if not row.held:
            assert not database.stop_reasons
            assert (result.outcome, result.code, result.run_status) == (
                PassOutcome.LOST,
                StopCode.LEASE_LOST,
                None,
            )
            return
        assert row.command is not None
        reached = next_status(row.status, row.command, Actor.WORKER)
        assert reached is not None
        # The stop reason commits with the transition (SP-012).
        assert database.stop_reasons == [(row.decided, True)]
        expected = PassOutcome.CANDIDATE if row.decided is None else PassOutcome.STOPPED
        assert (result.outcome, result.code, result.run_status) == (
            expected,
            row.decided,
            reached.value,
        )


def test_an_unmapped_code_is_logged_only_when_its_disposition_is_consulted(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Decision 0028 E3: the warning names the code so that it can join the table."""
    for name, row in ROWS.items():
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="autobots.worker"):
            _finish(monkeypatch, row)
        warned = [record.getMessage() for record in caplog.records]
        assert warned == (["worker.stop_code_unmapped"] if row.unmapped else []), name


def test_a_refused_transition_reports_its_own_code_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A person's pause or cancel can land after `finish` looks and before the row lock. The
    transaction rolls back, so no stop reason is kept, and the pass is not this worker's any more
    (R-34)."""
    row = ROWS["running, suspend code"]
    database, effects, result = _finish(monkeypatch, row, Effects(refusal=CommandRefused("moved")))
    assert [call[1] for call in effects.calls] == [RunCommand.SUSPEND]
    assert not database.writes and not database.stop_reasons
    assert (result.outcome, result.code, result.run_status) == (
        PassOutcome.LOST,
        StopCode.COMMAND_REFUSED,
        None,
    )


@pytest.mark.parametrize(
    "refusal", [LeaseLost("lost"), VersionConflict("moved")], ids=["lease", "version"]
)
def test_a_lost_lease_or_a_moved_version_reports_lease_lost(
    monkeypatch: pytest.MonkeyPatch, refusal: Exception
) -> None:
    _, _, result = _finish(monkeypatch, ROWS["running, fail code"], Effects(refusal=refusal))
    assert (result.outcome, result.code, result.run_status) == (
        PassOutcome.LOST,
        StopCode.LEASE_LOST,
        None,
    )


def test_a_refused_cancel_settlement_reports_its_own_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = ROWS["cancelling, owner, suspend code"]
    _, effects, result = _finish(monkeypatch, row, Effects(refusal=CommandRefused("moved")))
    assert effects.calls[-1][1] is RunCommand.FINISH_CANCEL
    assert (result.outcome, result.code) == (PassOutcome.LOST, StopCode.COMMAND_REFUSED)


def test_a_child_with_a_live_owner_requeues_the_cancelling_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is classified and no transition is tried until every child has settled."""
    row = ROWS["cancelling, owner, suspend code"]
    database, effects, result = _finish(monkeypatch, row, Effects(retry_at=RETRY_AT))
    assert effects.calls == [("settle_children",)]
    assert _released(database, "queued") and database.writes[0][1][0] == RETRY_AT
    assert not database.stop_reasons
    assert (result.outcome, result.code, result.run_status) == (
        PassOutcome.WAITING,
        StopCode.CHILDREN_SETTLING,
        RunStatus.CANCELLING.value,
    )


@pytest.mark.parametrize(
    ("left", "code"),
    [
        (Outstanding(0, 0), StopCode.CANCELLED),
        (Outstanding(0, 0, unreported_charges=2), StopCode.CANCELLED),
        (Outstanding(1, 0), StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES),
        (Outstanding(0, 1), StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES),
    ],
)
def test_the_settlement_names_what_it_left_unknown(
    monkeypatch: pytest.MonkeyPatch, left: Outstanding, code: StopCode
) -> None:
    row = ROWS["cancelling, owner, suspend code"]
    database, _, result = _finish(monkeypatch, row, Effects(left=left))
    assert database.stop_reasons == [(code, True)] and result.code == code


@pytest.mark.parametrize("name", list(ROWS))
def test_finish_reads_the_run_once(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Status and ownership come from one statement, so they agree, and nothing reads them again
    (PRUN-03). The transition's version is read on its own, for `apply_command` to compare."""
    database, _, _ = _finish(monkeypatch, ROWS[name])
    reads = [
        statement
        for statement in database.statements
        if statement.startswith(("select r.status", "select status from public.runs"))
        or statement.startswith("select 1 from app_private.run_jobs")
    ]
    assert len(reads) == 1 and reads[0].startswith("select r.status"), reads
    # Ownership as `apply_command` checks it: this generation, a claimed job, a live lease.
    for predicate in (
        "j.generation = %s",
        "j.status = 'claimed'",
        "j.lease_expires_at > clock_timestamp()",
    ):
        assert predicate in reads[0], predicate
