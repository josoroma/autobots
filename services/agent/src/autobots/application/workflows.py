"""Workflow definitions: drafts, immutable published versions and the workflow views, PRD 7.3.

Binding an execution to one exact version, and reading it back, is
application/workflow_executions.py; running it is application/workflow_runner.py; the row facts
beside each workflow are application/workflow_overview.py (PPRD-04).
"""

import json
import logging
from collections import defaultdict
from datetime import UTC
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation
from pydantic import ValidationError

from autobots.application.idempotency import (
    ExpectedVersionStale,
    VersionedRowMissing,
    next_version,
    receipted,
    set_latest,
)
from autobots.application.runs import CommandKey, Idempotent
from autobots.application.sql import SqlConnection, all_rows, optional_row, stored
from autobots.application.workflow_overview import RowFacts, row_facts
from autobots.contracts.persisted import WorkflowCreatedReceipt, WorkflowVersionReceipt
from autobots.contracts.workflows import (
    WORKFLOW_SOURCES,
    WorkflowDraftView,
    WorkflowGraph,
    WorkflowSource,
    WorkflowVersionView,
    WorkflowView,
)
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.workflows import (
    GraphError,
    block_versions,
    graph_hash,
    ir_normalized,
    validate_graph,
)
from autobots.persistence.rows import DraftRow, WorkflowRow, WorkflowVersionRow

logger = logging.getLogger("autobots.workflows")


class WorkflowRefused(Refusal):
    kinds = MappingProxyType(
        {
            "workflow_not_found": RefusalKind.NOT_FOUND,
            "workflow_draft_not_found": RefusalKind.NOT_FOUND,
            "workflow_version_not_found": RefusalKind.NOT_FOUND,
            "execution_not_found": RefusalKind.NOT_FOUND,
            "workflow_invalid": RefusalKind.INVALID,
            "workflow_inputs_invalid": RefusalKind.INVALID,
        }
    )

    def __init__(
        self, code: str, errors: list[GraphError] | None = None, reason: str | None = None
    ) -> None:
        super().__init__(code)
        self.errors = errors or []
        # A reason safe to show, such as which model isn't offered.
        self.reason = reason


def _plain(graph: WorkflowGraph) -> dict[str, Any]:
    return ir_normalized(graph.model_dump(mode="json"))


def draft_view(row: DraftRow) -> tuple[WorkflowDraftView | None, bool]:
    """The saved draft, and whether one is stored that can't be read. An owner can write a draft
    through PostgREST that the shape check admits and WorkflowGraph refuses (US-15.12#1, migration
    59). It reads as absent and is reported as unreadable, so the list and the workflow still load,
    the editor says that saving replaces it, and the owner discards it by key (R-56, SQLI-13)."""
    try:
        graph = WorkflowGraph.model_validate(row.graph)
    except ValidationError:
        logger.warning("workflow.draft_unreadable", extra={"fields": {"workflow": row.workflow_id}})
        return None, True
    return WorkflowDraftView(graph=graph, saved_at=row.saved_at.astimezone(UTC)), False


def version_view(row: WorkflowVersionRow) -> WorkflowVersionView:
    """An unknown stored source raises, instead of reaching a client."""
    return WorkflowVersionView(
        version=row.version,
        graph_hash=row.graph_hash,
        source=stored(WORKFLOW_SOURCES, row.source),
        graph=WorkflowGraph.model_validate(row.graph),
        block_versions=row.block_versions,
    )


def _view(
    workflow: WorkflowRow,
    versions: list[WorkflowVersionView],
    draft: DraftRow | None,
    facts: RowFacts,
) -> WorkflowView:
    shown, unreadable = draft_view(draft) if draft is not None else (None, False)
    return WorkflowView(
        schema_version=1,
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        latest_version=workflow.latest_version,
        versions=versions,
        draft=shown,
        draft_unreadable=unreadable,
        experts=facts.experts,
        step_count=facts.step_count,
        last_execution=facts.last_execution,
        run_count=facts.run_count,
    )


