"""What Workflows shows beside each workflow, PRD-Studio WF-01, WF-03 and WF-04. Read only."""

from collections.abc import Mapping
from datetime import UTC
from typing import Any
from uuid import UUID

from autobots.contracts.experts import ExpertConfig
from autobots.contracts.workflows import (
    WorkflowExecutionSummary,
    WorkflowStepView,
)
from autobots.domain.models import PROFILES, ModelRole, resolve_role_policy
from autobots.domain.runs import TERMINAL, RunStatus
from autobots.domain.workflows import step_order

# One execution per row, with the root run's ledger, as the run list counts it (RN-01).
_EXECUTIONS = (
    "select x.id, x.run_id, x.workflow_version, r.status, x.created_at, r.updated_at, "
    "r.created_at, "
    "(select coalesce(sum(coalesce(i.charged_micro_usd, 0)), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "(select coalesce(sum(i.reserved_micro_usd) filter (where i.status in "
    "('reserved', 'dispatched', 'uncertain') and i.reconciled_at is null), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "exists (select 1 from app_private.model_invocations i where (i.root_run_id = r.id "
    "or i.run_id = r.id) and i.status = 'uncertain' and i.reconciled_at is null "
    "and i.failure_class = 'charge_not_reported') "
    "from public.workflow_executions x join public.runs r on r.id = x.run_id "
    "and r.workspace_id = x.workspace_id "
    "where x.workflow_id = %s and x.workspace_id = %s order by x.created_at desc, x.id limit %s"
)


def _summary(row: Any) -> WorkflowExecutionSummary:
    finished = RunStatus(row[3]) in TERMINAL
    return WorkflowExecutionSummary(
        id=row[0],
        run_id=row[1],
        version=row[2],
        status=row[3],
        charged_micro_usd=int(row[7]),
        reserved_micro_usd=int(row[8]),
        unreported=bool(row[9]),
        started_at=row[4].astimezone(UTC).isoformat(),
        # The run's own time, from admission to its last change, to the nearest second.
        duration_seconds=max(round((row[5] - row[6]).total_seconds()), 0) if finished else None,
    )


async def recent_executions(
    connection: Any, workspace_id: UUID, workflow_id: UUID, limit: int = 10
) -> list[WorkflowExecutionSummary]:
    cursor = await connection.execute(_EXECUTIONS, (workflow_id, workspace_id, limit))
    return [_summary(row) for row in await cursor.fetchall()]


async def run_count(connection: Any, workspace_id: UUID, workflow_id: UUID) -> int:
    cursor = await connection.execute(
        "select count(*) from public.workflow_executions where workflow_id = %s "
        "and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _experts(
    connection: Any, workspace_id: UUID, expert_ids: list[str]
) -> dict[str, tuple[str, ExpertConfig]]:
    """Each named Expert's name and latest configuration, in this workspace only."""
    if not expert_ids:
        return {}
    cursor = await connection.execute(
        "select e.id::text, e.name, v.config from public.experts e "
        "join public.expert_versions v on v.expert_id = e.id and v.version = e.latest_version "
        "where e.workspace_id = %s and e.id::text = any(%s)",
        (workspace_id, expert_ids),
    )
    return {
        row[0]: (str(row[1]), ExpertConfig.model_validate(row[2]))
        for row in await cursor.fetchall()
    }


def _agent_experts(graph: Mapping[str, Any]) -> list[str]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    return [
        str(nodes[name].get("config", {}).get("expert_id"))
        for name in step_order(graph)
        if nodes[name]["block"] == "agent" and nodes[name].get("config", {}).get("expert_id")
    ]


async def expert_chain(
    connection: Any, workspace_id: UUID, graph: Mapping[str, Any] | None
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
    connection: Any, workspace_id: UUID, graph: Mapping[str, Any]
) -> list[WorkflowStepView]:
    """WF-03: each step in order. An agent step shows its Expert, the executor's model a run
    started now would use, and the Expert's tools. An approval step is marked as the gate."""
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    known = await _experts(connection, workspace_id, sorted(set(_agent_experts(graph))))
    cursor = await connection.execute(
        "select default_profile, role_overrides from app_private.model_policies "
        "where workspace_id = %s",
        (workspace_id,),
    )
    saved = await cursor.fetchone()
    steps = []
    for name in step_order(graph):
        node = nodes[name]
        expert_id = node.get("config", {}).get("expert_id") if node["block"] == "agent" else None
        found = known.get(str(expert_id)) if expert_id else None
        model = None
        if found is not None:
            policy = resolve_role_policy(
                run_role_overrides={
                    role: profile.value for role, profile in found[1].role_bindings.items()
                },
                workspace_default=saved[0] if saved else None,
                workspace_role_overrides=saved[1] if saved else None,
            )
            model = PROFILES[policy.bindings[ModelRole.EXECUTOR]].canonical_id
        steps.append(
            WorkflowStepView(
                id=name,
                block=node["block"],
                label=node.get("label"),
                expert_id=UUID(str(expert_id)) if found is not None else None,
                expert_name=found[0] if found is not None else None,
                model=model,
                tools=sorted(found[1].tools) if found is not None else [],
                approval=node["block"] == "approval",
            )
        )
    return steps
