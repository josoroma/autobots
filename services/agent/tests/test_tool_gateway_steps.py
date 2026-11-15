"""The tool gateway's steps in order, against a recorded fake database (PTOL-02, SP-013).

A call is resolved once, then refused by admission, held for approval or refused by the metered
budget, in that order, before any effect. Every step that names the operation names the same one,
and it is the pinned value in test_tool_call_resolution.py.
"""

import contextlib
import inspect
import io
import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from uuid import UUID

import pytest
from pydantic import BaseModel

from autobots.application.approvals import (
    ApprovalProposal,
    ApprovedRequest,
    scope_hash,
    scope_snapshot,
)
from autobots.application.runs import WorkerClaim
from autobots.application.sql import SqlParams
from autobots.application.tool_definitions import (
    ApprovalPolicy,
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import input_digest
from autobots.contracts.tools import CalculateInput, CalculateOutput
from autobots.domain.runs import RunCommand
from autobots.domain.tool_catalog import CostClass
from autobots.domain.tools import OperationClass, ToolOutcome
from autobots.logs import JsonFormatter
from sql_fakes import GATE_COLUMNS, Row, ScriptedRows

WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
RUN = UUID("b0000000-0000-4000-8000-000000000002")
GENERATION = 3
ARGUMENTS = {"operation": "sum", "values": [1, 2]}
# The same pins as test_tool_call_resolution.py, reached here through the whole gateway.
ARGUMENT_HASH = "268f9d982d17e412e15a12822688fd2cbc1339202b9431f8e2f73d98038b2cff"
OPERATION = "4f612f83b94c381030f813b6ad826913592c7c76479d6cf12f759e95ab5f7bae"
TARGET = "Mail to the controlled sink"
PLANTED = "sk-or-v1-planted0123456789 postgresql://user:hunter2@host/db"
SCOPE = ToolScope(WORKSPACE, RUN, GENERATION, {"calculate_x": 2}, paths=("outputs",))
STARTED_BY = UUID("c0000000-0000-4000-8000-000000000003")


@dataclass
class Database:
    """Answers the gateway's statements and records each one.

    `request` is the approval request's status, or None when there is none. `has_request` answers
    the review's own look for a request separately, so one dispatch can build a review and still
    find an approved request at the gate."""

    owned: bool = True
    expert: bool = True
    request: str | None = "approved"
    has_request: bool = False
    metered: int = 0
    # An earlier attempt's receipt as (status, result), or None when this attempt creates it.
    receipt: tuple[str, object] | None = None
    statements: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        self.statements.append((query, tuple(params) if isinstance(params, Sequence) else ()))
        answer = self._answer(query)
        return ScriptedRows([] if answer is None else [answer])

    def _answer(self, query: str) -> Row | None:
        generation = GENERATION if self.owned else GENERATION + 1
        request = (
            None
            if self.request is None
            else dict(
                zip(
                    GATE_COLUMNS,
                    (UUID(int=7), self.request, scope_hash(SCOPE.tools, SCOPE.paths), False, False),
                    strict=True,
                )
            )
        )
        rows: tuple[tuple[str, Row | None], ...] = (
            ("insert into app_private.tool_uses", (1,)),
            ("event_sequence = event_sequence + 1", (1,)),
            ("update app_private.tool_uses set outcome", (5,)),
            ("from app_private.run_jobs where run_id", (1,) if self.owned else None),
            (
                "join app_private.run_jobs",
                {
                    "run_status": "running",
                    "job_status": "claimed",
                    "generation": generation,
                    "lease_live": True,
                },
            ),
            ("from public.runs where id = %s for share", ("running",)),
            ("select expert_id is not null", (self.expert,)),
            ("from public.approval_requests where operation_id = %s for update", request),
            ("select 1 from public.approval_requests", (1,) if self.has_request else None),
            ("select resource_target, review_detail", (TARGET, None)),
            ("select count(*) from app_private.tool_uses", (self.metered,)),
            (
                "insert into app_private.tool_receipts",
                (OPERATION,) if self.receipt is None else None,
            ),
            ("select status, result from app_private.tool_receipts", self.receipt),
            (
                "select started_by, expert_id, expert_version",
                {"started_by": STARTED_BY, "expert_id": None, "expert_version": None},
            ),
            ("select version from public.runs", (1,)),
        )
        return next((row for part, row in rows if part in query), None)

    def index(self, part: str) -> int:
        """Where the first statement containing `part` ran, or -1 when none did."""
        return next((at for at, (query, _) in enumerate(self.statements) if part in query), -1)

    def ran(self, part: str) -> bool:
        return self.index(part) >= 0

    def hashes(self) -> set[object]:
        """Every 64-character hex parameter, which is an operation ID or an argument hash."""
        return {
            value
            for _, params in self.statements
            for value in params
            if isinstance(value, str)
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value)
        }


