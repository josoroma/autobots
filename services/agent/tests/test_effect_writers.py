"""One writer for each effect state machine, guarded by its own table (refactor plan R-50: PTOL-03,
XMOD-02, PADP-13; SP-010; Decision 0029 F8).

Only application/receipts.py writes a tool receipt and only application/approvals.py an approval
request. Each status write admits only the states its command moves from, so a move outside the
table matches no row. Adapters send no SQL to the application's tables and never read ToolContext's
connection: a key comes from the context's own `key` and `setting` (refactor plan R-53, PTOL-12).
"""

import ast
import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from uuid import UUID

import pytest

from autobots.application import approvals, receipts
from autobots.application.sql import SqlParams
from autobots.domain.effects import (
    ApprovalCommand,
    ApprovalStatus,
    ReceiptCommand,
    ReceiptStatus,
    approval_sources,
    receipt_sources,
)

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"
OPERATION = "operation-1"
RUN = UUID("b0000000-0000-4000-8000-000000000002")
WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
APPROVAL = UUID("d0000000-0000-4000-8000-000000000004")
ACTOR = UUID("c0000000-0000-4000-8000-000000000003")


def writers(pattern: str) -> list[str]:
    found = re.compile(pattern)
    return sorted(
        str(path.relative_to(SOURCE))
        for path in SOURCE.rglob("*.py")
        if found.search(path.read_text())
    )


def test_only_receipts_writes_a_tool_receipt() -> None:
    assert writers(r"(update|insert into)\s+app_private\.tool_receipts") == [
        "application/receipts.py"
    ]


def test_only_approvals_writes_an_approval_request() -> None:
    assert writers(r"(update|insert into)\s+public\.approval_requests") == [
        "application/approvals.py"
    ]


def sql_constants(module: str) -> list[str]:
    """Every string constant in a module. Adjacent literals are one constant once parsed."""
    tree = ast.parse((SOURCE / module).read_text())
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


@pytest.mark.parametrize(
    ("module", "table"),
    [
        ("application/receipts.py", "app_private.tool_receipts"),
        ("application/approvals.py", "public.approval_requests"),
    ],
)
def test_every_status_write_admits_only_its_starting_states(module: str, table: str) -> None:
    statements = sql_constants(module)
    assert status_writes(statements, table)
    assert unguarded(statements, table) == []


def status_writes(statements: list[str], table: str) -> list[tuple[str, str | None]]:
    """Each UPDATE on `table` whose SET list assigns status, wherever it sits in that list, as
    (SET list, WHERE clause or None)."""
    found = []
    for statement in statements:
        update = re.fullmatch(
            rf"\s*update {re.escape(table)} set (.*?)(?: where (.*))?", statement, re.DOTALL
        )
        if update and re.search(r"(^|,)\s*status\s*=", update.group(1)):
            found.append((update.group(1), update.group(2)))
    return found


def unguarded(statements: list[str], table: str) -> list[str]:
    """The status writes whose WHERE clause doesn't admit only their starting states."""
    return [
        set_list
        for set_list, where in status_writes(statements, table)
        if where is None or "status = any(%s)" not in where
    ]


def test_the_guard_check_sees_a_literal_or_reordered_status_write() -> None:
    planted = [
        "update public.approval_requests set status = 'expired' where id = %s",
        "update public.approval_requests set decided_by = %s, status = %s where id = %s",
        "update public.approval_requests set status = %s",
        "update public.approval_requests set status = %s where id = %s and status = any(%s)",
        # Not a status write: status is only in its WHERE clause.
        "update public.approval_requests set consumed_at = now() where id = %s and status = %s",
    ]
    assert unguarded(planted, "public.approval_requests") == [
        "status = 'expired'",
        "decided_by = %s, status = %s",
        "status = %s",
    ]


