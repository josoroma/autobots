"""The workspace's tool switches, Decision 0033 W1 to W4 and PRD-Tool-Catalog TW-01 to TW-03.

Kept in `app_private.tool_switches` (migration 64): no row means on, and every change carries the
switch's expected version, like Keys & vars. Availability reads them through the workspace's view
(`tool_keys.key_sources`), and the gateway reads them again before each call.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from autobots.application.provider_settings import StaleVersion
from autobots.application.sql import SqlConnection, all_rows, one, optional_row
from autobots.domain.tool_switches import Switch, Switches, SwitchKind, switchable_tool


@dataclass(frozen=True)
class _Row:
    kind: SwitchKind
    target: str
    enabled: bool
    version: int


@dataclass(frozen=True)
class _Version:
    version: int


class SwitchNotFound(LookupError):
    """A tool that isn't switchable, or a group that holds no switchable tool."""

    code = "switch_not_found"


async def load(connection: SqlConnection, workspace_id: UUID) -> Switches:
    rows = await all_rows(
        connection,
        _Row,
        "select kind, target, enabled, version from app_private.tool_switches "
        "where workspace_id = %s",
        (workspace_id,),
    )
    return {(row.kind, row.target): Switch(row.enabled, row.version) for row in rows}


def check_target(kind: SwitchKind, target: str, groups: Iterable[str]) -> None:
    """Refuses a target the catalog can't switch, before anything is read or written."""
    if kind == "tool" and not switchable_tool(target):
        raise SwitchNotFound(target)
    if kind == "group" and target not in set(groups):
        raise SwitchNotFound(target)


async def change(
    connection: SqlConnection,
    workspace_id: UUID,
    kind: SwitchKind,
    target: str,
    enabled: bool,
    expected: int,
) -> Switch:
    """Sets one switch at its expected version and returns it. A stale version changes nothing."""
    async with connection.transaction():
        found = await optional_row(
            connection,
            _Version,
            "select version from app_private.tool_switches "
            "where workspace_id = %s and kind = %s and target = %s for update",
            (workspace_id, kind, target),
        )
        current = found.version if found is not None else 0
        if current != expected:
            raise StaleVersion("the switch changed; reload the tools")
        if found is None:
            await connection.execute(
                "insert into app_private.tool_switches (workspace_id, kind, target, enabled) "
                "values (%s, %s, %s, %s)",
                (workspace_id, kind, target, enabled),
            )
        else:
            await connection.execute(
                "update app_private.tool_switches set enabled = %s, version = version + 1, "
                "updated_at = now() where workspace_id = %s and kind = %s and target = %s",
                (enabled, workspace_id, kind, target),
            )
    return Switch(enabled, current + 1)


async def turned_off(
    connection: SqlConnection, workspace_id: UUID, tool_id: str, group: str
) -> bool:
    """A fresh read for one call: whether this tool, or its group, is off now (W2)."""
    if not switchable_tool(tool_id):
        return False
    (count,) = await one(
        connection,
        "select count(*) from app_private.tool_switches where workspace_id = %s and not enabled "
        "and ((kind = 'tool' and target = %s) or (kind = 'group' and target = %s))",
        (workspace_id, tool_id, group),
    )
    return int(count) > 0
