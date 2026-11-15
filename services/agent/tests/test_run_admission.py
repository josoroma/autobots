"""Run admission's fingerprint, rows and transaction, SP-012 and SP-014 (refactor plan R-30).

A receipt replays only while `request_hash` gives the same digest for the same request, so each
caller's shape has a golden fingerprint captured from the admission code before R-30 changed it.
The expected digests are never edited: a changed digest means stored receipts no longer replay.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from autobots.application.experts import RunBinding
from autobots.application.runs import (
    AdmissionResult,
    Fresh,
    IdempotencyConflict,
    Inheritance,
    Inherited,
    LinkRefused,
    RunAdmission,
    RunGrant,
    admit,
    admit_run,
    request_hash,
)
from autobots.application.sql import SqlParams
from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import LOOP_TOOL_GRANTS
from sql_fakes import ScriptedRows

WORKSPACE = UUID("0a000000-0000-4000-8000-000000000001")
ACTOR = UUID("0a000000-0000-4000-8000-000000000002")
PERSON = UUID("0a000000-0000-4000-8000-000000000003")
SESSION = UUID("0a000000-0000-4000-8000-000000000004")
EXPERT = UUID("0a000000-0000-4000-8000-000000000005")
PARENT = UUID("0a000000-0000-4000-8000-000000000006")
ROOT = UUID("0a000000-0000-4000-8000-000000000007")
EARLIER = UUID("0a000000-0000-4000-8000-000000000008")
REPLAYED = UUID("0a000000-0000-4000-8000-000000000009")
STORED_GOAL = "  Repeat the stored goal  "
PLAN = {"propose_plan": 1, "complete_task": 1, "read_offload": 1}
LOOP = {**PLAN, "calculate": 1}
INHERITED_SNAPSHOT = {"version": 1, "bindings": {"coordinator": "openrouter_terra"}}

# Captured from the admission code at 9785411, before R-30 changed it. Never edit these values.
FINGERPRINTS = {
    "api_goal": "02dcf43b990efa771bb5388e781285f8ddc257d00940fb4a092de9f8f3aed8b0",
    "api_goal_in_full": "55f01a25319233c2b77d5ca75803eaede62a25db6cc0b888fba8d4ed377bd876",
    "api_session_expert": "ccfd8da273b1da7ce44cd283e8062e1d54308e355ee650592394df2a7b5b4139",
    "api_repeat": "c7f024a9e7e5521209f266ec509ec04240067d0869f553f52f8c1fecc2affd4e",
    "api_continue": "8a9f176f03200f64b7e83605c83d883b0b10ca7c58ce552ed032649ec7599d4d",
    "routine_expert": "2268da0744d82d6bbd1256239769d447f3430b4120c1cfce70e49ef07b7a90a2",
    "workflow": "7a5534586a99a49f4759560eabbb6d462012940422fbc900e0cbf829b8c24711",
    "improvement_replay": "0eaadb43bff660a43cff07cea52cb35aabd349292e44d9b34995b7c73fbca7cc",
    "browse_trial": "c02b68d1da0733957599b82ac3cf18ec8f5725b9a9179f9f90e3ddf593dc6d60",
    "assignment_child": "c245e43a12216d4d1b1e43af7e727853634940fce6c9c017f8b965827052b5e3",
}


def caller_shapes() -> dict[str, dict[str, Any]]:
    """What each caller passes `admit_run`, keyword for keyword, with fixed values."""
    policy = resolve_role_policy()
    return {
        # api/run_routes.py post_run, with no session.
        "api_goal": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "Write the report",
            "limit_micro_usd": 1_000_000,
            "policy": policy,
            "acceptance_criteria": (),
            "continues_run_id": None,
            "required_artifacts": (),
            "input_documents": (),
            "binding": None,
            "run_profile": None,
        },
        # post_run with every optional field the request can carry.
        "api_goal_in_full": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "  Compare the two tables  ",
            "limit_micro_usd": 250_000,
            "policy": resolve_role_policy(run_profile="openrouter_terra"),
            "acceptance_criteria": ("  Names the larger total ", "   ", "Shows the difference"),
            "continues_run_id": None,
            "required_artifacts": (
                RequiredArtifact(name="report.md", must_contain=["Total", "Difference"]),
            ),
            "input_documents": (
                InputDocument(path="inputs/notes.txt", content="plain notes"),
                InputDocument(path="inputs/table.csv", content="a,b\n1,2", media_type="text/csv"),
            ),
            "binding": None,
            "run_profile": "openrouter_terra",
        },
        # post_run through a session, with resolve_binding's RunBinding.
        "api_session_expert": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "Summarize the inputs",
            "limit_micro_usd": 1_000_000,
            "policy": policy,
            "acceptance_criteria": ("Cites a source",),
            "binding": RunBinding(
                session_id=SESSION,
                expert_id=EXPERT,
                version=3,
                instructions="Be brief.",
                tools={**PLAN, "calculate": 1, "web_search": 1},
                role_bindings={"researcher": "openrouter_terra"},
            ),
        },
        # post_run repeating an earlier goal: no text, so it is read from the stored request.
        "api_repeat": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": None,
            "limit_micro_usd": 1_000,
            "policy": policy,
            "continues_run_id": EARLIER,
        },
        # post_run continuing an ended run with new text.
        "api_continue": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "Try again with the figures",
            "limit_micro_usd": 1_000,
            "policy": policy,
            "continues_run_id": EARLIER,
        },
        # application/routines.py, an occurrence of a routine whose target is an Expert.
        "routine_expert": {
            "actor_id": ACTOR,
            "goal_text": "Check the overnight figures",
            "limit_micro_usd": 500_000,
            "policy": policy,
            "binding": SimpleNamespace(
                session_id=None,
                expert_id=EXPERT,
                version=2,
                instructions="Routine instructions\n\nReference: a skill",
                tools={**PLAN, "calculate": 1},
            ),
        },
        # application/workflows.py create_execution.
        "workflow": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "Workflow Weekly digest, version 4",
            "limit_micro_usd": 750_000,
            "policy": policy,
            "input_documents": (
                InputDocument(
                    path="inputs/brief.md", content="# Brief", media_type="text/markdown"
                ),
            ),
            "binding": SimpleNamespace(
                session_id=SESSION,
                expert_id=None,
                version=None,
                instructions="",
                tools={**LOOP, "assign_specialist": 1, "workflow_approval": 1},
            ),
        },
        # application/improvements.py replay_candidate, one held-out task.
        "improvement_replay": {
            "actor_id": PERSON,
            "started_by": PERSON,
            "goal_text": "Find the quarterly figure",
            "limit_micro_usd": 100_000,
            "acceptance_criteria": ("States the figure",),
            "policy": policy,
            "binding": SimpleNamespace(
                session_id=None,
                expert_id=None,
                version=None,
                instructions="Reference skill:\nfigures:\nRead the table first.",
                tools=dict(LOOP),
            ),
        },
        # operations/browse_trial.py run_trial, with its class built by type().
        "browse_trial": {
            "actor_id": ACTOR,
            "goal_text": "Live browse trial",
            "limit_micro_usd": 1_000_000,
            "policy": policy,
            "binding": type(
                "Binding",
                (),
                {
                    "session_id": None,
                    "expert_id": EXPERT,
                    "version": 1,
                    "instructions": "",
                    "tools": {**PLAN, "browse_goal": 1},
                },
            )(),
        },
        # application/assignments.py, a child admitted under its parent's run.
        "assignment_child": {
            "actor_id": PARENT,
            "goal_text": "Total the second table",
            "limit_micro_usd": 20_000,
            "acceptance_criteria": ("Gives the total",),
            "inherit": Inheritance(
                parent_run_id=PARENT,
                root_run_id=ROOT,
                snapshot=INHERITED_SNAPSHOT,
                tools={"calculate": 1},
                paths=("inputs", "outputs/child-1"),
                instructions="Child instructions",
                session_id=SESSION,
                expert_id=EXPERT,
                version=3,
            ),
        },
    }


def answered(row: tuple[Any, ...] | None) -> ScriptedRows:
    return ScriptedRows([] if row is None else [row])


class Connection:
    """Answers admission's reads, and logs every statement with the transaction around it."""

    def __init__(
        self,
        *,
        receipt: tuple[str, dict[str, Any]] | None = None,
        previous: str | None = "succeeded",
        stored_goal: str | None = STORED_GOAL,
    ) -> None:
        self.receipt = receipt
        self.previous = previous
        self.stored_goal = stored_goal
        self.log: list[tuple[str, Sequence[Any]]] = []

    async def execute(self, statement: str, values: SqlParams | None = None, /) -> ScriptedRows:
        self.log.append((statement, tuple(values or ())))
        if "from app_private.idempotency_receipts" in statement:
            return answered(self.receipt)
        if statement.startswith("select status from public.runs"):
            return answered(None if self.previous is None else (self.previous,))
        if "original_request" in statement:
            return answered(None if self.stored_goal is None else (self.stored_goal,))
        if "event_sequence = event_sequence + 1" in statement:
            return answered((1,))
        return answered(None)

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.log.append(("begin", ()))
        try:
            yield
        except BaseException:
            self.log.append(("rollback", ()))
            raise
        self.log.append(("commit", ()))

    def written(self, table: str) -> list[Sequence[Any]]:
        return [values for statement, values in self.log if f"insert into {table} " in statement]

    def fingerprint(self) -> str:
        (receipt,) = self.written("app_private.idempotency_receipts")
        return str(receipt[5])

    def run_row(self) -> Sequence[Any]:
        (row,) = self.written("public.runs")
        return row

    def goal_spec(self) -> dict[str, Any]:
        (row,) = self.written("app_private.goal_specs")
        spec: dict[str, Any] = json.loads(row[1])
        return spec


