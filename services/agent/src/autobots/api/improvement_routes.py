"""Reviewing improvement proposals. Promotion and rollback change what later runs read."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import reworded
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, provider_settings, require_owner
from autobots.application.improvements import (
    decide,
    list_candidates,
    request_replay,
    rollback,
    run_regression,
)
from autobots.application.provider_settings import ProviderSettings
from autobots.application.run_admission import (
    ModelNotReady,
    require_model_ready,
    workspace_role_policy,
)
from autobots.application.runs import IdempotencyConflict
from autobots.contracts.improvements import (
    CandidateDecision,
    CandidateList,
    KnowledgeHead,
    RegressionRun,
    ReplayRequest,
    RollbackRequest,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Owner = Annotated[UUID, Depends(require_owner)]


@router.get("/improvements", operation_id="listImprovements", response_model=CandidateList)
async def get_candidates(
    request: Request, workspace: Annotated[UUID, Depends(current_workspace)]
) -> CandidateList:
    async with request_pool(request).connection() as connection:
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace)
        )


@router.post(
    "/improvements/{candidate_id}/regression",
    operation_id="runImprovementRegression",
    response_model=CandidateList,
)
async def post_regression(
    candidate_id: UUID, body: RegressionRun, request: Request, workspace: Owner
) -> CandidateList:
    async with request_pool(request).connection() as connection:
        await run_regression(
            connection,
            workspace,
            candidate_id,
            [case.model_dump() for case in body.cases],
        )
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace)
        )


@router.post(
    "/improvements/{candidate_id}/replay",
    operation_id="replayImprovement",
    response_model=CandidateList,
    status_code=202,
)
async def post_replay(
    candidate_id: UUID,
    body: ReplayRequest,
    request: Request,
    workspace: Owner,
    user: Annotated[UUID, Depends(current_user)],
    settings: Annotated[ProviderSettings, Depends(provider_settings)],
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
) -> CandidateList:
    """Held-out tasks run as ordinary runs, each up to the limit. Requesting authorizes that."""
    try:
        await require_model_ready(settings.run_intent, workspace, needed=True)
    except ModelNotReady as refused:
        raise reworded(refused, "A replay needs a usable OpenRouter key.") from None
    async with request_pool(request).connection() as connection:
        # A held-out task names no Expert and no profile, so it resolves the workspace's saved
        # policy alone, and a profile there that isn't offered is a saved choice to change.
        policy = await workspace_role_policy(connection, workspace, require_offer=True)
        try:
            await request_replay(
                connection,
                workspace_id=workspace,
                candidate_id=candidate_id,
                actor_id=user,
                idempotency_key=key,
                tasks=[task.model_dump() for task in body.tasks],
                limit_micro_usd=body.limit_micro_usd,
                policy=policy,
            )
        except IdempotencyConflict as refused:
            raise reworded(refused, "That key was used for a different replay.") from None
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace)
        )


@router.post(
    "/improvements/{candidate_id}/decision",
    operation_id="decideImprovement",
    response_model=CandidateList,
)
async def post_decision(
    candidate_id: UUID,
    body: CandidateDecision,
    request: Request,
    workspace: Owner,
    user: Annotated[UUID, Depends(current_user)],
) -> CandidateList:
    async with request_pool(request).connection() as connection:
        await decide(connection, workspace, candidate_id, user, body.decision)
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace)
        )


@router.post("/knowledge/rollback", operation_id="rollbackKnowledge", response_model=KnowledgeHead)
async def post_rollback(body: RollbackRequest, request: Request, workspace: Owner) -> KnowledgeHead:
    async with request_pool(request).connection() as connection:
        return await rollback(connection, workspace, body.kind, body.key, body.to_version)
