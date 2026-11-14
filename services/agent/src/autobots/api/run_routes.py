"""Run admission and user commands. A request records intent; a worker owns execution."""

import os
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from psycopg import AsyncConnection

from autobots.api.errors import ApiError
from autobots.api.operation_routes import require_ready
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, provider_settings, require_owner
from autobots.application.experts import ExpertRefused, resolve_binding
from autobots.application.goal_loop import execution_block
from autobots.application.model_admission import ModelAdmission, remaining_daily_micro_usd
from autobots.application.provider_settings import ProviderSettings
from autobots.application.reconciliation import (
    ReconciliationRefused,
    has_unresolvable_effect,
    record_evidence,
)
from autobots.application.recovery import outstanding
from autobots.application.run_projection import public_text, read_summary
from autobots.application.runs import (
    IdempotencyConflict,
    LinkRefused,
    RunNotFound,
    VersionConflict,
    admit_run,
    apply_command,
    existing_receipt,
    request_hash,
    store_receipt,
)
from autobots.application.tool_catalog import ToolsUnavailable, require_available
from autobots.application.tool_keys import key_sources
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.run_commands import (
    EffectEvidence,
    ModelCallReconciliation,
    ReconciliationResult,
    RunAccepted,
    RunCommandRequest,
    RunCommandResult,
    RunInputRequest,
    RunRequest,
)
from autobots.contracts.runs import RunSummary
from autobots.contracts.settings import PreviewProfile, RunPreview, budget_range
from autobots.domain.budgets import BudgetRefused, require_budget
from autobots.domain.models import (
    PROFILES,
    ModelProfileId,
    ProfileNotOffered,
    is_offered,
    require_offered,
    resolve_role_policy,
)
from autobots.domain.runs import Actor, CommandRefused, RunCommand
from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


def as_api_error(error: Exception) -> ApiError:
    if isinstance(error, IdempotencyConflict):
        return ApiError(409, error.code, "This key was already used with different content.")
    if isinstance(error, VersionConflict):
        return ApiError(409, error.code, "The run changed. Reload and try again.")
    if isinstance(error, LinkRefused):
        return ApiError(
            409,
            error.code,
            "Only a finished goal run of its own, in this workspace, can be continued.",
        )
    if isinstance(error, RunNotFound):
        return ApiError(404, error.code, "That run is not available.")
    if isinstance(error, CommandRefused):
        return ApiError(
            409, "transition_refused", "That is not allowed in the run's current state."
        )
    raise error


BUDGET_MESSAGES = {
    "budget_out_of_range": "Choose a budget from US$0.25 to US$5.00.",
    "budget_off_step": "Choose a budget in steps of US$0.25.",
    "budget_above_daily_cap": "That budget is more than what's left of today's spending cap.",
}


def budget_error(code: str) -> ApiError:
    return ApiError(409 if code == "budget_above_daily_cap" else 422, code, BUDGET_MESSAGES[code])


PROFILE_LABELS = {
    ModelProfileId.DEEPSEEK_FLASH: "DeepSeek",
    ModelProfileId.TERRA: "Terra",
    ModelProfileId.SOL: "Sol",
}


