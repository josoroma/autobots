"""Run admission and user commands. A request records intent; a worker owns execution."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, provider_settings, require_owner
from autobots.application.model_admission import ModelAdmission
from autobots.application.provider_settings import ProviderSettings
from autobots.application.recovery import outstanding
from autobots.application.runs import (
    IdempotencyConflict,
    LinkRefused,
    RunNotFound,
    VersionConflict,
    admit_run,
    apply_command,
)
from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.run_commands import (
    ModelCallReconciliation,
    ReconciliationResult,
    RunAccepted,
    RunCommandRequest,
    RunCommandResult,
    RunInputRequest,
    RunRequest,
)
from autobots.contracts.runs import RunSummary
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, CommandRefused, RunCommand

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
RUN_COLUMNS = (
    "id, workspace_id, parent_run_id, status, created_at, updated_at, spent_micro_usd, "
    "reserved_micro_usd, limit_micro_usd, lease_generation, checkpoint_thread_id, version"
)


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def as_api_error(error: Exception) -> ApiError:
    if isinstance(error, IdempotencyConflict):
        return ApiError(409, error.code, "This key was already used with different content.")
    if isinstance(error, VersionConflict):
        return ApiError(409, error.code, "The run changed. Reload and try again.")
    if isinstance(error, LinkRefused):
        return ApiError(409, error.code, "Only a finished run can be continued.")
    if isinstance(error, RunNotFound):
        return ApiError(404, error.code, "That run is not available.")
    if isinstance(error, CommandRefused):
        return ApiError(
            409, "transition_refused", "That is not allowed in the run's current state."
        )
    raise error


@router.post(
    "/runs",
    operation_id="admitRun",
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
    code = await settings.run_intent(workspace_id)
    if code != "ready":
        raise ApiError(409, code, "Model-backed work needs a usable OpenRouter key.")
    async with _pool(request).connection() as connection:
        row = await (
            await connection.execute(
                "select default_profile, role_overrides from app_private.model_policies "
                "where workspace_id = %s",
                (workspace_id,),
            )
        ).fetchone()
        policy = resolve_role_policy(
            workspace_default=row[0] if row else None,
            workspace_role_overrides=row[1] if row else None,
        )
        try:
            result = await admit_run(
                connection,
                workspace_id=workspace_id,
                actor_id=user_id,
                idempotency_key=idempotency_key,
                goal_text=body.goal_text,
                limit_micro_usd=body.limit_micro_usd,
                acceptance_criteria=tuple(body.acceptance_criteria),
                continues_run_id=body.continues_run_id,
                policy=policy,
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
    async with _pool(request).connection() as connection:
        cursor = await connection.execute(
            f"select {RUN_COLUMNS} from public.runs where id = %s and workspace_id = %s",
            (run_id, workspace_id),
        )
        row = await cursor.fetchone()
    if row is None:
        raise ApiError(404, "run_not_found", "That run is not available.")
    names = [column.strip() for column in RUN_COLUMNS.split(",")]
    return run_summary_from_domain(run_from_row(dict(zip(names, row, strict=True))))  # type: ignore[arg-type]


async def _require_run(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
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
    async with _pool(request).connection() as connection:
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
    async with _pool(request).connection() as connection:
        await _require_run(connection, workspace, run_id)
        left = await outstanding(connection, run_id)
    if left.uncertain_calls:
        raise ApiError(
            409, "uncertain_model_call", "A model call's outcome must be reconciled first."
        )
    return await _command(request, run_id, workspace, user, RunCommand.RESUME, body, key)


@router.post(
    "/runs/{run_id}/model-calls/reconcile",
    operation_id="reconcileRunModelCalls",
    response_model=ReconciliationResult,
)
async def post_reconcile(
    run_id: UUID,
    body: ModelCallReconciliation,
    request: Request,
    workspace: Annotated[UUID, Depends(require_owner)],
) -> ReconciliationResult:
    """An owner records a charge seen in the provider's own account, for the oldest open call."""
    async with _pool(request).connection() as connection:
        await _require_run(connection, workspace, run_id)
        cursor = await connection.execute(
            "select id from app_private.model_invocations where run_id = %s "
            "and status = 'uncertain' and reconciled_at is null order by created_at limit 1",
            (run_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return ReconciliationResult(schema_version=1, reconciled_calls=0)
        await ModelAdmission(connection).reconcile(row[0], body.charged_micro_usd)
    return ReconciliationResult(schema_version=1, reconciled_calls=1)


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
