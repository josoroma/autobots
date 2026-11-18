"""List views read each kind of child row once for the whole list, not once per row (PPRD-11,
refactor plan R-63).

Each list is read for one parent and for three, and both send the same statements: a list of any
length costs the same round trips on its pooled connection. Children answered interleaved across
three parents land under their own parent, in the order read. The fakes answer scripted rows; no
database is used.
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from autobots.application.experts import list_experts
from autobots.application.improvements import list_candidates
from autobots.application.routines import list_routines
from autobots.application.workflows import list_workflows
from fake_api import FakeConnection, FakeDatabase

WORKSPACE = UUID("0f200000-0000-4000-8000-000000000001")
ROUTINE_CONFIG = {
    "target": {"kind": "expert", "id": str(UUID(int=7)), "version": 1},
    "trigger": {"kind": "interval", "minutes": 60},
    "timezone": "UTC",
    "goal": "Check",
    "inputs": {},
    "tools": None,
    "limit_micro_usd": 1000,
    "overlap": "skip",
}


def workflows(database: FakeDatabase, count: int) -> Coroutine[Any, Any, object]:
    database.answer(
        "select id, name, latest_version, description from public.workflows",
        *[
            {"id": uuid4(), "name": f"Flow {index}", "latest_version": 0, "description": None}
            for index in range(count)
        ],
    )
    return list_workflows(FakeConnection(database), WORKSPACE)


def experts(database: FakeDatabase, count: int) -> Coroutine[Any, Any, object]:
    database.answer(
        "select id, name, latest_version from public.experts",
        *[
            {"id": uuid4(), "name": f"Expert {index}", "latest_version": 1}
            for index in range(count)
        ],
    )
    return list_experts(FakeConnection(database), WORKSPACE)


def routines(database: FakeDatabase, count: int) -> Coroutine[Any, Any, object]:
    ids = [uuid4() for _ in range(count)]
    database.answer(
        "select id, name, enabled, latest_version from public.routines",
        *[
            {"id": item, "name": f"Routine {index}", "enabled": True, "latest_version": 1}
            for index, item in enumerate(ids)
        ],
    )
    database.answer(
        "select v.routine_id, v.config from public.routine_versions",
        *[{"routine_id": item, "config": ROUTINE_CONFIG} for item in ids],
    )
    return list_routines(FakeConnection(database), WORKSPACE)


def candidates(database: FakeDatabase, count: int) -> Coroutine[Any, Any, object]:
    database.answer(
        "from public.improvement_candidates where workspace_id",
        *[
            {
                "id": uuid4(),
                "kind": "memory",
                "key": f"k{index}",
                "content": "c",
                "status": "proposed",
                "regression_results": None,
            }
            for index in range(count)
        ],
    )
    return list_candidates(FakeConnection(database), WORKSPACE)


LISTS: dict[str, Callable[[FakeDatabase, int], Coroutine[Any, Any, object]]] = {
    "workflows": workflows,
    "experts": experts,
    "routines": routines,
    "candidates": candidates,
}


def sent(name: str, count: int) -> list[str]:
    database = FakeDatabase([])
    found = asyncio.run(LISTS[name](database, count))
    assert isinstance(found, list) and len(found) == count
    return [statement for statement, _ in database.statements]


@pytest.mark.parametrize("name", sorted(LISTS))
def test_a_longer_list_sends_no_more_statements(name: str) -> None:
    assert sent(name, 3) == sent(name, 1)


@pytest.mark.parametrize("name", sorted(LISTS))
def test_an_empty_list_reads_nothing_more(name: str) -> None:
    assert len(sent(name, 0)) == 1


A, B, C = UUID(int=0xA1), UUID(int=0xB1), UUID(int=0xC1)
MOMENT = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def at(hours: int) -> datetime:
    return MOMENT - timedelta(hours=hours)


@pytest.mark.asyncio
async def test_each_workflow_shows_its_own_versions_in_order_its_draft_and_its_runs() -> None:
    database = FakeDatabase([])
    database.answer(
        "select id, name, latest_version, description from public.workflows",
        *[
            {"id": item, "name": name, "latest_version": 2, "description": None}
            for item, name in ((A, "a"), (B, "b"), (C, "c"))
        ],
    )
    empty: dict[str, Any] = {"nodes": [], "links": []}
    one_step = {
        "nodes": [{"id": "in", "block": "input", "version": 1, "config": {"type": "string"}}],
        "links": [],
    }

    def version(workflow: UUID, number: int, graph: dict[str, Any]) -> dict[str, Any]:
        return {
            "workflow_id": workflow,
            "version": number,
            "graph_hash": f"{workflow.int:x}-{number}",
            "source": "user",
            "graph": graph,
            "block_versions": {},
        }

    database.answer(
        "from public.workflow_versions where workflow_id",
        version(B, 1, empty),
        version(A, 1, empty),
        version(B, 2, one_step),
    )
    database.answer(
        "from public.workflow_drafts where workflow_id",
        {"workflow_id": C, "graph": empty, "saved_at": MOMENT},
    )
    database.answer("count(*) as runs", {"workflow_id": A, "runs": 3})
    views = await list_workflows(FakeConnection(database), WORKSPACE)
    shown = [
        (
            view.id,
            [item.graph_hash for item in view.versions],
            view.step_count,
            view.draft is not None,
            view.run_count,
        )
        for view in views
    ]
    assert shown == [
        (A, [f"{A.int:x}-1"], 0, False, 3),
        (B, [f"{B.int:x}-1", f"{B.int:x}-2"], 1, False, 0),
        (C, [], 0, True, 0),
    ]


@pytest.mark.asyncio
async def test_each_expert_shows_its_own_versions_in_order_and_its_own_runs() -> None:
    database = FakeDatabase([])
    database.answer(
        "select id, name, latest_version from public.experts",
        *[
            {"id": item, "name": name, "latest_version": 2}
            for item, name in ((A, "a"), (B, "b"), (C, "c"))
        ],
    )
    database.answer(
        "from public.expert_versions where expert_id",
        {"expert_id": B, "version": 1, "config": {"purpose": "b1"}},
        {"expert_id": A, "version": 1, "config": {"purpose": "a1"}},
        {"expert_id": B, "version": 2, "config": {"purpose": "b2"}},
        {"expert_id": A, "version": 2, "config": {"purpose": "a2"}},
    )
    database.answer(
        "count(*) as run_count",
        {"expert_id": C, "run_count": 4, "last_run_at": at(1)},
        {"expert_id": A, "run_count": 1, "last_run_at": at(9)},
    )
    views = await list_experts(FakeConnection(database), WORKSPACE)
    shown = [
        (
            view.id,
            [(item.version, item.config.purpose) for item in view.versions],
            view.run_count,
            view.last_run_at,
        )
        for view in views
    ]
    assert shown == [
        (A, [(1, "a1"), (2, "a2")], 1, at(9)),
        (B, [(1, "b1"), (2, "b2")], 0, None),
        (C, [], 4, at(1)),
    ]


@pytest.mark.asyncio
async def test_each_routine_shows_its_own_configuration_and_occurrences_newest_first() -> None:
    database = FakeDatabase([])
    database.answer(
        "select id, name, enabled, latest_version from public.routines",
        *[
            {"id": item, "name": name, "enabled": True, "latest_version": 1}
            for item, name in ((A, "a"), (B, "b"), (C, "c"))
        ],
    )
    database.answer(
        "select v.routine_id, v.config from public.routine_versions",
        *[
            {"routine_id": item, "config": {**ROUTINE_CONFIG, "goal": f"Goal {name}"}}
            for item, name in ((C, "c"), (A, "a"), (B, "b"))
        ],
    )

    def occurred(routine: UUID, hours: int) -> dict[str, Any]:
        return {
            "routine_id": routine,
            "occurrence_time": at(hours),
            "routine_version": 1,
            "status": "missed",
            "reason": "host_away",
            "run_id": None,
        }

    database.answer(
        "from public.routine_occurrences o where o.routine_id",
        occurred(B, 1),
        occurred(A, 2),
        occurred(B, 3),
        occurred(A, 4),
    )
    views = await list_routines(FakeConnection(database), WORKSPACE)
    shown = [
        (view.id, view.config.goal, [item.occurrence_time for item in view.occurrences])
        for view in views
    ]
    assert shown == [
        (A, "Goal a", [at(2), at(4)]),
        (B, "Goal b", [at(1), at(3)]),
        (C, "Goal c", []),
    ]


@pytest.mark.asyncio
async def test_each_candidate_shows_its_own_latest_replay_with_its_runs_in_order() -> None:
    database = FakeDatabase([])
    database.answer(
        "from public.improvement_candidates where workspace_id",
        *[
            {
                "id": item,
                "kind": "skill",
                "key": name,
                "content": "c",
                "status": "regression_passed",
                "regression_results": None,
            }
            for item, name in ((A, "a"), (B, "b"), (C, "c"))
        ],
    )
    first, second, third = UUID(int=1), UUID(int=2), UUID(int=3)

    def replayed(candidate: UUID, run: UUID, goal: str, status: str) -> dict[str, Any]:
        return {
            "candidate_id": candidate,
            "replay_id": UUID(int=candidate.int + 0x100),
            "run_id": run,
            "goal_text": goal,
            "status": status,
        }

    database.answer(
        "from app_private.improvement_replays r",
        replayed(A, first, "first", "succeeded"),
        replayed(C, third, "third", "running"),
        replayed(A, second, "second", "failed"),
    )
    views = await list_candidates(FakeConnection(database), WORKSPACE)
    shown = [
        (
            view.id,
            None
            if view.replay is None
            else (view.replay.id, view.replay.state, [run.run_id for run in view.replay.runs]),
        )
        for view in views
    ]
    assert shown == [
        (A, (UUID(int=A.int + 0x100), "failed", [first, second])),
        (B, None),
        (C, (UUID(int=C.int + 0x100), "running", [third])),
    ]
