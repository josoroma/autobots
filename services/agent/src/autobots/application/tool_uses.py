"""The durable tool-use record, PRD-Tool-Catalog TU-01 to TU-07 and Decision 0017.

Every dispatch the gateway sees is recorded, of every class and including denials, with the plan
task it served as its "why". Writes are fenced like other worker writes: a worker that lost its
lease records nothing. Content never lands here, only public fields, digests and sizes.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from autobots.application.runs import LeaseLost, append_event
from autobots.application.tool_gateway import (
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    ToolScope,
    hold_lease,
)
from autobots.contracts.runs import ToolUseList, ToolUseView
from autobots.domain.tool_catalog import CostClass

# Decision 0017 Q4: a root run tree may make this many metered tool calls.
METERED_TOOL_CALLS = 20
COMPLETE_TASK = "complete_task"


def input_digest(arguments: Any) -> str:
    """The same normalization as the gateway's argument hash, for anything a model sent."""
    try:
        encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        encoded = repr(arguments)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _scrub(value: Any) -> Any:
    """URLs lose their query string and fragment, which can carry tokens (TU-04)."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def public_projection(values: Mapping[str, Any] | None, fields: Iterable[str]) -> dict[str, Any]:
    """Only the top-level fields a definition lists, after its own redaction. Default: none."""
    if not isinstance(values, Mapping):
        return {}
    return {name: _scrub(values[name]) for name in fields if name in values}


async def served_task(
    connection: Any, run_id: UUID, name: str, arguments: Any
) -> tuple[int | None, str | None]:
    """The plan task a call served: `complete_task`'s own task, or else the first open task whose
    dependencies are done and that lists this tool. None when no task claims it, such as a plan's
    own proposal. Nothing a model wrote as free text is used."""
    cursor = await connection.execute(
        "select version, tasks from app_private.plan_versions where run_id = %s "
        "order by version desc limit 1",
        (run_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None, None
    version, tasks = row[0], row[1] or []
    ids = [task.get("id") for task in tasks if isinstance(task, Mapping)]
    if name == COMPLETE_TASK and isinstance(arguments, Mapping):
        claimed = arguments.get("task_id")
        return version, claimed if claimed in ids else None
    cursor = await connection.execute(
        "select task_id from app_private.plan_evidence where run_id = %s", (run_id,)
    )
    done = {item[0] for item in await cursor.fetchall()}
    for task in tasks:
        if not isinstance(task, Mapping) or task.get("id") in done:
            continue
        if all(dependency in done for dependency in task.get("depends_on", [])) and name in (
            task.get("tools") or []
        ):
            return version, str(task["id"])
    return version, None


async def begin_use(
    connection: Any, scope: ToolScope, registry: ToolRegistry, name: str, arguments: Any
) -> int | None:
    """Recorded before anything else happens, with a started event in the same transaction."""
    if connection is None:
        return None
    version = scope.tools.get(name)
    tool = registry.get(name, version) if version is not None else None
    parsed: Mapping[str, Any] | None = None
    if tool is not None:
        try:
            parsed = tool.redact(tool.input_model.model_validate(arguments).model_dump(mode="json"))
        except Exception:
            parsed = None
    plan_version, task_id = await served_task(connection, scope.run_id, name, arguments)
    try:
        async with connection.transaction():
            await hold_lease(connection, scope)
            await connection.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"tool_uses|{scope.run_id}",),
            )
            cursor = await connection.execute(
                "insert into app_private.tool_uses (run_id, root_run_id, workspace_id, "
                "sequence_in_run, tool_id, tool_version, tool_group, provider, cost_class, "
                "plan_version, task_id, input_digest, input_public, generation) "
                "select %s, %s, %s, coalesce(max(sequence_in_run), 0) + 1, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s from app_private.tool_uses where run_id = %s "
                "returning id",
                (
                    scope.run_id,
                    scope.budget_run_id,
                    scope.workspace_id,
                    name[:100],
                    version,
                    tool.group.value if tool else None,
                    tool.provider.value if tool else None,
                    tool.cost_class.value if tool else None,
                    plan_version,
                    task_id,
                    input_digest(arguments),
                    json.dumps(public_projection(parsed, tool.public_input_fields if tool else ())),
                    scope.generation,
                    scope.run_id,
                ),
            )
            use_id: int = (await cursor.fetchone())[0]
            await append_event(
                connection,
                scope.run_id,
                {
                    "type": "tool.use.started",
                    "tool_use_id": use_id,
                    "tool_id": name[:100],
                    "tool_version": version,
                    "group": tool.group.value if tool else None,
                    "task_id": task_id,
                },
            )
    except LeaseLost:
        return None
    return use_id


async def admit_metered(
    connection: Any, scope: ToolScope, use_id: int, limit: int = METERED_TOOL_CALLS
) -> bool:
    """Counted per root run tree, under a lock, so concurrent children can't both take the last."""
    async with connection.transaction():
        await hold_lease(connection, scope)
        await connection.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"metered|{scope.budget_run_id}",),
        )
        cursor = await connection.execute(
            "select count(*) from app_private.tool_uses where root_run_id = %s and metered",
            (scope.budget_run_id,),
        )
        if (await cursor.fetchone())[0] >= limit:
            return False
        await connection.execute(
            "update app_private.tool_uses set metered = true where id = %s", (use_id,)
        )
    return True


