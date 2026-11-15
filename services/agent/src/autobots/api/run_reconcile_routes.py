"""An owner's reconciliation of what a run left unknown, from the destination's or the provider's
own records (SP-012). Nothing here treats an outcome as known without that evidence."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import CurrentUser, IdempotencyKey, OwnerWorkspace
from autobots.api.resources import request_pool
from autobots.api.security import require_internal
from autobots.application.reconciliation import reconcile_oldest_uncertain_call, record_evidence
from autobots.application.run_projection import public_text
from autobots.application.runs import require_run
from autobots.contracts.run_commands import (
    EffectEvidence,
    ModelCallReconciliation,
    ReconciliationResult,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.post(
    "/runs/{run_id}/effects/{operation_id}/reconcile",
    operation_id="reconcileRunEffect",
    response_model=ReconciliationResult,
)
async def post_effect_evidence(
    run_id: UUID,
    operation_id: str,
    body: EffectEvidence,
    request: Request,
    idempotency_key: IdempotencyKey,
    user_id: CurrentUser,
    workspace_id: OwnerWorkspace,
) -> ReconciliationResult:
    """An owner reports what the destination's own records show."""
    async with request_pool(request).connection() as connection:
        await require_run(connection, workspace_id, run_id)
        await record_evidence(
            connection,
            workspace_id=workspace_id,
            run_id=run_id,
            operation_id=operation_id,
            actor_id=user_id,
            idempotency_key=idempotency_key,
            outcome=body.outcome,
            evidence=public_text(body.evidence, limit=2000),
            generation=body.generation,
        )
    return ReconciliationResult(schema_version=1, reconciled_calls=1)


@router.post(
    "/runs/{run_id}/model-calls/reconcile",
    operation_id="reconcileRunModelCalls",
    response_model=ReconciliationResult,
)
async def post_reconcile(
    run_id: UUID,
    body: ModelCallReconciliation,
    request: Request,
    idempotency_key: IdempotencyKey,
    user_id: CurrentUser,
    workspace_id: OwnerWorkspace,
) -> ReconciliationResult:
    """An owner records a charge seen in the provider's own account, for the oldest open call."""
    async with request_pool(request).connection() as connection:
        await require_run(connection, workspace_id, run_id)
        reconciled = await reconcile_oldest_uncertain_call(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            run_id=run_id,
            idempotency_key=idempotency_key,
            charged_micro_usd=body.charged_micro_usd,
        )
    return ReconciliationResult(schema_version=1, reconciled_calls=reconciled)
