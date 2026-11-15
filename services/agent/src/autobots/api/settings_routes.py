"""Settings routes behind the BFF: the model policy (MP-05), provider and tool keys (PK-07), model
details (MD-02, MD-03), the run intent check and the shared session and workspace dependencies.
Changes need owner authority and a version."""

import os
from collections.abc import AsyncIterator, Mapping
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import ApiError, reworded
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.application.model_admission import remaining_daily_micro_usd
from autobots.application.provider_settings import (
    InvalidKey,
    ProviderSettings,
    policy_overrides_json,
)
from autobots.application.run_admission import (
    ModelNotReady,
    PolicyNotOffered,
    require_model_ready,
    saved_workspace_policy,
)
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.contracts.models import effective_policy
from autobots.contracts.settings import (
    CredentialDraft,
    ExpectedVersion,
    KeyOrVar,
    KeyOrVarDraft,
    KeyOrVarName,
    KeysAndVars,
    ModelList,
    ModelPolicyState,
    ModelPolicyUpdate,
    ProviderStatus,
    RunIntentCheck,
    budget_range,
)
from autobots.domain.models import (
    UnknownModelProfile,
    approved_profile,
    require_offered,
    resolve_role_policy,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def process_environment(request: Request) -> Mapping[str, str]:
    """The process environment as the entry point read it at start, which orders keys for admission
    and availability alike (Decisions 0024 K1 and 0025 V3, PAPI-10). An app built without a provider
    context, as some tests are, has only the live one."""
    context = request.app.state.provider_context
    return os.environ if context is None else context.process_environment


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
    await settings.save_credential(workspace_id, body.draft_key, body.expected_version)
    return await settings.status(workspace_id)


@router.delete(
    "/settings/model-providers/openrouter/credential",
    operation_id="deleteOpenRouterCredential",
    response_model=ProviderStatus,
)
async def delete_credential(
    body: ExpectedVersion, settings: Settings, workspace_id: Annotated[UUID, Depends(require_owner)]
) -> ProviderStatus:
    await settings.disconnect(workspace_id, body.expected_version)
    return await settings.status(workspace_id)


@router.post(
    "/settings/model-providers/openrouter/validate",
    operation_id="validateOpenRouter",
    response_model=ProviderStatus,
)
async def validate_credential(
    settings: Settings, workspace_id: Annotated[UUID, Depends(require_owner)]
) -> ProviderStatus:
    await settings.revalidate(workspace_id)
    return await settings.status(workspace_id)


async def keys_and_vars_settings(request: Request) -> AsyncIterator[ToolKeySettings]:
    pool = request.app.state.pool
    context = request.app.state.provider_context
    if pool is None or context is None:
        raise ApiError(503, "service_unavailable", "Keys & vars settings are unavailable.")
    async with pool.connection() as connection:
        # Decisions 0024 K1 and 0025 V3 order the keys, and the process environment in that order
        # is the one the entry point read at start, as the OpenRouter key's is.
        yield ToolKeySettings(connection, context.master_key_file, context.process_environment)


KeysAndVarsSettings = Annotated[ToolKeySettings, Depends(keys_and_vars_settings)]
_KEY_REFUSED = ("invalid_key", "That key was not accepted. The previous key is unchanged.")
REFUSED_VALUE: dict[str, tuple[str, str]] = {
    "tavily": _KEY_REFUSED,
    "jina": _KEY_REFUSED,
    "github_token": _KEY_REFUSED,
    "github_repository": ("invalid_value", "Use owner/name. The previous value is unchanged."),
    "browser_executor": (
        "invalid_value",
        "Use enabled or disabled. The previous value is unchanged.",
    ),
}


async def _keys_and_vars(settings: ToolKeySettings, workspace_id: UUID) -> KeysAndVars:
    states = await settings.status(workspace_id)
    return KeysAndVars(
        schema_version=1,
        items=[
            KeyOrVar.model_validate(
                {
                    "name": state.name,
                    "variable": state.variable,
                    "kind": state.kind,
                    "source": state.source,
                    "value": state.value,
                    "version": state.version,
                }
            )
            for state in states
        ],
    )


@router.get("/settings/keys-and-vars", operation_id="getKeysAndVars", response_model=KeysAndVars)
async def get_keys_and_vars(
    settings: KeysAndVarsSettings, workspace_id: Annotated[UUID, Depends(current_workspace)]
) -> KeysAndVars:
    """Every member sees each item's source and a value's value, never a secret (PK-07)."""
    return await _keys_and_vars(settings, workspace_id)


@router.put(
    "/settings/keys-and-vars/{name}", operation_id="putKeyOrVar", response_model=KeysAndVars
)
async def put_key_or_var(
    name: KeyOrVarName,
    body: KeyOrVarDraft,
    settings: KeysAndVarsSettings,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> KeysAndVars:
    try:
        await settings.save(workspace_id, name, body.value, body.expected_version)
    except InvalidKey as refused:
        # Fixed text per item, so nothing submitted is echoed back.
        code, message = REFUSED_VALUE[name]
        raise reworded(refused, message, code=code) from None
    return await _keys_and_vars(settings, workspace_id)


@router.delete(
    "/settings/keys-and-vars/{name}", operation_id="deleteKeyOrVar", response_model=KeysAndVars
)
async def delete_key_or_var(
    name: KeyOrVarName,
    body: ExpectedVersion,
    settings: KeysAndVarsSettings,
    workspace_id: Annotated[UUID, Depends(require_owner)],
) -> KeysAndVars:
    await settings.remove(workspace_id, name, body.expected_version)
    return await _keys_and_vars(settings, workspace_id)


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
    """A user's Run click checks readiness here. It admits nothing: POST /v1/runs admits a run
    (US-4.1)."""
    # current_workspace needs the database, so the pool is always open by now.
    pool = request_pool(request)
    try:
        await require_model_ready(settings.run_intent, workspace_id, needed=True)
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
