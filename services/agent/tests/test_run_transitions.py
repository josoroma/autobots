"""The one surface that moves a run, with no database (SP-010, SP-012, PRUN-06, PRUN-07, PRUN-20).

A person's command goes through `apply_command`, the lease holder's through `apply_worker_command`
and the system's through `cascade_command`, and a claim moves its run by `claim` in the table. Each
locks the job's row before the run's, as a claim does, so two of them can't deadlock. A worker's
lease is checked under that lock before the run is read, and its stop reason commits with its
transition. Every job write a lease makes keeps its generation and claimed-job predicates, and the
active-time segments take the same fence as a sleep's discount.
"""

import ast
import contextlib
import hashlib
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from autobots.application import approvals, run_usage, worker_leases
from autobots.application.runs import (
    CommandReceipt,
    LeaseLost,
    apply_command,
    apply_worker_command,
    cascade_command,
)
from autobots.application.sql import SqlParams
from autobots.application.worker_leases import Lease
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus, next_status
from sql_fakes import Row, ScriptedRows

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"
WORKSPACE = UUID(int=1)
RUN = UUID(int=2)
ACTOR = UUID(int=3)
APPROVAL = UUID(int=4)
LEASE = Lease(RUN, WORKSPACE, 3, "worker", 1, "running")
JOB_LOCK = "select status, generation, lease_expires_at > clock_timestamp()"
RUN_LOCK = "select status, version from public.runs"
STATUS_WRITE = "update public.runs set status = %s, version = %s"
JOB_WRITE = "update app_private.run_jobs set status = %s"


@dataclass
class Database:
    """One run and its job, answered as the transitions read them, and every statement in order
    with the transaction depth it ran at."""

    status: RunStatus
    job: tuple[object, ...] | None = ("claimed", 3, True)
    version: int = 7
    unsettled: bool = False
    extra: dict[str, Row | None] = field(default_factory=dict)
    statements: list[tuple[str, Any, int]] = field(default_factory=list)
    depth: int = 0

    def _answer(self, statement: str) -> Row | None:
        for prefix, answer in self.extra.items():
            if statement.startswith(prefix):
                return answer
        answers: dict[str, Callable[[], Row | None]] = {
            "select version from public.runs": lambda: (self.version,),
            JOB_LOCK: lambda: (
                None
                if self.job is None
                else dict(zip(("status", "generation", "lease_live"), self.job, strict=True))
            ),
            RUN_LOCK: lambda: (self.status.value, self.version),
            "select status from public.runs": lambda: (self.status.value,),
            "select exists": lambda: (self.unsettled,),
            "update public.runs set event_sequence": lambda: (1,),
        }
        for prefix, found in answers.items():
            if statement.startswith(prefix):
                return found()
        return None

    async def execute(self, statement: str, values: SqlParams | None = None, /) -> ScriptedRows:
        self.statements.append((statement, () if values is None else values, self.depth))
        answer = self._answer(statement)
        return ScriptedRows([] if answer is None else [answer])

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.depth += 1
        try:
            yield None
        finally:
            self.depth -= 1

    def index(self, prefix: str) -> int:
        return next(i for i, item in enumerate(self.statements) if item[0].startswith(prefix))

    def having(self, text: str) -> list[tuple[str, Any, int]]:
        return [item for item in self.statements if text in item[0]]


@pytest.mark.asyncio
async def test_a_persons_command_locks_the_job_row_then_the_run_row() -> None:
    database = Database(RunStatus.RUNNING, job=("done", 3, None))
    result = await apply_command(
        database,
        workspace_id=WORKSPACE,
        run_id=RUN,
        command=RunCommand.PAUSE,
        expected_version=7,
    )
    assert (result.status, result.version, result.changed) == ("paused", 8, True)
    job, run = database.index(JOB_LOCK), database.index(RUN_LOCK)
    assert job < run
    assert all("for update" in database.statements[at][0] for at in (job, run))
    assert all(depth > 0 for _, _, depth in database.statements)
    [(_, values, _)] = database.having(JOB_WRITE)
    assert values == ("done", RUN)