@router.get("/run-preview", operation_id="previewRun", response_model=RunPreview)
async def preview_run(
    request: Request,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    run_profile: ModelProfileId | None = None,
    expert_id: UUID | None = None,
) -> RunPreview:
    """HM-03: the profiles each role would resolve to, the tools and the budgets, as admission
    would see them now. It creates nothing and calls no model."""
    async with request_pool(request).connection() as connection:
        row = await (
            await connection.execute(
                "select default_profile, role_overrides from app_private.model_policies "
                "where workspace_id = %s",
                (workspace_id,),
            )
        ).fetchone()
        role_bindings: dict[str, str] | None = None
        tools = sorted(tool for tool in LOOP_TOOL_GRANTS if tool not in PLAN_TOOLS)
        if expert_id is not None:
            found = await (
                await connection.execute(
                    "select v.config from public.experts e join public.expert_versions v "
                    "on v.expert_id = e.id and v.version = e.latest_version "
                    "where e.id = %s and e.workspace_id = %s",
                    (expert_id, workspace_id),
                )
            ).fetchone()
            if found is None:
                raise ApiError(404, "expert_not_found", "That Expert is not available.")
            config = ExpertConfig.model_validate(found[0])
            role_bindings = {role: profile.value for role, profile in config.role_bindings.items()}
            tools = sorted(config.tools)
        remaining = await remaining_daily_micro_usd(connection, workspace_id)
    policy = resolve_role_policy(
        run_role_overrides=role_bindings,
        run_profile=run_profile.value if run_profile else None,
        workspace_default=row[0] if row else None,
        workspace_role_overrides=row[1] if row else None,
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
    idempotency_key: Key,
    settings: Annotated[ProviderSettings, Depends(provider_settings)],
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    user_id: Annotated[UUID, Depends(current_user)],
) -> RunAccepted:
    if body.session_id is None and (body.expert_id is not None or body.expert_version is not None):
        raise ApiError(422, "session_required", "An Expert is chosen through a session.")
    limit = body.limit_micro_usd
    if body.budget_micro_usd is not None:
        if "limit_micro_usd" in body.model_fields_set:
            raise ApiError(422, "budget_conflict", "Choose a budget or a limit, not both.")
        async with request_pool(request).connection() as connection:
            remaining = await remaining_daily_micro_usd(connection, workspace_id)
        try:
            require_budget(body.budget_micro_usd, remaining)
        except BudgetRefused as refused:
            raise budget_error(refused.code) from None
        limit = body.budget_micro_usd
    code = await settings.run_intent(workspace_id)
    if code != "ready":
        raise ApiError(409, code, "Model-backed work needs a usable OpenRouter key.")
    async with request_pool(request).connection() as connection:
        row = await (
            await connection.execute(
                "select default_profile, role_overrides from app_private.model_policies "
                "where workspace_id = %s",
                (workspace_id,),
            )
        ).fetchone()
        binding = None
        if body.session_id is not None:
            if (
                body.expert_version is not None
                and await request.app.state.membership.role_in(user_id, workspace_id) != "owner"
            ):
                # An earlier version could hold tools an owner has since removed.
                raise ApiError(403, "owner_required", "Only an owner can choose an Expert version.")
            try:
                binding = await resolve_binding(
                    connection,
                    workspace_id,
                    body.session_id,
                    expert_id=body.expert_id,
                    version=body.expert_version,
                )
            except ExpertRefused as error:
                status_code = 404 if error.code.endswith("not_found") else 409
                raise ApiError(status_code, error.code, "That routing isn't available.") from None
            try:
                # PK-02: only a run that grants an unavailable tool is refused, before it exists.
                require_available(
                    binding.tools, await key_sources(connection, workspace_id, os.environ)
                )
            except ToolsUnavailable as refused:
                raise ApiError(
                    409,
                    refused.code,
                    "A tool this Expert grants is unavailable in this install. "
                    "See Tools for what it needs.",
                ) from None
        policy = resolve_role_policy(
            run_role_overrides=binding.role_bindings if binding else None,
            run_profile=body.run_profile.value if body.run_profile else None,
            workspace_default=row[0] if row else None,
            workspace_role_overrides=row[1] if row else None,
        )
        try:
            require_offered(policy.bindings.values())
        except ProfileNotOffered as refused:
            # Named in this request it's a bad request. Otherwise it's a saved choice to change.
            named = body.run_profile is not None and not is_offered(body.run_profile)
            raise ApiError(422 if named else 409, refused.code, str(refused)) from None
        try:
            result = await admit_run(
                connection,
                workspace_id=workspace_id,
                actor_id=user_id,
                started_by=user_id,
                idempotency_key=idempotency_key,
                goal_text=body.goal_text,
                limit_micro_usd=limit,
                acceptance_criteria=tuple(body.acceptance_criteria),
                continues_run_id=body.continues_run_id,
                required_artifacts=tuple(body.required_artifacts),
                binding=binding,
                input_documents=tuple(body.input_documents),
                policy=policy,
                run_profile=body.run_profile.value if body.run_profile else None,
            )
        except (IdempotencyConflict, LinkRefused) as error:
            raise as_api_error(error) from None
    return RunAccepted(
        schema_version=1,
        run_id=result.run_id,
        version=result.version,
        status=result.status,  # type: ignore[arg-type]
        replayed=result.replayed,
    )


