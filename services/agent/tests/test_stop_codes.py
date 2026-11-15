"""R-29: one stop-code vocabulary, and an explicit disposition for every code a pass can stop with.

The `OLD_*` literals are copies of the sets the table replaced: goal_loop's PAUSE_FOR and NOT_OURS,
loop_middleware's STOPPING and REPAIRABLE, plans' PLAN_REJECTIONS and workflow_runner's STOPS. A
derived set that drifts from them changes run behavior, so it fails here (PRUN-02, PPRD-03,
PTOL-09). The one deliberate change is Decision 0028 E3: a code missing from the table suspends the
run instead of failing it.
"""

import ast
import asyncio
import contextlib
import logging
from collections.abc import Iterator, Sequence
from enum import StrEnum
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest
from psycopg.adapt import PyFormat, Transformer

from autobots.application import run_lifecycle
from autobots.application.approvals import LEASE_LOST
from autobots.application.model_admission import AdmissionRefused
from autobots.application.model_attempts import FailureClass
from autobots.application.plans import PlanView
from autobots.application.run_usage import Counter, LimitReached
from autobots.application.runs import TransitionResult
from autobots.application.worker_inference import INTENT_FAILURES
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.domain.execution import INCOMPATIBLE
from autobots.domain.runs import RunCommand
from autobots.domain.stops import (
    DISPOSITION,
    NOT_OURS,
    PAUSE_FOR,
    REPAIRABLE,
    RETRY_LATER,
    ROUTING,
    SETTLEMENT,
    STOPPING,
    STOPS,
    UNMAPPED,
    Disposition,
    GatewayCode,
    PassOutcome,
    StopCode,
    ToolRouting,
    disposition_of,
    repair_limit,
)

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"

OLD_PAUSE_FOR = {
    "budget_exceeded",
    "no_inference_slot",
    "cost_unavailable",
    "credentials_required",
    "credential_unavailable",
    "model_unavailable",
    "network_before_acceptance",
    "invalid_credential",
    "insufficient_credits",
    "partial_stream",
    "uncertain_acceptance",
    "uncertain_model_call",
    "assignment_paused",
    "assignment_lost",
    "assignment_busy",
    "parent_not_running",
    "outcome_unknown",
    "incompatible_version",
    "route_not_bound",
}
OLD_NOT_OURS = {"lease_lost", "run_not_running", "run_not_found", "approval_pending"}
# Every other code that reached `finish` failed the run, these by name.
OLD_FAILS = {
    "rate_limited",
    "provider_error",
    "incomplete_output",
    "other",
    "admission_refused",
    "unadmitted_model_call",
    "request_unencodable",
    "compaction_failed",
    "model_calls_limit",
    "tool_dispatches_limit",
    "repairs_limit",
    "plan_revisions_limit",
    "children_limit",
    "active_time_limit",
    "step_limit",
    "output_too_large",
    "plan_missing",
    "plan_incomplete",
    "criteria_unmet",
    "workflow_invalid",
    "workflow_node_failed",
    "workflow_stalled",
}
OLD_SETTLEMENT = {"cancelled", "cancelled_with_unknown_outcomes", "children_settling"}
OLD_STOPPING = {
    "plan_revisions_limit",
    "assignment_paused",
    "assignment_lost",
    "assignment_busy",
    "approval_pending",
    "outcome_unknown",
    "output_too_large",
}
OLD_PLAN_REJECTIONS = {
    "plan_duplicate_task",
    "plan_unknown_dependency",
    "plan_cycle",
    "plan_out_of_scope",
    "plan_uncovered_criteria",
    "plan_drops_completed",
    "plan_changes_completed",
    "plan_reason_required",
    "plan_missing",
    "task_unknown",
    "task_dependencies_open",
    "evidence_invalid",
}
OLD_REPAIRABLE = OLD_PLAN_REJECTIONS | {
    "invalid_arguments",
    "route_not_granted",
    "scope_expansion_denied",
}
OLD_STOPS = {
    "approval_pending",
    "outcome_unknown",
    "assignment_paused",
    "lease_lost",
    "run_not_running",
    "run_not_found",
    "assignment_lost",
    "assignment_busy",
}
# What the tool gateway returns itself, in tool_gateway.py and the approval gate (PTOL-09).
GATEWAY_OWN = {
    "tool_not_granted",
    "tool_not_registered",
    "capability_disabled",
    "invalid_arguments",
    "resource_not_granted",
    "run_not_found",
    "lease_lost",
    "run_not_running",
    "expert_grant_required",
    "connector_not_configured",
    "review_unavailable",
    "approval_pending",
    "approval_expired",
    "approval_scope_changed",
    "approval_consumed",
    "approval_rejected",
    "approval_target_changed",
    "tool_budget_exceeded",
    "tool_timeout",
    "tool_failed",
    "output_too_large",
    "outcome_unknown",
}
# Every code assign_tool raises, and what the goal loop does with each.
ASSIGNMENT_CODES = {
    GatewayCode.ASSIGNMENT_DEPTH_LIMIT: ToolRouting.SHOW,
    GatewayCode.ROUTE_NOT_GRANTED: ToolRouting.REPAIR,
    GatewayCode.SCOPE_EXPANSION_DENIED: ToolRouting.REPAIR,
    GatewayCode.PARENT_NOT_RUNNING: ToolRouting.SHOW,
    GatewayCode.OUTSTANDING_ASSIGNMENTS_LIMIT: ToolRouting.SHOW,
    GatewayCode.CHILDREN_LIMIT: ToolRouting.SHOW,
    GatewayCode.ASSIGNMENT_BUSY: ToolRouting.STOP,
    GatewayCode.ASSIGNMENT_PAUSED: ToolRouting.STOP,
    GatewayCode.ASSIGNMENT_LOST: ToolRouting.STOP,
}