OWNERSHIP = "join app_private.run_jobs"
EXPERT = "select expert_id is not null"
GATE = "for update"
BUDGET = "select count(*) from app_private.tool_uses"
RECEIPT = "insert into app_private.tool_receipts"


@dataclass
class Seen:
    """The operation ID each callback was handed, by callback."""

    ids: dict[str, str | None] = field(default_factory=dict)


def gated_tool(seen: Seen, *, output: Callable[[], BaseModel] | None = None) -> ToolDefinition:
    """A metered, Expert-only consequential write with a resolved target and a review."""

    async def handler(arguments: CalculateInput, context: ToolContext) -> BaseModel:
        seen.ids["handler"] = context.operation_id
        return output() if output is not None else CalculateOutput(result=sum(arguments.values))

    async def resolve_target(_: CalculateInput, context: ToolContext) -> str:
        seen.ids["target_resolver"] = context.operation_id
        return TARGET

    async def review(_: CalculateInput, context: ToolContext) -> dict[str, object]:
        seen.ids["review_detail"] = context.operation_id
        return {"diff": "+1"}

    return ToolDefinition(
        tool_id="calculate_x",
        version=2,
        description="Adds numbers somewhere else.",
        input_model=CalculateInput,
        output_model=CalculateOutput,
        operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
        handler=handler,
        approval=ApprovalPolicy(target_resolver=resolve_target, review_detail=review),
        cost_class=CostClass.METERED_PROVIDER,
        expert_only=True,
    )


async def call(
    tool: ToolDefinition, database: Database, arguments: object = ARGUMENTS
) -> ToolResult:
    registry = ToolRegistry()
    registry.register(tool)
    return await ToolGateway(registry).execute(database, SCOPE, tool.tool_id, arguments)


@pytest.mark.asyncio
async def test_every_step_names_the_one_pinned_operation() -> None:
    seen = Seen()
    database = Database()
    result = await call(gated_tool(seen), database)
    assert (result.outcome, result.operation_id) == (ToolOutcome.SUCCEEDED, OPERATION)
    assert seen.ids == {
        "target_resolver": OPERATION,
        "review_detail": OPERATION,
        "handler": OPERATION,
    }
    # The use record's digest is of the arguments as sent, and differs from the parsed hash.
    assert database.hashes() == {OPERATION, ARGUMENT_HASH, input_digest(ARGUMENTS)}
    for part in (
        "select 1 from public.approval_requests",
        GATE,
        "select status, reconciled_at, failure_code from app_private.tool_receipts",
        "select status from app_private.tool_receipts",
        "select resource_target, review_detail",
        RECEIPT,
        "update app_private.tool_receipts set status",
    ):
        params = next(params for query, params in database.statements if part in query)
        assert OPERATION in params, part


@pytest.mark.asyncio
async def test_an_approved_dispatch_hands_its_tool_what_the_person_approved() -> None:
    """XMOD-02: the gateway loads the approved request once the gate released the call, so an
    adapter reads its target and review detail from its context, never from the database. A call
    no policy holds is handed none."""
    handed: list[ApprovedRequest | None] = []

    async def handler(arguments: CalculateInput, context: ToolContext) -> BaseModel:
        handed.append(context.approval)
        return CalculateOutput(result=sum(arguments.values))

    gated = replace(gated_tool(Seen()), handler=handler)
    plain = replace(
        simple_tool(OperationClass.REVERSIBLE_INTERNAL_WRITE, lambda: CalculateOutput(result=3)),
        handler=handler,
    )
    for tool in (gated, plain):
        result = await call(tool, Database())
        assert result.outcome is ToolOutcome.SUCCEEDED
    assert handed == [ApprovedRequest(TARGET, None), None]


