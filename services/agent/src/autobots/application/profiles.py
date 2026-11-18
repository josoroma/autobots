"""Display names and the session's workspaces (PRD-Studio ID-01, ID-02).

Reads and writes go through the runtime role, so each statement is scoped to the verified user here,
the same boundary RLS enforces for the authenticated role.
"""

from typing import Literal
from uuid import UUID

from autobots.application.sql import SqlPool, all_rows, one, stored
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.persistence.rows import SessionWorkspaceRow

MAX_DISPLAY_NAME = 60
FALLBACK_NAME = "Member"


# A member's role, which public.workspace_members' check constraint holds to these two.
WorkspaceRole = Literal["owner", "member"]
_ROLES: tuple[WorkspaceRole, ...] = ("owner", "member")


class DisplayNameInvalid(FixedRefusal):
    """A display name that is empty or longer than 60 characters after trimming (PRD-Studio
    ID-01). Nothing is saved."""

    code = "display_name_invalid"
    kind = RefusalKind.INVALID


def normalize_display_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= MAX_DISPLAY_NAME:
        raise DisplayNameInvalid
    return name


def fallback_name(email: str | None) -> str:
    """The part of the email before `@`, bounded like a saved name; "Member" when there is none."""
    local = (email or "").partition("@")[0].strip()[:MAX_DISPLAY_NAME].strip()
    return local or FALLBACK_NAME


async def saved_name(pool: SqlPool | None, user_id: UUID) -> str | None:
    if pool is None:
        return None
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "select display_name from public.user_profiles where user_id = %s", (user_id,)
        )
        row = await cursor.fetchone()
        return str(row[0]) if row else None


async def save_name(pool: SqlPool, user_id: UUID, name: str) -> str:
    async with pool.connection() as connection:
        (saved,) = await one(
            connection,
            "insert into public.user_profiles (user_id, display_name) values (%s, %s) "
            "on conflict (user_id) do update set display_name = excluded.display_name, "
            "updated_at = now() returning display_name",
            (user_id, name),
        )
        return str(saved)


async def workspaces_with_roles(
    pool: SqlPool | None, user_id: UUID
) -> list[tuple[UUID, str, WorkspaceRole, str]]:
    """Each workspace's id, name, the user's role and its timezone. An unknown stored role raises,
    instead of reaching a client."""
    if pool is None:
        return []
    async with pool.connection() as connection:
        rows = await all_rows(
            connection,
            SessionWorkspaceRow,
            "select w.id, w.name, m.role, w.timezone from public.workspace_members m "
            "join public.workspaces w on w.id = m.workspace_id "
            "where m.user_id = %s order by w.id",
            (user_id,),
        )
    return [(row.id, str(row.name), stored(_ROLES, row.role), str(row.timezone)) for row in rows]