def _subclasses(kind: type[AdmissionRefused]) -> Iterator[type[AdmissionRefused]]:
    for child in kind.__subclasses__():
        yield child
        yield from _subclasses(child)


def _tree(module: str) -> ast.Module:
    return ast.parse((SOURCE / module).read_text())


def _named(node: ast.expr, vocabulary: str) -> str | None:
    """The member name when `node` is `<vocabulary>.<NAME>`."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == vocabulary
    ):
        return node.attr
    return None


def _codes_raised(
    module: str, raiser: str, passed_through: frozenset[str] = frozenset()
) -> set[str]:
    """The GatewayCode each `raiser(...)` call in a module names. Any other first argument fails,
    unless its source is in `passed_through`, a code raised again from one already counted."""
    found = set()
    for node in ast.walk(_tree(module)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != raiser:
            continue
        name = _named(node.args[0], "GatewayCode")
        if name is None:
            assert ast.unparse(node.args[0]) in passed_through, ast.unparse(node)
            continue
        found.add(GatewayCode[name].value)
    return found


def _strings_returned(value: ast.expr) -> Iterator[str]:
    """The strings a return statement can give, through any conditional expression in it."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        yield value.value
    elif isinstance(value, ast.IfExp):
        yield from _strings_returned(value.body)
        yield from _strings_returned(value.orelse)


def test_each_value_is_the_stored_string() -> None:
    vocabularies: tuple[type[StrEnum], ...] = (
        StopCode,
        GatewayCode,
        Disposition,
        ToolRouting,
        PassOutcome,
    )
    for vocabulary in vocabularies:
        for member in vocabulary:
            assert member.value == member.name.lower() and str(member) == member.value
    assert {code.value for code in StopCode} == (
        OLD_PAUSE_FOR | OLD_NOT_OURS | OLD_FAILS | OLD_SETTLEMENT
    )
    assert {outcome.value for outcome in PassOutcome} == {
        "candidate",
        "waiting",
        "lost",
        "stopped",
        "succeeded",
    }


def test_the_database_driver_writes_each_code_as_its_string() -> None:
    """`run_usage.stop_reason` and `tool_uses.code` receive exactly what they did before."""
    transformer = Transformer()
    for code in (*StopCode, *GatewayCode, *PassOutcome):
        dumped = transformer.get_dumper(code, PyFormat.AUTO).dump(code)
        assert dumped is not None and bytes(dumped) == code.value.encode()


