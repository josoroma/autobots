"""Binding an execution to one exact published version, and reading it back, PRD 7.3.

An execution names one version and hash, so later versions don't reach it. Its run is admitted as
any run is, under the workspace's saved policy, and the workflow runner drives it
(application/workflow_runner.py). Definitions and drafts are application/workflows.py (PPRD-04).
"""

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from autobots.application.experts import open_session
from autobots.application.idempotency import receipted
from autobots.application.run_admission import saved_workspace_policy
from autobots.application.run_projection import public_text
from autobots.application.runs import (
    CommandKey,
    Fresh,
    Idempotent,
    RunAdmission,
    RunGrant,
    admit,
)
from autobots.application.sql import SqlConnection, all_rows, optional_row
from autobots.application.workflows import WorkflowRefused
from autobots.contracts.experts import SessionExpert
from autobots.contracts.persisted import ExecutionReceipt
from autobots.contracts.plans import InputDocument
from autobots.contracts.workflows import (
    EmissionView,
    ExecutionBinding,
    ExecutionView,
    InstanceView,
)
from autobots.domain import workflows as graphs
from autobots.domain.models import ProfileNotOffered, RolePolicy
from autobots.domain.runs import RunStatus
from autobots.domain.tools import workflow_grant
from autobots.domain.workflow_execution import InstanceState, instance_states
from autobots.persistence.rows import (
    EmissionRow,
    ExecutionRow,
    NodeInstanceRow,
    PublishedVersionRow,
)

DEFAULT_LIMIT_MICRO_USD = 1_000_000


async def _published(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, version: int
) -> PublishedVersionRow:
    found = await optional_row(
        connection,
        PublishedVersionRow,
        "select v.graph, v.graph_hash, v.block_versions, w.name from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    if found is None:
        raise WorkflowRefused("workflow_version_not_found")
    return found


async def _agent_session(
    connection: SqlConnection, workspace_id: UUID, actor_id: UUID, graph: Mapping[str, Any]
) -> UUID | None:
    """An agent step can assign only the Experts its graph names. No person asked for this
    session, so it stores no receipt (PPRD-04)."""
    experts = sorted(set(graphs.agent_expert_ids(graph)))
    if not experts:
        return None
    return await open_session(
        connection,
        workspace_id=workspace_id,
        actor_id=actor_id,
        kind="coordinator",
        experts=[SessionExpert(expert_id=UUID(expert)) for expert in experts],
    )


async def _execution_policy(
    connection: SqlConnection, workspace_id: UUID, graph: Mapping[str, Any]
) -> RolePolicy:
    """With no Expert's role bindings, and a profile not offered refuses only when an agent step
    will call a model, so a workflow without one runs under any saved choice. Each agent step's
    child inherits this policy, and the workflow's preview shows it (Decision 0028 E6)."""
    saved = await saved_workspace_policy(connection, workspace_id)
    try:
        return saved.for_new_work(require_offer=graphs.needs_model(graph))
    except ProfileNotOffered as refused:
        raise WorkflowRefused(refused.code, reason=refused.reason) from None


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


def _binding(
    execution_id: UUID,
    run_id: UUID,
    workflow_id: UUID,
    version: int,
    published: PublishedVersionRow,
) -> ExecutionBinding:
    return ExecutionBinding(
        schema_version=1,
        id=execution_id,
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_version=version,
        graph_hash=published.graph_hash,
        block_versions=published.block_versions,
    )


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
    limit_micro_usd: int = DEFAULT_LIMIT_MICRO_USD,
    tools: list[str] | None = None,
    started_by: UUID | None = None,
) -> ExecutionBinding:
    """An execution always names one exact version and hash. Later versions don't reach it. Its
    policy is always the workspace's saved one, checked as offered when the graph calls a model."""
    published = await _published(connection, workspace_id, workflow_id, version)
    errors = graphs.input_errors(published.graph, inputs)
    if errors:
        raise WorkflowRefused("workflow_inputs_invalid", errors)
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "create_execution",
        str(workflow_id),
        {"version": version, "inputs": inputs},
    )
    async with receipted(connection, command, ExecutionReceipt) as receipt:
        if receipt.prior is not None:
            run_id = await _receipt_run(connection, workspace_id, receipt.prior)
            return _binding(receipt.prior.execution_id, run_id, workflow_id, version, published)
        execution_id = uuid4()
        session_id = await _agent_session(connection, workspace_id, actor_id, published.graph)
        policy = await _execution_policy(connection, workspace_id, published.graph)
        admitted = await admit(
            connection,
            RunAdmission(
                workspace_id=workspace_id,
                actor_id=actor_id,
                idempotency_key=f"workflow:{execution_id}",
                goal_text=f"Workflow {published.name}, version {version}",
                limit_micro_usd=limit_micro_usd,
                origin=Fresh(
                    policy,
                    RunGrant(instructions="", tools=workflow_grant(tools), session_id=session_id),
                    started_by=started_by,
                ),
                input_documents=documents,
            ),
        )
        await connection.execute(
            "insert into public.workflow_executions (id, workspace_id, workflow_id, "
            "workflow_version, graph_hash, block_versions, inputs, created_by, run_id) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                execution_id,
                workspace_id,
                workflow_id,
                version,
                published.graph_hash,
                json.dumps(published.block_versions),
                json.dumps(inputs),
                actor_id,
                admitted.run_id,
            ),
        )
        await receipt.store(ExecutionReceipt(execution_id=execution_id, run_id=admitted.run_id))
    return _binding(execution_id, admitted.run_id, workflow_id, version, published)


