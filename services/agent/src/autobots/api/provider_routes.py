"""The OpenRouter provider's settings behind the BFF (PRD-Model-Providers MP-05) and its model list.
Changes need owner authority and a version."""

from fastapi import APIRouter, Depends

from autobots.api.dependencies import MemberWorkspace, OwnerWorkspace, ProviderSettingsDep
from autobots.api.security import require_internal
from autobots.contracts.settings import CredentialDraft, ExpectedVersion, ModelList, ProviderStatus

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get(
    "/settings/model-providers", operation_id="getModelProviders", response_model=ProviderStatus
)
async def get_status(
    settings: ProviderSettingsDep, workspace_id: MemberWorkspace
) -> ProviderStatus:
    async with settings.opened() as provider:
        return await provider.status(workspace_id)


@router.put(
    "/settings/model-providers/openrouter/credential",
    operation_id="putOpenRouterCredential",
    response_model=ProviderStatus,
)
async def put_credential(
    body: CredentialDraft, settings: ProviderSettingsDep, workspace_id: OwnerWorkspace
) -> ProviderStatus:
    async with settings.opened() as provider:
        await provider.save_credential(workspace_id, body.draft_key, body.expected_version)
        return await provider.status(workspace_id)


@router.delete(
    "/settings/model-providers/openrouter/credential",
    operation_id="deleteOpenRouterCredential",
    response_model=ProviderStatus,
)
async def delete_credential(
    body: ExpectedVersion, settings: ProviderSettingsDep, workspace_id: OwnerWorkspace
) -> ProviderStatus:
    async with settings.opened() as provider:
        await provider.disconnect(workspace_id, body.expected_version)
        return await provider.status(workspace_id)


@router.post(
    "/settings/model-providers/openrouter/validate",
    operation_id="validateOpenRouter",
    response_model=ProviderStatus,
)
async def validate_credential(
    settings: ProviderSettingsDep, workspace_id: OwnerWorkspace
) -> ProviderStatus:
    async with settings.opened() as provider:
        await provider.revalidate(workspace_id)
        return await provider.status(workspace_id)


@router.get("/models", operation_id="getModels", response_model=ModelList)
async def get_models(settings: ProviderSettingsDep, _workspace_id: MemberWorkspace) -> ModelList:
    async with settings.opened() as provider:
        return await provider.models(_workspace_id)
