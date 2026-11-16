"""Every stored shape of a run's policy snapshot, its events' payloads and its idempotency receipts
still reads, and each writer stores the bytes it always stored (refactor plan R-51, XTYP-03,
PRUN-08, XDUP-04).

Each fixture under fixtures/stored/policy_snapshot, run_event and receipt is what a writer stores,
captured from it through the fake database, or a shape the history shows an older release wrote,
and says which. The captured ones came from the writers at d669265, before R-51, and the sha256 of
each byte string those writers sent is pinned below. Postgres normalizes jsonb as it stores it, so
tests/db/run_admission_check.py reads back what a real column holds; these pin what each writer
sends and how each shape reads.
"""

import asyncio
import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args
from uuid import UUID

import pytest
from pydantic import ValidationError

from autobots.adapters.tool_registry import catalog, catalog_registry
from autobots.api.dependencies import require_ready
from autobots.application import (
    approvals,
    artifacts,
    experts,
    improvements,
    reconciliation,
    routines,
    run_projection,
    runs,
    tool_uses,
    workflow_executions,
    workflows,
)
from autobots.application.run_projection import events as run_events
from autobots.application.run_projection import workspace as run_workspace
from autobots.application.tool_definitions import ToolResult, ToolScope
from autobots.application.tool_gateway import Refused
from autobots.application.worker_inference import frozen_policy
from autobots.application.worker_leases import Lease
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.contracts.persisted import (
    AdmissionReceipt,
    ApprovalDecisionReceipt,
    EffectRulingReceipt,
    ExecutionReceipt,
    ExpertCreatedReceipt,
    ExpertVersionReceipt,
    ModelCallReconciliationReceipt,
    PolicySnapshot,
    ReplayReceipt,
    RoutineCreatedReceipt,
    RoutineVersionReceipt,
    SessionCreatedReceipt,
    StoredEvent,
    StoredReceipt,
    TransitionReceipt,
    WorkflowCreatedReceipt,
    WorkflowVersionReceipt,
    read_policy_snapshot,
)
from autobots.contracts.routines import RoutineConfig
from autobots.contracts.runs import ResultTextDelta, RunEvent
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import ModelRole, UnknownModelProfile, resolve_role_policy
from autobots.domain.repetition import Repeated
from autobots.domain.runs import RunCommand
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import ToolOutcome
from fake_api import ApiClient, FakeConnection, FakeDatabase

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"
STORED = Path(__file__).parent / "fixtures/stored"
WORKSPACE = UUID("0d000000-0000-4000-8000-0000000000a1")
ACTOR = UUID("0d000000-0000-4000-8000-0000000000a2")
RUN = UUID("0d000000-0000-4000-8000-0000000000b1")
APPROVAL = UUID("0d000000-0000-4000-8000-0000000000b2")
ARTIFACT = UUID("0d000000-0000-4000-8000-0000000000b3")
MISSING = UUID("0d000000-0000-4000-8000-0000000000b4")
EXPERT = UUID("0d000000-0000-4000-8000-0000000000b5")
SESSION = UUID("0d000000-0000-4000-8000-0000000000b6")
FLOW = UUID("0d000000-0000-4000-8000-0000000000b7")
EXECUTION = UUID("0d000000-0000-4000-8000-0000000000b8")
REPLAY = UUID("0d000000-0000-4000-8000-0000000000b9")
CANDIDATE = UUID("0d000000-0000-4000-8000-0000000000ba")
ROUTINE = UUID("0d000000-0000-4000-8000-0000000000bb")
LEASE = Lease(RUN, WORKSPACE, 3, "worker", 1, "running")
MOMENT = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
RECEIPTS = "app_private.idempotency_receipts"
RECEIPT_READ = "select request_hash, result from app_private.idempotency_receipts"
EXPERT_CONFIG = ExpertConfig(purpose="Answers billing questions", tools=["calculate"])
PLAIN_GRAPH = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [{"source": "in", "source_port": "value", "target": "out", "target_port": "value"}],
}


def documents(kind: str) -> dict[str, Any]:
    return {
        path.stem: json.loads(path.read_text())["stored"]
        for path in sorted((STORED / kind).glob("*.json"))
    }


SNAPSHOTS = documents("policy_snapshot")
EVENTS = documents("run_event")
STORED_RECEIPTS = documents("receipt")
ROUTINE_CONFIG = documents("routine_config")["api_daily"]


def run[T](step: Awaitable[T]) -> T:
    async def awaited() -> T:
        return await step

    return asyncio.run(awaited())


async def shown(_connection: object, _workspace_id: UUID, item_id: UUID) -> UUID:
    """A view reader's stand-in: which item the service shows, the one its receipt names."""
    return item_id


def written_events(database: FakeDatabase) -> list[str]:
    return [
        str(values[2])
        for values in database.written("public.run_events")
        if isinstance(values, tuple)
    ]


# The writers, each through the fake database with what it reads answered. Each returns what its
# caller is answered, as plain values, so a replay can be compared with the first answer.
Writer = Callable[[FakeDatabase, pytest.MonkeyPatch], object]


