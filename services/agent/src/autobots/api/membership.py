"""Workspace membership: what the routes ask of it, the deny-all default, and the database's answer
through the restricted runtime role."""

from typing import Protocol
from uuid import UUID

from autobots.api.pool import Pool


class MembershipStore(Protocol):
    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool: ...
    async def workspaces_for(self, user_id: UUID) -> list[UUID]: ...
    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None: ...


class DenyAllMembership:
    """The default until real membership is connected: no identity reaches any workspace."""

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return False

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return None


class PoolHolder(Protocol):
    """The app's resources (api/resources.py), which hold the pool once the lifespan opens it."""

    @property
    def pool(self) -> Pool | None: ...


class PostgresMembership:
    """Reads the pool from the app's resources, so nothing connects before the lifespan opens it."""

    def __init__(self, state: PoolHolder) -> None:
        self._state = state

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        pool = self._state.pool
        if pool is None:
            return False
        async with pool.connection() as connection:
            cursor = await connection.execute(
                "select 1 from public.workspace_members where user_id = %s and workspace_id = %s",
                (user_id, workspace_id),
            )
            return await cursor.fetchone() is not None

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        pool = self._state.pool
        if pool is None:
            return None
        async with pool.connection() as connection:
            cursor = await connection.execute(
                "select role from public.workspace_members "
                "where user_id = %s and workspace_id = %s",
                (user_id, workspace_id),
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        pool = self._state.pool
        if pool is None:
            return []
        async with pool.connection() as connection:
            cursor = await connection.execute(
                "select workspace_id from public.workspace_members "
                "where user_id = %s order by workspace_id",
                (user_id,),
            )
            found: list[UUID] = [row[0] for row in await cursor.fetchall()]
            return found