class Recorder:
    """A connection that records each statement, and answers a statement holding one of `answers`'
    keys with its row, and anything else with `default`."""

    def __init__(
        self,
        answers: dict[str, tuple[object, ...] | None] | None = None,
        default: tuple[object, ...] | None = (1,),
    ) -> None:
        self.answers = answers or {}
        self.default = default
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self._row: tuple[object, ...] | None = None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    # Each answer is a tuple, read by position.
    description = None

    async def execute(self, query: str, params: SqlParams | None = None, /) -> "Recorder":
        self.statements.append((query, tuple(params) if isinstance(params, Sequence) else ()))
        self._row = next((row for part, row in self.answers.items() if part in query), self.default)
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    async def fetchall(self) -> list[tuple[object, ...]]:
        return [] if self._row is None else [self._row]

    def only(self) -> tuple[str, tuple[object, ...]]:
        [statement] = self.statements
        return statement


@pytest.mark.parametrize(
    "status", [ReceiptStatus.SUCCEEDED, ReceiptStatus.FAILED, ReceiptStatus.UNKNOWN]
)
def test_recording_an_outcome_admits_only_its_moves_starting_states(status: ReceiptStatus) -> None:
    """A success is kept whoever owns the run now; anything else speaks only for the attempt on
    record, at this generation or an earlier one."""
    connection = Recorder()
    outcome = receipts.Outcome(status, {"ok": True}, "code", "detail")
    asyncio.run(receipts.record(connection, OPERATION, outcome, 3))
    query, params = connection.only()
    assert query.startswith("update app_private.tool_receipts set status = %s")
    assert params[:5] == (status.value, json.dumps({"ok": True}), "code", "detail", OPERATION)
    assert params[5] == receipt_sources(ReceiptCommand.RECORD, status)
    fenced = status is not ReceiptStatus.SUCCEEDED
    assert ("generation <= %s" in query) is fenced
    assert params[6:] == ((3,) if fenced else ())


def test_an_attempt_records_no_return_to_started() -> None:
    with pytest.raises(ValueError, match="makes no move"):
        asyncio.run(
            receipts.record(Recorder(), OPERATION, receipts.Outcome(ReceiptStatus.STARTED), 3)
        )


def test_reopening_starts_a_new_attempt_from_anything_but_a_success() -> None:
    connection = Recorder()
    assert asyncio.run(receipts.reopen(connection, OPERATION, 4)) is True
    query, params = connection.only()
    assert "returning operation_id" in query
    assert params == (
        ReceiptStatus.STARTED.value,
        4,
        OPERATION,
        receipt_sources(ReceiptCommand.REOPEN, ReceiptStatus.STARTED),
    )
    assert asyncio.run(receipts.reopen(Recorder(default=None), OPERATION, 4)) is False


def test_a_lost_workers_started_attempts_become_unknown() -> None:
    connection = Recorder()
    asyncio.run(receipts.mark_unknown(connection, RUN, 5))
    query, params = connection.only()
    assert "generation < %s" in query
    assert params == (
        ReceiptStatus.UNKNOWN.value,
        RUN,
        receipt_sources(ReceiptCommand.MARK_UNKNOWN, ReceiptStatus.UNKNOWN),
        5,
    )


@pytest.mark.parametrize(
    ("status", "result"),
    [(ReceiptStatus.SUCCEEDED, {"reconciled": "operator"}), (ReceiptStatus.FAILED, None)],
)
def test_a_ruling_settles_only_an_unknown_outcome(
    status: ReceiptStatus, result: dict[str, str] | None
) -> None:
    connection = Recorder()
    asyncio.run(receipts.rule(connection, OPERATION, receipts.Ruling(status, "Seen it.", ACTOR)))
    query, params = connection.only()
    assert "reconciled_by = %s, reconciled_at = now()" in query
    assert params == (
        status.value,
        None if result is None else json.dumps(result),
        "Seen it.",
        ACTOR,
        OPERATION,
        receipt_sources(ReceiptCommand.RULE, status),
    )