async def _views(
    connection: SqlConnection, workspace_id: UUID, workflows: list[WorkflowRow]
) -> list[WorkflowView]:
    """Each workflow's view, from one read of each kind for all of them (PPRD-11). WF-01's row
    facts come from each one's latest published version and its executions."""
    if not workflows:
        return []
    ids = [workflow.id for workflow in workflows]
    rows = await all_rows(
        connection,
        WorkflowVersionRow,
        "select workflow_id, version, graph_hash, source, graph, block_versions "
        "from public.workflow_versions where workflow_id = any(%s) order by workflow_id, version",
        (ids,),
    )
    versions: dict[UUID, list[WorkflowVersionView]] = defaultdict(list)
    for row in rows:
        versions[row.workflow_id].append(version_view(row))
    drafts = await all_rows(
        connection,
        DraftRow,
        "select workflow_id, graph, saved_at from public.workflow_drafts "
        "where workflow_id = any(%s)",
        (ids,),
    )
    draft_of = {draft.workflow_id: draft for draft in drafts}
    latest = {
        workflow_id: (
            ir_normalized(versions[workflow_id][-1].graph.model_dump(mode="json"))
            if versions[workflow_id]
            else None
        )
        for workflow_id in ids
    }
    facts = await row_facts(connection, workspace_id, latest)
    return [
        _view(workflow, versions[workflow.id], draft_of.get(workflow.id), facts[workflow.id])
        for workflow in workflows
    ]


async def get_workflow(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID
) -> WorkflowView:
    row = await optional_row(
        connection,
        WorkflowRow,
        "select id, name, latest_version, description from public.workflows "
        "where id = %s and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    if row is None:
        raise WorkflowRefused("workflow_not_found")
    (view,) = await _views(connection, workspace_id, [row])
    return view


async def list_workflows(connection: SqlConnection, workspace_id: UUID) -> list[WorkflowView]:
    rows = await all_rows(
        connection,
        WorkflowRow,
        "select id, name, latest_version, description from public.workflows "
        "where workspace_id = %s order by name",
        (workspace_id,),
    )
    return await _views(connection, workspace_id, rows)


async def create_workflow(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    name: str,
    description: str | None = None,
) -> WorkflowView:
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "create_workflow",
        str(workspace_id),
        # Only when given, so a receipt from before descriptions still matches.
        {"name": name, **({"description": description} if description else {})},
    )
    async with receipted(connection, command, WorkflowCreatedReceipt) as receipt:
        if receipt.prior is not None:
            return await get_workflow(connection, workspace_id, receipt.prior.workflow_id)
        cursor = await connection.execute(
            "select 1 from public.workflows where workspace_id = %s and name = %s",
            (workspace_id, name),
        )
        if await cursor.fetchone() is not None:
            raise WorkflowRefused("workflow_name_taken")
        workflow_id = uuid4()
        await connection.execute(
            "insert into public.workflows (id, workspace_id, name, description) "
            "values (%s, %s, %s, %s)",
            (workflow_id, workspace_id, name, description),
        )
        await receipt.store(WorkflowCreatedReceipt(workflow_id=workflow_id))
    return await get_workflow(connection, workspace_id, workflow_id)


