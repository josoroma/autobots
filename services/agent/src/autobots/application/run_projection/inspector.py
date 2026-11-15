"""A run's inspector view: typed columns only, read from one snapshot (SP-011, PRUN-11). Graph
state is never read: checkpoints show their ids, steps and sources only."""

from collections.abc import Mapping
from uuid import UUID

from autobots.application.model_admission import InvocationStatus, SettlementReason
from autobots.application.run_projection.shown import canonical_id, public_text, shown_snapshot
from autobots.application.run_projection.summary import require_run, summary_of
from autobots.application.sql import SqlConnection, all_rows, required_row, snapshot
from autobots.contracts.persisted import FrozenRoute
from autobots.contracts.run_workspace import (
    CheckpointView,
    EvidenceView,
    ModelCallView,
    RunInspector,
    ToolAttemptView,
)
from autobots.domain.effects import ReceiptStatus
from autobots.persistence.rows import (
    CheckpointRow,
    InspectedRunRow,
    ModelCallRow,
    PlanEvidenceRow,
    ToolAttemptRow,
)

INSPECTOR_CHECKPOINTS = 500


def model_call_of(row: ModelCallRow, routes: Mapping[str, FrozenRoute]) -> ModelCallView:
    """An unknown stored status raises, instead of reaching a client."""
    return ModelCallView(
        id=row.id,
        run_id=row.run_id,
        role=row.role,
        attempt=row.attempt,
        status=InvocationStatus(row.status).value,
        provider="openrouter",
        profile=row.profile,
        canonical_id=canonical_id(row.profile, routes),
        wire_id=row.wire_id,
        upstream_provider=row.upstream_provider or "unknown",
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        reasoning_tokens=row.reasoning_tokens,
        reported_micro_usd=row.charged_micro_usd,
        estimated_micro_usd=row.reserved_micro_usd,
        finish_reason=row.finish_reason,
        failure_class=row.failure_class,
        created_at=row.created_at,
        reconciled=row.reconciled,
        # The call worked and only its charge was missing, so its outcome was never in doubt.
        outcome_unknown=row.reconciled
        and row.failure_class != SettlementReason.CHARGE_NOT_REPORTED,
        charge_source_unknown=row.charge_source_unknown,
    )


def tool_attempt_of(row: ToolAttemptRow) -> ToolAttemptView:
    """An unknown stored status raises, instead of reaching a client."""
    return ToolAttemptView(
        operation_id=row.operation_id,
        tool_id=row.tool_id,
        tool_version=row.tool_version,
        status=ReceiptStatus(row.status).value,
        failure_code=row.failure_code,
        created_at=row.created_at,
    )


def checkpoint_of(row: CheckpointRow) -> CheckpointView:
    return CheckpointView(
        checkpoint_id=row.checkpoint_id,
        parent_checkpoint_id=row.parent_checkpoint_id,
        step=row.step,
        source=row.source,
    )


def evidence_of(row: PlanEvidenceRow, published: Mapping[str, UUID]) -> list[EvidenceView]:
    """A task's evidence items. An artifact one names its published artifact, when there is one."""
    found = []
    for item in row.evidence or []:
        reference = str(item.get("reference", ""))
        found.append(
            EvidenceView(
                task_id=public_text(row.task_id),
                kind=str(item.get("kind", "")),
                reference=public_text(reference),
                summary=public_text(row.summary),
                artifact_id=published.get(reference.rsplit("/", 1)[-1])
                if item.get("kind") == "artifact"
                else None,
            )
        )
    return found


async def evidence(connection: SqlConnection, run_id: UUID) -> list[EvidenceView]:
    cursor = await connection.execute(
        "select name, id from public.artifacts where run_id = %s and status = 'published'",
        (run_id,),
    )
    published: dict[str, UUID] = {
        name: artifact_id for name, artifact_id in await cursor.fetchall()
    }
    rows = await all_rows(
        connection,
        PlanEvidenceRow,
        "select task_id, evidence, summary from app_private.plan_evidence "
        "where run_id = %s order by completed_at",
        (run_id,),
    )
    return [view for row in rows for view in evidence_of(row, published)]


async def read_inspector(
    connection: SqlConnection, workspace_id: UUID, run_id: UUID
) -> RunInspector:
    """Typed columns only. No checkpoint content, tool arguments or partial model output is read."""
    async with snapshot(connection):
        row = await require_run(connection, workspace_id, run_id)
        inspected = await required_row(
            connection,
            InspectedRunRow,
            "select goal_summary, policy_snapshot, "
            "coalesce(checkpoint_thread_id, id::text) as thread_id "
            "from public.runs where id = %s",
            (run_id,),
        )
        calls = await all_rows(
            connection,
            ModelCallRow,
            "select id, run_id, role, attempt, status, profile, wire_id, upstream_provider, "
            "input_tokens, output_tokens, reasoning_tokens, charged_micro_usd, reserved_micro_usd, "
            "finish_reason, failure_class, created_at, "
            "charge_source is not distinct from 'owner' as reconciled, "
            "reconciled_at is not null and charge_source is null as charge_source_unknown "
            "from app_private.model_invocations where run_id = %s or root_run_id = %s "
            "order by created_at, attempt",
            (run_id, run_id),
        )
        attempts = await all_rows(
            connection,
            ToolAttemptRow,
            "select operation_id, tool_id, tool_version, status, failure_code, created_at "
            "from app_private.tool_receipts where run_id = %s order by created_at",
            (run_id,),
        )
        checkpoints = await all_rows(
            connection,
            CheckpointRow,
            "select checkpoint_id, parent_checkpoint_id, (metadata ->> 'step')::integer as step, "
            "metadata ->> 'source' as source from agent_runtime.checkpoints where thread_id = %s "
            "order by checkpoint_id limit %s",
            (inspected.thread_id, INSPECTOR_CHECKPOINTS + 1),
        )
        shown_evidence = await evidence(connection, run_id)
    routes = shown_snapshot(inspected.policy_snapshot).routes
    return RunInspector(
        schema_version=1,
        run=summary_of(row),
        goal_summary=public_text(inspected.goal_summary),
        model_calls=[model_call_of(call, routes) for call in calls],
        tool_attempts=[tool_attempt_of(attempt) for attempt in attempts],
        checkpoints=[checkpoint_of(item) for item in checkpoints[:INSPECTOR_CHECKPOINTS]],
        checkpoints_truncated=len(checkpoints) > INSPECTOR_CHECKPOINTS,
        evidence=shown_evidence,
    )
