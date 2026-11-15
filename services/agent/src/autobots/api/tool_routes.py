"""Tool discovery, PRD-Tool-Catalog TC-05. Read-only, member-readable, and never a secret."""

from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import MemberWorkspace, catalog_of, process_environment
from autobots.api.errors import ApiError
from autobots.api.resources import app_resources, request_pool
from autobots.api.security import require_internal
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
    ToolVersions,
)

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
    workspace_id: MemberWorkspace,
    group: ToolGroupName | None = None,
    availability: AvailabilityName | None = None,
    provider: ToolProviderName | None = None,
) -> ToolCatalog:
    keys = await _keys(request, workspace_id)
    return catalog_of(request).catalog(
        keys, group=group, availability=availability, provider=provider
    )


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