def test_an_attempt_starts_its_receipt_once() -> None:
    connection = Recorder()
    attempt = receipts.Attempt(OPERATION, RUN, WORKSPACE, "send_note", 1, "hash", 3, True)
    assert asyncio.run(receipts.start(connection, attempt)) is True
    query, params = connection.only()
    assert "on conflict (operation_id) do nothing" in query
    assert params == (
        OPERATION,
        RUN,
        WORKSPACE,
        "send_note",
        1,
        "hash",
        ReceiptStatus.STARTED.value,
        3,
        True,
    )
    assert asyncio.run(receipts.start(Recorder(default=None), attempt)) is False


def test_cancelling_withdraws_only_pending_requests() -> None:
    connection = Recorder()
    asyncio.run(approvals.withdraw_pending(connection, RUN))
    query, params = connection.only()
    assert query.startswith("update public.approval_requests set status = %s")
    assert params == (
        ApprovalStatus.WITHDRAWN.value,
        RUN,
        approval_sources(ApprovalCommand.WITHDRAW, ApprovalStatus.WITHDRAWN),
    )


def test_an_expiry_never_overwrites_a_decision_or_a_withdrawal() -> None:
    """An expiry pass that read the request as pending before a person decided or the run was
    cancelled matches no row, so it writes nothing else: no met obligation, no event, no pause.
    Only the job row lock that every transition takes first comes before it."""
    connection = Recorder({"update public.approval_requests": None})
    assert asyncio.run(approvals.expire(connection, APPROVAL, RUN, WORKSPACE)) is False
    [(lock, locked), (query, params)] = connection.statements
    assert lock.startswith("select 1 from app_private.run_jobs") and "for update" in lock
    assert locked == (RUN,)
    assert "status = any(%s)" in query and "returning id" in query
    assert params == (
        ApprovalStatus.EXPIRED.value,
        APPROVAL,
        approval_sources(ApprovalCommand.EXPIRE, ApprovalStatus.EXPIRED),
    )


def test_an_expiry_of_a_pending_request_meets_its_wait() -> None:
    connection = Recorder({"select status from public.runs": ("running",)})
    assert asyncio.run(approvals.expire(connection, APPROVAL, RUN, WORKSPACE)) is True
    written = [query for query, _ in connection.statements]
    assert any("run_obligations set status = 'met'" in query for query in written)
    assert any(query.startswith("insert into public.run_events") for query in written)


def test_adapters_send_no_sql_to_the_applications_tables() -> None:
    """PADP-13 and XMOD-02: a run, lease, usage, approval, receipt or run-file query belongs to the
    module that owns its table, which the adapter calls."""
    found = [
        path.name
        for path in sorted((SOURCE / "adapters").rglob("*.py"))
        if re.search(r"\b(public|app_private)\.[a-z_]+", path.read_text())
    ]
    assert found == []


def connection_reads(tree: ast.AST) -> list[str]:
    """Every way a module could reach a connection attribute: any `.connection`, whatever names
    its owner, and the name as a string, as `getattr` or `attrgetter` would take it. As
    `line:source`."""
    return [
        f"{node.lineno}:{ast.unparse(node)}"
        for node in ast.walk(tree)
        if (isinstance(node, ast.Attribute) and node.attr == "connection")
        or (isinstance(node, ast.Constant) and node.value == "connection")
    ]


def test_adapters_never_read_a_connection() -> None:
    """The hand-off ratchet R-62 left at two is at zero, and adapters reach no connection at all:
    a key comes from ToolContext.key or ToolContext.setting, which resolve it in the application
    (R-53, XMOD-02). Application tools still use the connection for the tables they own."""
    found = {
        path.name: reads
        for path in sorted((SOURCE / "adapters").rglob("*.py"))
        if (reads := connection_reads(ast.parse(path.read_text())))
    }
    assert found == {}


def test_the_connection_check_sees_an_alias_or_getattr() -> None:
    planted = ast.parse(
        "async def handler(arguments: X, ctx: ToolContext) -> None:\n"
        "    await ctx.connection.execute('select 1')\n"
        "    getattr(ctx, 'connection')\n"
        "    held = ctx\n"
        "    held.connection\n"
    )
    assert sorted(read.split(":", 1)[1] for read in connection_reads(planted)) == [
        "'connection'",
        "ctx.connection",
        "held.connection",
    ]
