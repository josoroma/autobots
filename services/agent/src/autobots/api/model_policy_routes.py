"""The workspace model policy behind the BFF (PRD-Model-Providers MP-05, MD-02 and MD-03) and the
run intent check that reads it. Changes need owner authority and the version they expect."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import MemberWorkspace, ModelKeyCheck, OwnerWorkspace
from autobots.api.errors import ApiError, reworded
from autobots.api.pool import Pool
from autobots.api.resources import app_resources, request_pool
from autobots.api.security import require_internal
from autobots.application.model_admission import remaining_daily_micro_usd
from autobots.application.model_policy import (
    PolicyChanged,
    StoredPolicy,
    read_model_policy,
    refused_on_every_source,
    reset_role_overrides,
    save_model_policy,
    validated_choice,
)
from autobots.application.model_source import save_local_default
from autobots.application.provider_settings import workspace_model_source
from autobots.application.run_admission import (
    NO_LOCAL_DEFAULT,
    ROLE_OVERRIDE_ON_LOCAL,
    ModelNotReady,
    PolicyNotOffered,
    require_model_ready,
    saved_workspace_policy,
)
from autobots.application.sql import SqlConnection
from autobots.contracts.models import effective_policy
from autobots.contracts.settings import (
    ExpectedVersion,
    ModelPolicyState,
    ModelPolicyUpdate,
    RunIntentCheck,
    budget_range,
)
from autobots.domain.models import (
    ModelSource,
    ProfileNotOffered,
    approved_profile,
    resolve_role_policy,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
POLICY_CHANGED = "The policy changed. Reload and try again."


def policy_pool(request: Request) -> Pool:
    """The pool, or 503 in the wording these routes have always used."""
    pool = app_resources(request).pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "Provider settings are unavailable.")
    return pool


def _policy_state(stored: StoredPolicy) -> ModelPolicyState:
    """On Local, the Local default answers every role and no override applies (Decision 0041 A8);
    OpenRouter's saved choices stay stored for a switch back."""
    if stored.model_source is ModelSource.LOCAL:
        local = None if stored.local_profile is None else approved_profile(stored.local_profile)
        policy = resolve_role_policy(workspace_default=None if local is None else local.value)
        return ModelPolicyState(
            schema_version=1,
            version=stored.version,
            default_profile=local,
            role_overrides={},
            policy=effective_policy(policy),
        )
    policy = resolve_role_policy(
        workspace_default=stored.default_profile, workspace_role_overrides=stored.role_overrides
    )
    return ModelPolicyState(
        schema_version=1,
        version=stored.version,
        default_profile=(
            None if stored.default_profile is None else approved_profile(stored.default_profile)
        ),
        role_overrides={
            role: approved_profile(profile) for role, profile in stored.role_overrides.items()
        },
        policy=effective_policy(policy),
    )


@router.get(
    "/settings/model-policy", operation_id="getModelPolicy", response_model=ModelPolicyState
)
async def get_model_policy(request: Request, workspace_id: MemberWorkspace) -> ModelPolicyState:
    """What a new run would freeze. No row yet means version 0, naming no workspace default, so
    each role reads its built-in default as admission resolves it (MD-02)."""
    async with policy_pool(request).connection() as connection:
        stored = await read_model_policy(connection, workspace_id)
    return _policy_state(stored)


@router.put(
    "/settings/model-policy", operation_id="putModelPolicy", response_model=ModelPolicyState
)
async def put_model_policy(
    body: ModelPolicyUpdate,
    request: Request,
    workspace_id: OwnerWorkspace,
) -> ModelPolicyState:
    refused_on_every_source(body.default_profile, body.role_overrides)
    try:
        async with policy_pool(request).connection() as connection:
            if await workspace_model_source(connection, workspace_id) is ModelSource.LOCAL:
                return _policy_state(await _save_on_local(connection, workspace_id, body))
            chosen_default, overrides = validated_choice(body.default_profile, body.role_overrides)
            stored = await save_model_policy(
                connection,
                workspace_id,
                expected_version=body.expected_version,
                default_profile=chosen_default,
                role_overrides=overrides,
            )
    except PolicyChanged as refused:
        raise reworded(refused, POLICY_CHANGED) from None
    return _policy_state(stored)


async def _save_on_local(
    connection: SqlConnection, workspace_id: UUID, body: ModelPolicyUpdate
) -> StoredPolicy:
    """On Local, a save sets the Local default only. A role override is refused, as one local
    model answers every role (Decision 0041 A8), and OpenRouter's saved choices aren't touched."""
    if body.role_overrides:
        raise ProfileNotOffered(ROLE_OVERRIDE_ON_LOCAL)
    if body.default_profile is None:
        raise ProfileNotOffered(NO_LOCAL_DEFAULT)
    return await save_local_default(
        connection,
        workspace_id,
        expected_version=body.expected_version,
        local_profile=body.default_profile,
    )


@router.post(
    "/settings/model-policy/reset",
    operation_id="resetModelPolicyOverrides",
    response_model=ModelPolicyState,
)
async def reset_model_policy_overrides(
    body: ExpectedVersion,
    request: Request,
    workspace_id: OwnerWorkspace,
) -> ModelPolicyState:
    """Reset all, MD-03: every role override is cleared and the workspace default is kept. On
    Local no override applies, so nothing changes, and OpenRouter's are kept for a switch back."""
    try:
        async with policy_pool(request).connection() as connection:
            if await workspace_model_source(connection, workspace_id) is ModelSource.LOCAL:
                current = await read_model_policy(connection, workspace_id)
                if current.version != body.expected_version:
                    raise PolicyChanged("a stale version on Local")
                return _policy_state(current)
            stored = await reset_role_overrides(
                connection, workspace_id, expected_version=body.expected_version
            )
    except PolicyChanged as refused:
        raise reworded(refused, POLICY_CHANGED) from None
    return _policy_state(stored)


@router.post("/runs/intent", operation_id="checkRunIntent", response_model=RunIntentCheck)
async def check_run_intent(
    request: Request,
    model_key: ModelKeyCheck,
    workspace_id: MemberWorkspace,
) -> RunIntentCheck:
    """A user's Run click checks readiness here. It admits nothing: POST /v1/runs admits a run
    (US-4.1)."""
    # current_workspace needs the database, so the pool is always open by now.
    pool = request_pool(request)
    try:
        await require_model_ready(model_key, workspace_id, needed=True)
        # Kept here, as a resume and the worker read `run_intent` for the key alone. It names no
        # Expert or profile, so it resolves the saved policy alone, and reports instead of refusing.
        async with pool.connection() as connection:
            saved = await saved_workspace_policy(connection, workspace_id)
        saved.for_new_work(require_offer=True)
    except (ModelNotReady, PolicyNotOffered) as refused:
        code = refused.code
    else:
        code = "ready"
    async with pool.connection() as connection:
        budget = budget_range(await remaining_daily_micro_usd(connection, workspace_id))
    return RunIntentCheck(
        schema_version=1,
        ready=code == "ready",
        code=code,  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal
        budget=budget,
    )