def admitting(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(runs, "uuid4", lambda: RUN)
    database.answer("event_sequence = event_sequence + 1", (1,))
    result = run(
        runs.admit_run(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            goal_text="Sum the figures",
            limit_micro_usd=1_000_000,
            policy=resolve_role_policy(),
        )
    )
    return (result.run_id, result.version, result.status, result.replayed)


def pausing(database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch) -> object:
    database.answer("select version from public.runs", (7,))
    database.answer(
        "select status, generation, lease_expires_at",
        {"status": "done", "generation": 3, "lease_live": None},
    )
    database.answer("select status, version from public.runs", ("running", 7))
    database.answer("select exists", (False,))
    database.answer("event_sequence = event_sequence + 1", (2,))
    result = run(
        runs.apply_command(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            run_id=RUN,
            command=RunCommand.PAUSE,
            expected_version=7,
            receipt=runs.CommandReceipt(ACTOR, "fixture"),
        )
    )
    return (result.version, result.status, result.changed)


def deciding(database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch) -> object:
    database.answer("select run_id from public.approval_requests", (RUN,))
    database.answer(
        "select run_id, status, argument_hash",
        {
            "run_id": RUN,
            "status": "pending",
            "argument_hash": "hash",
            "expired": False,
            "arguments": "{}",
        },
    )
    database.answer("select version from public.runs", (7,))
    database.answer(
        "select status, generation, lease_expires_at",
        {"status": "done", "generation": 3, "lease_live": None},
    )
    database.answer("select status, version from public.runs", ("waiting_approval", 7))
    database.answer("select exists", (False,))
    database.answer("event_sequence = event_sequence + 1", (3,))
    result = run(
        approvals.decide(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            approval_id=APPROVAL,
            idempotency_key="fixture",
            decision="approve",
            argument_hash="hash",
        )
    )
    return (result.status, result.replayed)


def expiring(database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch) -> object:
    database.answer("update public.approval_requests", (APPROVAL,))
    database.answer("event_sequence = event_sequence + 1", (4,))
    return run(approvals.expire(FakeConnection(database), APPROVAL, RUN, WORKSPACE))


def requesting(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(approvals, "uuid4", lambda: APPROVAL)
    database.answer(
        "select started_by, expert_id, expert_version",
        {"started_by": ACTOR, "expert_id": None, "expert_version": None},
    )
    database.answer("event_sequence = event_sequence + 1", (5,))
    proposal = approvals.ApprovalProposal(
        operation_id="op-1",
        tool_id="mock_send",
        tool_version=1,
        operation_class="external_write",
        argument_hash="hash",
        arguments={"to": "x"},
        scope={"tools": {}, "paths": []},
        policy_version="1",
        policy_rule="rule",
        policy_reason="reason",
        resource_target=None,
        review_detail=None,
    )
    return run(approvals._request_review(FakeConnection(database), LEASE, proposal, 60))


def ruling(database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch) -> object:
    database.answer("select status, generation from app_private.tool_receipts", ("unknown", 1))
    database.answer("event_sequence = event_sequence + 1", (6,))
    return run(
        reconciliation.record_evidence(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            run_id=RUN,
            operation_id="op-1",
            actor_id=ACTOR,
            idempotency_key="fixture",
            outcome="delivered",
            evidence="Seen in the destination",
            generation=1,
        )
    )


def using_a_tool(
    database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch, use_id: int = 41
) -> object:
    calculate = catalog_registry().get("calculate", 1)
    scope = ToolScope(WORKSPACE, RUN, 3, {"calculate": 1})
    database.answer("from app_private.run_jobs where run_id = %s and generation = %s", (1,))
    database.answer(
        "select version, tasks from app_private.plan_versions",
        (2, [{"id": "t1", "tools": ["calculate"], "depends_on": []}]),
    )
    database.answer("insert into app_private.tool_uses", (use_id,))
    database.answer("update app_private.tool_uses set outcome", (12,))
    database.answer("event_sequence = event_sequence + 1", (7,))
    resolved = Refused(GatewayCode.TOOL_NOT_GRANTED, tool=calculate)
    connection = FakeConnection(database)
    use = run(tool_uses.begin_use(connection, scope, "calculate", {"a": 1}, resolved))
    assert use is not None
    result = ToolResult(ToolOutcome.SUCCEEDED, None, {"value": 2}, "op-2")
    return run(tool_uses.complete_use(connection, scope, use, "calculate", resolved, result))


class ArtifactStore:
    """One verified staged object, and a published one whose object is gone."""

    async def names(self, _prefix: str) -> list[str]:
        return []

    async def get(self, path: str) -> bytes | None:
        return b"Total: 2" if path == "staged" else None


def reconciling_artifacts(database: FakeDatabase, _monkeypatch: pytest.MonkeyPatch) -> object:
    database.answer(
        "select id, name, object_path, sha256, status from public.artifacts",
        {
            "id": ARTIFACT,
            "name": "total.md",
            "object_path": "staged",
            "sha256": hashlib.sha256(b"Total: 2").hexdigest(),
            "status": "staged",
        },
        {
            "id": MISSING,
            "name": "notes.md",
            "object_path": "gone",
            "sha256": "0" * 64,
            "status": "published",
        },
    )
    database.answer("event_sequence = event_sequence + 1", (8,))
    store: Any = ArtifactStore()
    return run(artifacts.reconcile_run(FakeConnection(database), store, WORKSPACE, RUN))


def creating_an_expert(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(experts, "uuid4", lambda: EXPERT)
    monkeypatch.setattr(experts, "get_expert", shown)
    return run(
        experts.create_expert(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            name="Billing",
            config=EXPERT_CONFIG,
            catalog=catalog(),
        )
    )


def versioning_an_expert(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(experts, "get_expert", shown)
    database.answer('select latest_version from "public"."experts"', (1,))
    return run(
        experts.add_version(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            expert_id=EXPERT,
            idempotency_key="fixture",
            expected_version=1,
            config=EXPERT_CONFIG,
            catalog=catalog(),
        )
    )


def opening_a_session(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(experts, "uuid4", lambda: SESSION)
    monkeypatch.setattr(experts, "get_expert", shown)
    monkeypatch.setattr(experts, "get_session", shown)
    database.answer(
        "select e.id as expert_id, v.version, e.name, v.config from public.experts e",
        {
            "expert_id": EXPERT,
            "version": 1,
            "name": "Billing",
            "config": EXPERT_CONFIG.model_dump(),
        },
    )
    return run(
        experts.create_session(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            kind="direct",
            experts=[SessionExpert(expert_id=EXPERT, version=1)],
        )
    )


def creating_a_workflow(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(workflows, "uuid4", lambda: FLOW)
    monkeypatch.setattr(workflows, "get_workflow", shown)
    return run(
        workflows.create_workflow(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            name="Weekly digest",
        )
    )


def publishing_a_workflow(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(workflows, "get_workflow", shown)
    database.answer('select latest_version from "public"."workflows"', (1,))
    return run(
        workflows.publish_version(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            workflow_id=FLOW,
            idempotency_key="fixture",
            expected_version=1,
            graph=WorkflowGraph.model_validate(PLAIN_GRAPH),
            source="user",
        )
    )


def executing_a_workflow(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    """Under the workspace's saved policy, which this database has none of, so the default."""
    monkeypatch.setattr(workflow_executions, "uuid4", lambda: EXECUTION)
    monkeypatch.setattr(runs, "uuid4", lambda: RUN)
    database.answer(
        "select v.graph, v.graph_hash",
        {
            "graph": PLAIN_GRAPH,
            "graph_hash": "digest",
            "block_versions": {},
            "name": "Weekly digest",
        },
    )
    database.answer("event_sequence = event_sequence + 1", (1,))
    binding = run(
        workflow_executions.create_execution(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            workflow_id=FLOW,
            idempotency_key="fixture",
            version=2,
            inputs={"in": "x"},
        )
    )
    return (binding.id, binding.run_id)


def routine_target(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routines, "get_routine", shown)
    database.answer("from public.experts e join public.expert_versions v", ({"tools": []},))
    database.answer("from public.workflow_versions v join public.workflows w", (1,))


def creating_a_routine(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(routines, "uuid4", lambda: ROUTINE)
    routine_target(database, monkeypatch)
    return run(
        routines.create_routine(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            name="Fixture",
            config=RoutineConfig.model_validate(ROUTINE_CONFIG),
            budget_cap=None,
        )
    )


def editing_a_routine(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    routine_target(database, monkeypatch)
    database.answer('select latest_version from "public"."routines"', (1,))
    return run(
        routines.add_routine_version(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            routine_id=ROUTINE,
            idempotency_key="fixture",
            expected_version=1,
            config=RoutineConfig.model_validate(ROUTINE_CONFIG),
            budget_cap=None,
        )
    )


def replaying_a_candidate(database: FakeDatabase, monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(improvements, "uuid4", lambda: REPLAY)
    monkeypatch.setattr(runs, "uuid4", lambda: RUN)
    database.answer("event_sequence = event_sequence + 1", (1,))
    database.answer(
        "from public.improvement_candidates",
        {
            "kind": "skill",
            "key": "figures",
            "content": "Read the table first.",
            "status": "regression_passed",
            "evidence": [],
            "source": None,
        },
    )
    return run(
        improvements.request_replay(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            candidate_id=CANDIDATE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            tasks=[{"goal_text": "Sum the figures", "criteria": ["The total is right"]}],
            limit_micro_usd=1_000_000,
            policy=resolve_role_policy(),
        )
    )


# The policy snapshot


# Each policy admission froze for a fixture, and the sha256 of the bytes runs.admit stored for it,
# captured before R-51.
POLICIES = {
    "current": resolve_role_policy(),
    "current_with_choices": resolve_role_policy(
        run_role_overrides={"executor": "openrouter_sol"},
        workspace_role_overrides={"summarizer": "openrouter_deepseek_flash"},
        workspace_default="openrouter_terra",
    ),
}
SNAPSHOT_BYTES = {
    "current": "6fa956f36841f500797022f024ff387a3091a153cc43d9c91002ccfa1235e26e",
    "current_with_choices": "0cfcb76485ab30b48ea272357f99815221f7f0e07164a80c6f691cea591f509f",
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_every_stored_snapshot_reads_as_it_was_stored(name: str) -> None:
    stored = SNAPSHOTS[name]
    snapshot = read_policy_snapshot(stored)
    assert snapshot.record_version == 1
    assert (snapshot.version, dict(snapshot.bindings), dict(snapshot.sources)) == (
        stored.get("version", 0),
        stored.get("bindings", {}),
        stored.get("sources", {}),
    )
    routes = {profile: route.model_dump() for profile, route in snapshot.routes.items()}
    assert routes == stored.get("routes", {})


@pytest.mark.parametrize("name", sorted(POLICIES))
def test_admission_stores_a_snapshot_in_the_bytes_it_always_did(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = PolicySnapshot.of(POLICIES[name]).stored()
    assert text == json.dumps(SNAPSHOTS[name], sort_keys=True)
    assert hashlib.sha256(text.encode()).hexdigest() == SNAPSHOT_BYTES[name]
    monkeypatch.setattr(runs, "uuid4", lambda: RUN)
    database = FakeDatabase([])
    database.answer("event_sequence = event_sequence + 1", (1,))
    run(
        runs.admit_run(
            FakeConnection(database),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            goal_text="Sum the figures",
            limit_micro_usd=1_000_000,
            policy=POLICIES[name],
        )
    )
    (row,) = database.written("public.runs")
    assert isinstance(row, tuple) and row[6] == text


# What a worker routes on in each stored shape it can use: the executor's profile, and how many
# bindings say where they came from.
WORKER_READS = {
    "current": ("openrouter_terra", 14),
    "current_with_choices": ("openrouter_sol", 14),
    "before_sources": ("openrouter_terra", 0),
    "before_routes": ("openrouter_deepseek_flash", 0),
}


@pytest.mark.parametrize("name", sorted(WORKER_READS))
def test_a_worker_routes_each_stored_policy_as_admission_froze_it(name: str) -> None:
    policy = frozen_policy(SNAPSHOTS[name])
    profile, sources = WORKER_READS[name]
    assert policy.bindings[ModelRole.EXECUTOR].value == profile
    assert (len(policy.bindings), len(policy.sources), policy.version) == (14, sources, 1)


@pytest.mark.parametrize("name", ["retired_profile", "column_default"])
def test_a_stored_policy_with_nothing_approved_to_route_has_no_route(name: str) -> None:
    """A retired profile is never mapped to another (Decision 0004), and nothing is bound in the
    column's default."""
    with pytest.raises(UnknownModelProfile):
        frozen_policy(SNAPSHOTS[name])


def test_a_route_that_moved_stops_the_run_and_one_with_more_keys_reads() -> None:
    stored = SNAPSHOTS["current"]
    terra = stored["routes"]["openrouter_terra"]
    moved = {"wire_id": "openai/other", "canonical_id": "openai/other-20261101"}
    with pytest.raises(UnknownModelProfile):
        frozen_policy({**stored, "routes": {**stored["routes"], "openrouter_terra": moved}})
    wider = {**stored["routes"], "openrouter_terra": {**terra, "provider": "fixture"}}
    assert frozen_policy({**stored, "routes": wider}) == frozen_policy(stored)


@pytest.mark.parametrize(
    "change",
    [
        {"bindings": None},
        {"bindings": {"executor": 1}},
        {"routes": {"openrouter_terra": "openai/gpt-6.1-terra"}},
        {"routes": {"openrouter_terra": {"wire_id": "openai/gpt-6.1-terra"}}},
        {"version": "one"},
        {"record_version": 2},
    ],
)
def test_a_snapshot_that_cant_be_read_has_no_route(change: dict[str, object]) -> None:
    with pytest.raises(UnknownModelProfile):
        frozen_policy({**SNAPSHOTS["current"], **change})


@pytest.mark.parametrize("stored", [None, [], "text"])
def test_a_snapshot_that_isnt_a_document_has_no_route(stored: object) -> None:
    with pytest.raises(UnknownModelProfile):
        read_policy_snapshot(stored)


# How the run page shows each stored shape's executor: its profile, the identities admission froze
# or else what the profile means now, and where the binding came from when that was recorded.
SHOWN = {
    "current": (
        "openrouter_terra",
        "openai/gpt-6.1-terra-20261026",
        "openai/gpt-6.1-terra",
        "builtin_default",
    ),
    "current_with_choices": (
        "openrouter_sol",
        "openai/gpt-6.1-sol-20260929",
        "openai/gpt-6.1-sol",
        "run_override",
    ),
    "before_sources": (
        "openrouter_terra",
        "openai/gpt-6.1-terra-20261026",
        "openai/gpt-6.1-terra",
        None,
    ),
    "before_routes": (
        "openrouter_deepseek_flash",
        "deepseek/deepseek-v4.1-flash-20261017",
        "unknown",
        None,
    ),
    "retired_profile": ("openrouter_astra", "unknown", "unknown", None),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_the_run_page_shows_each_stored_policy(name: str) -> None:
    database = FakeDatabase([])
    database.answer("select policy_snapshot from public.runs", (SNAPSHOTS[name],))
    bindings = run(run_workspace.role_map(FakeConnection(database), RUN))
    assert len(bindings) == len(SNAPSHOTS[name].get("bindings", {}))
    if name in SHOWN:
        (executor,) = [binding for binding in bindings if binding.role == "executor"]
        found = (executor.profile, executor.canonical_id, executor.wire_id, executor.source)
        assert found == SHOWN[name]


# Snapshots routing refuses (test_a_snapshot_that_cant_be_read_has_no_route), which the run's pages
# show as nothing bound, as they did before R-51.
UNREADABLE = [{"bindings": None}, {**SNAPSHOTS["current"], "record_version": 2}]


@pytest.mark.parametrize("stored", UNREADABLE, ids=["null bindings", "a newer record version"])
def test_the_run_page_shows_a_snapshot_it_cant_read_as_nothing_bound(stored: object) -> None:
    database = FakeDatabase([])
    database.answer("select policy_snapshot from public.runs", (stored,))
    assert run(run_workspace.role_map(FakeConnection(database), RUN)) == []


@pytest.mark.parametrize("stored", UNREADABLE, ids=["null bindings", "a newer record version"])
def test_the_inspector_shows_a_snapshot_it_cant_read_as_nothing_frozen(stored: object) -> None:
    """A call's canonical ID is then what its profile means now, as for a run frozen before routes
    were."""
    database = FakeDatabase([])
    database.answer(
        "from public.runs r where r.id = %(run)s",
        {
            "id": RUN,
            "workspace_id": WORKSPACE,
            "parent_run_id": None,
            "status": "running",
            "created_at": MOMENT,
            "updated_at": MOMENT,
            "charged_micro_usd": 0,
            "reserved_micro_usd": 0,
            "limit_micro_usd": 1_000_000,
            "lease_generation": 1,
            "checkpoint_thread_id": None,
            "version": 1,
            "event_sequence": 0,
        },
    )
    database.answer(
        "select goal_summary, policy_snapshot",
        {"goal_summary": "Sum the figures", "policy_snapshot": stored, "thread_id": "thread"},
    )
    database.answer(
        "from app_private.model_invocations where run_id = %s or root_run_id = %s",
        {
            "id": UUID(int=9),
            "run_id": RUN,
            "role": "executor",
            "attempt": 1,
            "status": "succeeded",
            "profile": "openrouter_terra",
            "wire_id": "fixture/wire",
            "upstream_provider": "fixture",
            "input_tokens": 1,
            "output_tokens": 1,
            "reasoning_tokens": 0,
            "charged_micro_usd": 10,
            "reserved_micro_usd": 10,
            "finish_reason": "stop",
            "failure_class": None,
            "created_at": MOMENT,
            "reconciled": False,
            "charge_source_unknown": False,
        },
    )
    inspector = run(run_projection.read_inspector(FakeConnection(database), WORKSPACE, RUN))
    (shown,) = inspector.model_calls
    assert shown.canonical_id == "openai/gpt-6.1-terra-20261026"


def test_the_sql_that_reads_a_snapshot_names_keys_the_snapshot_stores() -> None:
    """run_projection filters and lists runs by `bindings` in SQL, which no type checks."""
    stored = set(PolicySnapshot.of(resolve_role_policy()).document())
    named = {
        key
        for path in SOURCE.rglob("*.py")
        for key in re.findall(r"policy_snapshot\s*->>?\s*'(\w+)'", path.read_text())
    }
    assert named and named <= stored


# Run events


# The sha256 of the bytes each writer stored at d669265, before R-51.
EVENT_BYTES = {
    "approval_decided": "a10f8b68b2f8c6dd494827878119ef524f5c30999c3559270b411bf18d717a76",
    "approval_expired": "b89d9b9522b87c742d31af7b3f6cd79131512ccdc2875ad627dc380d8be65cec",
    "approval_requested": "8e54d0bdbed5a9c19ff80b3237fbd4cbcde673599a8ae3520b72a4efe61f6b9c",
    "artifact_missing": "1a302712f4c6d236dd8a7786d6b4fbece44de1610d7d01b6040f33eb13fd3cd4",
    "artifact_published": "ee63dd10fefaa3a0891732a9b79f2e644d5f98c4021595fc811fb1461facaf2a",
    "effect_reconciled": "bbde063709c63fec9ccc3990e7235b597f9a79c6de1bbf9a62c4dc2fe7615397",
    "run_admitted": "175a2251789b3d5521a1b7d05f4a8a5c047e6dc1b533b59fd71e38548daf8bff",
    "run_status_changed": "ca2b1bef1eec2a2302cf87af02563d6fa077be94a127ad6603b820e29bcbfed5",
    "tool_use_completed": "d15f555dfeb0ff7f237a0d69d8657742cc9e1c22c0ad71b0bc2395691fc9981d",
    "tool_use_started": "2c100d17809ee3e177d2052631b1fcf351d8caf7a8c2abe295b8a32560da74cb",
}
# Each stored event fixture, the writer that stores it and which of its events it is.
EVENT_WRITERS: dict[str, tuple[Writer, int]] = {
    "run_admitted": (admitting, 0),
    "run_status_changed": (pausing, 0),
    "approval_decided": (deciding, 1),
    "approval_expired": (expiring, 0),
    "approval_requested": (requesting, 0),
    "effect_reconciled": (ruling, 0),
    "tool_use_started": (using_a_tool, 0),
    "tool_use_completed": (using_a_tool, 1),
    "artifact_published": (reconciling_artifacts, 0),
    "artifact_missing": (reconciling_artifacts, 1),
}


@pytest.mark.parametrize("name", sorted(EVENT_WRITERS))
def test_each_writer_stores_its_event_in_the_bytes_it_always_did(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer, index = EVENT_WRITERS[name]
    database = FakeDatabase([])
    writer(database, monkeypatch)
    text = written_events(database)[index]
    assert text == json.dumps(EVENTS[name])
    assert hashlib.sha256(text.encode()).hexdigest() == EVENT_BYTES[name]


@pytest.mark.parametrize("name", sorted(EVENT_WRITERS))
def test_every_stored_event_reaches_the_public_stream(name: str) -> None:
    event = run_projection.project_event(RUN, 4, EVENTS[name], MOMENT)
    assert event is not None
    assert event.payload.model_dump(mode="json") == EVENTS[name]


def test_every_stored_payload_type_is_one_the_public_stream_carries() -> None:
    """Result text is only ever sent live, so it is the one public type no writer stores."""
    stored = set(get_args(StoredEvent))
    public = set(get_args(RunEvent.model_fields["payload"].annotation))
    assert stored < public and public - stored == {ResultTextDelta}


def test_a_payload_no_writer_stores_is_left_out_without_a_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        assert run_projection.project_event(RUN, 5, EVENTS["raw_framework_event"], MOMENT) is None
    assert caplog.records == []


@pytest.mark.parametrize(
    "kind", [[], {"nested": 1}, 7, None], ids=["list", "map", "number", "null"]
)
def test_a_payload_whose_type_isnt_text_is_left_out_without_a_line(
    kind: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Such a type can't be hashed or compared as a known one, and the page still reads."""
    with caplog.at_level(logging.DEBUG):
        assert run_projection.project_event(RUN, 5, {"type": kind}, MOMENT) is None
    assert caplog.records == []


def test_a_known_type_that_fails_is_left_out_and_logged_by_type_and_sequence(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first time and then every Nth, with the count, as every page that reaches the event
    reads it again (Repeated)."""
    monkeypatch.setattr(run_events, "_NOT_PROJECTED", Repeated(every=3))
    payload = {**EVENTS["tool_use_started"], "tool_use_id": 0, "tool_id": "PRIVATE-CONTENT"}
    with caplog.at_level(logging.DEBUG):
        for _ in range(4):
            assert run_projection.project_event(RUN, 6, payload, MOMENT) is None
    first, third = caplog.records
    assert (first.levelno, first.getMessage()) == (logging.WARNING, "run.event.not_projected")
    fields = {"run": RUN, "type": "tool.use.started", "sequence": 6}
    assert first.__dict__["fields"] == {**fields, "failures": 1}
    assert third.__dict__["fields"] == {**fields, "failures": 3}
    assert "PRIVATE-CONTENT" not in repr(first.__dict__) + repr(third.__dict__)


def test_a_payload_its_contract_refuses_fails_its_write_as_a_database_error_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built in the write's transaction, so a refused payload rolls it back and reaches the caller,
    as a failed insert would, and nothing is stored."""
    database = FakeDatabase([])
    with pytest.raises(ValidationError):
        using_a_tool(database, monkeypatch, use_id=0)
    assert "rollback" in database.log and written_events(database) == []


# Idempotency receipts


# Each stored receipt fixture's model, and its operation where the fixture is named otherwise.
RECEIPT_MODELS: dict[str, type[StoredReceipt]] = {
    "admit_run": AdmissionReceipt,
    "run_command": TransitionReceipt,
    "decide_approval": ApprovalDecisionReceipt,
    "reconcile_effect": EffectRulingReceipt,
    "reconcile_model_call": ModelCallReconciliationReceipt,
    "create_expert": ExpertCreatedReceipt,
    "add_expert_version": ExpertVersionReceipt,
    "create_session": SessionCreatedReceipt,
    "create_workflow": WorkflowCreatedReceipt,
    "publish_workflow": WorkflowVersionReceipt,
    "create_execution": ExecutionReceipt,
    "create_execution_before_runs": ExecutionReceipt,
    "create_routine": RoutineCreatedReceipt,
    "edit_routine": RoutineVersionReceipt,
    "replay_candidate": ReplayReceipt,
}
OPERATIONS = {"run_command": "pause"}
RECEIPT_WRITERS: dict[str, Writer] = {
    "admit_run": admitting,
    "run_command": pausing,
    "decide_approval": deciding,
    "reconcile_effect": ruling,
    "create_expert": creating_an_expert,
    "add_expert_version": versioning_an_expert,
    "create_session": opening_a_session,
    "create_workflow": creating_a_workflow,
    "publish_workflow": publishing_a_workflow,
    "create_execution": executing_a_workflow,
    "create_routine": creating_a_routine,
    "edit_routine": editing_a_routine,
    "replay_candidate": replaying_a_candidate,
}
# Each operation's request hash for its writer's arguments above, captured before R-51: a retry
# across the upgrade still matches its receipt.
FINGERPRINTS = {
    "admit_run": "c6668196a0898081250e86f89c7ee26a01a6518f311b44205780a5d8e1545344",
    "run_command": "a10fec2e59ac54134ea1a5014c9a9473c21a3b7d3f5bb76736c5cc0026d0dc40",
    "decide_approval": "f0b3a9cf7ff81d574de1eeaf71d4b4123dd50434fef8b4ff415f33e1f599bd2b",
    "reconcile_effect": "73572f475fcb02263704482998320879b3859dfd65ffbbbd2dacf71cbd59a33f",
    "reconcile_model_call": "8f5b1bcf3e55f71a4d0210ac92f753f9deb9d49916ff6629690617283bb6b877",
    "create_expert": "fbb914115899fac794417eebdde5843ce8b96ba1b9b6980af9223ffb431c713b",
    "add_expert_version": "b8e9adc73625915abecfca1c8133e0c36a468996d6080a265f0db22b84aee244",
    "create_session": "9282bddee945d60d5d51848854635c27a3f404d3d5d019491e3c74a2c2c6c7ad",
    "create_workflow": "2abe7963725407876bb4739cc803972452c38fd5f053bf122e2734a57a483afd",
    "publish_workflow": "ab0fafb67859929df47500cefc57f9798f79e99c9bb7b31cb8c37c007f087b62",
    "create_execution": "a11863a14053d47670be6b82fdd81ce38254cd5294bee1cbdd14fc3d4411fc25",
    "create_routine": "b14499d834373218cadedce5ca5e3acfd5939ae45c858d58cd8bdcaeaa587d9f",
    "edit_routine": "0116c53bbb5d13914dc2661daf0104850d951e59e569bc5954df6b8923eec4d5",
    "replay_candidate": "ee1584af778400823bccb4d3d1720ef88d9049b902d83ab4f6c7e5cd470e52fa",
}
# The sha256 of the result bytes each operation stored at d669265, before R-51.
RECEIPT_BYTES = {
    "add_expert_version": "0899eaeee76dcfdd3c97f3afd61ce31158e7b795a26f1568d83727897e6cee85",
    "admit_run": "26d98a7fb7651383ca4edd1cdb9be01f2a166165201c659e6af6b707c5e24e07",
    "create_execution": "aabcecf1724e5d9fab4a62bd09a5bffef4952ce587972648ad5e1ebc8b6d8628",
    "create_expert": "1ce028f4d3871be0f28a436c86ab7a668d5819d33559e8a8dfad03eb7c6e3361",
    "create_routine": "adcb4b88aaf9dfb0ef7374ab9dc0de335ad269628253f0737ba00e0ab008512a",
    "create_session": "049dac010df50fc56552092f029afffeaaf2ca74e130fb2893e593bb98d3dc4e",
    "create_workflow": "c2b79e7e7d640acba8127ea45f17305352e3735c9e906fa7239d674b123de20d",
    "decide_approval": "70a2b23f8dda7b740a4dec35f5bd28b935ede7a3c9d0a9efa0c916ab04f750e5",
    "edit_routine": "0899eaeee76dcfdd3c97f3afd61ce31158e7b795a26f1568d83727897e6cee85",
    "publish_workflow": "0899eaeee76dcfdd3c97f3afd61ce31158e7b795a26f1568d83727897e6cee85",
    "reconcile_effect": "f9e41e194fd1ca8f6871cd423b1704aed15e7bb18ee481bf44268cc5989f190f",
    "reconcile_model_call": "47e0985ef3b76530984fa83cefb7270d30dbbe2913aca37d66c54f9e39e06b9a",
    "replay_candidate": "26830c8c5d7ceeb8dd2e88ff991ef314271ee0c90ba0cbe60183c46e3d889635",
    "run_command": "676dd7a734c66efdcbccedd2faf73495a7c6d9087043480d368d7f6b9c3e20cf",
}
# The advisory lock key each writer takes, in order, captured before R-63's receipt helper: a
# concurrent retry from before the change waits on the same lock.
LOCK_KEYS: dict[str, list[str]] = {
    "add_expert_version": [f"{WORKSPACE}|{ACTOR}|add_expert_version|{EXPERT}|fixture"],
    "admit_run": [f"{WORKSPACE}|{ACTOR}|admit_run|{WORKSPACE}|fixture"],
    "create_execution": [
        f"{WORKSPACE}|{ACTOR}|create_execution|{FLOW}|fixture",
        f"{WORKSPACE}|{ACTOR}|admit_run|{WORKSPACE}|workflow:{EXECUTION}",
    ],
    "create_expert": [f"{WORKSPACE}|{ACTOR}|create_expert|{WORKSPACE}|fixture"],
    "create_routine": [f"{WORKSPACE}|{ACTOR}|create_routine|{WORKSPACE}|fixture"],
    "create_session": [f"{WORKSPACE}|{ACTOR}|create_session|{WORKSPACE}|fixture"],
    "create_workflow": [f"{WORKSPACE}|{ACTOR}|create_workflow|{WORKSPACE}|fixture"],
    "decide_approval": [f"{WORKSPACE}|{ACTOR}|decide_approval|{APPROVAL}|fixture"],
    "edit_routine": [f"{WORKSPACE}|{ACTOR}|edit_routine|{ROUTINE}|fixture"],
    "publish_workflow": [f"{WORKSPACE}|{ACTOR}|publish_workflow|{FLOW}|fixture"],
    "reconcile_effect": [f"{WORKSPACE}|{ACTOR}|reconcile_effect|op-1|fixture"],
    "replay_candidate": [
        f"{WORKSPACE}|{ACTOR}|replay_candidate|{CANDIDATE}|fixture",
        f"{WORKSPACE}|{ACTOR}|admit_run|{WORKSPACE}|replay:{REPLAY}:0",
    ],
    "run_command": [f"{WORKSPACE}|{ACTOR}|pause|{RUN}|fixture"],
}
# What each replay answers its caller: what the first call answered.
REPLAYS: dict[str, object] = {
    "admit_run": (RUN, 1, "queued", True),
    "run_command": (8, "paused", False),
    "decide_approval": ("approved", True),
    "reconcile_effect": "succeeded",
    "create_expert": EXPERT,
    "add_expert_version": EXPERT,
    "create_session": SESSION,
    "create_workflow": FLOW,
    "publish_workflow": FLOW,
    "create_execution": (EXECUTION, RUN),
    "create_routine": ROUTINE,
    "edit_routine": ROUTINE,
    "replay_candidate": REPLAY,
}


@pytest.mark.parametrize("name", sorted(RECEIPT_MODELS))
def test_every_stored_receipt_reads_with_its_operations_model(name: str) -> None:
    receipt = RECEIPT_MODELS[name].model_validate(STORED_RECEIPTS[name])
    assert receipt.record_version == 1
    if name != "create_execution_before_runs":
        assert receipt.stored() == json.dumps(STORED_RECEIPTS[name])


def test_an_execution_receipt_from_before_runs_reads_without_its_run() -> None:
    receipt = ExecutionReceipt.model_validate(STORED_RECEIPTS["create_execution_before_runs"])
    assert (receipt.execution_id, receipt.run_id) == (EXECUTION, None)


@pytest.mark.parametrize("name", sorted(RECEIPT_WRITERS))
def test_each_operation_stores_its_receipt_in_the_bytes_it_always_did(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([])
    RECEIPT_WRITERS[name](database, monkeypatch)
    operation = OPERATIONS.get(name, name)
    (row,) = [
        values
        for values in database.written(RECEIPTS)
        if isinstance(values, tuple) and values[2] == operation
    ]
    assert (row[5], row[6]) == (FINGERPRINTS[name], json.dumps(STORED_RECEIPTS[name]))
    assert hashlib.sha256(str(row[6]).encode()).hexdigest() == RECEIPT_BYTES[name]


@pytest.mark.parametrize("name", sorted(RECEIPT_WRITERS))
def test_each_operation_locks_its_key_as_it_always_did(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([])
    RECEIPT_WRITERS[name](database, monkeypatch)
    locked = [
        values
        for text, values in database.statements
        if text == "select pg_advisory_xact_lock(hashtextextended(%s, 0))"
    ]
    assert locked == [(key,) for key in LOCK_KEYS[name]]


@pytest.mark.parametrize("name", sorted(RECEIPT_WRITERS))
def test_each_operation_replays_its_stored_receipt_and_changes_nothing(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([])
    database.answer(RECEIPT_READ, (FINGERPRINTS[name], STORED_RECEIPTS[name]))
    assert RECEIPT_WRITERS[name](database, monkeypatch) == REPLAYS[name]
    assert database.changes() == []


@pytest.mark.parametrize("name", sorted(RECEIPT_WRITERS))
def test_a_stored_receipt_that_cant_be_read_is_never_run_again(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It fails as a defect, never as a first call that sends or creates something twice."""
    database = FakeDatabase([])
    database.answer(RECEIPT_READ, (FINGERPRINTS[name], {"unexpected": True}))
    with pytest.raises(ValidationError):
        RECEIPT_WRITERS[name](database, monkeypatch)
    assert database.changes() == []


def test_an_execution_receipt_from_before_runs_replays_its_executions_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeDatabase([])
    stored = STORED_RECEIPTS["create_execution_before_runs"]
    database.answer(RECEIPT_READ, (FINGERPRINTS["create_execution"], stored))
    database.answer("select run_id from public.workflow_executions", (RUN,))
    assert executing_a_workflow(database, monkeypatch) == (EXECUTION, RUN)
    assert database.changes() == []


@pytest.mark.parametrize("found", [[], [(None,)]], ids=["no execution", "no run"])
def test_an_execution_receipt_from_before_runs_without_a_run_is_not_found(
    found: list[tuple[object, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An execution started before each had its run (US-6.2) can't be shown as one, so the retry is
    refused as not found, instead of a 500 (refactor plan R-51)."""
    database = FakeDatabase([])
    stored = STORED_RECEIPTS["create_execution_before_runs"]
    database.answer(RECEIPT_READ, (FINGERPRINTS["create_execution"], stored))
    database.answer("select run_id from public.workflow_executions", *found)
    with pytest.raises(workflows.WorkflowRefused, match="execution_not_found"):
        executing_a_workflow(database, monkeypatch)
    assert database.changes() == []


def _reconcile(api_client: ApiClient) -> tuple[int, Any]:
    api_client.app.dependency_overrides[require_ready] = lambda: None
    api_client.database.answer("select 1 from public.runs where id", (1,))
    reply = api_client.http.post(
        f"/v1/runs/{RUN}/model-calls/reconcile",
        json={"charged_micro_usd": 10},
        headers={**api_client.headers(), "Idempotency-Key": "fixture"},
    )
    return reply.status_code, reply.json()


def test_a_model_call_reconciliation_stores_its_receipt_in_the_bytes_it_always_did(
    api_client: ApiClient,
) -> None:
    assert _reconcile(api_client) == (200, {"schema_version": 1, "reconciled_calls": 0})
    (row,) = api_client.database.written(RECEIPTS)
    assert isinstance(row, tuple) and row[2] == "reconcile_model_call"
    stored = STORED_RECEIPTS["reconcile_model_call"]
    assert (row[5], row[6]) == (FINGERPRINTS["reconcile_model_call"], json.dumps(stored))
    assert hashlib.sha256(str(row[6]).encode()).hexdigest() == RECEIPT_BYTES["reconcile_model_call"]


def test_a_model_call_reconciliation_replays_its_stored_receipt(api_client: ApiClient) -> None:
    stored = {"reconciled_calls": 1}
    api_client.database.answer(RECEIPT_READ, (FINGERPRINTS["reconcile_model_call"], stored))
    assert _reconcile(api_client) == (200, {"schema_version": 1, "reconciled_calls": 1})
    assert api_client.database.changes() == []


@pytest.mark.parametrize("name", sorted(RECEIPT_MODELS))
def test_each_receipt_model_names_what_its_operation_stores(name: str) -> None:
    """Exactly the stored keys of today's shape, and every key of an older one, so neither drops
    nor invents a field. One model per operation, so changing one changes no other's."""
    fields = set(RECEIPT_MODELS[name].model_fields) - {"record_version"}
    stored = set(STORED_RECEIPTS[name])
    if name == "create_execution_before_runs":
        assert stored < fields
    else:
        assert stored == fields
    assert len(set(RECEIPT_MODELS.values())) == len(RECEIPT_MODELS) - 1