def test_every_known_code_has_one_explicit_disposition() -> None:
    assert set(DISPOSITION) == set(StopCode) - SETTLEMENT
    assert not set(DISPOSITION) & SETTLEMENT
    assert set(ROUTING) == set(GatewayCode)


def test_every_disposition_keeps_todays_behavior() -> None:
    for code, disposition in DISPOSITION.items():
        if code in OLD_NOT_OURS:
            assert disposition is Disposition.RELEASE, code
        elif code in OLD_PAUSE_FOR:
            assert disposition is Disposition.SUSPEND, code
        else:
            assert disposition is Disposition.FAIL, code
    counts = {
        disposition: sum(1 for value in DISPOSITION.values() if value is disposition)
        for disposition in Disposition
    }
    assert counts == {
        Disposition.VERIFY: 0,
        Disposition.SUSPEND: 19,
        Disposition.FAIL: 22,
        Disposition.RELEASE: 4,
    }
    assert disposition_of(None) is Disposition.VERIFY


def test_derived_sets_equal_the_literals_they_replaced() -> None:
    assert PAUSE_FOR == OLD_PAUSE_FOR
    assert NOT_OURS == OLD_NOT_OURS
    # The loop stopped on these two inline as well, beside its STOPPING set.
    assert STOPPING == OLD_STOPPING | {"lease_lost", "run_not_running"}
    assert REPAIRABLE == OLD_REPAIRABLE
    assert RETRY_LATER == {
        "assignment_paused",
        "assignment_lost",
        "assignment_busy",
        "parent_not_running",
        "outcome_unknown",
    }
    # A pause inside an assignment's creation stops the node instead of failing it (PPRD-03).
    assert STOPS == OLD_STOPS | {"parent_not_running"}


def test_every_failure_class_has_a_disposition() -> None:
    for failure in FailureClass:
        assert StopCode(failure.value) in DISPOSITION, failure


def test_every_admission_refusal_has_a_disposition() -> None:
    refusals: list[type[AdmissionRefused]] = [AdmissionRefused, *_subclasses(AdmissionRefused)]
    assert len(refusals) >= 4
    for refusal in refusals:
        assert StopCode(refusal.code) in DISPOSITION, refusal


def test_every_limit_has_a_disposition_and_keeps_its_stored_code() -> None:
    counters: tuple[Counter, ...] = get_args(Counter)
    assert len(counters) == 5
    for counter in counters:
        code = LimitReached(counter).code
        assert code == f"{counter}_limit"
        assert DISPOSITION[StopCode(code)] is Disposition.FAIL


def test_every_refusal_before_dispatch_has_a_disposition() -> None:
    """worker_inference's refusals are FailureClass values; credential_invalid is renamed first."""
    assert INTENT_FAILURES["credential_invalid"] is FailureClass.INVALID_CREDENTIAL
    for failure in INTENT_FAILURES.values():
        assert DISPOSITION[StopCode(failure.value)] is Disposition.SUSPEND
    assert DISPOSITION[StopCode(INCOMPATIBLE)] is Disposition.SUSPEND


def test_every_code_that_stops_the_loop_has_a_disposition() -> None:
    for code in STOPPING:
        assert StopCode(code) in DISPOSITION, code


def test_a_workflow_stop_never_fails_its_run() -> None:
    for code in STOPS:
        assert DISPOSITION[StopCode(code)] in {Disposition.RELEASE, Disposition.SUSPEND}, code
    for code in GatewayCode:
        if code not in STOPS:
            assert disposition_of(code) in {None, Disposition.FAIL}, code


def test_every_code_assign_tool_raises_is_classified() -> None:
    raised = _codes_raised("application/assignments.py", "ToolFailed")
    assert raised == set(ASSIGNMENT_CODES)
    for code, routing in ASSIGNMENT_CODES.items():
        assert ROUTING[code] is routing, code
    assert {code for code in ASSIGNMENT_CODES if code in STOPS} == {
        GatewayCode.ASSIGNMENT_BUSY,
        GatewayCode.ASSIGNMENT_PAUSED,
        GatewayCode.ASSIGNMENT_LOST,
        GatewayCode.PARENT_NOT_RUNNING,
    }


