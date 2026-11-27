"""A workspace's Model source, OpenRouter or Local, and switching it (Decision 0041 A1, A7, A8;
US-23.3).

The source is stored on the workspace's model policy row, with the Local default profile. The
OpenRouter default and role overrides on that row are left alone while Local is on, so switching
back restores them. A switch takes the row's lock and its expected version, as a policy save does.

A switch to Local is refused while no offered local profile covers `executor`, and also
`researcher` while the latest version of any of the workspace's Experts grants `browse_goal` (A7).
One local profile answers every role on Local (A8), so a profile that is offered covers both.
"""

from collections.abc import Iterable
from uuid import UUID

from autobots.application.local_offering import LOCAL_NAMES, offered_locally
from autobots.application.model_policy import PolicyChanged, StoredPolicy, read_model_policy
from autobots.application.provider_settings import read_route_qualifications
from autobots.application.sql import SqlConnection
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.models import (
    PROFILES,
    ModelProfileId,
    ModelRole,
    ModelSource,
    ProfileNotOffered,
)

BROWSE_TOOL = "browse_goal"


class SourceRolesUncovered(FixedRefusal):
    """Local can't be chosen yet: no offered local profile covers these roles. Nothing changes."""

    code = "model_source_roles_uncovered"
    kind = RefusalKind.CONFLICT

    def __init__(self, roles: Iterable[ModelRole]) -> None:
        self.roles = tuple(roles)
        names = " and ".join(role.value for role in self.roles)
        # Built from role names only, server values, so it is safe to show.
        self.reason = f"Local can't be chosen yet: no offered local profile covers {names}."
        super().__init__(self.reason)


async def offered_local_profiles(connection: SqlConnection) -> frozenset[ModelProfileId]:
    """The local profiles the Local source offers, from their stored qualifications (A7)."""
    return offered_locally(await read_route_qualifications(connection))


async def grants_browsing(connection: SqlConnection, workspace_id: UUID) -> bool:
    """Whether the latest version of any of the workspace's Experts grants `browse_goal`."""
    cursor = await connection.execute(
        "select exists (select 1 from public.experts e join public.expert_versions v "
        "on v.expert_id = e.id and v.version = e.latest_version "
        "where e.workspace_id = %s and v.config -> 'tools' ? %s)",
        (workspace_id, BROWSE_TOOL),
    )
    row = await cursor.fetchone()
    return bool(row and row[0])


def roles_needed(browsing: bool) -> tuple[ModelRole, ...]:
    return (ModelRole.EXECUTOR, ModelRole.RESEARCHER) if browsing else (ModelRole.EXECUTOR,)


def local_default(
    requested: ModelProfileId | None, saved: str | None, offered: frozenset[ModelProfileId]
) -> ModelProfileId | None:
    """The Local default a switch keeps: the one asked for, which must be offered, else the saved
    one while it is still offered, else the first offered in the registry's order."""
    if requested is not None:
        if requested not in offered:
            raise ProfileNotOffered(not_offered_locally(requested))
        return requested
    if saved is not None and ModelProfileId(saved) in offered:
        return ModelProfileId(saved)
    return next((profile for profile in PROFILES if profile in offered), None)


def not_offered_locally(profile: ModelProfileId) -> str:
    if PROFILES[profile].is_local:
        name = LOCAL_NAMES.get(profile, PROFILES[profile].wire_id)
        return f"{name} isn't offered on the Local source until its route qualifies."
    return "On the Local source, only offered local profiles answer model calls."


async def switch_model_source(
    connection: SqlConnection,
    workspace_id: UUID,
    *,
    expected_version: int,
    source: ModelSource,
    local_profile: ModelProfileId | None,
) -> StoredPolicy:
    """Raises PolicyChanged, SourceRolesUncovered or ProfileNotOffered, with nothing written."""
    async with connection.transaction():
        cursor = await connection.execute(
            "select version, local_profile from app_private.model_policies "
            "where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current, saved_local = (row[0], row[1]) if row else (0, None)
        if current != expected_version:
            raise PolicyChanged(f"saved version {current}, expected {expected_version}")
        chosen: str | None = saved_local
        if source is ModelSource.LOCAL:
            offered = await offered_local_profiles(connection)
            picked = local_default(local_profile, saved_local, offered)
            if picked is None:
                raise SourceRolesUncovered(
                    roles_needed(await grants_browsing(connection, workspace_id))
                )
            chosen = picked.value
        await connection.execute(
            "insert into app_private.model_policies "
            "(workspace_id, version, role_overrides, model_source, local_profile) "
            "values (%s, %s, '{}', %s, %s) "
            "on conflict (workspace_id) do update set version = excluded.version, "
            "model_source = excluded.model_source, local_profile = excluded.local_profile",
            (workspace_id, current + 1, source.value, chosen),
        )
    return await read_model_policy(connection, workspace_id)


async def save_local_default(
    connection: SqlConnection,
    workspace_id: UUID,
    *,
    expected_version: int,
    local_profile: ModelProfileId,
) -> StoredPolicy:
    """The model policy's default, saved on Local: the Local default only. OpenRouter's saved
    choices are left as they are. Raises PolicyChanged or ProfileNotOffered."""
    if local_profile not in await offered_local_profiles(connection):
        raise ProfileNotOffered(not_offered_locally(local_profile))
    async with connection.transaction():
        cursor = await connection.execute(
            "select version from app_private.model_policies where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        if current != expected_version:
            raise PolicyChanged(f"saved version {current}, expected {expected_version}")
        await connection.execute(
            "update app_private.model_policies set version = %s, local_profile = %s "
            "where workspace_id = %s",
            (current + 1, local_profile.value, workspace_id),
        )
    return await read_model_policy(connection, workspace_id)
