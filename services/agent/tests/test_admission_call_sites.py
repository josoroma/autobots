"""Each caller of run admission, driven through its own call site, keeps its golden receipt
fingerprint, SP-014 (refactor plan R-30).

tests/test_run_admission.py holds each caller shape's golden `request_hash`, checked there through
grants that test builds. Here each call site builds its own: POST /v1/runs in process, a routine's
Expert occurrence, a workflow execution, a held-out replay and a specialist's child. A call site
that changes what its grant or request carries changes the digest, and a receipt stored before then
stops replaying, so these fail. The fakes answer scripted rows; no socket, database or model is
used.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from autobots.application.assignments import Delegation, assign_tool
from autobots.application.experts import RunBinding
from autobots.application.improvements import request_replay
from autobots.application.routines import admit_occurrence, routine_record
from autobots.application.run_usage import RootLimits
from autobots.application.tool_gateway import ToolContext, ToolScope
from autobots.application.worker_leases import Lease
from autobots.application.workflows import create_execution
from autobots.contracts.assignments import AssignSpecialist
from autobots.contracts.improvements import HeldOutTask
from autobots.contracts.routines import CronjobSchedule, RoutineConfig, RoutineTarget
from autobots.domain.stops import PassOutcome
from autobots.domain.tools import DELEGATION_TOOL, LOOP_TOOL_GRANTS
from fake_api import WORKSPACE, ApiClient, FakeConnection, FakeDatabase
from test_run_admission import FINGERPRINTS, PERSON, STORED_GOAL, caller_shapes
from test_run_request_admission import Arranged, post

ROUTINE = UUID("0c000000-0000-4000-8000-0000000000b1")
FLOW = UUID("0c000000-0000-4000-8000-0000000000d1")
CANDIDATE = UUID("0c000000-0000-4000-8000-0000000000c1")
# Any run the claim's row names: the drive below is a fake, and never reads it.
CLAIMED = UUID("0c000000-0000-4000-8000-0000000000e1")
MOMENT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
RECEIPTS = "app_private.idempotency_receipts"
API_SHAPES = ("api_goal", "api_goal_in_full", "api_session_expert", "api_repeat", "api_continue")
# A workflow with no agent step, so its execution opens no session, which no digest includes.
PLAIN_GRAPH = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [{"source": "in", "source_port": "value", "target": "out", "target_port": "value"}],
}


def scripted() -> FakeDatabase:
    """A pool whose run row answers the event sequence, as every admission reads it."""
    database = FakeDatabase([])
    database.answer("event_sequence = event_sequence + 1", (1,))
    return database


def admission_digest(database: FakeDatabase) -> str:
    """The request hash on the receipt `runs.admit` wrote, not on any receipt of the caller's."""
    (receipt,) = [
        values
        for values in database.written(RECEIPTS)
        if isinstance(values, tuple) and values[2] == "admit_run"
    ]
    return str(receipt[5])


def admitted_through(
    database: FakeDatabase, call: Callable[[FakeConnection], Awaitable[object]]
) -> str:
    async def drive() -> None:
        async with database.connection() as connection:
            await call(connection)

    asyncio.run(drive())
    return admission_digest(database)


# POST /v1/runs


def request_of(shape: str) -> Arranged:
    """POST /v1/runs's body for a captured shape, and a session pinning its Expert's version."""
    options = caller_shapes()[shape]
    body: dict[str, object] = {
        "limit_micro_usd": options["limit_micro_usd"],
        "acceptance_criteria": list(options.get("acceptance_criteria", ())),
        "required_artifacts": [item.model_dump() for item in options.get("required_artifacts", ())],
        # As a request sends them, so a document that names no media type sends none.
        "input_documents": [
            item.model_dump(exclude_unset=True) for item in options.get("input_documents", ())
        ],
    }
    if options["goal_text"] is not None:
        body["goal_text"] = options["goal_text"]
    if options.get("continues_run_id") is not None:
        body["continues_run_id"] = str(options["continues_run_id"])
    if options.get("run_profile") is not None:
        body["run_profile"] = options["run_profile"]
    binding = options.get("binding")
    if binding is None:
        return Arranged(body=body, stored_goal=STORED_GOAL)
    assert isinstance(binding, RunBinding)
    body |= {"session_id": str(binding.session_id), "expert_id": str(binding.expert_id)}
    pinned: list[dict[str, object]] = [
        {"expert_id": str(binding.expert_id), "version": binding.version}
    ]
    return Arranged(body=body, session=("direct", pinned), stored_goal=STORED_GOAL)


@pytest.mark.parametrize("shape", API_SHAPES)
def test_post_run_admits_each_request_shape_with_its_golden_fingerprint(
    api_client: ApiClient, shape: str
) -> None:
    reply = post(api_client, request_of(shape))
    assert (reply.status_code, reply.body["replayed"]) == (202, False)
    assert admission_digest(api_client.database) == FINGERPRINTS[shape]


# application/routines.py


