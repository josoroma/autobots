"""Settings → Keys & vars behind the BFF (PRD-Tool-Catalog PK-07). Every member reads each item's
source and a value's value, never a secret. Changes need owner authority and a version."""

from uuid import UUID

from fastapi import APIRouter, Depends

from autobots.api.dependencies import KeysAndVarsDep, MemberWorkspace, OwnerWorkspace
from autobots.api.errors import reworded
from autobots.api.security import require_internal
from autobots.application.provider_settings import InvalidKey
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.contracts.settings import (
    ExpectedVersion,
    KeyOrVar,
    KeyOrVarDraft,
    KeyOrVarName,
    KeysAndVars,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
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
async def get_keys_and_vars(settings: KeysAndVarsDep, workspace_id: MemberWorkspace) -> KeysAndVars:
    """Every member sees each item's source and a value's value, never a secret (PK-07)."""
    async with settings.opened() as items:
        return await _keys_and_vars(items, workspace_id)


@router.put(
    "/settings/keys-and-vars/{name}", operation_id="putKeyOrVar", response_model=KeysAndVars
)
async def put_key_or_var(
    name: KeyOrVarName,
    body: KeyOrVarDraft,
    settings: KeysAndVarsDep,
    workspace_id: OwnerWorkspace,
) -> KeysAndVars:
    async with settings.opened() as items:
        try:
            await items.save(workspace_id, name, body.value, body.expected_version)
        except InvalidKey as refused:
            # Fixed text per item, so nothing submitted is echoed back.
            code, message = REFUSED_VALUE[name]
            raise reworded(refused, message, code=code) from None
        return await _keys_and_vars(items, workspace_id)


@router.delete(
    "/settings/keys-and-vars/{name}", operation_id="deleteKeyOrVar", response_model=KeysAndVars
)
async def delete_key_or_var(
    name: KeyOrVarName,
    body: ExpectedVersion,
    settings: KeysAndVarsDep,
    workspace_id: OwnerWorkspace,
) -> KeysAndVars:
    async with settings.opened() as items:
        await items.remove(workspace_id, name, body.expected_version)
        return await _keys_and_vars(items, workspace_id)
