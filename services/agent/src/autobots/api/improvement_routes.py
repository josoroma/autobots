"""Reviewing improvement proposals. Promotion and rollback change what later runs read."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, provider_settings, require_owner
from autobots.application.improvements import (
    ImprovementRefused,
    decide,
    list_candidates,
    request_replay,
    rollback,
    run_regression,
)
from autobots.application.provider_settings import ProviderSettings
from autobots.application.runs import IdempotencyConflict
from autobots.contracts.improvements import (
    CandidateDecision,
    CandidateList,
    KnowledgeHead,
    RegressionRun,
    ReplayRequest,
    RollbackRequest,
)
from autobots.domain.models import ProfileNotOffered, require_offered, resolve_role_policy

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Owner = Annotated[UUID, Depends(require_owner)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _error(error: ImprovementRefused) -> ApiError:
    status_code = 404 if error.code.endswith("not_found") else 409
    return ApiError(status_code, error.code, "That can't be done to this proposal.")


@router.get("/improvements", operation_id="listImprovements", response_model=CandidateList)
async def get_candidates(
    request: Request, workspace: Annotated[UUID, Depends(current_workspace)]
) -> CandidateList:
    async with _pool(request).connection() as connection:
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
    async with _pool(request).connection() as connection:
        try:
            await run_regression(
                connection,
                workspace,
                candidate_id,
                [case.model_dump() for case in body.cases],
            )
        except ImprovementRefused as error:
            raise _error(error) from None
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
    code = await settings.run_intent(workspace)
    if code != "ready":
        raise ApiError(409, code, "A replay needs a usable OpenRouter key.")
    async with _pool(request).connection() as connection:
        row = await (
            await connection.execute(
                "select default_profile, role_overrides from app_private.model_policies "
                "where workspace_id = %s",
                (workspace,),
            )
        ).fetchone()
        policy = resolve_role_policy(
            workspace_default=row[0] if row else None,
            workspace_role_overrides=row[1] if row else None,
        )
        try:
            require_offered(policy.bindings.values())
        except ProfileNotOffered as refused:
            raise ApiError(409, refused.code, str(refused)) from None
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
        except ImprovementRefused as error:
            raise _error(error) from None
        except IdempotencyConflict as error:
            raise ApiError(409, error.code, "That key was used for a different replay.") from None
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
    async with _pool(request).connection() as connection:
        try:
            await decide(connection, workspace, candidate_id, user, body.decision)
        except ImprovementRefused as error:
            raise _error(error) from None
        return CandidateList(
            schema_version=1, candidates=await list_candidates(connection, workspace)
        )


@router.post("/knowledge/rollback", operation_id="rollbackKnowledge", response_model=KnowledgeHead)
async def post_rollback(body: RollbackRequest, request: Request, workspace: Owner) -> KnowledgeHead:
    async with _pool(request).connection() as connection:
        try:
            return await rollback(connection, workspace, body.kind, body.key, body.to_version)
        except ImprovementRefused as error:
            raise _error(error) from None
