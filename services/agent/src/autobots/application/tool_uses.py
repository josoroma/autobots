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
from autobots.application.sql import SqlConnection, all_rows, one
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolResult, ToolScope
from autobots.application.tool_gateway import Call, Refused, hold_lease
from autobots.contracts.runs import ToolUseCompleted, ToolUseList, ToolUseStarted, ToolUseView
from autobots.domain.tool_catalog import CostClass
from autobots.domain.tools import ToolOutcome
from autobots.persistence.rows import ToolUseRow

# Decision 0017 Q4: a root run tree may make this many metered tool calls, 40 by Decision 0034 L3.
METERED_TOOL_CALLS = 40
COMPLETE_TASK = "complete_task"


def input_digest(arguments: object) -> str:
    """A digest of the arguments as the model sent them, before parsing. The gateway hashes the
    parsed arguments, so the two agree only when parsing changes nothing."""
    try:
        encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        encoded = repr(arguments)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _scrub(value: object) -> object:
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
    connection: SqlConnection, run_id: UUID, name: str, arguments: object
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


def _public_arguments(resolved: Call | Refused) -> Mapping[str, Any] | None:
    """The parsed arguments after the tool's own redaction, or None when they didn't parse."""
    if resolved.tool is None or resolved.parsed is None:
        return None
    try:
        return resolved.tool.redact(resolved.parsed.model_dump(mode="json"))
    except Exception:  # noqa: BLE001 - arguments the tool can't redact stay out of the public record
        return None


async def begin_use(
    connection: SqlConnection,
    scope: ToolScope,
    name: str,
    arguments: object,
    resolved: Call | Refused,
) -> int | None:
    """Recorded before anything else happens, with a started event in the same transaction.

    `arguments` are as the model sent them, for the digest and the served task. `resolved` is the
    gateway's one resolution of the call, so the tool is looked up and its arguments parsed once.
    """
    version = scope.tools.get(name)
    tool = resolved.tool
    parsed = _public_arguments(resolved)
    shown = public_projection(parsed, tool.public_input_fields if tool else ())
    if tool is not None and tool.public_context is not None:
        shown |= await tool.public_context(ToolContext(connection, scope, None))
    plan_version, task_id = await served_task(connection, scope.run_id, name, arguments)
    try:
        async with connection.transaction():
            await hold_lease(connection, scope)
            await connection.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"tool_uses|{scope.run_id}",),
            )
            (use_id,) = await one(
                connection,
                "insert into app_private.tool_uses (run_id, root_run_id, workspace_id, "
                "sequence_in_run, tool_id, tool_version, tool_group, provider, cost_class, "
                "plan_version, task_id, input_digest, input_public, generation, instance_key) "
                "select %s, %s, %s, coalesce(max(sequence_in_run), 0) + 1, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s from app_private.tool_uses where run_id = %s "
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
                    json.dumps(shown),
                    scope.generation,
                    scope.instance,
                    scope.run_id,
                ),
            )
            if task_id is not None:
                # RN-05: a task starts with the first use that serves it, in database time, fenced
                # by this transaction's lease. A later use keeps the first start.
                await connection.execute(
                    "insert into app_private.plan_task_times (run_id, task_id) values (%s, %s) "
                    "on conflict (run_id, task_id) do nothing",
                    (scope.run_id, task_id),
                )
            await append_event(
                connection,
                scope.run_id,
                ToolUseStarted(
                    type="tool.use.started",
                    tool_use_id=use_id,
                    tool_id=name[:100],
                    tool_version=version,
                    group=tool.group.value if tool else None,
                    task_id=task_id,
                ),
            )
    except LeaseLost:
        return None
    return int(use_id)


async def admit_metered(
    connection: SqlConnection, scope: ToolScope, use_id: int, limit: int = METERED_TOOL_CALLS
) -> bool:
    """Counted per root run tree, under a lock, so concurrent children can't both take the last."""
    async with connection.transaction():
        await hold_lease(connection, scope)
        await connection.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"metered|{scope.budget_run_id}",),
        )
        (metered,) = await one(
            connection,
            "select count(*) from app_private.tool_uses where root_run_id = %s and metered",
            (scope.budget_run_id,),
        )
        if metered >= limit:
            return False
        await connection.execute(
            "update app_private.tool_uses set metered = true where id = %s", (use_id,)
        )
    return True


