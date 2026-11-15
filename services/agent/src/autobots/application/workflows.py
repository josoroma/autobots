"""Publishing immutable workflow versions, and binding executions to them exactly, PRD 7.3."""

import json
import logging
from datetime import UTC
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from autobots.application.experts import create_session
from autobots.application.run_admission import saved_workspace_policy
from autobots.application.run_projection import public_text
from autobots.application.runs import (
    Fresh,
    RunAdmission,
    RunGrant,
    admit,
    existing_receipt,
    request_hash,
    store_receipt,
)
from autobots.application.sql import (
    SqlConnection,
    all_rows,
    one,
    optional_row,
    required_row,
    stored,
)
from autobots.application.workflow_overview import expert_chain, recent_executions, run_count
from autobots.contracts.experts import SessionExpert
from autobots.contracts.persisted import (
    ExecutionReceipt,
    WorkflowCreatedReceipt,
    WorkflowVersionReceipt,
)
from autobots.contracts.plans import InputDocument
from autobots.contracts.workflows import (
    WORKFLOW_SOURCES,
    EmissionView,
    ExecutionBinding,
    ExecutionView,
    InstanceView,
    WorkflowDraftView,
    WorkflowGraph,
    WorkflowSource,
    WorkflowVersionView,
    WorkflowView,
)
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import ProfileNotOffered, RolePolicy
from autobots.domain.runs import TERMINAL, RunStatus
from autobots.domain.tools import PLAN_TOOLS, WORKFLOW_TOOLS
from autobots.domain.workflows import (
    GraphError,
    block_versions,
    graph_hash,
    input_errors,
    ir_normalized,
    validate_graph,
)
from autobots.persistence.rows import (
    EmissionRow,
    ExecutionProgressRow,
    ExecutionRow,
    NodeInstanceRow,
    PublishedVersionRow,
    WorkflowRow,
    WorkflowVersionRow,
)

logger = logging.getLogger("autobots.workflows")
DEFAULT_LIMIT_MICRO_USD = 1_000_000


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