@pytest.mark.asyncio
async def test_an_approved_read_uses_up_its_approval() -> None:
    """A read leaves no receipt, so the gate consumes the approval that released it, in the gate's
    own transaction (PTOL-06; Decisions 0018 B6 and 0020 L5)."""
    handed: list[ApprovedRequest | None] = []

    async def handler(arguments: CalculateInput, context: ToolContext) -> BaseModel:
        handed.append(context.approval)
        return CalculateOutput(result=sum(arguments.values))

    read = replace(
        simple_tool(OperationClass.READ_ONLY, lambda: CalculateOutput(result=3)),
        handler=handler,
        approval=ApprovalPolicy(always=True),
    )
    database = Database()
    result = await call(read, database)
    assert result.outcome is ToolOutcome.SUCCEEDED
    assert handed == [ApprovedRequest(TARGET, None)]
    assert database.index(GATE) < database.index("set consumed_at = clock_timestamp()")
    assert not database.ran("tool_receipts set")


@pytest.mark.asyncio
async def test_the_guards_run_in_order_before_the_effect() -> None:
    database = Database()
    await call(gated_tool(Seen()), database)
    order = [database.index(part) for part in (OWNERSHIP, EXPERT, GATE, BUDGET, RECEIPT)]
    assert -1 not in order
    assert order == sorted(order)


@pytest.mark.parametrize(
    ("arranged", "code", "reached"),
    [
        (lambda: Database(owned=False), "lease_lost", (OWNERSHIP,)),
        (lambda: Database(expert=False), "expert_grant_required", (OWNERSHIP, EXPERT)),
        (lambda: Database(request="rejected"), "approval_rejected", (OWNERSHIP, EXPERT, GATE)),
        (lambda: Database(metered=20), "tool_budget_exceeded", (OWNERSHIP, EXPERT, GATE, BUDGET)),
    ],
    ids=["admission", "expert", "approval", "budget"],
)
@pytest.mark.asyncio
async def test_a_refusal_stops_every_later_step(
    arranged: Callable[[], Database], code: str, reached: tuple[str, ...]
) -> None:
    """Each step runs only after every earlier one let the call through."""
    seen = Seen()
    database = arranged()
    result = await call(gated_tool(seen), database)
    assert (result.outcome, result.code, result.operation_id) == (ToolOutcome.DENIED, code, None)
    for part in (OWNERSHIP, EXPERT, GATE, BUDGET, RECEIPT):
        assert database.ran(part) is (part in reached), part
    assert "handler" not in seen.ids


@pytest.mark.asyncio
async def test_invalid_arguments_reach_no_run_statement() -> None:
    """SP-013: completed arguments are validated before anything about the run is read."""
    seen = Seen()
    database = Database()
    result = await call(gated_tool(seen), database, {"operation": "sum", "values": []})
    assert (result.outcome, result.code) == (ToolOutcome.DENIED, "invalid_arguments")
    assert seen.ids == {}
    for part in (OWNERSHIP, EXPERT, GATE, BUDGET, RECEIPT):
        assert not database.ran(part), part
    # The use is still recorded and completed (TU-01), with no public arguments.
    [(_, began)] = [
        item for item in database.statements if "insert into app_private.tool_uses" in item[0]
    ]
    assert json.loads(str(began[11])) == {}
    assert database.ran("update app_private.tool_uses set outcome")


