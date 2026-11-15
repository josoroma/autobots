"""Run admission and user commands. A request records intent; a worker owns execution.

This module previews and admits runs and reads one. Commands are in run_command_routes.py and an
owner's reconciliation in run_reconcile_routes.py (refactor plan R-55, PAPI-12).
"""

from functools import partial
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from autobots.api.dependencies import (
    CurrentUser,
    IdempotencyKey,
    MemberWorkspace,
    ModelKeyCheck,
    catalog_of,
    membership,
    process_environment,
    require_ready,
)
from autobots.api.errors import ApiError, reworded
from autobots.api.resources import request_pool
from autobots.api.security import require_internal
from autobots.application.experts import ExpertRefused, latest_version_config
from autobots.application.model_admission import remaining_daily_micro_usd
from autobots.application.run_admission import (
    AdmissionInput,
    admit_from_request,
    expert_overrides,
    saved_workspace_policy,
)
from autobots.application.run_projection import read_summary
from autobots.contracts.run_commands import RunAccepted, RunRequest
from autobots.contracts.runs import RunSummary
from autobots.contracts.settings import PreviewProfile, RunPreview, budget_range
from autobots.domain.models import PROFILES, ModelProfileId
from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


PROFILE_LABELS = {
    ModelProfileId.DEEPSEEK_FLASH: "DeepSeek",
    ModelProfileId.TERRA: "Terra",
    ModelProfileId.SOL: "Sol",
}


@router.get("/run-preview", operation_id="previewRun", response_model=RunPreview)
async def preview_run(
    request: Request,
    workspace_id: MemberWorkspace,
    run_profile: ModelProfileId | None = None,
    expert_id: UUID | None = None,
) -> RunPreview:
    """HM-03: the profiles each role would resolve to, the tools and the budgets, as admission
    would see them now. It creates nothing and calls no model."""
    async with request_pool(request).connection() as connection:
        saved = await saved_workspace_policy(connection, workspace_id)
        role_bindings: dict[str, str] | None = None
        tools = sorted(tool for tool in LOOP_TOOL_GRANTS if tool not in PLAN_TOOLS)
        if expert_id is not None:
            config = await latest_version_config(connection, workspace_id, expert_id)
            if config is None:
                raise ApiError(404, "expert_not_found", "That Expert is not available.")
            role_bindings = expert_overrides(config)
            tools = sorted(config.tools)
        remaining = await remaining_daily_micro_usd(connection, workspace_id)
    # It shows what admission would resolve, and refusing a profile that isn't offered is
    # admission's to do.
    policy = saved.for_new_work(
        run_role_overrides=role_bindings, run_profile=run_profile, require_offer=False
    )
    grouped: dict[ModelProfileId, list[str]] = {}
    for role, profile in policy.bindings.items():
        grouped.setdefault(profile, []).append(role.value)
    return RunPreview(
        schema_version=1,
        budget=budget_range(remaining),
        profiles=[
            PreviewProfile(
                profile=profile,
                label=PROFILE_LABELS[profile],
                canonical_id=PROFILES[profile].canonical_id,
                roles=roles,
            )
            for profile, roles in sorted(grouped.items(), key=lambda item: -len(item[1]))
        ],
        tools=tools,
    )


@router.post(
    "/runs",
    operation_id="admitRun",
    dependencies=[Depends(require_ready)],
    response_model=RunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_run(
    body: RunRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    model_key: ModelKeyCheck,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
) -> RunAccepted:
    # The first step's refusal is the answer, in api/errors.py's wording, apart from routing's.
    try:
        result = await admit_from_request(
            AdmissionInput.of(
                body, workspace_id=workspace_id, user_id=user_id, idempotency_key=idempotency_key
            ),
            database=request_pool(request),
            model_ready=model_key,
            role=partial(membership(request).role_in, user_id, workspace_id),
            # Decisions 0024 K1 and 0025 V3 order the keys, and the process environment in that
            # order is the one the entry point read at start, as the OpenRouter key's is. The
            # key check's dependency has already refused a missing provider context.
            environment=process_environment(request),
            catalog=catalog_of(request),
        )
    except ExpertRefused as refused:
        raise reworded(refused, "That routing isn't available.") from None
    return RunAccepted(
        schema_version=1,
        run_id=result.run_id,
        version=result.version,
        status=result.status,
        replayed=result.replayed,
    )


@router.get("/runs/{run_id}", operation_id="getRun", response_model=RunSummary)
async def get_run(run_id: UUID, request: Request, workspace_id: MemberWorkspace) -> RunSummary:
    async with request_pool(request).connection() as connection:
        summary = await read_summary(connection, workspace_id, run_id)
    if summary is None:
        raise ApiError(404, "run_not_found", "That run is not available.")
    return summary