async def needs_model(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, version: int
) -> bool:
    """A workflow with no agent step can run with no provider key. A version this workspace
    doesn't have needs none, and creating its execution refuses it as not found."""
    cursor = await connection.execute(
        "select v.graph from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    row = await cursor.fetchone()
    return row is not None and graphs.needs_model(row[0])


async def read_execution(
    connection: SqlConnection, workspace_id: UUID, execution_id: UUID
) -> ExecutionView:
    """Instances with no row yet are waiting. That comes from the graph, not from a stored guess
    (domain workflow_execution.instance_states)."""
    row = await optional_row(
        connection,
        ExecutionRow,
        "select e.workflow_id, e.workflow_version, e.graph_hash, e.block_versions, e.run_id, "
        "r.status as run_status, u.stop_reason, v.graph, e.current_instance, exists (select 1 "
        "from public.approval_requests a where a.run_id = r.id and a.status = 'pending') "
        "as approval_pending from public.workflow_executions e "
        "join public.runs r on r.id = e.run_id "
        "join public.workflow_versions v on v.workflow_id = e.workflow_id "
        "and v.version = e.workflow_version "
        "left join app_private.run_usage u on u.run_id = e.run_id "
        "where e.id = %s and e.workspace_id = %s",
        (execution_id, workspace_id),
    )
    if row is None:
        raise WorkflowRefused("execution_not_found")
    saved = await all_rows(
        connection,
        NodeInstanceRow,
        "select instance_key, node_id, iteration, status, error_code "
        "from public.workflow_node_instances where execution_id = %s",
        (execution_id,),
    )
    run_status = RunStatus(row.run_status)
    states = instance_states(
        [instance_state(item) for item in saved],
        [node["id"] for node in row.graph["nodes"]],
        row.current_instance,
        run_status,
        row.approval_pending,
    )
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
        run_status=run_status,
        stop_reason=row.stop_reason,
        instances=[instance_view(state) for state in states],
        emissions=[emission_view(item) for item in emissions],
    )


def instance_state(row: NodeInstanceRow) -> InstanceState:
    return InstanceState(row.instance_key, row.node_id, row.iteration, row.status, row.error_code)


def instance_view(state: InstanceState) -> InstanceView:
    return InstanceView(
        key=state.key,
        node_id=state.node_id,
        iteration=state.iteration,
        status=str(state.status),
        error_code=state.error_code,
    )


def emission_view(row: EmissionRow) -> EmissionView:
    """An emitted value is a model's text, so a key it was shown is redacted."""
    return EmissionView(
        instance_key=row.instance_key,
        port=row.port,
        sequence=row.sequence,
        value=public_text(row.value),
    )
