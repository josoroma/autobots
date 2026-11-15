"""What Workflows shows beside each workflow, PRD-Studio WF-01, WF-03 and WF-04. Read only."""

from collections.abc import Mapping
from datetime import UTC
from typing import Any
from uuid import UUID

from autobots.application.model_admission import LEDGER_PARAMS, spend_columns, unreported_column
from autobots.application.run_admission import saved_workspace_policy
from autobots.application.sql import SqlConnection, all_rows
from autobots.contracts.workflows import (
    WorkflowExecutionSummary,
    WorkflowStepView,
)
from autobots.domain.models import PROFILES, ModelRole
from autobots.domain.runs import TERMINAL, RunStatus
from autobots.domain.workflows import AgentConfig, block_config, step_order
from autobots.persistence.records import ExpertConfigRecord, read_expert_config
from autobots.persistence.rows import ExecutionSummaryRow, ExpertConfigRow

# One execution per row, with the root run's ledger, as the run list and admission count it (RN-01,
# Decision 0029 F10).
_EXECUTIONS = (
    "select x.id, x.run_id, x.workflow_version, r.status, x.created_at as started_at, "
    "r.updated_at as run_updated_at, "
    f"r.created_at as run_created_at, {spend_columns('r')}, {unreported_column('r')} "
    "as unreported "
    "from public.workflow_executions x join public.runs r on r.id = x.run_id "
    "and r.workspace_id = x.workspace_id "
    "where x.workflow_id = %(workflow)s and x.workspace_id = %(workspace)s "
    "order by x.created_at desc, x.id limit %(limit)s"
)


def execution_summary(row: ExecutionSummaryRow) -> WorkflowExecutionSummary:
    """An unknown stored status raises, instead of reaching a client."""
    status = RunStatus(row.status)
    elapsed = (row.run_updated_at - row.run_created_at).total_seconds()
    return WorkflowExecutionSummary(
        id=row.id,
        run_id=row.run_id,
        version=row.workflow_version,
        status=status,
        charged_micro_usd=int(row.charged_micro_usd),
        reserved_micro_usd=int(row.reserved_micro_usd),
        unreported=bool(row.unreported),
        started_at=row.started_at.astimezone(UTC),
        # The run's own time, from admission to its last change, to the nearest second.
        duration_seconds=max(round(elapsed), 0) if status in TERMINAL else None,
    )


async def recent_executions(
    connection: SqlConnection, workspace_id: UUID, workflow_id: UUID, limit: int = 10
) -> list[WorkflowExecutionSummary]:
    rows = await all_rows(
        connection,
        ExecutionSummaryRow,
        _EXECUTIONS,
        {"workflow": workflow_id, "workspace": workspace_id, "limit": limit, **LEDGER_PARAMS},
    )
    return [execution_summary(row) for row in rows]


async def run_count(connection: SqlConnection, workspace_id: UUID, workflow_id: UUID) -> int:
    cursor = await connection.execute(
        "select count(*) from public.workflow_executions where workflow_id = %s "
        "and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _experts(
    connection: SqlConnection, workspace_id: UUID, expert_ids: list[str]
) -> dict[str, tuple[str, ExpertConfigRecord]]:
    """Each named Expert's name and latest configuration, in this workspace only."""
    if not expert_ids:
        return {}
    rows = await all_rows(
        connection,
        ExpertConfigRow,
        "select e.id::text as id, e.name, v.config from public.experts e "
        "join public.expert_versions v on v.expert_id = e.id and v.version = e.latest_version "
        "where e.workspace_id = %s and e.id::text = any(%s)",
        (workspace_id, expert_ids),
    )
    return {row.id: (str(row.name), read_expert_config(row.config)) for row in rows}


def _agent_expert(node: Mapping[str, Any]) -> str | None:
    """The Expert an agent step names, or None for any other step, or one that names none. Only an
    agent step's configuration is read, so another step's draft value can't fail a preview."""
    if node["block"] != "agent":
        return None
    config = block_config(node)
    return config.expert_id if isinstance(config, AgentConfig) else None


def _agent_experts(graph: Mapping[str, Any]) -> list[str]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    named = (_agent_expert(nodes[name]) for name in step_order(graph))
    return [expert_id for expert_id in named if expert_id is not None]


async def expert_chain(
    connection: SqlConnection, workspace_id: UUID, graph: Mapping[str, Any] | None
) -> list[str]:
    """WF-01: the Experts its agent steps use, in step order, such as Research analyst then
    Brief writer. An Expert used twice in a row is named once."""
    if graph is None:
        return []
    ordered = _agent_experts(graph)
    known = await _experts(connection, workspace_id, sorted(set(ordered)))
    chain: list[str] = []
    for expert_id in ordered:
        name = known.get(expert_id, ("Unavailable Expert", None))[0]
        if not chain or chain[-1] != name:
            chain.append(name)
    return chain


async def preview_steps(
    connection: SqlConnection, workspace_id: UUID, graph: Mapping[str, Any]
) -> list[WorkflowStepView]:
    """WF-03: each step in order. An agent step shows its Expert, the model its child run would
    use if the workflow started now, and the Expert's tools. An approval step is marked as the
    gate."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    known = await _experts(connection, workspace_id, sorted(set(_agent_experts(graph))))
    saved = await saved_workspace_policy(connection, workspace_id)
    # An agent step's child inherits the workflow run's frozen policy, which creating the execution
    # resolves with no Expert's role bindings, so each step shows that policy's executor, not its
    # Expert's binding (Decision 0028 E6). A preview refuses nothing, and with no step that has a
    # known Expert, it resolves nothing.
    executor = None
    if known:
        policy = saved.for_new_work(require_offer=False)
        executor = PROFILES[policy.bindings[ModelRole.EXECUTOR]].canonical_id
    steps = []
    for name in step_order(graph):
        node = nodes[name]
        expert_id = _agent_expert(node)
        found = known.get(expert_id) if expert_id is not None else None
        steps.append(
            WorkflowStepView(
                id=name,
                block=node["block"],
                label=node.get("label"),
                expert_id=UUID(expert_id) if expert_id is not None and found is not None else None,
                expert_name=found[0] if found is not None else None,
                model=executor if found is not None else None,
                tools=sorted(found[1].tools) if found is not None else [],
                approval=node["block"] == "approval",
            )
        )
    return steps