@pytest.mark.parametrize(
    "job",
    [("claimed", 4, True), ("claimed", 3, False), ("done", 3, None), None],
    ids=["a later generation", "an expired lease", "a finished job", "no job"],
)
@pytest.mark.asyncio
async def test_a_workers_command_is_refused_before_the_run_is_read(job: tuple[object, ...]) -> None:
    database = Database(RunStatus.RUNNING, job=job)
    with pytest.raises(LeaseLost):
        await apply_worker_command(database, LEASE, RunCommand.VERIFY)
    assert not database.having(RUN_LOCK) and not database.having(STATUS_WRITE)


@pytest.mark.asyncio
async def test_a_workers_command_reads_its_version_before_the_locks() -> None:
    """So a person's command that lands between the read and the locks is a version conflict,
    and a race between them still has one winner."""
    database = Database(RunStatus.RUNNING, version=9)
    result = await apply_worker_command(database, LEASE, RunCommand.VERIFY)
    first, values, depth = database.statements[0]
    assert first.startswith("select version from public.runs") and values == (RUN,)
    assert depth == 0 and (result.status, result.version) == ("verifying", 10)


@pytest.mark.asyncio
async def test_a_workers_stop_reason_commits_with_its_transition() -> None:
    database = Database(RunStatus.RUNNING)
    await apply_worker_command(database, LEASE, RunCommand.FAIL, stop_reason="arranged")
    [(statement, values, depth)] = database.having("stop_reason")
    assert statement.startswith("insert into app_private.run_usage")
    assert values == (RUN, "arranged") and depth > 0
    assert database.index(STATUS_WRITE) < database.index("insert into app_private.run_usage")


@pytest.mark.asyncio
async def test_a_stop_reason_is_written_only_when_given() -> None:
    database = Database(RunStatus.RUNNING)
    await apply_worker_command(database, LEASE, RunCommand.VERIFY)
    assert database.having("stop_reason") == []
    database = Database(RunStatus.RUNNING)
    await apply_worker_command(database, LEASE, RunCommand.FAIL, stop_reason=None)
    [(_, values, _)] = database.having("stop_reason")
    assert values == (RUN, None)


@pytest.mark.asyncio
async def test_a_refused_workers_command_writes_no_stop_reason() -> None:
    database = Database(RunStatus.PAUSED)
    with pytest.raises(CommandRefused):
        await apply_worker_command(database, LEASE, RunCommand.VERIFY, stop_reason="x")
    assert database.having("stop_reason") == []


@pytest.mark.asyncio
async def test_a_receipt_takes_its_actor_and_key_together_and_keeps_its_bytes() -> None:
    """The scope and fingerprint a stored receipt was written under, so it still replays."""
    database = Database(RunStatus.RUNNING, job=("done", 3, None))
    receipt = CommandReceipt(ACTOR, "key-1")
    await apply_command(
        database,
        workspace_id=WORKSPACE,
        run_id=RUN,
        command=RunCommand.PAUSE,
        expected_version=7,
        receipt=receipt,
    )
    scope = (WORKSPACE, ACTOR, "pause", str(RUN), "key-1")
    fingerprint = hashlib.sha256(
        b'{"command":"pause","expected_version":7,"response":null}'
    ).hexdigest()
    [(_, locked, _)] = database.having("pg_advisory_xact_lock")
    assert locked == ("|".join(str(part) for part in scope),)
    [(_, stored, depth)] = database.having("insert into app_private.idempotency_receipts")
    assert stored[:6] == (*scope, fingerprint) and depth > 0
    plain = Database(RunStatus.RUNNING, job=("done", 3, None))
    await apply_command(
        plain,
        workspace_id=WORKSPACE,
        run_id=RUN,
        command=RunCommand.PAUSE,
        expected_version=7,
    )
    assert plain.having("idempotency_receipts") == [] and plain.having("pg_advisory") == []


@pytest.mark.asyncio
async def test_the_system_cascades_a_cancel_and_applies_no_workers_command() -> None:
    database = Database(RunStatus.RUNNING, job=("done", 3, None))
    result = await cascade_command(
        database, workspace_id=WORKSPACE, run_id=RUN, command=RunCommand.CANCEL
    )
    assert result.status == "cancelled"
    assert database.statements[0][0].startswith("select version from public.runs")
    with pytest.raises(CommandRefused):
        await cascade_command(
            Database(RunStatus.VERIFYING),
            workspace_id=WORKSPACE,
            run_id=RUN,
            command=RunCommand.COMPLETE,
        )


