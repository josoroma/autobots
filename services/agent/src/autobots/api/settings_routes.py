"""The exact MP-05 routes, behind the BFF. Changes need owner authority and a version."""

import os
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.application.credentials.store import (
    CredentialMissing,
    CredentialStorageUnavailable,
)
from autobots.application.model_admission import remaining_daily_micro_usd
from autobots.application.provider_settings import (
    EnvironmentManaged,
    InvalidKey,
    ProviderSettings,
    StaleVersion,
    ValidationUnavailable,
    policy_overrides_json,
)
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.contracts.models import effective_policy
from autobots.contracts.settings import (
    CredentialDraft,
    ExpectedVersion,
    ModelList,
    ModelPolicyState,
    ModelPolicyUpdate,
    ProviderStatus,
    RunIntentCheck,
    ToolKeyList,
    ToolKeyProvider,
    ToolKeyStatus,
    budget_range,
)
from autobots.domain.models import (
    ProfileNotOffered,
    UnknownModelProfile,
    approved_profile,
    require_offered,
    resolve_role_policy,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


async def current_workspace(
    request: Request,
    user_id: Annotated[UUID, Depends(current_user)],
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> UUID:
    """The chosen workspace, verified, or the user's only one. Never trusted from the browser."""
    workspaces = await request.app.state.membership.workspaces_for(user_id)
    if x_autobots_workspace is not None:
        if x_autobots_workspace not in workspaces:
            raise ApiError(403, "forbidden", "This workspace is not available.")
        return x_autobots_workspace
    if len(workspaces) != 1:
        raise ApiError(403, "workspace_required", "Choose a workspace.")
    workspace: UUID = workspaces[0]
    return workspace


async def require_owner(
    request: Request,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    user_id: Annotated[UUID, Depends(current_user)],
) -> UUID:
    if await request.app.state.membership.role_in(user_id, workspace_id) != "owner":
        raise ApiError(403, "owner_required", "Only the workspace owner can change this.")
    return workspace_id


async def provider_settings(request: Request) -> AsyncIterator[ProviderSettings]:
    pool = request.app.state.pool
    context = request.app.state.provider_context
    if pool is None or context is None:
        raise ApiError(503, "service_unavailable", "Provider settings are unavailable.")
    async with pool.connection() as connection:
        yield ProviderSettings(connection, context)


Settings = Annotated[ProviderSettings, Depends(provider_settings)]


def as_api_error(error: Exception) -> ApiError:
    """Each message is fixed, so no upstream response or submitted key can reach the client."""
    if isinstance(error, StaleVersion):
        return ApiError(409, error.code, "The settings changed. Reload and try again.")
    if isinstance(error, EnvironmentManaged):
        return ApiError(409, error.code, "The environment supplies this key. Change it there.")
    if isinstance(error, InvalidKey):
        return ApiError(
            422, error.code, "That key was not accepted. The previous key is unchanged."
        )
    if isinstance(error, ValidationUnavailable):
        return ApiError(503, error.code, "The key could not be checked right now. Nothing changed.")
    if isinstance(error, CredentialStorageUnavailable):
        return ApiError(503, error.code, "Credential storage is unavailable.")
    if isinstance(error, CredentialMissing):
        return ApiError(409, error.code, "No credential is configured.")
    raise error


HANDLED = (
    StaleVersion,
    EnvironmentManaged,
    InvalidKey,
    ValidationUnavailable,
    CredentialStorageUnavailable,
    CredentialMissing,
)


@router.get(
    "/settings/model-providers", operation_id="getModelProviders", response_model=ProviderStatus
)
async def get_status(
    settings: Settings, workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> ProviderStatus:
    return await settings.status(workspace_id)


@router.put(
    "/settings/model-providers/openrouter/credential",
    operation_id="putOpenRouterCredential",
    response_model=ProviderStatus,
)
async def put_credential(
    body: CredentialDraft, settings: Settings, workspace_id: Annotated[UUID, Depends(require_owner)]
) -> ProviderStatus:
    try:
        await settings.save_credential(workspace_id, body.draft_key, body.expected_version)
    except HANDLED as error:
        raise as_api_error(error) from None
    return await settings.status(workspace_id)


@router.delete(
    "/settings/model-providers/openrouter/credential",
    operation_id="deleteOpenRouterCredential",
    response_model=ProviderStatus,
)
async def delete_credential(
    body: ExpectedVersion, settings: Settings, workspace_id: Annotated[UUID, Depends(require_owner)]
) -> ProviderStatus:
    try:
        await settings.disconnect(workspace_id, body.expected_version)
    except HANDLED as error:
        raise as_api_error(error) from None
    return await settings.status(workspace_id)


@router.post(
    "/settings/model-providers/openrouter/validate",
    operation_id="validateOpenRouter",
    response_model=ProviderStatus,
)
async def validate_credential(
    settings: Settings, workspace_id: Annotated[UUID, Depends(require_owner)]
) -> ProviderStatus:
    try:
        await settings.revalidate(workspace_id)
    except HANDLED as error:
        raise as_api_error(error) from None
    return await settings.status(workspace_id)


async def tool_key_settings(request: Request) -> AsyncIterator[ToolKeySettings]:
    pool = request.app.state.pool
    context = request.app.state.provider_context
    if pool is None or context is None:
        raise ApiError(503, "service_unavailable", "Tool key settings are unavailable.")
    async with pool.connection() as connection:
        yield ToolKeySettings(connection, context.master_key_file, os.environ)


ToolKeys = Annotated[ToolKeySettings, Depends(tool_key_settings)]


async def _tool_keys(keys: ToolKeySettings, workspace_id: UUID) -> ToolKeyList:
    states = await keys.status(workspace_id)
    return ToolKeyList(
        schema_version=1,
        keys=[
            ToolKeyStatus.model_validate(
                {
                    "provider": state.provider,
                    "variable": state.variable,
                    "source": state.source,
                    "version": state.version,
                }
            )
            for state in states
        ],
    )


@router.get("/settings/tool-keys", operation_id="getToolKeys", response_model=ToolKeyList)
async def get_tool_keys(
    keys: ToolKeys, workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> ToolKeyList:
    """Every member sees where each key comes from, never the key (PK-05)."""
    return await _tool_keys(keys, workspace_id)


@router.put("/settings/tool-keys/{provider}", operation_id="putToolKey", response_model=ToolKeyList)
async def put_tool_key(
    provider: ToolKeyProvider,
    body: CredentialDraft,
    keys: ToolKeys,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> ToolKeyList:
    try:
        await keys.save(workspace_id, provider, body.draft_key, body.expected_version)
    except HANDLED as error:
        raise as_api_error(error) from None
    return await _tool_keys(keys, workspace_id)


@router.delete(
    "/settings/tool-keys/{provider}", operation_id="deleteToolKey", response_model=ToolKeyList
)
async def delete_tool_key(
    provider: ToolKeyProvider,
    body: ExpectedVersion,
    keys: ToolKeys,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> ToolKeyList:
    try:
        await keys.remove(workspace_id, provider, body.expected_version)
    except HANDLED as error:
        raise as_api_error(error) from None
    return await _tool_keys(keys, workspace_id)


@router.get("/models", operation_id="getModels", response_model=ModelList)
async def get_models(
    settings: Settings, _workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> ModelList:
    return await settings.models()


def _policy_state(
    version: int, default_profile: str | None, overrides: dict[str, str]
) -> ModelPolicyState:
    policy = resolve_role_policy(
        workspace_default=default_profile, workspace_role_overrides=overrides
    )
    return ModelPolicyState(
        schema_version=1,
        version=version,
        default_profile=None if default_profile is None else approved_profile(default_profile),
        role_overrides={role: approved_profile(profile) for role, profile in overrides.items()},
        policy=effective_policy(policy),
    )


@router.get(
    "/settings/model-policy", operation_id="getModelPolicy", response_model=ModelPolicyState
)
async def get_model_policy(
    request: Request, workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> ModelPolicyState:
    """What a new run would freeze. No row yet means version 0, naming no workspace default, so
    each role reads its built-in default as admission resolves it (MD-02)."""
    pool: Any = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "Provider settings are unavailable.")
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "select version, default_profile, role_overrides from app_private.model_policies "
            "where workspace_id = %s",
            (workspace_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return _policy_state(0, None, {})
    return _policy_state(row[0], row[1], row[2] or {})


@router.put(
    "/settings/model-policy", operation_id="putModelPolicy", response_model=ModelPolicyState
)
async def put_model_policy(
    body: ModelPolicyUpdate,
    request: Request,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> ModelPolicyState:
    overrides = {role: profile.value for role, profile in body.role_overrides.items()}
    chosen_default = None if body.default_profile is None else body.default_profile.value
    named = [
        *([body.default_profile] if body.default_profile else []),
        *body.role_overrides.values(),
    ]
    try:
        resolve_role_policy(workspace_default=chosen_default, workspace_role_overrides=overrides)
        require_offered(named)
    except UnknownModelProfile as error:
        raise ApiError(422, "unknown_model", "Choose an approved model and role.") from error
    except ProfileNotOffered as refused:
        raise ApiError(422, refused.code, str(refused)) from None
    pool: Any = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "Provider settings are unavailable.")
    async with pool.connection() as connection, connection.transaction():
        cursor = await connection.execute(
            "select version from app_private.model_policies where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        if current != body.expected_version:
            raise ApiError(409, "stale_version", "The policy changed. Reload and try again.")
        await connection.execute(
            "insert into app_private.model_policies "
            "(workspace_id, version, default_profile, role_overrides) values (%s, %s, %s, %s) "
            "on conflict (workspace_id) do update set version = excluded.version, "
            "default_profile = excluded.default_profile, role_overrides = excluded.role_overrides",
            (workspace_id, current + 1, chosen_default, policy_overrides_json(overrides)),
        )
    return _policy_state(current + 1, chosen_default, overrides)


@router.post(
    "/settings/model-policy/reset",
    operation_id="resetModelPolicyOverrides",
    response_model=ModelPolicyState,
)
async def reset_model_policy_overrides(
    body: ExpectedVersion,
    request: Request,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> ModelPolicyState:
    """Reset all, MD-03: every role override is cleared and the workspace default is kept."""
    pool: Any = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "Provider settings are unavailable.")
    async with pool.connection() as connection, connection.transaction():
        cursor = await connection.execute(
            "select version, default_profile from app_private.model_policies "
            "where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current, kept = (row[0], row[1]) if row else (0, None)
        if current != body.expected_version:
            raise ApiError(409, "stale_version", "The policy changed. Reload and try again.")
        await connection.execute(
            "insert into app_private.model_policies "
            "(workspace_id, version, default_profile, role_overrides) values (%s, %s, %s, '{}') "
            "on conflict (workspace_id) do update set version = excluded.version, "
            "role_overrides = excluded.role_overrides",
            (workspace_id, current + 1, kept),
        )
    return _policy_state(current + 1, kept, {})


@router.post("/runs/intent", operation_id="checkRunIntent", response_model=RunIntentCheck)
async def check_run_intent(
    request: Request,
    settings: Settings,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
) -> RunIntentCheck:
    """Only a user's Run click reaches this. It admits nothing: run admission is a later story."""
    code = await settings.run_intent(workspace_id)
    pool: Any = request.app.state.pool
    if code == "ready" and pool is not None:
        # Kept here, as a resume and the worker read `run_intent` for the key alone.
        async with pool.connection() as connection:
            cursor = await connection.execute(
                "select default_profile, role_overrides from app_private.model_policies "
                "where workspace_id = %s",
                (workspace_id,),
            )
            row = await cursor.fetchone()
        policy = resolve_role_policy(
            workspace_default=row[0] if row else None,
            workspace_role_overrides=row[1] if row else None,
        )
        try:
            require_offered(policy.bindings.values())
        except ProfileNotOffered as refused:
            code = refused.code
    budget = None
    if pool is not None:
        async with pool.connection() as connection:
            budget = budget_range(await remaining_daily_micro_usd(connection, workspace_id))
    return RunIntentCheck(
        schema_version=1,
        ready=code == "ready",
        code=code,  # type: ignore[arg-type]
        budget=budget,
    )
