"""What the tool gateway keeps when a tool fails in a way it didn't choose (R-25, XERR-02, PTOL-10).

An effect's receipt says why its outcome is unknown: the tool's own category, a timeout or the
defect's type, in the existing `failure_detail`. Reads and review denials keep no receipt, so they
get the private log line only. Outcomes, codes, retries and receipt statuses are as before.
"""

import asyncio
import contextlib
import gc
import io
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from uuid import UUID

import pytest
from pydantic import BaseModel

from autobots.adapters import github_pulls
from autobots.adapters.github_issues import UnclearReply
from autobots.application.bounded import stop_task
from autobots.application.tool_gateway import (
    ApprovalPolicy,
    OutcomeUnknown,
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolGateway,
    ToolRegistry,
    ToolResult,
    ToolScope,
)
from autobots.domain.tools import OperationClass, ToolOutcome
from autobots.operations.logs import JsonFormatter

WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
RUN = UUID("b0000000-0000-4000-8000-000000000002")
GENERATION = 3
PLANTED = "sk-or-v1-planted0123456789 postgresql://user:hunter2@host/db"


class Note(BaseModel):
    text: str


class Saved(BaseModel):
    saved: bool


class Cursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._row


# The rows the gateway's other statements read, for a run this worker owns and that is running.
OWNED_AND_RUNNING: tuple[tuple[str, tuple[object, ...]], ...] = (
    ("insert into app_private.tool_uses", (1,)),
    ("event_sequence = event_sequence + 1", (1,)),
    ("update app_private.tool_uses", (5,)),
    ("from app_private.run_jobs where run_id", (1,)),
    ("join app_private.run_jobs", ("running", "claimed", GENERATION, True)),
    ("from public.runs where id = %s for share", ("running",)),
)


class Database:
    """Records receipt writes. `receipt` is an earlier attempt's (status, result), or None."""

    def __init__(self, receipt: tuple[str, object] | None = None) -> None:
        self.receipt = receipt
        self.receipts: list[tuple[object, ...]] = []

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def execute(self, query: str, params: tuple[object, ...] = ()) -> Cursor:
        if query.startswith("update app_private.tool_receipts set status = %s"):
            self.receipts.append(params)
        return Cursor(self._answer(query))

    def _answer(self, query: str) -> tuple[object, ...] | None:
        if query.startswith("insert into app_private.tool_receipts"):
            return ("created",) if self.receipt is None else None
        if query.startswith("select status, result from app_private.tool_receipts"):
            return self.receipt
        return next((row for part, row in OWNED_AND_RUNNING if part in query), None)

    def settled(self) -> list[tuple[object, object, object]]:
        """Each receipt write as (status, failure_code, failure_detail)."""
        return [(params[0], params[2], params[3]) for params in self.receipts]


@pytest.fixture
def lines() -> Iterator[Callable[[], list[dict[str, object]]]]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("autobots.tools")
    logger.addHandler(handler)
    try:
        yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    finally:
        logger.removeHandler(handler)


Handler = Callable[[Note, ToolContext], Awaitable[Saved]]


def tool(
    handler: Handler,
    operation_class: OperationClass = OperationClass.REVERSIBLE_INTERNAL_WRITE,
    *,
    timeout_seconds: float = 10.0,
    max_output_bytes: int = 300_000,
    reconcile: Callable[[Note, ToolContext], Awaitable[Saved | None]] | None = None,
    approval_required: bool = False,
    review_detail: Callable[[Note, ToolContext], Awaitable[dict[str, object]]] | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        tool_id="save_note",
        version=1,
        description="Saves a note.",
        input_model=Note,
        output_model=Saved,
        operation_class=operation_class,
        handler=handler,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        reconcile=reconcile,
        approval=ApprovalPolicy(always=approval_required, review_detail=review_detail),
    )


async def call(definition: ToolDefinition, database: Database) -> ToolResult:
    registry = ToolRegistry()
    registry.register(definition)
    scope = ToolScope(
        workspace_id=WORKSPACE,
        run_id=RUN,
        generation=GENERATION,
        tools={definition.tool_id: definition.version},
    )
    return await ToolGateway(registry).execute(database, scope, definition.tool_id, {"text": "x"})


def no_planted_text(line: dict[str, object]) -> bool:
    written = json.dumps(line)
    return "hunter2" not in written and "sk-or-v1" not in written