@pytest.mark.asyncio
async def test_a_held_call_stores_every_decision_0015_field_and_is_not_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gateway builds one ApprovalProposal, and the request stores all of it. A call that now
    waits for a person isn't counted against the metered budget until it is approved."""
    waits: list[dict[str, object]] = []

    async def enter_wait(
        _: object, claim: WorkerClaim, command: RunCommand, **fields: object
    ) -> None:
        waits.append({"command": command, "generation": claim.generation, **fields})

    monkeypatch.setattr("autobots.application.approvals.apply_worker_command", enter_wait)
    database = Database(request=None)
    result = await call(gated_tool(Seen()), database)
    assert (result.outcome, result.code) == (ToolOutcome.DENIED, "approval_pending")
    assert not database.ran(BUDGET) and not database.ran(RECEIPT)
    [stored] = [
        params
        for query, params in database.statements
        if query.startswith("insert into public.approval_requests")
    ]
    columns = (
        "id workspace_id run_id operation_id tool_id tool_version operation_class argument_hash "
        "arguments scope_hash policy_reason resource_target requested_by requested_by_agent "
        "scope_snapshot policy_version policy_rule review_detail ttl_seconds"
    ).split()
    row = dict(zip(columns, stored, strict=True))
    assert {name: row[name] for name in columns[1:]} == {
        "workspace_id": WORKSPACE,
        "run_id": RUN,
        "operation_id": OPERATION,
        "tool_id": "calculate_x",
        "tool_version": 2,
        "operation_class": "consequential_external_write",
        "argument_hash": ARGUMENT_HASH,
        "arguments": json.dumps({"operation": "sum", "values": [1.0, 2.0]}),
        "scope_hash": scope_hash(SCOPE.tools, SCOPE.paths),
        "policy_reason": (
            "This tool changes something outside this Mac, so policy holds each call for a person."
        ),
        "resource_target": TARGET,
        "requested_by": STARTED_BY,
        "requested_by_agent": json.dumps({"kind": "coordinator"}),
        "scope_snapshot": json.dumps(scope_snapshot(SCOPE.tools, SCOPE.paths)),
        "policy_version": "approval-policy/2",
        "policy_rule": "consequential_external_write",
        "review_detail": json.dumps({"diff": "+1"}),
        "ttl_seconds": 86_400,
    }
    [wait] = waits
    assert (wait["command"], wait["generation"], wait["detail"]) == (
        "request_approval",
        GENERATION,
        str(row["id"]),
    )


def test_a_proposal_hashes_its_own_scope_snapshot_and_requires_every_field() -> None:
    """Decision 0015: the stored snapshot must hash to the stored scope hash, so the hash is
    computed from the snapshot rather than passed beside it. No field has a default, so a caller
    can't leave out the snapshot, the policy version or the rule."""
    snapshot = scope_snapshot({"b": 2, "a": 1}, ("outputs",))
    proposal = ApprovalProposal(
        operation_id=OPERATION,
        tool_id="calculate_x",
        tool_version=2,
        operation_class="consequential_external_write",
        argument_hash=ARGUMENT_HASH,
        arguments={},
        scope=snapshot,
        policy_version="approval-policy/2",
        policy_rule="consequential_external_write",
        policy_reason="Held.",
        resource_target=None,
        review_detail=None,
    )
    assert proposal.scope_hash == scope_hash({"a": 1, "b": 2}, ["outputs"])
    parameters = inspect.signature(ApprovalProposal).parameters.values()
    assert {item.name for item in parameters} >= {"scope", "policy_version", "policy_rule"}
    assert all(item.default is inspect.Parameter.empty for item in parameters)


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


class Leak(BaseModel):
    text: str