async def set_description(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, description: str | None
) -> WorkflowView:
    """PRD-Studio WF-06. Describing a workflow changes no version."""
    cursor = await connection.execute(
        "update public.workflows set description = %s where id = %s and workspace_id = %s "
        "returning id",
        (description, workflow_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise WorkflowRefused("workflow_not_found")
    return await get_workflow(connection, workspace_id, workflow_id)


async def rename_workflow(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, name: str
) -> WorkflowView:
    """Only the name changes (Decision 0037 N3). The workspace's unique constraint decides a taken
    name, a lost race included, and the workflow's own name violates nothing (N2, N5)."""
    try:
        cursor = await connection.execute(
            "update public.workflows set name = %s where id = %s and workspace_id = %s "
            "returning id",
            (name, workflow_id, workspace_id),
        )
    except UniqueViolation:
        raise WorkflowRefused("workflow_name_taken") from None
    if await cursor.fetchone() is None:
        raise WorkflowRefused("workflow_not_found")
    return await get_workflow(connection, workspace_id, workflow_id)


async def save_draft(
    connection: SqlConnection,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    graph: WorkflowGraph,
) -> WorkflowView:
    """WF-02: one draft per workflow, replaced by each save. A draft needn't be valid yet."""
    cursor = await connection.execute(
        "insert into public.workflow_drafts (workflow_id, workspace_id, graph, saved_by) "
        "select id, workspace_id, %s, %s from public.workflows where id = %s and workspace_id = %s "
        "on conflict (workflow_id) do update set graph = excluded.graph, "
        "saved_by = excluded.saved_by, saved_at = now() returning workflow_id",
        (json.dumps(_plain(graph)), actor_id, workflow_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise WorkflowRefused("workflow_not_found")
    return await get_workflow(connection, workspace_id, workflow_id)


async def _require_workflow(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID
) -> None:
    cursor = await connection.execute(
        "select 1 from public.workflows where id = %s and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise WorkflowRefused("workflow_not_found")


async def discard_draft(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID
) -> WorkflowView:
    """Removes only the draft, by its key and without reading its graph, so a draft that no longer
    validates can still be discarded (R-56, SQLI-13). Published versions and their hashes are
    untouched."""
    cursor = await connection.execute(
        "delete from public.workflow_drafts where workflow_id = %s and workspace_id = %s "
        "returning workflow_id",
        (workflow_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        # Not found names a workflow outside this workspace before a missing draft.
        await _require_workflow(connection, workspace_id, workflow_id)
        raise WorkflowRefused("workflow_draft_not_found")
    return await get_workflow(connection, workspace_id, workflow_id)


async def _owned_draft(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID
) -> WorkflowDraftView | None:
    """This workspace's workflow's readable draft, or None. Another workspace's is not found."""
    await _require_workflow(connection, workspace_id, workflow_id)
    row = await optional_row(
        connection,
        DraftRow,
        "select workflow_id, graph, saved_at from public.workflow_drafts where workflow_id = %s",
        (workflow_id,),
    )
    return draft_view(row)[0] if row is not None else None


async def publish_draft(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    expected_version: int,
) -> WorkflowView:
    """Validates the draft and publishes it as the next immutable version, under the expected
    version. Only then is the draft removed, so a stale or invalid publish keeps it."""
    draft = await _owned_draft(connection, workspace_id, workflow_id)
    if draft is None:
        raise WorkflowRefused("workflow_draft_not_found")
    await _publish(
        connection,
        workspace_id=workspace_id,
        actor_id=actor_id,
        workflow_id=workflow_id,
        idempotency_key=idempotency_key,
        expected_version=expected_version,
        graph=draft.graph,
        source="user",
    )
    await connection.execute(
        "delete from public.workflow_drafts where workflow_id = %s and graph = %s",
        (workflow_id, json.dumps(_plain(draft.graph))),
    )
    return await get_workflow(connection, workspace_id, workflow_id)


async def publish_version(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    expected_version: int,
    graph: WorkflowGraph,
    source: WorkflowSource,
) -> WorkflowView:
    """A model's proposal goes through the same validation, and is marked as what it is."""
    await _publish(
        connection,
        workspace_id=workspace_id,
        actor_id=actor_id,
        workflow_id=workflow_id,
        idempotency_key=idempotency_key,
        expected_version=expected_version,
        graph=graph,
        source=source,
    )
    return await get_workflow(connection, workspace_id, workflow_id)


async def _publish(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    expected_version: int,
    graph: WorkflowGraph,
    source: WorkflowSource,
) -> None:
    """The next immutable version, once, under its idempotency key. A replay changes nothing."""
    plain = _plain(graph)
    errors = validate_graph(plain)
    if errors:
        raise WorkflowRefused("workflow_invalid", errors)
    digest = graph_hash(plain)
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "publish_workflow",
        str(workflow_id),
        {"expected": expected_version, "graph": digest, "source": source},
    )
    async with receipted(connection, command, WorkflowVersionReceipt) as receipt:
        if receipt.prior is not None:
            return
        try:
            version = await next_version(
                connection, "workflows", workflow_id, workspace_id, expected_version
            )
        except VersionedRowMissing:
            raise WorkflowRefused("workflow_not_found") from None
        except ExpectedVersionStale:
            raise WorkflowRefused("workflow_version_conflict") from None
        await connection.execute(
            "insert into public.workflow_versions (workflow_id, version, graph, graph_hash, "
            "block_versions, source, created_by) values (%s, %s, %s, %s, %s, %s, %s)",
            (
                workflow_id,
                version,
                json.dumps(plain),
                digest,
                json.dumps(block_versions(plain)),
                source,
                actor_id,
            ),
        )
        await set_latest(connection, "workflows", workflow_id, version)
        await receipt.store(WorkflowVersionReceipt(version=version))
