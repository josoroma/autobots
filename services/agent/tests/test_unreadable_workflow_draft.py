"""A saved draft that fails WorkflowGraph can't break the workflow list or its own discard.

An owner may write a draft through PostgREST (US-15.12), and migration 59's CHECK admits any object
holding nodes and links arrays. Such a draft reads as absent and is reported as unreadable, so the
list and the workflow still load, the editor can say that saving replaces it, and the owner discards
it by key or saves over it (R-56, SQLI-13, Decision 0029 F3).
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from autobots.application import workflows
from autobots.application.workflows import (
    WorkflowRefused,
    discard_draft,
    get_workflow,
    list_workflows,
    publish_draft,
)

WORKSPACE = uuid4()
# Passes the CHECK, fails WorkflowGraph: a node has no block or version.
UNREADABLE: dict[str, Any] = {"nodes": [{"id": "x"}], "links": []}
READABLE: dict[str, Any] = {"nodes": [], "links": []}


class Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


SAVED_AT = datetime(2026, 11, 15, tzinfo=UTC)
DISCARD = "delete from public.workflow_drafts where workflow_id = %s and workspace_id = %s"


class Workflows:
    """One workspace's workflows, each with its saved draft or None, answering workflows.py."""

    def __init__(self, drafts: dict[UUID, dict[str, Any] | None]) -> None:
        self.names = {workflow: f"Flow {index}" for index, workflow in enumerate(drafts)}
        self.drafts = {workflow: draft for workflow, draft in drafts.items() if draft is not None}
        self.sent: list[str] = []

    async def execute(self, sql: str, values: tuple[Any, ...] = ()) -> Cursor:
        self.sent.append(sql)
        if sql.startswith("select id, name, latest_version, description from public.workflows"):
            wanted = self.names if "order by name" in sql else {values[0]}
            found = [(item, name) for item, name in self.names.items() if item in wanted]
            return Cursor([(item, name, 0, None) for item, name in found])
        if sql.startswith("select version, graph_hash"):
            return Cursor([])
        if sql.startswith("select graph, saved_at from public.workflow_drafts"):
            draft = self.drafts.get(values[0])
            return Cursor([] if draft is None else [(draft, SAVED_AT)])
        if sql.startswith("select workspace_id from public.workflows"):
            return Cursor([(WORKSPACE,)])
        if sql.startswith(DISCARD):
            gone = self.drafts.pop(values[0], None) if values[1] == WORKSPACE else None
            return Cursor([] if gone is None else [(values[0],)])
        raise AssertionError(f"unexpected SQL: {sql}")


@pytest.fixture(autouse=True)
def _no_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    """The row facts read executions and Experts, which these cases don't concern."""

    async def nothing(*_args: object, **_kwargs: object) -> list[object]:
        return []

    async def none(*_args: object, **_kwargs: object) -> int:
        return 0

    monkeypatch.setattr(workflows, "recent_executions", nothing)
    monkeypatch.setattr(workflows, "expert_chain", nothing)
    monkeypatch.setattr(workflows, "run_count", none)


def test_an_unreadable_draft_reads_as_absent_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    flow = uuid4()
    with caplog.at_level(logging.WARNING, logger="autobots.workflows"):
        view = asyncio.run(get_workflow(Workflows({flow: UNREADABLE}), WORKSPACE, flow))
    assert (view.draft, view.draft_unreadable) == (None, True)
    assert [record.getMessage() for record in caplog.records] == ["workflow.draft_unreadable"]


def test_the_list_still_loads_beside_an_unreadable_draft() -> None:
    broken, kept = uuid4(), uuid4()
    views = asyncio.run(list_workflows(Workflows({broken: UNREADABLE, kept: READABLE}), WORKSPACE))
    drafts = {view.id: (view.draft is not None, view.draft_unreadable) for view in views}
    assert drafts == {broken: (False, True), kept: (True, False)}


def test_an_unreadable_draft_is_discarded_by_its_key() -> None:
    flow = uuid4()
    connection = Workflows({flow: UNREADABLE})
    view = asyncio.run(discard_draft(connection, WORKSPACE, flow))
    assert (view.draft, view.draft_unreadable) == (None, False)
    assert flow not in connection.drafts
    # Deleted before any read of the stored graph.
    assert connection.sent[0].startswith(DISCARD)


def test_an_unreadable_draft_is_never_published() -> None:
    flow = uuid4()
    connection = Workflows({flow: UNREADABLE})
    with pytest.raises(WorkflowRefused) as refused:
        asyncio.run(
            publish_draft(
                connection,
                workspace_id=WORKSPACE,
                actor_id=uuid4(),
                workflow_id=flow,
                idempotency_key="k",
                expected_version=0,
            )
        )
    assert refused.value.code == "workflow_draft_not_found"
    assert flow in connection.drafts


def test_discarding_with_no_draft_is_refused() -> None:
    flow = uuid4()
    with pytest.raises(WorkflowRefused) as refused:
        asyncio.run(discard_draft(Workflows({flow: None}), WORKSPACE, flow))
    assert refused.value.code == "workflow_draft_not_found"


def test_discarding_another_workspace_s_workflow_is_not_found() -> None:
    with pytest.raises(WorkflowRefused) as refused:
        asyncio.run(discard_draft(Workflows({}), WORKSPACE, uuid4()))
    assert refused.value.code == "workflow_not_found"