@pytest.mark.asyncio
async def test_a_cancel_withdraws_waits_and_cascades_inside_its_transaction() -> None:
    database = Database(RunStatus.WAITING_APPROVAL, job=("done", 3, None))
    await apply_command(
        database,
        workspace_id=WORKSPACE,
        run_id=RUN,
        command=RunCommand.CANCEL,
        expected_version=7,
    )
    for text in (
        "update public.approval_requests set status = %s",
        "response = 'cancelled'",
        "select id from public.runs where parent_run_id = %s",
    ):
        [(_, _, depth)] = database.having(text)
        assert depth > 0, text


@pytest.mark.parametrize(
    ("job", "written"),
    [(("claimed", 3, True), []), (("done", 3, None), [("done", RUN)])],
    ids=["a live owner", "no owner"],
)
@pytest.mark.asyncio
async def test_an_approval_expirys_pause_keeps_the_live_owner_rule(
    job: tuple[object, ...], written: list[tuple[object, ...]]
) -> None:
    """The system's pause leaves a live owner its job, as a person's did (Decision 0029 F5)."""
    database = Database(
        RunStatus.WAITING_APPROVAL,
        job=job,
        extra={"update public.approval_requests": (APPROVAL,)},
    )
    assert await approvals.expire(database, APPROVAL, RUN, WORKSPACE) is True
    [(_, moved, _)] = database.having(STATUS_WRITE)
    assert moved[0] == RunStatus.PAUSED.value
    assert [values for _, values, _ in database.having(JOB_WRITE)] == written


@pytest.mark.asyncio
async def test_an_expiry_locks_the_job_row_before_the_run_row() -> None:
    """As a person's cancel does, so a racing expiry and cancel can't deadlock (SP-012). The
    request's guarded update comes after the lock, and nothing touches the run row before it."""
    database = Database(
        RunStatus.WAITING_APPROVAL,
        job=("done", 3, None),
        extra={"update public.approval_requests": (APPROVAL,)},
    )
    assert await approvals.expire(database, APPROVAL, RUN, WORKSPACE) is True
    lock = database.index("select 1 from app_private.run_jobs")
    assert "for update" in database.statements[lock][0]
    assert lock == 0
    assert lock < database.index("update public.approval_requests")
    assert lock < database.index("update public.runs set event_sequence")
    assert lock < database.index(RUN_LOCK)


@pytest.mark.parametrize("expired", [False, True], ids=["decided", "expired"])
@pytest.mark.asyncio
async def test_a_decision_locks_the_job_then_the_run_then_the_request(expired: bool) -> None:
    """The order a person's cancel takes them in, as it withdraws pending requests after the job
    and the run, so a decision and a cancel can't deadlock (SP-012). The request's run is read
    first, without a lock."""
    database = Database(
        RunStatus.WAITING_APPROVAL,
        job=("done", 3, None),
        extra={
            "select run_id from public.approval_requests": (RUN,),
            "select run_id, status, argument_hash": {
                "run_id": RUN,
                "status": "pending",
                "argument_hash": "hash",
                "expired": expired,
                "arguments": "{}",
            },
            "update public.approval_requests": (APPROVAL,),
        },
    )
    decision = approvals.decide(
        database,
        workspace_id=WORKSPACE,
        actor_id=ACTOR,
        approval_id=APPROVAL,
        idempotency_key="key-1",
        decision="approve",
        argument_hash="hash",
    )
    if expired:
        with pytest.raises(approvals.ApprovalRefused):
            await decision
    else:
        assert (await decision).status == "approved"
    locks = [
        statement
        for statement, _, _ in database.statements
        if "for update" in statement and "pg_advisory" not in statement
    ]
    assert locks[0].startswith("select 1 from app_private.run_jobs")
    assert locks[1].startswith("select 1 from public.runs")
    assert locks[2].startswith("select run_id, status, argument_hash")
    found = database.index("select run_id from public.approval_requests")
    assert "for update" not in database.statements[found][0]
    assert found < database.index("select 1 from app_private.run_jobs")


