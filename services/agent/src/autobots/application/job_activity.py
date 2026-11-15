"""A workspace's recent job activity, for Local Operations: counts and routine names, never content.

The 24-hour jobs chart (PRD-Studio OP-03, Decision 0022 D14) and the routine occurrences that didn't
run at their time.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from autobots.application.sql import SqlConnection, all_rows, stored
from autobots.contracts.operations import DELAYED_STATUSES, DelayedOccurrence
from autobots.domain.runs import NEEDS_YOU, TERMINAL, RunStatus
from autobots.persistence.rows import DelayedOccurrenceRow, JobHourRow

DELAYED_SHOWN = 10


async def delayed_occurrences(
    connection: SqlConnection, workspace_id: UUID, limit: int = DELAYED_SHOWN
) -> list[DelayedOccurrenceRow]:
    """Occurrences of this workspace's routines that didn't run at their time, newest first."""
    return await all_rows(
        connection,
        DelayedOccurrenceRow,
        "select r.name, o.occurrence_time, o.status, o.reason from public.routine_occurrences o "
        "join public.routines r on r.id = o.routine_id where r.workspace_id = %s "
        "and o.status in ('missed', 'skipped_overlap', 'blocked') "
        "order by o.occurrence_time desc limit %s",
        (workspace_id, limit),
    )


def delayed_view(row: DelayedOccurrenceRow, routine: str) -> DelayedOccurrence:
    """`routine` is the routine's name as the page may show it. An unknown stored status raises,
    instead of reaching a client."""
    return DelayedOccurrence(
        routine=routine,
        occurrence_time=row.occurrence_time,
        status=stored(DELAYED_STATUSES, row.status),
        reason=row.reason,
    )


@dataclass(frozen=True)
class JobHourCounts:
    starts_at: datetime
    hour: str
    succeeded: int
    waited: int
    failed: int
    in_progress: int


# PRD-Studio OP-03 and Decision 0022 D14. Each hour of the last 24 in the workspace's timezone, from
# the runs' own status changes: succeeded, waited for a person (entered waiting_approval or
# waiting_input), failed with cancelled, and in progress (a run now running or paused, in the hour
# of its latest change). Counts only.
_JOB_HOURS = """
with zone as (
  select coalesce(nullif(timezone, ''), 'UTC') as name from public.workspaces
  where id = %(workspace)s
), hours as (
  select local_hour at time zone zone.name as starts_at, to_char(local_hour, 'HH24:00') as hour
  from zone, generate_series(
    date_trunc('hour', now() at time zone zone.name) - interval '23 hours',
    date_trunc('hour', now() at time zone zone.name), interval '1 hour') as local_hour
), changes as (
  select e.run_id, e.payload ->> 'current' as status, e.occurred_at
  from public.run_events e join public.runs r on r.id = e.run_id
  where r.workspace_id = %(workspace)s and e.payload ->> 'type' = 'run.status_changed'
    and e.occurred_at >= (select min(starts_at) from hours)
), latest as (
  select distinct on (e.run_id) e.run_id, e.occurred_at
  from public.run_events e join public.runs r on r.id = e.run_id
  where r.workspace_id = %(workspace)s and r.status = any(%(moving)s)
    and e.payload ->> 'type' = 'run.status_changed'
  order by e.run_id, e.sequence desc
)
select h.starts_at, h.hour,
  (select count(distinct c.run_id) from changes c where c.status = %(succeeded)s
     and c.occurred_at >= h.starts_at and c.occurred_at < h.starts_at + interval '1 hour')
     as succeeded,
  (select count(distinct c.run_id) from changes c
     where c.status = any(%(needs_you)s)
     and c.occurred_at >= h.starts_at and c.occurred_at < h.starts_at + interval '1 hour')
     as waited,
  (select count(distinct c.run_id) from changes c where c.status = any(%(unsuccessful)s)
     and c.occurred_at >= h.starts_at and c.occurred_at < h.starts_at + interval '1 hour')
     as failed,
  (select count(*) from latest l
     where l.occurred_at >= h.starts_at and l.occurred_at < h.starts_at + interval '1 hour')
     as in_progress
from hours h order by h.starts_at
"""


async def job_hours(
    connection: SqlConnection, workspace_id: UUID
) -> tuple[str, list[JobHourCounts]]:
    """The workspace's timezone, and its last 24 hours of job counts, oldest first."""
    cursor = await connection.execute(
        "select coalesce(nullif(timezone, ''), 'UTC') from public.workspaces where id = %s",
        (workspace_id,),
    )
    zone = await cursor.fetchone()
    hours = await all_rows(
        connection,
        JobHourRow,
        _JOB_HOURS,
        {
            "workspace": workspace_id,
            "succeeded": RunStatus.SUCCEEDED.value,
            "needs_you": sorted(NEEDS_YOU),
            "unsuccessful": sorted(TERMINAL - {RunStatus.SUCCEEDED}),
            "moving": [RunStatus.RUNNING.value, RunStatus.PAUSED.value],
        },
    )
    rows = [
        JobHourCounts(
            row.starts_at,
            str(row.hour),
            int(row.succeeded),
            int(row.waited),
            int(row.failed),
            int(row.in_progress),
        )
        for row in hours
    ]
    return (str(zone[0]) if zone else "UTC"), rows