Admit = Callable[[Connection, str], Coroutine[Any, Any, AdmissionResult]]


async def keyword_admission(connection: Connection, shape: str) -> AdmissionResult:
    """The keyword form the database checks call, with each binding in its captured shape."""
    options = dict(caller_shapes()[shape])
    return await admit_run(
        connection, workspace_id=WORKSPACE, idempotency_key=f"key-{shape}", **options
    )


def as_request(shape: str) -> RunAdmission:
    """The typed request each caller builds: post_run's RunBinding, a child's Inheritance, and a
    RunGrant for a routine, a workflow, a held-out replay or a trial."""
    options = dict(caller_shapes()[shape])
    inherit = options.pop("inherit", None)
    binding = options.pop("binding", None)
    policy = options.pop("policy", None)
    started_by = options.pop("started_by", None)
    if binding is not None and not isinstance(binding, RunBinding):
        binding = RunGrant(
            instructions=binding.instructions,
            tools=binding.tools,
            session_id=binding.session_id,
            expert_id=binding.expert_id,
            version=binding.version,
        )
    origin = Inherited(inherit) if inherit is not None else Fresh(policy, binding, started_by)
    return RunAdmission(
        workspace_id=WORKSPACE, idempotency_key=f"key-{shape}", origin=origin, **options
    )