@pytest.mark.asyncio
async def test_a_claim_moves_a_queued_run_by_claim_in_the_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[object, ...]] = []

    def spy(
        current: RunStatus, command: RunCommand, actor: Actor, *, has_active_work: bool = False
    ) -> RunStatus | None:
        seen.append((current, command, actor))
        return next_status(current, command, actor, has_active_work=has_active_work)

    # The name `apply_claim` calls, in the module that applies it.
    monkeypatch.setattr("autobots.application.runs.next_status", spy)
    for status, moved in (("queued", True), ("running", False)):
        seen.clear()
        database = Database(
            RunStatus(status),
            extra={
                "select 1 from app_private.installation_holds": None,
                "select j.run_id": {
                    "run_id": RUN,
                    "workspace_id": WORKSPACE,
                    "status": status,
                    "version": 1,
                },
                "update app_private.run_jobs set status = 'claimed'": (4, 2),
            },
        )
        lease = await worker_leases.claim_run(database, RUN, worker_id="w")
        assert lease is not None and lease.run_status == "running"
        writes = database.having(STATUS_WRITE)
        if moved:
            assert seen == [(RunStatus.QUEUED, RunCommand.CLAIM, Actor.WORKER)]
            assert [values[:2] for _, values, _ in writes] == [("running", 2)]
        else:
            assert seen == [] and writes == []


def _sql(path: Path) -> list[str]:
    """Every string constant in a module, adjacent literals joined as Python joins them. An
    f-string's text is joined without its fields, and its pieces aren't counted again alone."""
    tree = ast.parse(path.read_text())
    joined = [node for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)]
    pieces = {id(part) for node in joined for part in node.values}
    found = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in pieces
    ]
    found += [
        "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
        for node in joined
    ]
    return found


def test_every_job_write_a_lease_makes_keeps_its_fence() -> None:
    """Outside the transitions, under their own row lock, and the claim, which raises the
    generation, a job write names the lease's generation, and a status write a claimed job too."""
    writes = [
        (path.name, text)
        for path in sorted(SOURCE.rglob("*.py"))
        if path.name != "runs.py"
        for text in _sql(path)
        if re.search(r"update app_private\.run_jobs\b", text)
        and "generation = generation + 1" not in text
    ]
    assert writes, "the scan found no job writes"
    for name, text in writes:
        assert re.search(r"\bgeneration = %s", text), (name, text)
        if re.search(r"set status = ", text):
            assert re.search(r"\bstatus = 'claimed'", text.split(" where ", 1)[1]), (name, text)


def test_job_statuses_are_written_only_by_the_transitions_and_the_lease_helpers() -> None:
    writers = sorted(
        {
            path.relative_to(SOURCE).as_posix()
            for path in SOURCE.rglob("*.py")
            for text in _sql(path)
            if re.search(r"update app_private\.run_jobs( j)? set status", text)
        }
    )
    assert writers == ["application/runs.py", "application/worker_leases.py"]


def _fence(statement: str) -> str:
    match = re.search(r"exists \(select 1 from app_private\.run_jobs j where [^)]*\)", statement)
    assert match is not None, statement
    return match.group(0)


@pytest.mark.parametrize("write", [run_usage.begin_segment, run_usage.end_segment])
@pytest.mark.asyncio
async def test_a_segment_write_takes_the_fence_a_sleeps_discount_takes(
    write: Callable[[Any, Any], Any],
) -> None:
    """A worker that lost the run can't start or end the new owner's segment (PRUN-20)."""
    discount = Database(RunStatus.RUNNING)
    await run_usage.discount_sleep(discount, LEASE, 5.0)
    database = Database(RunStatus.RUNNING)
    await write(database, LEASE)
    [(statement, values, _)] = database.statements
    assert _fence(statement) == _fence(discount.statements[0][0])
    assert values[-2:] == (RUN, LEASE.generation)


def test_only_model_admission_writes_the_ledger() -> None:
    writers = sorted(
        {
            path.relative_to(SOURCE).as_posix()
            for path in SOURCE.rglob("*.py")
            for text in _sql(path)
            if re.search(r"(update|insert into) app_private\.model_invocations\b", text)
        }
    )
    assert writers == ["application/model_admission.py"]
