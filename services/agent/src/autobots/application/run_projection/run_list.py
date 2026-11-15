"""The run list: status groups with server counts, filters and a keyset cursor (PRD-Studio RN-01 and
RN-02), read from one snapshot (PRUN-11)."""

import base64
from datetime import datetime
from uuid import UUID

from autobots.application.model_admission import LEDGER_PARAMS, spend_columns, unreported_column
from autobots.application.run_projection.shown import public_text
from autobots.application.sql import SqlConnection, all_rows, required_row, snapshot, stored
from autobots.contracts.run_workspace import (
    RUN_LABEL_KINDS,
    RunGroupCounts,
    RunList,
    RunListGroup,
    RunListItem,
)
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.runs import IN_PROGRESS, NEEDS_YOU, TERMINAL, RunStatus
from autobots.persistence.rows import RunGroupCountRow, RunListRow

RUN_LIST_SIZE = 100
# Plain values, since these go to SQL as parameters.
GROUPS: dict[str, tuple[str, ...]] = {
    "active": tuple(sorted(status.value for status in IN_PROGRESS)),
    "needs_you": tuple(sorted(status.value for status in NEEDS_YOU)),
    "finished": tuple(sorted(status.value for status in TERMINAL)),
}
MAX_QUERY = 200


class InvalidCursor(FixedRefusal, ValueError):
    """A cursor this API didn't issue."""

    code = "invalid_cursor"
    kind = RefusalKind.INVALID


def encode_cursor(created_at: datetime, run_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{run_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, identifier = raw.partition("|")
        moment = datetime.fromisoformat(stamp)
        if moment.tzinfo is None:
            raise ValueError("naive")
        return moment, UUID(identifier)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidCursor("invalid_cursor") from error


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# One row per run (PRD-Studio RN-01). The joins only label a run; they never widen the workspace.
LIST_FROM = (
    "from public.runs r "
    "left join public.experts e on e.id = r.expert_id and e.workspace_id = r.workspace_id "
    "left join public.sessions s on s.id = r.session_id and s.workspace_id = r.workspace_id "
    "left join public.workflow_executions x on x.run_id = r.id and x.workspace_id = r.workspace_id "
    "left join public.workflows w on w.id = x.workflow_id and w.workspace_id = r.workspace_id "
    "where r.workspace_id = %(workspace)s "
    "and (%(like)s::text is null or r.goal_summary ilike %(like)s or e.name ilike %(like)s "
    "or w.name ilike %(like)s) "
    "and (%(profile)s::text is null or exists (select 1 from "
    "jsonb_each_text(coalesce(r.policy_snapshot -> 'bindings', '{}'::jsonb)) b "
    "where b.value = %(profile)s)) "
)
LIST_SELECT = (
    "select r.id, r.parent_run_id, r.status, r.goal_summary, r.created_at, r.updated_at, "
    "case when x.id is not null then 'workflow' when s.kind = 'coordinator' then 'session' "
    "when e.id is not null then 'expert' else 'goal' end as label_kind, "
    "case when x.id is not null then w.name || ', version ' || x.workflow_version "
    "when s.kind = 'coordinator' then 'Coordinator session' else e.name end as label, "
    "(select u.stop_reason from app_private.run_usage u where u.run_id = r.id) as stop_reason, "
    "coalesce((select jsonb_array_length(p.tasks) from app_private.plan_versions p "
    "where p.run_id = r.id order by p.version desc limit 1), 0) as tasks_total, "
    "(select count(*) from app_private.plan_evidence v where v.run_id = r.id and v.task_id in "
    "(select t ->> 'id' from app_private.plan_versions p, jsonb_array_elements(p.tasks) t "
    "where p.run_id = r.id and p.version = (select max(version) from app_private.plan_versions q "
    "where q.run_id = r.id))) as tasks_complete, "
    "array(select distinct b.value from "
    "jsonb_each_text(coalesce(r.policy_snapshot -> 'bindings', '{}'::jsonb)) b order by 1) "
    "as profiles, "
    f"{spend_columns('r')}, {unreported_column('r')} as unreported, "
    "r.limit_micro_usd "
)


def run_list_item(row: RunListRow) -> RunListItem:
    """An unknown stored status or label raises, instead of reaching a client."""
    return RunListItem(
        id=row.id,
        parent_run_id=row.parent_run_id,
        status=RunStatus(row.status),
        goal_summary=public_text(row.goal_summary),
        created_at=row.created_at,
        updated_at=row.updated_at,
        label_kind=stored(RUN_LABEL_KINDS, row.label_kind),
        label=public_text(row.label) if row.label else None,
        stop_reason=row.stop_reason,
        tasks_complete=int(row.tasks_complete),
        tasks_total=int(row.tasks_total),
        profiles=list(row.profiles),
        charged_micro_usd=int(row.charged_micro_usd),
        reserved_micro_usd=int(row.reserved_micro_usd),
        unreported=bool(row.unreported),
        limit_micro_usd=int(row.limit_micro_usd),
    )


def group_counts(row: RunGroupCountRow) -> RunGroupCounts:
    return RunGroupCounts(
        all=int(row.total),
        active=int(row.active),
        needs_you=int(row.needs_you),
        finished=int(row.finished),
    )


async def read_run_list(
    connection: SqlConnection,
    workspace_id: UUID,
    limit: int = RUN_LIST_SIZE,
    *,
    group: RunListGroup = "all",
    query: str | None = None,
    profile: str | None = None,
    cursor: str | None = None,
) -> RunList:
    """Only this workspace's, newest first, with its counts from the page's snapshot. A read, so
    it starts nothing and needs no key."""
    text = (query or "").strip()[:MAX_QUERY]
    params: dict[str, object] = {
        "workspace": workspace_id,
        "like": _like(text) if text else None,
        "profile": profile,
    }
    async with snapshot(connection):
        totals = await required_row(
            connection,
            RunGroupCountRow,
            "select count(*) as total, "
            "count(*) filter (where r.status = any(%(active)s)) as active, "
            "count(*) filter (where r.status = any(%(needs)s)) as needs_you, "
            "count(*) filter (where r.status = any(%(finished)s)) as finished " + LIST_FROM,
            {
                **params,
                "active": list(GROUPS["active"]),
                "needs": list(GROUPS["needs_you"]),
                "finished": list(GROUPS["finished"]),
            },
        )
        where = ""
        page_params = {**params, **LEDGER_PARAMS, "limit": limit + 1}
        if group != "all":
            where += "and r.status = any(%(statuses)s) "
            page_params["statuses"] = list(GROUPS[group])
        if cursor is not None:
            moment, after = decode_cursor(cursor)
            where += "and (r.created_at, r.id) < (%(moment)s, %(after)s) "
            page_params["moment"], page_params["after"] = moment, after
        rows = await all_rows(
            connection,
            RunListRow,
            LIST_SELECT
            + LIST_FROM
            + where
            + "order by r.created_at desc, r.id desc limit %(limit)s",
            page_params,
        )
    counts = group_counts(totals)
    shown = rows[:limit]
    return RunList(
        schema_version=1,
        runs=[run_list_item(row) for row in shown],
        has_more=len(rows) > limit,
        next_cursor=encode_cursor(shown[-1].created_at, shown[-1].id)
        if len(rows) > limit
        else None,
        total=getattr(counts, group),
        counts=counts,
    )
