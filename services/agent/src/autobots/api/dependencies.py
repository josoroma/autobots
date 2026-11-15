"""Request plumbing every router shares: whom a session acts for, the owner gate, the
installation's readiness gate, provider and Keys & vars settings, the OpenRouter key check and what
the process read at start (refactor plan R-55, PAPI-06, PAPI-07 and XMOD-11).

Route modules import this, `api/resources.py` and application code, never each other. A workspace is
resolved in three deliberate ways, all here: a feature route's (`current_workspace`), Readiness's
(`readiness_workspace`) and Local Operations' (`operations_workspace`). `require_workspace_member`
checks a workspace the path names.
"""

import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.membership import MembershipStore
from autobots.api.pool import Pool
from autobots.api.resources import app_resources
from autobots.api.security import current_user
from autobots.application.operations import Condition, ProbeTimes
from autobots.application.provider_settings import (
    ProviderContext,
    ProviderSettings,
    WorkspaceReadiness,
)
from autobots.application.readiness import first_blocking, installation_conditions
from autobots.application.sql import SqlConnection
from autobots.application.tool_catalog import Catalog
from autobots.application.tool_key_settings import ToolKeySettings

CurrentUser = Annotated[UUID, Depends(current_user)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
WORKSPACE_FORBIDDEN = "This workspace is not available."


def membership(request: Request) -> MembershipStore:
    return app_resources(request).membership


# The session's workspace


async def resolve_workspace(store: MembershipStore, user_id: UUID, chosen: UUID | None) -> UUID:
    """The chosen workspace, verified, or the user's only one. Never trusted from the browser."""
    workspaces = await store.workspaces_for(user_id)
    if chosen is not None:
        if chosen not in workspaces:
            raise ApiError(403, "forbidden", WORKSPACE_FORBIDDEN)
        return chosen
    if len(workspaces) != 1:
        raise ApiError(403, "workspace_required", "Choose a workspace.")
    workspace: UUID = workspaces[0]
    return workspace


async def current_workspace(
    request: Request,
    user_id: CurrentUser,
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> UUID:
    """A feature route's workspace, by `resolve_workspace`."""
    return await resolve_workspace(membership(request), user_id, x_autobots_workspace)


async def is_owner(request: Request, user_id: UUID, workspace_id: UUID) -> bool:
    """The one owner test, which every owner gate, check and label asks."""
    return await membership(request).role_in(user_id, workspace_id) == "owner"


async def require_owner(
    request: Request,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    user_id: CurrentUser,
) -> UUID:
    if not await is_owner(request, user_id, workspace_id):
        raise ApiError(403, "owner_required", "Only the workspace owner can change this.")
    return workspace_id


MemberWorkspace = Annotated[UUID, Depends(current_workspace)]
OwnerWorkspace = Annotated[UUID, Depends(require_owner)]


async def readiness_workspace(request: Request, user_id: UUID, chosen: UUID | None) -> UUID:
    """PRD-Studio SH-04 and HM-05: the chosen workspace, verified, or else the session's first, as
    the shell's footer shows it. A user with no workspace is refused. Unlike `current_workspace`,
    it never asks a member of several workspaces to choose."""
    workspaces = await membership(request).workspaces_for(user_id)
    if chosen is not None and chosen not in workspaces:
        raise ApiError(403, "forbidden", WORKSPACE_FORBIDDEN)
    if not workspaces:
        raise ApiError(403, "forbidden", WORKSPACE_FORBIDDEN)
    return chosen or sorted(workspaces)[0]


async def operations_workspace(
    request: Request, user_id: UUID, chosen: UUID | None, *, database_up: bool
) -> UUID | None:
    """Local Operations' workspace: the owner's, by `resolve_workspace`, once the database answers.
    With it down there is none, since Operations has to answer then, to any signed-in user."""
    if not database_up:
        return None
    workspace_id = await resolve_workspace(membership(request), user_id, chosen)
    if not await is_owner(request, user_id, workspace_id):
        raise ApiError(403, "owner_required", "Only the workspace owner can see this.")
    return workspace_id


async def require_workspace_member(
    workspace_id: UUID,
    request: Request,
    user_id: CurrentUser,
) -> UUID:
    """A workspace the path names, which the session's user belongs to."""
    if not await membership(request).is_member(user_id, workspace_id):
        raise ApiError(403, "forbidden", WORKSPACE_FORBIDDEN)
    return workspace_id


# What the process read at start, and the readiness gate


def process_environment(request: Request) -> Mapping[str, str]:
    """The process environment as the entry point read it at start, which orders keys for admission
    and availability alike (Decisions 0024 K1 and 0025 V3, PAPI-10). An app built without a provider
    context, as some tests are, has only the live one."""
    context = app_resources(request).provider_context
    return os.environ if context is None else context.process_environment


def catalog_of(request: Request) -> Catalog:
    """The catalog the app was built with, over the registry the worker runs (TC-01). The routes
    that read or admit tools take it from here, never build one (XMOD-01)."""
    return app_resources(request).tools


def probe_times(request: Request) -> ProbeTimes:
    """This process's readiness probe window."""
    return app_resources(request).probe_times


async def installation_conditions_of(request: Request) -> list[Condition]:
    """Database, schema, hold, adapter, Storage and disk, by the settings read at start."""
    resources = app_resources(request)
    return await installation_conditions(
        resources.pool, resources.object_store, resources.settings.readiness, resources.probe_times
    )


async def require_ready(request: Request) -> None:
    """Admission stops when required persistence is unhealthy (LM-07), before any job can exist.
    A due routine waits on the same gate in the worker (Decision 0023 E2)."""
    if first_blocking(await installation_conditions_of(request)) is not None:
        raise ApiError(503, "not_ready", "Local services aren't ready, so nothing was started.")


# Provider and Keys & vars settings, and the key check


def _provider_resources(request: Request, unavailable: str) -> tuple[Pool, ProviderContext]:
    resources = app_resources(request)
    pool, context = resources.pool, resources.provider_context
    if pool is None or context is None:
        raise ApiError(503, "service_unavailable", unavailable)
    return pool, context


@dataclass(frozen=True)
class SettingsSource[T]:
    """Settings a handler opens on a pooled connection of its own, once the workspace and owner
    checks, which may borrow one too, have answered. So a request holds one at a time (PAPI-11)."""

    pool: Pool
    build: Callable[[SqlConnection], T]

    @asynccontextmanager
    async def opened(self) -> AsyncIterator[T]:
        async with self.pool.connection() as connection:
            yield self.build(connection)


async def provider_settings(request: Request) -> SettingsSource[ProviderSettings]:
    """Provider settings, or 503 before the workspace is checked when there are none to open.
    Model-backed work checks its key through `model_key_check` instead."""
    pool, context = _provider_resources(request, "Provider settings are unavailable.")
    return SettingsSource(pool, lambda connection: ProviderSettings(connection, context))


async def keys_and_vars_settings(request: Request) -> SettingsSource[ToolKeySettings]:
    """Keys & vars, or 503 before the workspace is checked, as `provider_settings`."""
    pool, context = _provider_resources(request, "Keys & vars settings are unavailable.")
    # Decisions 0024 K1 and 0025 V3 order the keys, and the process environment in that order is
    # the one the entry point read at start, as the OpenRouter key's is.
    return SettingsSource(
        pool,
        lambda connection: ToolKeySettings(
            connection, context.master_key_file, context.process_environment
        ),
    )


async def model_key_check(request: Request) -> WorkspaceReadiness:
    """`ProviderSettings.run_intent` for a workspace, each answer read on a pooled connection held
    only while it answers. A handler checks the key between its own connections, never inside one,
    so a request holds one connection at a time (PAPI-11)."""
    pool, context = _provider_resources(request, "Provider settings are unavailable.")

    async def run_intent(workspace_id: UUID) -> str:
        async with pool.connection() as connection:
            return await ProviderSettings(connection, context).run_intent(workspace_id)

    return run_intent


ProviderSettingsDep = Annotated[SettingsSource[ProviderSettings], Depends(provider_settings)]
KeysAndVarsDep = Annotated[SettingsSource[ToolKeySettings], Depends(keys_and_vars_settings)]
ModelKeyCheck = Annotated[WorkspaceReadiness, Depends(model_key_check)]