async def typed_admission(connection: Connection, shape: str) -> AdmissionResult:
    return await admit(connection, as_request(shape))


ADMISSIONS: dict[str, Admit] = {"keywords": keyword_admission, "request": typed_admission}


def admitted(shape: str, admit: Admit) -> Connection:
    connection = Connection()
    asyncio.run(admit(connection, shape))
    return connection


def test_request_hash_encodes_sorted_compact_json_with_strings_for_other_values() -> None:
    payload = {"b": [EXPERT, 2], "a": {"z": None, "y": "  kept  "}}
    assert (
        request_hash(payload) == "3d6f6a3f893d0d1a6144a1c59d8ded2c0a1d0718c95f26f34faa17c0f3fe93c7"
    )


def test_every_caller_shape_has_a_golden_fingerprint() -> None:
    assert set(caller_shapes()) == set(FINGERPRINTS)


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
@pytest.mark.parametrize("shape", sorted(FINGERPRINTS))
def test_each_caller_shape_keeps_its_golden_fingerprint(shape: str, way: str) -> None:
    assert admitted(shape, ADMISSIONS[way]).fingerprint() == FINGERPRINTS[shape]


# What each shape writes on the run row, in the insert's parameter order: session, Expert, version,
# parent, root, started_by, and the run whose started_by a child takes (Decision 0015).
RUN_SCOPE = {
    "api_goal": (None, None, None, None, None, PERSON, None),
    "api_goal_in_full": (None, None, None, None, None, PERSON, None),
    "api_session_expert": (SESSION, EXPERT, 3, None, None, PERSON, None),
    "api_repeat": (None, None, None, None, None, PERSON, None),
    "api_continue": (None, None, None, None, None, PERSON, None),
    "routine_expert": (None, EXPERT, 2, None, None, None, None),
    "workflow": (SESSION, None, None, None, None, PERSON, None),
    "improvement_replay": (None, None, None, None, None, PERSON, None),
    "browse_trial": (None, EXPERT, 1, None, None, None, None),
    "assignment_child": (SESSION, EXPERT, 3, PARENT, ROOT, None, PARENT),
}


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
@pytest.mark.parametrize("shape", sorted(RUN_SCOPE))
def test_each_caller_shape_writes_its_scope_and_started_by(shape: str, way: str) -> None:
    connection = admitted(shape, ADMISSIONS[way])
    row = connection.run_row()
    options = caller_shapes()[shape]
    assert (row[8], row[9], row[10], row[11], row[12], row[14], row[15]) == RUN_SCOPE[shape]
    assert row[1:4] == (WORKSPACE, "queued", options["limit_micro_usd"])
    assert row[7] == options.get("continues_run_id")
    snapshot = json.loads(row[6])
    if "inherit" in options:
        assert snapshot == INHERITED_SNAPSHOT
    else:
        policy = options["policy"]
        assert snapshot["version"] == policy.version
        assert snapshot["bindings"] == {r.value: p.value for r, p in policy.bindings.items()}


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
@pytest.mark.parametrize("shape", sorted(FINGERPRINTS))
def test_each_caller_shape_freezes_its_goal_tools_instructions_and_paths(
    shape: str, way: str
) -> None:
    connection = admitted(shape, ADMISSIONS[way])
    options = caller_shapes()[shape]
    grant = options.get("inherit") or options.get("binding")
    spec = connection.goal_spec()
    request = STORED_GOAL if options["goal_text"] is None else options["goal_text"]
    goal = request.strip()
    criteria = [text.strip() for text in options.get("acceptance_criteria", ()) if text.strip()]
    assert connection.run_row()[4:6] == (goal, goal[:200])
    assert spec["objective"] == goal
    assert spec["original_request"] == request
    assert spec["criteria"] == {f"c{i}": text for i, text in enumerate(criteria or [goal], 1)}
    assert spec["allowed_tools"] == (dict(grant.tools) if grant else LOOP_TOOL_GRANTS)
    assert spec["instructions"] == (grant.instructions if grant else "")
    inherited = options.get("inherit")
    assert spec["allowed_paths"] == (list(inherited.paths) if inherited else ["inputs", "outputs"])
    assert spec["required_artifacts"] == [
        item.model_dump() for item in options.get("required_artifacts", ())
    ]
    documents = options.get("input_documents", ())
    files = connection.written("app_private.run_files")
    assert [(row[1], row[2], row[4]) for row in files] == [
        (item.path, item.content, item.media_type) for item in documents
    ]


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
def test_run_job_inputs_goal_event_and_receipt_commit_in_one_transaction(way: str) -> None:
    connection = admitted("api_goal_in_full", ADMISSIONS[way])
    begin = connection.log.index(("begin", ()))
    assert connection.log[-1] == ("commit", ())
    tables = [
        words[2] if words[0] == "insert" else words[1]
        for words in (statement.split() for statement, _ in connection.log[begin + 1 : -1])
        if words[0] in {"insert", "update"}
    ]
    assert tables == [
        "public.runs",
        "app_private.run_jobs",
        "app_private.run_files",
        "app_private.run_files",
        "app_private.goal_specs",
        "public.runs",
        "public.run_events",
        "app_private.idempotency_receipts",
    ]
    assert all(
        not statement.startswith(("insert", "update")) for statement, _ in connection.log[:begin]
    )


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
def test_a_repeat_with_the_same_content_replays_the_receipt_and_writes_nothing(way: str) -> None:
    stored = (
        FINGERPRINTS["routine_expert"],
        {"run_id": str(REPLAYED), "version": 4, "status": "running"},
    )
    connection = Connection(receipt=stored)
    result = asyncio.run(ADMISSIONS[way](connection, "routine_expert"))
    assert (result.run_id, result.version, result.status, result.replayed) == (
        REPLAYED,
        4,
        "running",
        True,
    )
    assert not [statement for statement, _ in connection.log if statement.startswith("insert")]


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
def test_a_repeat_with_other_content_is_refused(way: str) -> None:
    stored = (FINGERPRINTS["api_goal"], {"run_id": str(REPLAYED), "version": 1, "status": "queued"})
    connection = Connection(receipt=stored)
    with pytest.raises(IdempotencyConflict):
        asyncio.run(ADMISSIONS[way](connection, "routine_expert"))
    assert connection.log[-1] == ("rollback", ())


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
@pytest.mark.parametrize("previous", [None, "running"])
def test_only_an_ended_run_in_the_workspace_can_be_continued(
    way: str, previous: str | None
) -> None:
    connection = Connection(previous=previous)
    with pytest.raises(LinkRefused):
        asyncio.run(ADMISSIONS[way](connection, "api_continue"))
    assert not [statement for statement, _ in connection.log if statement.startswith("insert")]


