"""Workspace membership from the database, through the restricted runtime role."""

from typing import Any
from uuid import UUID


class PostgresMembership:
    """Reads the pool from application state, so nothing connects before the lifespan starts it."""

    def __init__(self, state: Any) -> None:
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
            return row[0] if row else None

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
            return [row[0] for row in await cursor.fetchall()]