async def _draft(
    connection: SqlConnection, workflow_id: UUID
) -> tuple[WorkflowDraftView | None, bool]:
    """The saved draft, and whether one is stored that can't be read. An owner can write a draft
    through PostgREST that the shape check admits and WorkflowGraph refuses (US-15.12#1, migration
    59). It reads as absent and is reported as unreadable, so the list and the workflow still load,
    the editor says that saving replaces it, and the owner discards it by key (R-56, SQLI-13)."""
    cursor = await connection.execute(
        "select graph, saved_at from public.workflow_drafts where workflow_id = %s",
        (workflow_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None, False
    try:
        graph = WorkflowGraph.model_validate(row[0])
    except ValidationError:
        logger.warning("workflow.draft_unreadable", extra={"fields": {"workflow": workflow_id}})
        return None, True
    return WorkflowDraftView(graph=graph, saved_at=row[1].astimezone(UTC).isoformat()), False


def version_view(row: WorkflowVersionRow) -> WorkflowVersionView:
    """An unknown stored source raises, instead of reaching a client."""
    return WorkflowVersionView(
        version=row.version,
        graph_hash=row.graph_hash,
        source=stored(WORKFLOW_SOURCES, row.source),
        graph=WorkflowGraph.model_validate(row.graph),
        block_versions=row.block_versions,
    )


async def _view(connection: SqlConnection, workflow: WorkflowRow) -> WorkflowView:
    rows = await all_rows(
        connection,
        WorkflowVersionRow,
        "select version, graph_hash, source, graph, block_versions "
        "from public.workflow_versions where workflow_id = %s order by version",
        (workflow.id,),
    )
    versions = [version_view(row) for row in rows]
    draft, unreadable = await _draft(connection, workflow.id)
    return WorkflowView(
        schema_version=1,
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        latest_version=workflow.latest_version,
        versions=versions,
        draft=draft,
        draft_unreadable=unreadable,
        **await _overview(connection, workflow.id, versions),
    )


async def _overview(
    connection: SqlConnection, workflow_id: UUID, versions: list[WorkflowVersionView]
) -> dict[str, Any]:
    """WF-01's row facts, from the latest published version and this workflow's executions."""
    (workspace_id,) = await one(
        connection, "select workspace_id from public.workflows where id = %s", (workflow_id,)
    )
    latest = ir_normalized(versions[-1].graph.model_dump(mode="json")) if versions else None
    recent = await recent_executions(connection, workspace_id, workflow_id, limit=1)
    return {
        "experts": await expert_chain(connection, workspace_id, latest),
        "step_count": len(latest["nodes"]) if latest else 0,
        "last_execution": recent[0] if recent else None,
        "run_count": await run_count(connection, workspace_id, workflow_id),
    }


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
    return await _view(connection, row)


async def list_workflows(connection: SqlConnection, workspace_id: UUID) -> list[WorkflowView]:
    rows = await all_rows(
        connection,
        WorkflowRow,
        "select id, name, latest_version, description from public.workflows "
        "where workspace_id = %s order by name",
        (workspace_id,),
    )
    return [await _view(connection, row) for row in rows]


async def create_workflow(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    name: str,
    description: str | None = None,
) -> WorkflowView:
    # Only when given, so a receipt from before descriptions still matches.
    fingerprint = request_hash(
        {"name": name, **({"description": description} if description else {})}
    )
    scope = (workspace_id, actor_id, "create_workflow", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint, WorkflowCreatedReceipt)
        if existing is not None:
            return await get_workflow(connection, workspace_id, existing.workflow_id)
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
        await store_receipt(
            connection, scope, fingerprint, WorkflowCreatedReceipt(workflow_id=workflow_id)
        )
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
        await get_workflow(connection, workspace_id, workflow_id)
        raise WorkflowRefused("workflow_draft_not_found")
    return await get_workflow(connection, workspace_id, workflow_id)


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
    view = await get_workflow(connection, workspace_id, workflow_id)
    if view.draft is None:
        raise WorkflowRefused("workflow_draft_not_found")
    published = await publish_version(
        connection,
        workspace_id=workspace_id,
        actor_id=actor_id,
        workflow_id=workflow_id,
        idempotency_key=idempotency_key,
        expected_version=expected_version,
        graph=view.draft.graph,
        source="user",
    )
    await connection.execute(
        "delete from public.workflow_drafts where workflow_id = %s and graph = %s",
        (workflow_id, json.dumps(_plain(view.draft.graph))),
    )
    return await get_workflow(connection, workspace_id, published.id)


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
    plain = _plain(graph)
    errors = validate_graph(plain)
    if errors:
        raise WorkflowRefused("workflow_invalid", errors)
    digest = graph_hash(plain)
    fingerprint = request_hash({"expected": expected_version, "graph": digest, "source": source})
    scope = (workspace_id, actor_id, "publish_workflow", str(workflow_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint, WorkflowVersionReceipt)
        if existing is not None:
            return await get_workflow(connection, workspace_id, workflow_id)
        cursor = await connection.execute(
            "select latest_version from public.workflows "
            "where id = %s and workspace_id = %s for update",
            (workflow_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise WorkflowRefused("workflow_not_found")
        if row[0] != expected_version:
            raise WorkflowRefused("workflow_version_conflict")
        version = row[0] + 1
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
        await connection.execute(
            "update public.workflows set latest_version = %s where id = %s", (version, workflow_id)
        )
        await store_receipt(connection, scope, fingerprint, WorkflowVersionReceipt(version=version))
    return await get_workflow(connection, workspace_id, workflow_id)


async def _agent_session(
    connection: SqlConnection, workspace_id: UUID, actor_id: UUID, graph: dict[str, Any]
) -> UUID | None:
    """An agent step can assign only the Experts its graph names."""
    experts = sorted(
        {node["config"]["expert_id"] for node in graph["nodes"] if node["block"] == "agent"}
    )
    if not experts:
        return None
    session = await create_session(
        connection,
        workspace_id=workspace_id,
        actor_id=actor_id,
        idempotency_key=str(uuid4()),
        kind="coordinator",
        experts=[SessionExpert(expert_id=UUID(expert)) for expert in experts],
    )
    return session.id


async def _receipt_run(
    connection: SqlConnection, workspace_id: UUID, receipt: ExecutionReceipt
) -> UUID:
    """The run a stored execution receipt names. One stored from US-6.1 (9a0fb39) until US-6.2
    (902d1cd) names none, so its execution's own is read. An execution from then has none, and the
    retry is refused as not found instead of failing (refactor plan R-51)."""
    if receipt.run_id is not None:
        return receipt.run_id
    cursor = await connection.execute(
        "select run_id from public.workflow_executions where id = %s and workspace_id = %s",
        (receipt.execution_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None or row[0] is None:
        raise WorkflowRefused("execution_not_found")
    run_id: UUID = row[0]
    return run_id


async def create_execution(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    version: int,
    inputs: dict[str, Any],
    documents: tuple[InputDocument, ...] = (),
    policy: RolePolicy | None = None,
    limit_micro_usd: int = DEFAULT_LIMIT_MICRO_USD,
    tools: list[str] | None = None,
    started_by: UUID | None = None,
) -> ExecutionBinding:
    """An execution always names one exact version and hash. Later versions don't reach it."""
    published = await optional_row(
        connection,
        PublishedVersionRow,
        "select v.graph, v.graph_hash, v.block_versions, w.name from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    if published is None:
        raise WorkflowRefused("workflow_version_not_found")
    graph, digest, blocks, name = (
        published.graph,
        published.graph_hash,
        published.block_versions,
        published.name,
    )
    errors = input_errors(graph, inputs)
    if errors:
        raise WorkflowRefused("workflow_inputs_invalid", errors)
    fingerprint = request_hash({"version": version, "inputs": inputs})
    scope = (workspace_id, actor_id, "create_execution", str(workflow_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint, ExecutionReceipt)
        execution_id = existing.execution_id if existing else uuid4()
        run_id = await _receipt_run(connection, workspace_id, existing) if existing else None
        if existing is None:
            session_id = await _agent_session(connection, workspace_id, actor_id, graph)
            if policy is None:
                saved = await saved_workspace_policy(connection, workspace_id)
                try:
                    # With no Expert's role bindings, and a profile not offered refuses only when an
                    # agent step will call a model, so a workflow without one runs under any saved
                    # choice. Each agent step's child inherits this policy, and the workflow's
                    # preview shows it (Decision 0028 E6).
                    policy = saved.for_new_work(
                        require_offer=await needs_model(
                            connection, workspace_id, workflow_id, version
                        )
                    )
                except ProfileNotOffered as refused:
                    raise WorkflowRefused(refused.code, reason=refused.reason) from None
            granted = (
                WORKFLOW_TOOLS
                if tools is None
                else {
                    name: version
                    for name, version in WORKFLOW_TOOLS.items()
                    if name in tools or name in PLAN_TOOLS or name == "workflow_approval"
                }
            )
            admitted = await admit(
                connection,
                RunAdmission(
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    idempotency_key=f"workflow:{execution_id}",
                    goal_text=f"Workflow {name}, version {version}",
                    limit_micro_usd=limit_micro_usd,
                    origin=Fresh(
                        policy,
                        RunGrant(instructions="", tools=granted, session_id=session_id),
                        started_by=started_by,
                    ),
                    input_documents=documents,
                ),
            )
            run_id = admitted.run_id
            await connection.execute(
                "insert into public.workflow_executions (id, workspace_id, workflow_id, "
                "workflow_version, graph_hash, block_versions, inputs, created_by, run_id) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    execution_id,
                    workspace_id,
                    workflow_id,
                    version,
                    digest,
                    json.dumps(blocks),
                    json.dumps(inputs),
                    actor_id,
                    run_id,
                ),
            )
            await store_receipt(
                connection,
                scope,
                fingerprint,
                ExecutionReceipt(execution_id=execution_id, run_id=run_id),
            )
    assert run_id is not None
    return ExecutionBinding(
        schema_version=1,
        id=execution_id,
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_version=version,
        graph_hash=digest,
        block_versions=blocks,
    )


async def needs_model(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, version: int
) -> bool:
    """A workflow with no agent step can run with no provider key."""
    cursor = await connection.execute(
        "select v.graph from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    row = await cursor.fetchone()
    return row is not None and any(node["block"] == "agent" for node in row[0]["nodes"])


async def read_execution(
    connection: SqlConnection, workspace_id: UUID, execution_id: UUID
) -> ExecutionView:
    """Instances with no row yet are waiting. That comes from the graph, not from a stored guess."""
    row = await optional_row(
        connection,
        ExecutionRow,
        "select e.workflow_id, e.workflow_version, e.graph_hash, e.block_versions, e.run_id, "
        "r.status, u.stop_reason, v.graph from public.workflow_executions e "
        "join public.runs r on r.id = e.run_id "
        "join public.workflow_versions v on v.workflow_id = e.workflow_id "
        "and v.version = e.workflow_version "
        "left join app_private.run_usage u on u.run_id = e.run_id "
        "where e.id = %s and e.workspace_id = %s",
        (execution_id, workspace_id),
    )
    if row is None:
        raise WorkflowRefused("execution_not_found")
    graph = row.graph
    saved = await all_rows(
        connection,
        NodeInstanceRow,
        "select instance_key, node_id, iteration, status, error_code "
        "from public.workflow_node_instances where execution_id = %s",
        (execution_id,),
    )
    instances = [instance_view(item) for item in saved]
    started = {item.node_id for item in saved}
    progress = await required_row(
        connection,
        ExecutionProgressRow,
        "select e.current_instance, r.status as run_status, exists (select 1 "
        "from public.approval_requests a where a.run_id = r.id and a.status = 'pending') "
        "as approval_pending from public.workflow_executions e "
        "join public.runs r on r.id = e.run_id where e.id = %s",
        (execution_id,),
    )
    current, run_status = progress.current_instance, RunStatus(progress.run_status)
    approval_pending = progress.approval_pending
    settled = {item.instance_key for item in saved}

    def _unsaved_status(key: str) -> str:
        if key != current:
            return "not_run" if run_status in TERMINAL else "waiting"
        # This node started. On a finished run its effect may have happened, so it can't be
        # reported as never run.
        if run_status == "waiting_approval" or approval_pending:
            return "waiting_approval"
        if run_status == "running":
            return "running"
        return "waiting" if run_status == "queued" else "stopped_here"

    instances.extend(
        InstanceView(
            key=node["id"],
            node_id=node["id"],
            iteration=None,
            status=_unsaved_status(node["id"]),
            error_code=None,
        )
        for node in graph["nodes"]
        if node["id"] not in started and node["id"] != (current or "").split("#")[0]
    )
    if current and current not in settled:
        # An iteration is keyed apart from its node, so it's added by what's running.
        node_id = current.split("#")[0]
        iteration = int(current.split("#")[1]) if "#" in current else None
        instances.append(
            InstanceView(
                key=current,
                node_id=node_id,
                iteration=iteration,
                status=_unsaved_status(current),
                error_code=None,
            )
        )
    order = {node["id"]: index for index, node in enumerate(graph["nodes"])}
    instances.sort(key=lambda item: (order[item.node_id], item.iteration or 0))
    emissions = await all_rows(
        connection,
        EmissionRow,
        "select instance_key, port, sequence, value::text as value from public.workflow_emissions "
        "where execution_id = %s order by created_at, instance_key, port, sequence",
        (execution_id,),
    )
    return ExecutionView(
        schema_version=1,
        id=execution_id,
        workflow_id=row.workflow_id,
        workflow_version=row.workflow_version,
        graph_hash=row.graph_hash,
        block_versions=row.block_versions,
        run_id=row.run_id,
        run_status=RunStatus(row.status),
        stop_reason=row.stop_reason,
        instances=instances,
        emissions=[emission_view(item) for item in emissions],
    )


def instance_view(row: NodeInstanceRow) -> InstanceView:
    return InstanceView(
        key=row.instance_key,
        node_id=row.node_id,
        iteration=row.iteration,
        status=row.status,
        error_code=row.error_code,
    )


def emission_view(row: EmissionRow) -> EmissionView:
    """An emitted value is a model's text, so a key it was shown is redacted."""
    return EmissionView(
        instance_key=row.instance_key,
        port=row.port,
        sequence=row.sequence,
        value=public_text(row.value),
    )
