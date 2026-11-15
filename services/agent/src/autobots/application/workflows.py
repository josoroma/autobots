"""Publishing immutable workflow versions, and binding executions to them exactly, PRD 7.3."""

import json
from datetime import UTC
from typing import Any
from uuid import UUID, uuid4

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
from autobots.application.workflow_overview import expert_chain, recent_executions, run_count
from autobots.contracts.experts import SessionExpert
from autobots.contracts.plans import InputDocument
from autobots.contracts.workflows import (
    EmissionView,
    ExecutionBinding,
    ExecutionView,
    InstanceView,
    WorkflowDraftView,
    WorkflowGraph,
    WorkflowVersionView,
    WorkflowView,
)
from autobots.domain.models import ProfileNotOffered, RolePolicy
from autobots.domain.runs import TERMINAL
from autobots.domain.tools import DELEGATION_TOOL, LOOP_TOOL_GRANTS, PLAN_TOOLS
from autobots.domain.workflows import (
    GraphError,
    block_versions,
    graph_hash,
    input_errors,
    ir_normalized,
    validate_graph,
)

# What a workflow's own blocks reach. Its approval step is the only consequential one here.
DEFAULT_LIMIT_MICRO_USD = 1_000_000
WORKFLOW_TOOLS = {**LOOP_TOOL_GRANTS, DELEGATION_TOOL: 1, "workflow_approval": 1}


class WorkflowRefused(Exception):
    def __init__(
        self, code: str, errors: list[GraphError] | None = None, reason: str | None = None
    ) -> None:
        super().__init__(code)
        self.code = code
        self.errors = errors or []
        # A reason safe to show, such as which model isn't offered.
        self.reason = reason


def _plain(graph: WorkflowGraph) -> dict[str, Any]:
    return ir_normalized(graph.model_dump(mode="json"))