def test_a_routines_expert_occurrence_admits_with_the_golden_fingerprint() -> None:
    options = caller_shapes()["routine_expert"]
    expert = options["binding"]
    database = scripted()
    database.answer(
        "select v.config from public.experts e join public.expert_versions v",
        ({"tools": ["calculate"]},),
    )
    config = routine_record(
        RoutineConfig(
            target=RoutineTarget(kind="expert", id=expert.expert_id, version=expert.version),
            trigger=CronjobSchedule(kind="interval", minutes=60),
            goal=options["goal_text"],
            limit_micro_usd=options["limit_micro_usd"],
        )
    )
    digest = admitted_through(
        database,
        lambda connection: admit_occurrence(connection, WORKSPACE, ROUTINE, 1, config, MOMENT),
    )
    assert digest == FINGERPRINTS["routine_expert"]


# application/workflows.py


def test_a_workflow_execution_admits_with_the_golden_fingerprint() -> None:
    options = caller_shapes()["workflow"]
    database = scripted()
    # The shape's goal is "Workflow Weekly digest, version 4", from this name and version.
    database.answer("select v.graph, v.graph_hash", (PLAIN_GRAPH, "digest", {}, "Weekly digest"))
    digest = admitted_through(
        database,
        lambda connection: create_execution(
            connection,
            workspace_id=WORKSPACE,
            actor_id=PERSON,
            started_by=PERSON,
            workflow_id=FLOW,
            idempotency_key="key-workflow",
            version=4,
            inputs={"in": "x"},
            documents=options["input_documents"],
            limit_micro_usd=options["limit_micro_usd"],
        ),
    )
    assert digest == FINGERPRINTS["workflow"]


# application/improvements.py


def test_a_held_out_replay_admits_its_task_with_the_golden_fingerprint() -> None:
    options = caller_shapes()["improvement_replay"]
    database = scripted()
    database.answer(
        "from public.improvement_candidates",
        ("skill", "figures", "Read the table first.", "regression_passed", [], None),
    )
    task = HeldOutTask(
        goal_text=options["goal_text"], criteria=list(options["acceptance_criteria"])
    )
    digest = admitted_through(
        database,
        lambda connection: request_replay(
            connection,
            workspace_id=WORKSPACE,
            candidate_id=CANDIDATE,
            actor_id=PERSON,
            idempotency_key="key-replay",
            tasks=[task.model_dump()],
            limit_micro_usd=options["limit_micro_usd"],
            policy=options["policy"],
        ),
    )
    assert digest == FINGERPRINTS["improvement_replay"]


# application/assignments.py


async def finished(_connection: object, _lease: Lease) -> SimpleNamespace:
    """The child's pass, faked: it ends verified with nothing left."""
    return SimpleNamespace(
        run_status="succeeded",
        outcome=PassOutcome.SUCCEEDED.value,
        code=None,
        completed=(),
        remaining=(),
    )


async def no_wait(_seconds: float) -> None:
    raise AssertionError("the child is claimed at the first attempt")


def test_a_specialists_child_admits_with_the_golden_fingerprint() -> None:
    options = caller_shapes()["assignment_child"]
    inherited = options["inherit"]
    parent_goal = {
        "objective": "Total both tables",
        "original_request": "Total both tables",
        "criteria": {"c1": "Total both tables"},
        "allowed_tools": {**LOOP_TOOL_GRANTS, DELEGATION_TOOL: 1},
        "allowed_paths": ["inputs", "outputs"],
    }
    database = scripted()
    database.answer(
        "select r.session_id, r.policy_snapshot, r.limit_micro_usd",
        (inherited.session_id, inherited.snapshot, options["limit_micro_usd"], 0),
    )
    database.answer(
        "select kind, experts from public.sessions",
        ("coordinator", [{"expert_id": str(inherited.expert_id), "version": inherited.version}]),
    )
    database.answer(
        "from public.expert_versions v join public.experts e", ({"tools": ["calculate"]},)
    )
    database.answer("select spec from app_private.goal_specs", (parent_goal,))
    database.answer("from app_private.run_jobs where run_id = %s and generation = %s", (1,))
    database.answer("select status from public.runs where id = %s for share", ("running",))
    database.answer("count(*) filter (where status = 'open')", (0, 0))
    database.answer("set children = children + 1", (1,))
    database.answer(
        "from app_private.run_jobs j join public.runs r", (CLAIMED, WORKSPACE, "running", 1)
    )
    database.answer("returning generation, attempts", (1, 1))
    scope = ToolScope(
        workspace_id=WORKSPACE,
        run_id=inherited.parent_run_id,
        generation=1,
        tools={DELEGATION_TOOL: 1},
        root_run_id=inherited.root_run_id,
    )
    tool = assign_tool(Delegation(finished, RootLimits(), lease_seconds=1.0, sleep=no_wait))
    arguments = AssignSpecialist(
        expert_id=str(inherited.expert_id),
        goal=options["goal_text"],
        criteria=list(options["acceptance_criteria"]),
    )
    digest = admitted_through(
        database,
        lambda connection: tool.handler(arguments, ToolContext(connection, scope, "op-assign")),
    )
    assert digest == FINGERPRINTS["assignment_child"]
