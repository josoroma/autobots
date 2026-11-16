"""A workflow execution's session for its agent steps stores no receipt, and checks its Experts as
a person's session does (PPRD-04, refactor plan R-63).

No person asked for that session and no retry can name it again, so it stores no idempotency
receipt. It still pins only Experts and versions this workspace has. The fakes answer scripted
rows; no database, socket or model is used.
"""

import asyncio
import json
from typing import Any
from uuid import UUID

import pytest

from autobots.application.experts import ExpertRefused
from autobots.application.workflow_executions import create_execution
from fake_api import FakeConnection, FakeDatabase

WORKSPACE = UUID("0f000000-0000-4000-8000-0000000000a1")
ACTOR = UUID("0f000000-0000-4000-8000-0000000000a2")
FLOW = UUID("0f000000-0000-4000-8000-0000000000a3")
EXPERT = UUID("0f000000-0000-4000-8000-0000000000a4")
RECEIPTS = "app_private.idempotency_receipts"
GRAPH: dict[str, Any] = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "ask", "block": "agent", "version": 1, "config": {"expert_id": str(EXPERT)}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [
        {"source": "in", "source_port": "value", "target": "ask", "target_port": "goal"},
        {"source": "ask", "source_port": "result", "target": "out", "target_port": "value"},
    ],
}
CONFIG = {"tools": ["calculate"]}


def database(*, expert_found: bool = True) -> FakeDatabase:
    found = FakeDatabase([])
    found.answer("event_sequence = event_sequence + 1", (1,))
    found.answer(
        "select v.graph, v.graph_hash",
        {"graph": GRAPH, "graph_hash": "digest", "block_versions": {}, "name": "Digest"},
    )
    if expert_found:
        found.answer(
            "select id, name, latest_version from public.experts",
            {"id": EXPERT, "name": "Researcher", "latest_version": 3},
        )
        found.answer(
            "select e.id as expert_id, v.version, e.name, v.config from public.experts e",
            {"expert_id": EXPERT, "version": 3, "name": "Researcher", "config": CONFIG},
        )
    return found


def execute(found: FakeDatabase) -> object:
    return asyncio.run(
        create_execution(
            FakeConnection(found),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            workflow_id=FLOW,
            idempotency_key="k",
            version=1,
            inputs={"in": "x"},
        )
    )


def test_an_agent_steps_session_pins_its_expert_and_stores_no_receipt() -> None:
    found = database()
    execute(found)
    (session,) = found.written("public.sessions")
    assert isinstance(session, tuple)
    assert (session[1], session[2], json.loads(session[3]), session[4]) == (
        WORKSPACE,
        "coordinator",
        [{"expert_id": str(EXPERT), "version": 3}],
        ACTOR,
    )
    operations = [values[2] for values in found.written(RECEIPTS) if isinstance(values, tuple)]
    assert "create_session" not in operations
    assert "create_execution" in operations


def test_an_expert_this_workspace_lacks_refuses_the_execution_before_any_run() -> None:
    found = database(expert_found=False)
    with pytest.raises(ExpertRefused) as refused:
        execute(found)
    assert refused.value.code == "expert_not_found"
    assert found.written("public.sessions") == []
    assert found.written("public.runs") == []