async def _draft(connection: Any, workflow_id: UUID) -> WorkflowDraftView | None:
    cursor = await connection.execute(
        "select graph, saved_at from public.workflow_drafts where workflow_id = %s",
        (workflow_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return WorkflowDraftView(
        graph=WorkflowGraph.model_validate(row[0]), saved_at=row[1].astimezone(UTC).isoformat()
    )


async def _view(
    connection: Any, workflow_id: UUID, name: str, latest: int, description: str | None
) -> WorkflowView:
    cursor = await connection.execute(
        "select version, graph_hash, source, graph, block_versions "
        "from public.workflow_versions where workflow_id = %s order by version",
        (workflow_id,),
    )
    versions = [
        WorkflowVersionView(
            version=row[0],
            graph_hash=row[1],
            source=row[2],
            graph=WorkflowGraph.model_validate(row[3]),
            block_versions=row[4],
        )
        for row in await cursor.fetchall()
    ]
    return WorkflowView(
        schema_version=1,
        id=workflow_id,
        name=name,
        description=description,
        latest_version=latest,
        versions=versions,
        draft=await _draft(connection, workflow_id),
        **await _overview(connection, workflow_id, versions),
    )


async def _overview(
    connection: Any, workflow_id: UUID, versions: list[WorkflowVersionView]
) -> dict[str, Any]:
    """WF-01's row facts, from the latest published version and this workflow's executions."""
    cursor = await connection.execute(
        "select workspace_id from public.workflows where id = %s", (workflow_id,)
    )
    row = await cursor.fetchone()
    workspace_id = row[0]
    latest = ir_normalized(versions[-1].graph.model_dump(mode="json")) if versions else None
    recent = await recent_executions(connection, workspace_id, workflow_id, limit=1)
    return {
        "experts": await expert_chain(connection, workspace_id, latest),
        "step_count": len(latest["nodes"]) if latest else 0,
        "last_execution": recent[0] if recent else None,
        "run_count": await run_count(connection, workspace_id, workflow_id),
    }


async def get_workflow(connection: Any, workspace_id: UUID, workflow_id: UUID) -> WorkflowView:
    cursor = await connection.execute(
        "select id, name, latest_version, description from public.workflows "
        "where id = %s and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise WorkflowRefused("workflow_not_found")
    return await _view(connection, *row)


async def list_workflows(connection: Any, workspace_id: UUID) -> list[WorkflowView]:
    cursor = await connection.execute(
        "select id, name, latest_version, description from public.workflows "
        "where workspace_id = %s order by name",
        (workspace_id,),
    )
    return [await _view(connection, *row) for row in await cursor.fetchall()]


async def create_workflow(
    connection: Any,
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
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_workflow(connection, workspace_id, UUID(existing["workflow_id"]))
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
        await store_receipt(connection, scope, fingerprint, {"workflow_id": str(workflow_id)})
    return await get_workflow(connection, workspace_id, workflow_id)


async def set_description(
    connection: Any, workspace_id: UUID, workflow_id: UUID, description: str | None
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
    connection: Any, workspace_id: UUID, actor_id: UUID, workflow_id: UUID, graph: WorkflowGraph
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


async def discard_draft(connection: Any, workspace_id: UUID, workflow_id: UUID) -> WorkflowView:
    """Removes only the draft. Published versions and their hashes are untouched."""
    view = await get_workflow(connection, workspace_id, workflow_id)
    if view.draft is None:
        raise WorkflowRefused("workflow_draft_not_found")
    await connection.execute(
        "delete from public.workflow_drafts where workflow_id = %s and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    return await get_workflow(connection, workspace_id, workflow_id)


async def publish_draft(
    connection: Any,
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
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    expected_version: int,
    graph: WorkflowGraph,
    source: str,
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
        existing = await existing_receipt(connection, scope, fingerprint)
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
        await store_receipt(connection, scope, fingerprint, {"version": version})
    return await get_workflow(connection, workspace_id, workflow_id)


async def _agent_session(
    connection: Any, workspace_id: UUID, actor_id: UUID, graph: dict[str, Any]
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


async def create_execution(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
    connection: Any,
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
    cursor = await connection.execute(
        "select v.graph, v.graph_hash, v.block_versions, w.name from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise WorkflowRefused("workflow_version_not_found")
    graph, digest, blocks, name = row
    errors = input_errors(graph, inputs)
    if errors:
        raise WorkflowRefused("workflow_inputs_invalid", errors)
    fingerprint = request_hash({"version": version, "inputs": inputs})
    scope = (workspace_id, actor_id, "create_execution", str(workflow_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        execution_id = UUID(existing["execution_id"]) if existing else uuid4()
        run_id = UUID(existing["run_id"]) if existing else None
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
                    raise WorkflowRefused(refused.code, reason=str(refused)) from None
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
                {"execution_id": str(execution_id), "run_id": str(run_id)},
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


async def needs_model(connection: Any, workspace_id: UUID, workflow_id: UUID, version: int) -> bool:
    """A workflow with no agent step can run with no provider key."""
    cursor = await connection.execute(
        "select v.graph from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    row = await cursor.fetchone()
    return row is not None and any(node["block"] == "agent" for node in row[0]["nodes"])


async def read_execution(connection: Any, workspace_id: UUID, execution_id: UUID) -> ExecutionView:
    """Instances with no row yet are waiting. That comes from the graph, not from a stored guess."""
    cursor = await connection.execute(
        "select e.workflow_id, e.workflow_version, e.graph_hash, e.block_versions, e.run_id, "
        "r.status, u.stop_reason, v.graph from public.workflow_executions e "
        "join public.runs r on r.id = e.run_id "
        "join public.workflow_versions v on v.workflow_id = e.workflow_id "
        "and v.version = e.workflow_version "
        "left join app_private.run_usage u on u.run_id = e.run_id "
        "where e.id = %s and e.workspace_id = %s",
        (execution_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise WorkflowRefused("execution_not_found")
    workflow_id, version, digest, blocks, run_id, run_status, stop_reason, graph = row
    cursor = await connection.execute(
        "select instance_key, node_id, iteration, status, error_code "
        "from public.workflow_node_instances where execution_id = %s",
        (execution_id,),
    )
    saved = await cursor.fetchall()
    instances = [
        InstanceView(
            key=item[0], node_id=item[1], iteration=item[2], status=item[3], error_code=item[4]
        )
        for item in saved
    ]
    started = {item[1] for item in saved}
    cursor = await connection.execute(
        "select e.current_instance, r.status, exists (select 1 from public.approval_requests a "
        "where a.run_id = r.id and a.status = 'pending') from public.workflow_executions e "
        "join public.runs r on r.id = e.run_id where e.id = %s",
        (execution_id,),
    )
    current, run_status, approval_pending = await cursor.fetchone()
    settled = {item[0] for item in saved}

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
    cursor = await connection.execute(
        "select instance_key, port, sequence, value::text from public.workflow_emissions "
        "where execution_id = %s order by created_at, instance_key, port, sequence",
        (execution_id,),
    )
    emissions = [
        EmissionView(
            instance_key=item[0], port=item[1], sequence=item[2], value=public_text(item[3])
        )
        for item in await cursor.fetchall()
    ]
    return ExecutionView(
        schema_version=1,
        id=execution_id,
        workflow_id=workflow_id,
        workflow_version=version,
        graph_hash=digest,
        block_versions=blocks,
        run_id=run_id,
        run_status=run_status,
        stop_reason=stop_reason,
        instances=instances,
        emissions=emissions,
    )