def is_metered(tool: ToolDefinition | None) -> bool:
    return tool is not None and tool.cost_class is CostClass.METERED_PROVIDER


async def complete_use(
    connection: Any,
    scope: ToolScope,
    registry: ToolRegistry,
    use_id: int,
    name: str,
    result: ToolResult,
) -> None:
    """The outcome, by database time, with a completed event. A lost lease leaves it open."""
    version = scope.tools.get(name)
    tool = registry.get(name, version) if version is not None else None
    output = result.output
    output_public = (
        public_projection(output, tool.public_output_fields) if tool and output else None
    )
    output_bytes = len(json.dumps(output).encode()) if output is not None else None
    try:
        async with connection.transaction():
            await hold_lease(connection, scope)
            cursor = await connection.execute(
                "update app_private.tool_uses set outcome = %s, code = %s, "
                "finished_at = clock_timestamp(), output_public = %s, output_bytes = %s, "
                "operation_id = %s where id = %s and generation = %s and outcome is null "
                "returning (extract(epoch from finished_at - requested_at) * 1000)::bigint",
                (
                    result.outcome.value,
                    result.code,
                    json.dumps(output_public) if output_public is not None else None,
                    output_bytes,
                    result.operation_id,
                    use_id,
                    scope.generation,
                ),
            )
            row = await cursor.fetchone()
            if row is None:
                return
            await append_event(
                connection,
                scope.run_id,
                {
                    "type": "tool.use.completed",
                    "tool_use_id": use_id,
                    "tool_id": name[:100],
                    "tool_version": version,
                    "outcome": result.outcome.value,
                    "code": result.code,
                    "duration_ms": max(int(row[0]), 0),
                    "operation_id": result.operation_id,
                },
            )
    except LeaseLost:
        return


def _utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


async def list_tool_uses(
    connection: Any, workspace_id: UUID, run_id: UUID, after: int = 0, limit: int = 100
) -> ToolUseList | None:
    """A run's uses, or a root run's whole tree, in order, with the plan task's title (TU-07)."""
    cursor = await connection.execute(
        "select parent_run_id from public.runs where id = %s and workspace_id = %s",
        (run_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    column = "u.root_run_id" if row[0] is None else "u.run_id"
    cursor = await connection.execute(
        "select u.id, u.run_id, u.sequence_in_run, u.tool_id, u.tool_version, u.tool_group, "
        "u.provider, u.plan_version, u.task_id, "
        "(select t ->> 'title' from app_private.plan_versions p "
        " cross join lateral jsonb_array_elements(p.tasks) t where p.run_id = u.run_id "
        " and p.version = u.plan_version and t ->> 'id' = u.task_id limit 1), "
        "u.requested_at, u.finished_at, "
        "(extract(epoch from u.finished_at - u.requested_at) * 1000)::bigint, "
        "u.outcome, u.code, u.input_public, u.output_public, u.input_digest, u.output_bytes, "
        "u.operation_id, u.provider_units "
        f"from app_private.tool_uses u where u.workspace_id = %s and u.id > %s and {column} = %s "
        "order by u.id limit %s",
        (workspace_id, after, run_id, limit + 1),
    )
    rows = await cursor.fetchall()
    uses = [
        ToolUseView(
            id=item[0],
            run_id=item[1],
            sequence_in_run=item[2],
            tool_id=item[3],
            tool_version=item[4],
            group=item[5],
            provider=item[6],
            plan_version=item[7],
            task_id=item[8],
            task_title=item[9],
            requested_at=item[10].astimezone(UTC),
            finished_at=_utc(item[11]),
            duration_ms=max(int(item[12]), 0) if item[12] is not None else None,
            outcome=item[13],
            code=item[14],
            input_public=item[15] or {},
            output_public=item[16],
            input_digest=item[17],
            output_bytes=item[18],
            operation_id=item[19],
            provider_units=float(item[20]) if item[20] is not None else None,
        )
        for item in rows[:limit]
    ]
    return ToolUseList(
        schema_version=1,
        run_id=run_id,
        uses=uses,
        next_cursor=uses[-1].id if len(rows) > limit else None,
    )
