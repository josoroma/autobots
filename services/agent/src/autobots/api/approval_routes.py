"""The inbox and decisions. A decision changes what a run may do, so only an owner makes one."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.approvals import (
    ARGUMENT_LIMIT,
    ApprovalRefused,
    decide,
    exceeds_review_limit,
    list_approvals,
)
from autobots.application.run_projection import public_text
from autobots.application.runs import IdempotencyConflict
from autobots.contracts.approvals import (
    ApprovalDecision,
    ApprovalList,
    ApprovalRequester,
    ApprovalResult,
    ApprovalScope,
    ApprovalView,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _requester(row: dict[str, Any], viewer: UUID) -> ApprovalRequester | None:
    """None only for a request saved before US-13.1, which always stores the agent now."""
    agent = row["requested_by_agent"]
    if agent is None:
        return None
    person = row["requested_by"]
    return ApprovalRequester(
        person_id=person,
        person_is_viewer=person is not None and person == viewer,
        agent=agent["kind"],
        expert_id=agent.get("id"),
        expert_version=agent.get("version"),
        expert_name=row["expert_name"] if agent["kind"] == "expert" else None,
    )


@router.get("/approvals", operation_id="listApprovals", response_model=ApprovalList)
async def get_approvals(
    request: Request,
    workspace: Annotated[UUID, Depends(current_workspace)],
    user: Annotated[UUID, Depends(current_user)],
    status: Annotated[
        Literal["pending", "approved", "rejected", "expired", "withdrawn"], Query()
    ] = "pending",
) -> ApprovalList:
    async with _pool(request).connection() as connection:
        rows = await list_approvals(connection, workspace, status)
    return ApprovalList(
        schema_version=1,
        approvals=[
            ApprovalView(
                id=row["id"],
                run_id=row["run_id"],
                tool_id=row["tool_id"],
                tool_version=row["tool_version"],
                operation_class=row["operation_class"],
                argument_hash=row["argument_hash"],
                # Redaction can lengthen text a little, so the cut only ever applies past the limit.
                arguments=public_text(row["arguments"], limit=ARGUMENT_LIMIT * 2)
                if not exceeds_review_limit(row["arguments"])
                else public_text(row["arguments"], limit=ARGUMENT_LIMIT),
                arguments_truncated=exceeds_review_limit(row["arguments"]),
                status=row["status"],
                expires_at=row["expires_at"].isoformat(),
                policy_reason=row["policy_reason"],
                resource_target=row["resource_target"],
                requester=_requester(row, user),
                scope_snapshot=None
                if row["scope_snapshot"] is None
                else ApprovalScope.model_validate(row["scope_snapshot"]),
                policy_version=row["policy_version"],
                policy_rule=row["policy_rule"],
            )
            for row in rows
        ],
    )


@router.post(
    "/approvals/{approval_id}/decision",
    operation_id="decideApproval",
    response_model=ApprovalResult,
)
async def post_decision(
    approval_id: UUID,
    body: ApprovalDecision,
    request: Request,
    key: Key,
    workspace: Annotated[UUID, Depends(require_owner)],
    user: Annotated[UUID, Depends(current_user)],
) -> ApprovalResult:
    async with _pool(request).connection() as connection:
        try:
            result = await decide(
                connection,
                workspace_id=workspace,
                actor_id=user,
                approval_id=approval_id,
                idempotency_key=key,
                decision=body.decision,
                argument_hash=body.argument_hash,
            )
        except ApprovalRefused as error:
            status_code = 404 if error.code == "approval_not_found" else 409
            raise ApiError(status_code, error.code, "That decision can't be applied.") from None
        except IdempotencyConflict as error:
            raise ApiError(
                409, error.code, "This key was used with a different decision."
            ) from None
    return ApprovalResult(
        schema_version=1,
        approval_id=result.approval_id,
        status=result.status,
        replayed=result.replayed,
    )
