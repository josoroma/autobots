"""Reviewing improvement proposals. Promotion and rollback change what later runs read."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from autobots.api.dependencies import (
    CurrentUser,
    IdempotencyKey,
    MemberWorkspace,
    ModelKeyCheck,
    OwnerWorkspace,
)
from autobots.api.errors import reworded
from autobots.api.resources import request_pool
from autobots.api.security import require_internal
from autobots.application.improvements import (
    decide,
    list_candidates,
    request_replay,
    rollback,
    run_regression,
)
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


@router.get("/improvements", operation_id="listImprovements", response_model=CandidateList)
async def get_candidates(request: Request, workspace_id: MemberWorkspace) -> CandidateList:
    async with request_pool(request).connection() as connection:
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace_id)
        )


@router.post(
    "/improvements/{candidate_id}/regression",
    operation_id="runImprovementRegression",
    response_model=CandidateList,
)
async def post_regression(
    candidate_id: UUID, body: RegressionRun, request: Request, workspace_id: OwnerWorkspace
) -> CandidateList:
    async with request_pool(request).connection() as connection:
        await run_regression(
            connection,
            workspace_id,
            candidate_id,
            [case.model_dump() for case in body.cases],
        )
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace_id)
        )


@router.post(
    "/improvements/{candidate_id}/replay",
    operation_id="replayImprovement",
    response_model=CandidateList,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_replay(
    candidate_id: UUID,
    body: ReplayRequest,
    request: Request,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
    model_key: ModelKeyCheck,
    idempotency_key: IdempotencyKey,
) -> CandidateList:
    """Held-out tasks run as ordinary runs, each up to the limit. Requesting authorizes that."""
    try:
        await require_model_ready(model_key, workspace_id, needed=True)
    except ModelNotReady as refused:
        raise reworded(refused, "A replay needs a usable OpenRouter key.") from None
    async with request_pool(request).connection() as connection:
        # A held-out task names no Expert and no profile, so it resolves the workspace's saved
        # policy alone, and a profile there that isn't offered is a saved choice to change.
        policy = await workspace_role_policy(connection, workspace_id, require_offer=True)
        try:
            await request_replay(
                connection,
                workspace_id=workspace_id,
                candidate_id=candidate_id,
                actor_id=user_id,
                idempotency_key=idempotency_key,
                tasks=[task.model_dump() for task in body.tasks],
                limit_micro_usd=body.limit_micro_usd,
                policy=policy,
            )
        except IdempotencyConflict as refused:
            raise reworded(refused, "That key was used for a different replay.") from None
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace_id)
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
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> CandidateList:
    async with request_pool(request).connection() as connection:
        await decide(connection, workspace_id, candidate_id, user_id, body.decision)
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace_id)
        )


@router.post("/knowledge/rollback", operation_id="rollbackKnowledge", response_model=KnowledgeHead)
async def post_rollback(
    body: RollbackRequest, request: Request, workspace_id: OwnerWorkspace
) -> KnowledgeHead:
    async with request_pool(request).connection() as connection:
        return await rollback(connection, workspace_id, body.kind, body.key, body.to_version)
