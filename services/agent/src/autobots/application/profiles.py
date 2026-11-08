"""Display names and the session's workspaces (PRD-Studio ID-01, ID-02).

Reads and writes go through the runtime role, so each statement is scoped to the verified user here,
the same boundary RLS enforces for the authenticated role.
"""

from typing import Any
from uuid import UUID

MAX_DISPLAY_NAME = 60
FALLBACK_NAME = "Member"


class DisplayNameInvalid(ValueError):
    """A display name that is empty or longer than 60 characters after trimming."""


def normalize_display_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= MAX_DISPLAY_NAME:
        raise DisplayNameInvalid("display_name_invalid")
    return name


def fallback_name(email: str | None) -> str:
    """The part of the email before `@`, bounded like a saved name; "Member" when there is none."""
    local = (email or "").partition("@")[0].strip()[:MAX_DISPLAY_NAME].strip()
    return local or FALLBACK_NAME


async def saved_name(pool: Any, user_id: UUID) -> str | None:
    if pool is None:
        return None
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "select display_name from public.user_profiles where user_id = %s", (user_id,)
        )
        row = await cursor.fetchone()
        return str(row[0]) if row else None


async def save_name(pool: Any, user_id: UUID, name: str) -> str:
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "insert into public.user_profiles (user_id, display_name) values (%s, %s) "
            "on conflict (user_id) do update set display_name = excluded.display_name, "
            "updated_at = now() returning display_name",
            (user_id, name),
        )
        row = await cursor.fetchone()
        return str(row[0])


async def workspaces_with_roles(pool: Any, user_id: UUID) -> list[tuple[UUID, str, str, str]]:
    if pool is None:
        return []
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "select w.id, w.name, m.role, w.timezone from public.workspace_members m "
            "join public.workspaces w on w.id = m.workspace_id "
            "where m.user_id = %s order by w.id",
            (user_id,),
        )
        return [(row[0], str(row[1]), str(row[2]), str(row[3])) for row in await cursor.fetchall()]