@pytest.mark.parametrize("way", sorted(ADMISSIONS))
def test_a_repeat_needs_a_goal_run_of_its_own_before_anything_is_locked(way: str) -> None:
    connection = Connection(stored_goal=None)
    with pytest.raises(LinkRefused):
        asyncio.run(ADMISSIONS[way](connection, "api_repeat"))
    assert [statement for statement, _ in connection.log if statement == "begin"] == []


def test_a_childs_inheritance_replaces_any_binding_policy_and_started_by() -> None:
    connection = Connection()
    other = SimpleNamespace(
        session_id=None, expert_id=None, version=None, instructions="ignored", tools={}
    )
    asyncio.run(
        admit_run(
            connection,
            workspace_id=WORKSPACE,
            idempotency_key="key-child-with-extras",
            **caller_shapes()["assignment_child"],
            policy=resolve_role_policy(),
            binding=other,
            started_by=PERSON,
        )
    )
    row = connection.run_row()
    assert connection.fingerprint() == FINGERPRINTS["assignment_child"]
    assert (row[8], row[9], row[10], row[11], row[12], row[14], row[15]) == RUN_SCOPE[
        "assignment_child"
    ]
    assert json.loads(row[6]) == INHERITED_SNAPSHOT
    assert connection.goal_spec()["instructions"] == "Child instructions"


def test_a_run_needs_a_role_policy_or_an_inheritance_and_writes_nothing_without() -> None:
    options = dict(caller_shapes()["api_goal"])
    del options["policy"]
    connection = Connection()
    with pytest.raises(ValueError, match="a run needs a role policy or an inherited one"):
        asyncio.run(
            admit_run(connection, workspace_id=WORKSPACE, idempotency_key="key-none", **options)
        )
    assert not [statement for statement, _ in connection.log if statement.startswith("insert")]