def is_metered(tool: ToolDefinition | None) -> bool:
    return tool is not None and tool.cost_class is CostClass.METERED_PROVIDER


async def complete_use(
    connection: SqlConnection,
    scope: ToolScope,
    use_id: int,
    name: str,
    resolved: Call | Refused,
    result: ToolResult,
    fenced: bool = True,
) -> None:
    """The outcome, by database time, with a completed event. A lost lease leaves it open.

    `resolved` is the same resolution `begin_use` recorded. `fenced=False` is for the one case
    where this worker released the lease itself: a call that now waits for a person. Only this
    generation's own open row can still be completed.
    """
    version = scope.tools.get(name)
    tool = resolved.tool
    output = result.output
    output_public = (
        public_projection(output, tool.public_output_fields) if tool and output else None
    )
    output_bytes = len(json.dumps(output).encode()) if output is not None else None
    try:
        async with connection.transaction():
            if fenced:
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
                ToolUseCompleted(
                    type="tool.use.completed",
                    tool_use_id=use_id,
                    tool_id=name[:100],
                    tool_version=version,
                    outcome=result.outcome.value,
                    code=result.code,
                    duration_ms=max(int(row[0]), 0),
                    operation_id=result.operation_id,
                ),
            )
    except LeaseLost:
        return


def _utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


def tool_use_view(row: ToolUseRow) -> ToolUseView:
    """An unknown stored outcome raises, instead of reaching a client."""
    return ToolUseView(
        id=row.id,
        run_id=row.run_id,
        sequence_in_run=row.sequence_in_run,
        tool_id=row.tool_id,
        tool_version=row.tool_version,
        group=row.tool_group,
        provider=row.provider,
        plan_version=row.plan_version,
        task_id=row.task_id,
        task_title=row.task_title,
        requested_at=row.requested_at.astimezone(UTC),
        finished_at=_utc(row.finished_at),
        duration_ms=max(int(row.duration_ms), 0) if row.duration_ms is not None else None,
        outcome=None if row.outcome is None else ToolOutcome(row.outcome).value,
        code=row.code,
        input_public=row.input_public or {},
        output_public=row.output_public,
        input_digest=row.input_digest,
        output_bytes=row.output_bytes,
        operation_id=row.operation_id,
        provider_units=float(row.provider_units) if row.provider_units is not None else None,
        instance_key=row.instance_key,
    )


async def list_tool_uses(
    connection: SqlConnection, workspace_id: UUID, run_id: UUID, after: int = 0, limit: int = 100
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
    rows = await all_rows(
        connection,
        ToolUseRow,
        "select u.id, u.run_id, u.sequence_in_run, u.tool_id, u.tool_version, u.tool_group, "
        "u.provider, u.plan_version, u.task_id, "
        "(select t ->> 'title' from app_private.plan_versions p "
        " cross join lateral jsonb_array_elements(p.tasks) t where p.run_id = u.run_id "
        " and p.version = u.plan_version and t ->> 'id' = u.task_id limit 1) as task_title, "
        "u.requested_at, u.finished_at, "
        "(extract(epoch from u.finished_at - u.requested_at) * 1000)::bigint as duration_ms, "
        "u.outcome, u.code, u.input_public, u.output_public, u.input_digest, u.output_bytes, "
        "u.operation_id, u.provider_units, u.instance_key "
        f"from app_private.tool_uses u where u.workspace_id = %s and u.id > %s and {column} = %s "
        "order by u.id limit %s",
        (workspace_id, after, run_id, limit + 1),
    )
    uses = [tool_use_view(item) for item in rows[:limit]]
    return ToolUseList(
        schema_version=1,
        run_id=run_id,
        uses=uses,
        next_cursor=uses[-1].id if len(rows) > limit else None,
    )