@pytest.mark.asyncio
async def test_a_defect_in_an_effect_stays_unknown_and_its_receipt_names_the_type(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def parse(_: Note, __: ToolContext) -> Saved:
        reply: dict[str, bool] = {}
        return Saved(saved=reply[PLANTED])

    database = Database()
    result = await call(tool(parse), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "outcome_unknown")
    assert database.settled() == [("unknown", None, "defect:builtins.KeyError")]
    [line] = lines()
    assert (line["event"], line["level"]) == ("tool.operation.unknown", "error")
    assert (line["tool"], line["version"], line["operation"]) == (
        "save_note",
        1,
        result.operation_id,
    )
    assert line["error_type"] == "builtins.KeyError"
    frames = line["frames"]
    assert isinstance(frames, list) and str(frames[-1]).endswith(".parse")
    assert no_planted_text(line)


@pytest.mark.asyncio
async def test_an_unclear_reply_keeps_its_category_on_the_receipt(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def unclear(_: Note, __: ToolContext) -> Saved:
        raise UnclearReply(502)

    database = Database()
    result = await call(tool(unclear), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "outcome_unknown")
    assert database.settled() == [("unknown", None, "github_unclear_502")]
    [line] = lines()
    assert (line["event"], line["level"], line["error_type"]) == (
        "tool.operation.unknown",
        "warning",
        "autobots.adapters.github_issues.UnclearReply",
    )


@pytest.mark.asyncio
async def test_a_timed_out_effect_says_so(lines: Callable[[], list[dict[str, object]]]) -> None:
    async def hangs(_: Note, __: ToolContext) -> Saved:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    database = Database()
    result = await call(tool(hangs, timeout_seconds=0.01), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "outcome_unknown")
    assert database.settled() == [("unknown", None, "timeout")]
    assert [line["level"] for line in lines()] == ["warning"]


@pytest.mark.asyncio
async def test_a_tool_that_knows_it_failed_keeps_its_own_detail_and_logs_nothing(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def refused(_: Note, __: ToolContext) -> Saved:
        raise ToolFailed("github_refused_422", detail="validation")

    database = Database()
    result = await call(tool(refused), database)
    assert (result.outcome, result.code) == (ToolOutcome.FAILED, "github_refused_422")
    assert database.settled() == [("failed", "github_refused_422", "validation")]
    assert lines() == []


@pytest.mark.asyncio
async def test_a_tool_cannot_claim_the_code_only_the_gateway_writes() -> None:
    """The approval gate trusts lease_lost to mean nothing was written (Decision 0025 V8), so a tool
    raising it is recorded as tool_failed and still uses the person's decision."""

    async def claims(_: Note, __: ToolContext) -> Saved:
        raise ToolFailed("lease_lost")

    database = Database()
    result = await call(tool(claims), database)
    assert (result.outcome, result.code) == (ToolOutcome.FAILED, "tool_failed")
    assert database.settled() == [("failed", "tool_failed", "reserved_code:lease_lost")]


@pytest.mark.asyncio
async def test_output_too_large_says_why_it_is_unknown() -> None:
    async def saved(_: Note, __: ToolContext) -> Saved:
        return Saved(saved=True)

    database = Database()
    result = await call(tool(saved, max_output_bytes=1), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "output_too_large")
    assert database.settled() == [("unknown", None, "output_too_large")]


@pytest.mark.asyncio
async def test_a_defect_in_a_read_is_still_tool_failed_and_is_logged(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def parse(_: Note, __: ToolContext) -> Saved:
        reply: dict[str, bool] = {}
        return Saved(saved=reply[PLANTED])

    database = Database()
    result = await call(tool(parse, OperationClass.READ_ONLY), database)
    assert (result.outcome, result.code) == (ToolOutcome.FAILED, "tool_failed")
    assert database.receipts == []
    [line] = lines()
    assert (line["event"], line["level"], line["error_type"]) == (
        "tool.operation.failed",
        "error",
        "builtins.KeyError",
    )
    assert "operation" not in line
    assert no_planted_text(line)


@pytest.mark.asyncio
async def test_a_readback_that_cannot_tell_leaves_an_interrupted_effect_unknown(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def never(_: Note, __: ToolContext) -> Saved:
        raise AssertionError("an interrupted effect is never sent again blindly")

    async def readback(_: Note, __: ToolContext) -> Saved | None:
        raise UnclearReply(503)

    database = Database(receipt=("started", None))
    result = await call(tool(never, reconcile=readback), database)
    assert (result.outcome, result.code, result.replayed) == (
        ToolOutcome.UNKNOWN,
        "outcome_unknown",
        True,
    )
    assert database.settled() == [("unknown", None, "readback:github_unclear_503")]
    [line] = lines()
    assert (line["event"], line["level"]) == ("tool.operation.readback_failed", "warning")


@pytest.mark.asyncio
async def test_an_interrupted_effect_with_no_readback_is_marked_interrupted() -> None:
    async def never(_: Note, __: ToolContext) -> Saved:
        raise AssertionError("an interrupted effect is never sent again blindly")

    database = Database(receipt=("started", None))
    result = await call(tool(never), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "outcome_unknown")
    assert database.settled() == [("unknown", None, "interrupted")]


@pytest.mark.asyncio
async def test_a_review_that_cannot_be_built_is_denied_and_logged(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    async def never(_: Note, __: ToolContext) -> Saved:
        raise AssertionError("nothing runs without a review")

    async def review(_: Note, __: ToolContext) -> dict[str, object]:
        reply: dict[str, object] = {}
        return {"diff": reply[PLANTED]}

    database = Database()
    result = await call(tool(never, approval_required=True, review_detail=review), database)
    assert (result.outcome, result.code) == (ToolOutcome.DENIED, "review_unavailable")
    assert database.receipts == []
    [line] = lines()
    assert (line["event"], line["level"], line["error_type"]) == (
        "tool.operation.review_failed",
        "error",
        "builtins.KeyError",
    )
    assert no_planted_text(line)


def test_both_github_connectors_share_one_unclear_reply() -> None:
    # The pull-request connector imports the class rather than defining its own.
    assert vars(github_pulls)["UnclearReply"] is UnclearReply
    assert issubclass(UnclearReply, OutcomeUnknown)
    assert UnclearReply(504).detail == "github_unclear_504"


@pytest.mark.asyncio
async def test_stopping_a_task_raises_nothing_and_leaves_nothing_unretrieved() -> None:
    reported: list[dict[str, object]] = []
    asyncio.get_running_loop().set_exception_handler(lambda _, context: reported.append(context))

    async def fails() -> None:
        raise RuntimeError("arranged")

    task = asyncio.create_task(fails())
    await asyncio.sleep(0)
    await stop_task(task)
    assert task.done()
    del task
    gc.collect()
    assert reported == []


async def slow_to_stop(release: asyncio.Event) -> None:
    """Runs until cancelled, then takes until `release`, or a second at most, to stop. The bound
    turns a swallowed cancellation into a failed assertion instead of a hung test."""
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(release.wait(), 1.0)
        raise


@pytest.mark.asyncio
async def test_stopping_a_task_keeps_the_callers_own_cancellation() -> None:
    """XERR-13: a cancel aimed at the caller while it waits is the caller's, and propagates."""
    release = asyncio.Event()
    child = asyncio.create_task(slow_to_stop(release))
    await asyncio.sleep(0)
    caller = asyncio.create_task(stop_task(child))
    await asyncio.sleep(0)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert not child.done()
    release.set()
    await asyncio.wait({child})
    assert child.cancelled()


@pytest.mark.asyncio
async def test_the_gateways_timeout_holds_while_a_tool_cleans_up() -> None:
    """A tool's cleanup can't swallow the cancellation that bounds it, so it can't return late."""
    release = asyncio.Event()
    watchers: list[asyncio.Task[None]] = []

    async def browse(_: Note, __: ToolContext) -> Saved:
        watcher = asyncio.create_task(slow_to_stop(release))
        watchers.append(watcher)
        await asyncio.sleep(0)
        try:
            return Saved(saved=True)
        finally:
            await stop_task(watcher)

    database = Database()
    result = await call(tool(browse, timeout_seconds=0.05), database)
    assert (result.outcome, result.code) == (ToolOutcome.UNKNOWN, "outcome_unknown")
    assert database.settled() == [("unknown", None, "timeout")]
    release.set()
    await asyncio.wait(watchers)