def test_every_plan_rejection_spends_the_repair() -> None:
    rejected = _codes_raised("application/plans.py", "PlanRejected")
    failed = _codes_raised(
        "application/plans.py", "ToolFailed", passed_through=frozenset({"rejected.code"})
    )
    routed = {code: ROUTING[GatewayCode(code)] for code in rejected | failed}
    assert {code for code, route in routed.items() if route is ToolRouting.REPAIR} == (
        OLD_PLAN_REJECTIONS
    )
    assert {code for code, route in routed.items() if route is not ToolRouting.REPAIR} == {
        "plan_revisions_limit"
    }
    assert ROUTING[GatewayCode.PLAN_REVISIONS_LIMIT] is ToolRouting.STOP


def test_every_code_the_gateway_produces_is_classified() -> None:
    gateway = _tree("application/tool_gateway.py")
    named = {
        GatewayCode[name].value
        for node in (*ast.walk(gateway), *ast.walk(_tree("application/approvals.py")))
        if isinstance(node, ast.expr) and (name := _named(node, "GatewayCode")) is not None
    }
    # tool_gateway.py names codes only through GatewayCode; a bare string as a code fails here.
    for node in ast.walk(gateway):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            position = {"_denied": 0, "ToolResult": 1}.get(node.func.id)
            if position is not None and len(node.args) > position:
                for part in ast.walk(node.args[position]):
                    assert not isinstance(part, ast.Constant), ast.unparse(node)
    approvals = _tree("application/approvals.py")
    gate = next(
        node
        for node in ast.walk(approvals)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "approval_gate"
    )
    returned = {
        code
        for node in ast.walk(gate)
        if isinstance(node, ast.Return) and node.value is not None
        for code in _strings_returned(node.value)
    }
    assert named | returned == GATEWAY_OWN
    for code in GATEWAY_OWN:
        assert GatewayCode(code) in ROUTING, code


def test_every_code_a_pass_stops_with_by_name_has_a_disposition() -> None:
    """A literal or member handed to LoopStopped, a workflow's `InstanceStopped`, `finish` or
    `result_of`."""
    checked = 0
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            position = {"LoopStopped": 0, "InstanceStopped": 0, "finish": 3, "result_of": 4}.get(
                node.func.id
            )
            if position is None or len(node.args) <= position:
                continue
            argument = node.args[position]
            where = f"{path.relative_to(SOURCE)}:{node.lineno}"
            if isinstance(argument, ast.Constant):
                value = argument.value
                assert value is None or (isinstance(value, str) and disposition_of(value)), where
                checked += 1
            elif (name := _named(argument, "StopCode")) is not None:
                assert StopCode[name] in DISPOSITION or StopCode[name] in SETTLEMENT, where
                checked += 1
    # Every caller in goal_loop.py, workflow_runner.py, run_lifecycle.py and loop_middleware.py
    # was reached.
    assert checked >= 24


def test_a_spent_repair_fails_the_run_and_keeps_its_stored_code() -> None:
    for code in REPAIRABLE:
        stop = repair_limit(code)
        assert stop == f"repair_limit:{code.value}"
        assert disposition_of(stop) is Disposition.FAIL
    # Only a repairable code has a repair to spend, so any other is missing from the table.
    assert disposition_of("repair_limit:tool_failed") is None


def test_codes_named_elsewhere_are_the_same_strings() -> None:
    assert LEASE_LOST == StopCode.LEASE_LOST.value == GatewayCode.LEASE_LOST.value
    assert INCOMPATIBLE == StopCode.INCOMPATIBLE_VERSION
    both = {code.value for code in GatewayCode} & {code.value for code in StopCode}
    assert both >= {code.value for code in STOPPING} | {code.value for code in STOPS}


