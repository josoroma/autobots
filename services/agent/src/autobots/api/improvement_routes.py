"""Reviewing improvement proposals. Promotion and rollback change what later runs read."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.improvements import (
    ImprovementRefused,
    decide,
    list_candidates,
    rollback,
    run_regression,
)
from autobots.contracts.improvements import (
    CandidateDecision,
    CandidateList,
    KnowledgeHead,
    RollbackRequest,
)

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
async def post_regression(candidate_id: UUID, request: Request, workspace: Owner) -> CandidateList:
    async with _pool(request).connection() as connection:
        try:
            await run_regression(connection, workspace, candidate_id)
        except ImprovementRefused as error:
            raise _error(error) from None
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