@pytest.mark.asyncio
async def test_an_output_that_fails_its_model_after_the_effect_stays_unknown(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    """The handler returned, so the effect happened: an output its model refuses is a defect whose
    outcome is unknown, recorded on the receipt and logged, never an escape that leaves the receipt
    started (R-25, XERR-02)."""
    database = Database()
    result = await call(gated_tool(Seen(), output=lambda: Leak(text=PLANTED)), database)
    assert (result.outcome, result.code, result.operation_id) == (
        ToolOutcome.UNKNOWN,
        "outcome_unknown",
        OPERATION,
    )
    settled = [
        (params[0], params[2], params[3])
        for query, params in database.statements
        if query.startswith("update app_private.tool_receipts set status")
    ]
    assert settled == [("unknown", None, "defect:pydantic_core._pydantic_core.ValidationError")]
    [completed] = [
        params
        for query, params in database.statements
        if "update app_private.tool_uses set outcome" in query
    ]
    assert completed[:2] == ("unknown", "outcome_unknown")
    [line] = lines()
    assert (line["event"], line["level"], line["operation"]) == (
        "tool.operation.unknown",
        "error",
        OPERATION,
    )
    assert line["error_type"] == "pydantic_core._pydantic_core.ValidationError"
    assert "hunter2" not in json.dumps(line) and "hunter2" not in repr(database.statements)


def simple_tool(
    operation_class: OperationClass,
    output: Callable[[], BaseModel],
    reconcile: Callable[[], BaseModel] | None = None,
) -> ToolDefinition:
    """A tool no policy holds, whose handler and readback return what they're given."""

    async def handler(_: CalculateInput, __: ToolContext) -> BaseModel:
        return output()

    async def readback(_: CalculateInput, __: ToolContext) -> BaseModel | None:
        return None if reconcile is None else reconcile()

    return ToolDefinition(
        tool_id="calculate_x",
        version=2,
        description="Adds numbers.",
        input_model=CalculateInput,
        output_model=CalculateOutput,
        operation_class=operation_class,
        handler=handler,
        reconcile=readback if reconcile is not None else None,
    )


def settled(database: Database) -> list[tuple[object, object, object]]:
    """Each receipt write as (status, failure_code, failure_detail)."""
    return [
        (params[0], params[2], params[3])
        for query, params in database.statements
        if query.startswith("update app_private.tool_receipts set status")
    ]


def completed(database: Database) -> tuple[object, ...]:
    """The tool use's (outcome, code)."""
    [params] = [
        params
        for query, params in database.statements
        if "update app_private.tool_uses set outcome" in query
    ]
    return params[:2]


@pytest.mark.asyncio
async def test_a_read_whose_output_fails_its_model_is_a_logged_tool_failure(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    """A read has no effect, so its outcome is never unknown: a refused output is tool_failed, like
    any other defect in a read, with the log line as its only record (R-25, XERR-02)."""
    database = Database()
    result = await call(simple_tool(OperationClass.READ_ONLY, lambda: Leak(text=PLANTED)), database)
    assert (result.outcome, result.code, result.operation_id) == (
        ToolOutcome.FAILED,
        "tool_failed",
        None,
    )
    assert not database.ran("tool_receipts")
    assert completed(database) == ("failed", "tool_failed")
    [line] = lines()
    assert (line["event"], line["level"], line["error_type"]) == (
        "tool.operation.failed",
        "error",
        "pydantic_core._pydantic_core.ValidationError",
    )
    assert "operation" not in line
    assert "hunter2" not in json.dumps(line) and "hunter2" not in repr(database.statements)


@pytest.mark.asyncio
async def test_a_readback_whose_output_fails_its_model_leaves_the_effect_unknown(
    lines: Callable[[], list[dict[str, object]]],
) -> None:
    """The readback answered, but with an output its model refuses: a defect in the readback, so the
    interrupted effect stays unknown and is never sent again blindly (R-25, XERR-02)."""

    def never() -> BaseModel:
        raise AssertionError("an interrupted effect is never sent again blindly")

    database = Database(receipt=("started", None))
    tool = simple_tool(
        OperationClass.REVERSIBLE_INTERNAL_WRITE, never, reconcile=lambda: Leak(text=PLANTED)
    )
    result = await call(tool, database)
    assert (result.outcome, result.code, result.operation_id, result.replayed) == (
        ToolOutcome.UNKNOWN,
        "outcome_unknown",
        OPERATION,
        True,
    )
    assert settled(database) == [
        ("unknown", None, "readback:defect:pydantic_core._pydantic_core.ValidationError")
    ]
    assert completed(database) == ("unknown", "outcome_unknown")
    [line] = lines()
    assert (line["event"], line["level"], line["operation"]) == (
        "tool.operation.readback_failed",
        "error",
        OPERATION,
    )
    assert "hunter2" not in json.dumps(line) and "hunter2" not in repr(database.statements)