def test_a_code_missing_from_the_table_has_no_disposition_of_its_own() -> None:
    assert disposition_of("made_up_stop") is None
    assert disposition_of("cancelled") is None
    assert UNMAPPED is Disposition.SUSPEND


GOAL = GoalSpec(
    objective="Write the report",
    original_request="Write the report",
    criteria={"c1": "the report exists"},
    allowed_tools={},
    allowed_paths=[],
)
LEASE = Lease(uuid4(), uuid4(), 3, "worker", 1, "running")


class Connection:
    """What `finish` sends once its reads are replaced: the run's version and the stop reason."""

    def __init__(self) -> None:
        self.stop_reasons: list[object] = []

    async def execute(self, statement: str, values: Sequence[object] = ()) -> "Connection":
        if "stop_reason" in statement:
            self.stop_reasons.append(values[1])
        return self

    async def fetchone(self) -> tuple[int]:
        return (4,)

    async def fetchall(self) -> list[tuple[int]]:
        return [(4,)]

    def transaction(self) -> contextlib.nullcontext[None]:
        return contextlib.nullcontext()


def _finish(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> tuple[list[object], Connection, run_lifecycle.LoopResult]:
    """`finish` on a running run whose plan is done, with its reads and transition replaced."""
    applied: list[object] = []
    reached = {RunCommand.SUSPEND: "paused", RunCommand.FAIL: "failed"}

    async def plan_view(*_: object) -> PlanView:
        return PlanView(1, ("t1",), (), ())

    async def run_status(*_: object) -> str:
        return "running"

    async def apply_command(_: object, **fields: object) -> TransitionResult:
        command = fields["command"]
        applied.append(command)
        assert isinstance(command, RunCommand)
        return TransitionResult(LEASE.run_id, 5, reached[command], True)

    async def usage_view(*_: object) -> dict[str, object]:
        return {}

    monkeypatch.setattr(run_lifecycle, "plan_view", plan_view)
    monkeypatch.setattr(run_lifecycle, "run_status", run_status)
    monkeypatch.setattr(run_lifecycle, "apply_command", apply_command)
    monkeypatch.setattr(run_lifecycle, "usage_view", usage_view)
    connection = Connection()
    result = asyncio.run(run_lifecycle.finish(connection, LEASE, GOAL, code))
    return applied, connection, result


def test_an_unmapped_code_suspends_the_run_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Decision 0028 E3: paused and resumable, never a terminal failure (SP-010)."""
    with caplog.at_level(logging.WARNING, logger="autobots.worker"):
        applied, connection, result = _finish(monkeypatch, "made_up_stop")
    assert applied == [RunCommand.SUSPEND]
    assert connection.stop_reasons == ["made_up_stop"]
    assert (result.outcome, result.code, result.run_status) == (
        PassOutcome.STOPPED,
        "made_up_stop",
        "paused",
    )
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert [record.getMessage() for record in warnings] == ["worker.stop_code_unmapped"]
    fields = getattr(warnings[0], "fields", {})
    assert fields["code"] == "made_up_stop" and fields["run"] == str(LEASE.run_id)


def test_a_mapped_code_keeps_its_disposition_and_logs_nothing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="autobots.worker"):
        failed, _, failure = _finish(monkeypatch, StopCode.RATE_LIMITED)
        suspended, _, suspension = _finish(monkeypatch, StopCode.BUDGET_EXCEEDED)
        repaired, _, _ = _finish(monkeypatch, repair_limit(GatewayCode.PLAN_CYCLE))
    assert failed == [RunCommand.FAIL] and failure.run_status == "failed"
    assert suspended == [RunCommand.SUSPEND] and suspension.run_status == "paused"
    assert repaired == [RunCommand.FAIL]
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_a_code_prints_as_its_stored_string_inside_a_tuple() -> None:
    from autobots.domain.stops import GatewayCode, StopCode

    assert repr(StopCode.LEASE_LOST) == "'lease_lost'"
    pair = (StopCode.LEASE_LOST, GatewayCode.OUTCOME_UNKNOWN)
    assert str(pair) == "('lease_lost', 'outcome_unknown')"
