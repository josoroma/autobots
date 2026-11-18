"""Tool discovery, PRD-Tool-Catalog TC-05, member-readable and never a secret, and the owner's
tool switches, Decision 0033 W3 to W5."""

from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import (
    CurrentUser,
    MemberWorkspace,
    OwnerWorkspace,
    catalog_of,
    is_owner,
    process_environment,
)
from autobots.api.errors import ApiError
from autobots.api.resources import app_resources, request_pool
from autobots.api.security import require_internal
from autobots.application import tool_switches
from autobots.application.tool_grants import tool_grants
from autobots.application.tool_keys import key_sources
from autobots.contracts.tool_catalog import (
    AvailabilityName,
    GrantedTo,
    ToolCatalog,
    ToolDescriptor,
    ToolGrants,
    ToolGroupName,
    ToolProviderName,
    ToolSwitchDraft,
    ToolSwitchView,
    ToolVersions,
)
from autobots.domain.tool_switches import SwitchKind

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


async def _keys(request: Request, workspace_id: UUID) -> Mapping[str, str]:
    """PK-04: availability is the workspace's, since it may have saved a tool's key in Settings.
    With no database, the process environment's keys alone."""
    environment = process_environment(request)
    if app_resources(request).pool is None:
        return environment
    async with request_pool(request).connection() as connection:
        return await key_sources(connection, workspace_id, environment)


@router.get("/tools", operation_id="listTools", response_model=ToolCatalog)
async def list_tools(
    request: Request,
    user_id: CurrentUser,
    workspace_id: MemberWorkspace,
    group: ToolGroupName | None = None,
    availability: AvailabilityName | None = None,
    provider: ToolProviderName | None = None,
) -> ToolCatalog:
    keys = await _keys(request, workspace_id)
    found = catalog_of(request).catalog(
        keys, group=group, availability=availability, provider=provider
    )
    # W4: every member sees the switches, and only the owner may change them.
    owner = await is_owner(request, user_id, workspace_id)
    return found.model_copy(update={"viewer_can_switch": owner})


async def _switch(
    request: Request, workspace_id: UUID, kind: SwitchKind, target: str, body: ToolSwitchDraft
) -> ToolSwitchView:
    keys = await _keys(request, workspace_id)
    groups = [item.group for item in catalog_of(request).catalog(keys).groups if item.switch]
    try:
        tool_switches.check_target(kind, target, groups)
    except tool_switches.SwitchNotFound:
        raise ApiError(404, "switch_not_found", "That tool or group has no switch.") from None
    async with request_pool(request).connection() as connection:
        saved = await tool_switches.change(
            connection, workspace_id, kind, target, body.enabled, body.expected_version
        )
    return ToolSwitchView(enabled=saved.enabled, version=saved.version)


@router.put(
    "/tools/groups/{group}/switch", operation_id="putToolGroupSwitch", response_model=ToolSwitchView
)
async def put_tool_group_switch(
    group: ToolGroupName, body: ToolSwitchDraft, request: Request, workspace_id: OwnerWorkspace
) -> ToolSwitchView:
    """W1: turns a whole group on or off for the workspace."""
    return await _switch(request, workspace_id, "group", group, body)


@router.put("/tools/{tool_id}/switch", operation_id="putToolSwitch", response_model=ToolSwitchView)
async def put_tool_switch(
    tool_id: str, body: ToolSwitchDraft, request: Request, workspace_id: OwnerWorkspace
) -> ToolSwitchView:
    """W1: turns one tool on or off for the workspace."""
    await _versions(request, workspace_id, tool_id)
    return await _switch(request, workspace_id, "tool", tool_id, body)


async def _versions(request: Request, workspace_id: UUID, tool_id: str) -> list[ToolDescriptor]:
    keys = await _keys(request, workspace_id)
    found = [item for item in catalog_of(request).descriptors(keys) if item.tool_id == tool_id]
    if not found:
        raise ApiError(404, "tool_not_found", "That tool isn't in the catalog.")
    return found


@router.get("/tools/{tool_id}", operation_id="getToolVersions", response_model=ToolVersions)
async def get_tool(tool_id: str, request: Request, workspace_id: MemberWorkspace) -> ToolVersions:
    return ToolVersions(tool_id=tool_id, versions=await _versions(request, workspace_id, tool_id))


@router.get(
    "/tools/{tool_id}/versions/{version}",
    operation_id="getToolVersion",
    response_model=ToolDescriptor,
)
async def get_tool_version(
    tool_id: str, version: int, request: Request, workspace_id: MemberWorkspace
) -> ToolDescriptor:
    for item in await _versions(request, workspace_id, tool_id):
        if item.version == version:
            return item
    raise ApiError(404, "tool_version_not_found", "That tool version isn't in the catalog.")


@router.get("/tools/{tool_id}/grants", operation_id="getToolGrants", response_model=ToolGrants)
async def get_tool_grants(
    tool_id: str, request: Request, workspace_id: MemberWorkspace
) -> ToolGrants:
    await _versions(request, workspace_id, tool_id)
    async with request_pool(request).connection() as connection:
        experts, workflows = await tool_grants(connection, workspace_id, tool_id)
    return ToolGrants(
        schema_version=1,
        tool_id=tool_id,
        experts=[GrantedTo(id=i, name=n, version=v) for i, n, v in experts],
        workflows=[GrantedTo(id=i, name=n, version=v) for i, n, v in workflows],
    )
