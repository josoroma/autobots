"""Run admission and user commands. A request records intent; a worker owns execution."""

from functools import partial
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from psycopg import AsyncConnection

from autobots.api.errors import ApiError, reworded
from autobots.api.operation_routes import require_ready
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import (
    current_workspace,
    process_environment,
    provider_settings,
    require_owner,
)
from autobots.api.tool_routes import catalog_of
from autobots.application.experts import ExpertRefused
from autobots.application.model_admission import ModelAdmission, remaining_daily_micro_usd
from autobots.application.provider_settings import ProviderSettings
from autobots.application.reconciliation import has_unresolvable_effect, record_evidence
from autobots.application.recovery import execution_block, outstanding
from autobots.application.run_admission import (
    AdmissionInput,
    admit_from_request,
    expert_overrides,
    require_model_ready,
    saved_workspace_policy,
)
from autobots.application.run_projection import public_text, read_summary
from autobots.application.runs import (
    CommandReceipt,
    apply_command,
    existing_receipt,
    request_hash,
    store_receipt,
)
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
from autobots.domain.models import PROFILES, ModelProfileId
from autobots.domain.runs import RunCommand
from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS
from autobots.persistence.records import read_expert_config

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


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
        saved = await saved_workspace_policy(connection, workspace_id)
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
            config = read_expert_config(found[0])
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
    idempotency_key: Key,
    settings: Annotated[ProviderSettings, Depends(provider_settings)],
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    user_id: Annotated[UUID, Depends(current_user)],
) -> RunAccepted:
    # The first step's refusal is the answer, in api/errors.py's wording, apart from routing's.
    try:
        result = await admit_from_request(
            AdmissionInput.of(
                body, workspace_id=workspace_id, user_id=user_id, idempotency_key=idempotency_key
            ),
            database=request_pool(request),
            model_ready=settings.run_intent,
            role=partial(request.app.state.membership.role_in, user_id, workspace_id),
            # Decisions 0024 K1 and 0025 V3 order the keys, and the process environment in that
            # order is the one the entry point read at start, as the OpenRouter key's is. The
            # `settings` dependency has already refused a missing provider context.
            environment=process_environment(request),
            catalog=catalog_of(request),
        )
    except ExpertRefused as refused:
        raise reworded(refused, "That routing isn't available.") from None
    return RunAccepted(
        schema_version=1,
        run_id=result.run_id,
        version=result.version,
        status=result.status,  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal
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
        result = await apply_command(
            connection,
            workspace_id=workspace_id,
            run_id=run_id,
            command=command,
            expected_version=body.expected_version,
            receipt=CommandReceipt(user_id, key),
            response=response,
        )
    return RunCommandResult(
        schema_version=1,
        run_id=result.run_id,
        version=result.version,
        status=result.status,  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal
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
    # Offering isn't checked again: a resumed run keeps the policy it froze at admission, as a
    # policy change reaches future runs only (PRD-Model-Providers MP-01).
    await require_model_ready(settings.run_intent, workspace, needed=True)
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
            await store_receipt(connection, scope, fingerprint, {"reconciled_calls": reconciled})
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