@router.get("/runs/{run_id}", operation_id="getRun", response_model=RunSummary)
async def get_run(
    run_id: UUID, request: Request, workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> RunSummary:
    async with request_pool(request).connection() as connection:
        summary = await read_summary(connection, workspace_id, run_id)
    if summary is None:
        raise ApiError(404, "run_not_found", "That run is not available.")
    return summary


async def _require_run(connection: AsyncConnection[Any], workspace_id: UUID, run_id: UUID) -> None:
    cursor = await connection.execute(
        "select 1 from public.runs where id = %s and workspace_id = %s", (run_id, workspace_id)
    )
    if await cursor.fetchone() is None:
        raise ApiError(404, "run_not_found", "That run is not available.")


async def _command(
    request: Request,
    run_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    command: RunCommand,
    body: RunCommandRequest | RunInputRequest,
    key: str,
    response: str | None = None,
) -> RunCommandResult:
    async with request_pool(request).connection() as connection:
        try:
            result = await apply_command(
                connection,
                workspace_id=workspace_id,
                run_id=run_id,
                command=command,
                actor=Actor.USER,
                expected_version=body.expected_version,
                actor_id=user_id,
                idempotency_key=key,
                response=response,
            )
        except (IdempotencyConflict, VersionConflict, RunNotFound, CommandRefused) as error:
            raise as_api_error(error) from None
    return RunCommandResult(
        schema_version=1,
        run_id=result.run_id,
        version=result.version,
        status=result.status,  # type: ignore[arg-type]
        changed=result.changed,
    )


Workspace = Annotated[UUID, Depends(current_workspace)]
User = Annotated[UUID, Depends(current_user)]


@router.post("/runs/{run_id}/input", operation_id="submitRunInput", response_model=RunCommandResult)
async def post_input(
    run_id: UUID,
    body: RunInputRequest,
    request: Request,
    key: Key,
    workspace: Workspace,
    user: User,
) -> RunCommandResult:
    return await _command(
        request, run_id, workspace, user, RunCommand.SUBMIT_INPUT, body, key, response=body.value
    )


@router.post("/runs/{run_id}/pause", operation_id="pauseRun", response_model=RunCommandResult)
async def post_pause(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    key: Key,
    workspace: Workspace,
    user: User,
) -> RunCommandResult:
    return await _command(request, run_id, workspace, user, RunCommand.PAUSE, body, key)


@router.post("/runs/{run_id}/resume", operation_id="resumeRun", response_model=RunCommandResult)
async def post_resume(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    key: Key,
    workspace: Workspace,
    user: User,
    settings: Annotated[ProviderSettings, Depends(provider_settings)],
) -> RunCommandResult:
    """Readiness is checked here, and again by the worker before anything is dispatched."""
    code = await settings.run_intent(workspace)
    if code != "ready":
        raise ApiError(409, code, "Model-backed work needs a usable OpenRouter key.")
    async with request_pool(request).connection() as connection:
        await _require_run(connection, workspace, run_id)
        left = await outstanding(connection, run_id)
        # A tool with a readback resolves itself on replay. Otherwise a person has to say.
        blocked = await has_unresolvable_effect(connection, run_id)
        blocked_contract = await execution_block(connection, run_id)
    if blocked_contract is not None:
        raise ApiError(
            409, "incompatible_version", "This run can't continue on this release. Start a new one."
        )
    if left.uncertain_calls:
        raise ApiError(
            409, "uncertain_model_call", "A model call's outcome must be reconciled first."
        )
    if blocked:
        raise ApiError(409, "unknown_effect", "An effect's outcome must be reconciled first.")
    return await _command(request, run_id, workspace, user, RunCommand.RESUME, body, key)


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
    key: Key,
    user: User,
    workspace: Annotated[UUID, Depends(require_owner)],
) -> ReconciliationResult:
    """An owner reports what the destination's own records show."""
    async with request_pool(request).connection() as connection:
        await _require_run(connection, workspace, run_id)
        try:
            await record_evidence(
                connection,
                workspace_id=workspace,
                run_id=run_id,
                operation_id=operation_id,
                actor_id=user,
                idempotency_key=key,
                outcome=body.outcome,
                evidence=public_text(body.evidence, limit=2000),
                generation=body.generation,
            )
        except ReconciliationRefused as error:
            status_code = 404 if error.code == "operation_not_found" else 409
            raise ApiError(status_code, error.code, "That can't be recorded.") from None
        except IdempotencyConflict as error:
            raise as_api_error(error) from None
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
    key: Key,
    user: User,
    workspace: Annotated[UUID, Depends(require_owner)],
) -> ReconciliationResult:
    """An owner records a charge seen in the provider's own account, for the oldest open call."""
    async with request_pool(request).connection() as connection:
        await _require_run(connection, workspace, run_id)
        scope = (workspace, user, "reconcile_model_call", str(run_id), key)
        fingerprint = request_hash({"charged": body.charged_micro_usd})
        try:
            async with connection.transaction():
                existing = await existing_receipt(connection, scope, fingerprint)
                if existing is not None:
                    return ReconciliationResult(
                        schema_version=1, reconciled_calls=existing["reconciled_calls"]
                    )
                cursor = await connection.execute(
                    "select id from app_private.model_invocations "
                    "where (run_id = %s or root_run_id = %s) "
                    "and status = 'uncertain' and reconciled_at is null "
                    "order by created_at limit 1 for update",
                    (run_id, run_id),
                )
                row = await cursor.fetchone()
                if row is not None:
                    await ModelAdmission(connection).reconcile(row[0], body.charged_micro_usd)
                reconciled = 0 if row is None else 1
                await store_receipt(
                    connection, scope, fingerprint, {"reconciled_calls": reconciled}
                )
        except IdempotencyConflict as error:
            raise as_api_error(error) from None
    return ReconciliationResult(schema_version=1, reconciled_calls=reconciled)


@router.post("/runs/{run_id}/cancel", operation_id="cancelRun", response_model=RunCommandResult)
async def post_cancel(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    key: Key,
    workspace: Workspace,
    user: User,
) -> RunCommandResult:
    return await _command(request, run_id, workspace, user, RunCommand.CANCEL, body, key)
