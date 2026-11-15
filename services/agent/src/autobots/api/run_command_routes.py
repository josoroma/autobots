"""A person's commands to a run: input, pause, resume and cancel (SP-010). Each records intent under
its idempotency key and the run's expected version, and a worker acts on it."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import CurrentUser, IdempotencyKey, MemberWorkspace, ModelKeyCheck
from autobots.api.pool import request_pool
from autobots.api.security import require_internal
from autobots.application.reconciliation import require_resumable
from autobots.application.run_admission import require_model_ready
from autobots.application.runs import CommandReceipt, apply_command
from autobots.contracts.run_commands import RunCommandRequest, RunCommandResult, RunInputRequest
from autobots.domain.runs import RunCommand

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


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


@router.post("/runs/{run_id}/input", operation_id="submitRunInput", response_model=RunCommandResult)
async def post_input(
    run_id: UUID,
    body: RunInputRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
) -> RunCommandResult:
    return await _command(
        request,
        run_id,
        workspace_id,
        user_id,
        RunCommand.SUBMIT_INPUT,
        body,
        idempotency_key,
        response=body.value,
    )


@router.post("/runs/{run_id}/pause", operation_id="pauseRun", response_model=RunCommandResult)
async def post_pause(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
) -> RunCommandResult:
    return await _command(
        request, run_id, workspace_id, user_id, RunCommand.PAUSE, body, idempotency_key
    )


@router.post("/runs/{run_id}/resume", operation_id="resumeRun", response_model=RunCommandResult)
async def post_resume(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
    model_key: ModelKeyCheck,
) -> RunCommandResult:
    """Readiness is checked here, and again by the worker before anything is dispatched."""
    # Offering isn't checked again: a resumed run keeps the policy it froze at admission, as a
    # policy change reaches future runs only (PRD-Model-Providers MP-01).
    await require_model_ready(model_key, workspace_id, needed=True)
    async with request_pool(request).connection() as connection:
        await require_resumable(connection, workspace_id, run_id)
    return await _command(
        request, run_id, workspace_id, user_id, RunCommand.RESUME, body, idempotency_key
    )


@router.post("/runs/{run_id}/cancel", operation_id="cancelRun", response_model=RunCommandResult)
async def post_cancel(
    run_id: UUID,
    body: RunCommandRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
) -> RunCommandResult:
    return await _command(
        request, run_id, workspace_id, user_id, RunCommand.CANCEL, body, idempotency_key
    )
