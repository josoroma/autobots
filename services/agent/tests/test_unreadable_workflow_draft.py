"""A saved draft that fails WorkflowGraph can't break the workflow list or its own discard.

An owner may write a draft through PostgREST (US-15.12), and migration 59's CHECK admits any object
holding nodes and links arrays. Such a draft reads as absent and is reported as unreadable, so the
list and the workflow still load, the editor can say that saving replaces it, and the owner discards
it by key or saves over it (R-56, SQLI-13, Decision 0029 F3).
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from autobots.application import workflows
from autobots.application.sql import SqlParams
from autobots.application.workflow_overview import RowFacts
from autobots.application.workflows import (
    WorkflowRefused,
    discard_draft,
    get_workflow,
    list_workflows,
    publish_draft,
)
from sql_fakes import ScriptedRows

WORKSPACE = uuid4()
# Passes the CHECK, fails WorkflowGraph: a node has no block or version.
UNREADABLE: dict[str, Any] = {"nodes": [{"id": "x"}], "links": []}
READABLE: dict[str, Any] = {"nodes": [], "links": []}


SAVED_AT = datetime(2026, 11, 15, tzinfo=UTC)
DISCARD = "delete from public.workflow_drafts where workflow_id = %s and workspace_id = %s"


class Workflows:
    """One workspace's workflows, each with its saved draft or None, answering workflows.py."""

    def __init__(self, drafts: dict[UUID, dict[str, Any] | None]) -> None:
        self.names = {workflow: f"Flow {index}" for index, workflow in enumerate(drafts)}
        self.drafts = {workflow: draft for workflow, draft in drafts.items() if draft is not None}
        self.sent: list[str] = []

    async def execute(self, sql: str, params: SqlParams | None = None, /) -> ScriptedRows:
        values: tuple[Any, ...] = tuple(params) if isinstance(params, Sequence) else ()
        self.sent.append(sql)
        if sql.startswith("select id, name, latest_version, description from public.workflows"):
            wanted = self.names if "order by name" in sql else {values[0]}
            found = [(item, name) for item, name in self.names.items() if item in wanted]
            return ScriptedRows(
                [(item, name, 0, None) for item, name in found],
                ("id", "name", "latest_version", "description"),
            )
        if sql.startswith("select workflow_id, version, graph_hash"):
            return ScriptedRows()
        if sql.startswith("select workflow_id, graph, saved_at from public.workflow_drafts"):
            asked: list[UUID] = values[0] if "any(%s)" in sql else [values[0]]
            return ScriptedRows(
                [(item, self.drafts[item], SAVED_AT) for item in asked if item in self.drafts],
                ("workflow_id", "graph", "saved_at"),
            )
        if sql.startswith("select 1 from public.workflows where id = %s and workspace_id = %s"):
            owned = values[0] in self.names and values[1] == WORKSPACE
            return ScriptedRows([(1,)] if owned else [])
        if sql.startswith(DISCARD):
            gone = self.drafts.pop(values[0], None) if values[1] == WORKSPACE else None
            return ScriptedRows([] if gone is None else [(values[0],)])
        raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield


@pytest.fixture(autouse=True)
def _no_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    """The row facts read executions and Experts, which these cases don't concern."""

    async def nothing(
        _connection: object, _workspace_id: UUID, latest: Mapping[UUID, object]
    ) -> dict[UUID, RowFacts]:
        return {item: RowFacts([], 0, None, 0) for item in latest}

    monkeypatch.setattr(workflows, "row_facts", nothing)


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
