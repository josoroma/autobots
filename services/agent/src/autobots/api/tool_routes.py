"""Tool discovery, PRD-Tool-Catalog TC-05. Read-only, member-readable, and never a secret."""

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from autobots.api.errors import ApiError
from autobots.api.security import require_internal
from autobots.api.settings_routes import current_workspace
from autobots.application.tool_catalog import all_descriptors, tool_catalog
from autobots.contracts.tools import (
    AvailabilityName,
    ToolCatalog,
    ToolDescriptor,
    ToolGroupName,
    ToolProviderName,
    ToolVersions,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Member = Annotated[UUID, Depends(current_workspace)]


@router.get("/tools", operation_id="listTools", response_model=ToolCatalog)
async def list_tools(
    _: Member,
    group: ToolGroupName | None = None,
    availability: AvailabilityName | None = None,
    provider: ToolProviderName | None = None,
) -> ToolCatalog:
    return tool_catalog(os.environ, group=group, availability=availability, provider=provider)


def _versions(tool_id: str) -> list[ToolDescriptor]:
    found = [item for item in all_descriptors(os.environ) if item.tool_id == tool_id]
    if not found:
        raise ApiError(404, "tool_not_found", "That tool isn't in the catalog.")
    return found


@router.get("/tools/{tool_id}", operation_id="getToolVersions", response_model=ToolVersions)
async def get_tool(tool_id: str, _: Member) -> ToolVersions:
    return ToolVersions(tool_id=tool_id, versions=_versions(tool_id))


@router.get(
    "/tools/{tool_id}/versions/{version}",
    operation_id="getToolVersion",
    response_model=ToolDescriptor,
)
async def get_tool_version(tool_id: str, version: int, _: Member) -> ToolDescriptor:
    for item in _versions(tool_id):
        if item.version == version:
            return item
    raise ApiError(404, "tool_version_not_found", "That tool version isn't in the catalog.")
