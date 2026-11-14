"""Declared retention, SP-014 and LM-07: scoped to one workspace, and never ahead of a receipt."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg

from autobots.domain.runs import TERMINAL
from autobots.operations.logs import log_event

logger = logging.getLogger("autobots.retention")
_BATCH = 100
_MAX_BATCHES = 20


@dataclass(frozen=True)
class RetentionPolicy:
    """A null window keeps everything, which is also what a workspace with no policy gets."""

    run_days: int | None = None
    receipt_days: int | None = None


@dataclass
class RetentionReport:
    purged_runs: int = 0
    refused: dict[str, int] = field(default_factory=dict)
    keys_expired: int = 0
    objects_removed: int = 0
    objects_pending: int = 0


async def read_policy(connection: Any, workspace_id: UUID) -> RetentionPolicy:
    cursor = await connection.execute(
        "select run_days, receipt_days from app_private.workspace_retention "
        "where workspace_id = %s",
        (workspace_id,),
    )
    row = await cursor.fetchone()
    return RetentionPolicy() if row is None else RetentionPolicy(row[0], row[1])


async def write_policy(
    connection: Any, workspace_id: UUID, actor_id: UUID, policy: RetentionPolicy
) -> None:
    await connection.execute(
        "insert into app_private.workspace_retention "
        "(workspace_id, run_days, receipt_days, updated_by) values (%s, %s, %s, %s) "
        "on conflict (workspace_id) do update set run_days = excluded.run_days, "
        "receipt_days = excluded.receipt_days, updated_by = excluded.updated_by, "
        "updated_at = now()",
        (workspace_id, policy.run_days, policy.receipt_days, actor_id),
    )


async def _commit(connection: Any) -> None:
    """The API's pooled connections aren't autocommit, and these steps have to be durable each."""
    if not connection.autocommit:
        await connection.commit()


async def _remove_expired_objects(
    connection: Any, store: Any, workspace_id: UUID, report: RetentionReport
) -> None:
    """After the rows commit, so a crash leaves bytes to retry, never a row pointing at nothing."""
    cursor = await connection.execute(
        "select id, object_path from public.artifacts where workspace_id = %s "
        "and status = 'expired' and bytes_removed_at is null limit %s",
        (workspace_id, _BATCH),
    )
    rows = await cursor.fetchall()
    await _commit(connection)
    # Storage being down fails every object in the batch, so the first failure in a pass is logged
    # and `retention.applied` counts the rest (XERR-11).
    said = False
    for artifact_id, path in rows:
        if store is None:
            report.objects_pending += 1
            continue
        try:
            await store.remove(path)
        except Exception as error:  # noqa: BLE001 - any failure waits for the next pass
            # Any failure here waits for the next pass. Storage being down isn't a retention error.
            report.objects_pending += 1
            if not said:
                said = True
                log_event(
                    logger,
                    "retention.object_kept",
                    logging.WARNING,
                    workspace=workspace_id,
                    error=error,
                )
            continue
        await connection.execute(
            "update public.artifacts set bytes_removed_at = now() where id = %s", (artifact_id,)
        )
        await _commit(connection)
        report.objects_removed += 1


async def apply_retention(
    connection: Any, store: Any, workspace_id: UUID, now: datetime | None = None
) -> RetentionReport:
    """One workspace's declared windows. The database refuses anything else, and says why."""
    policy = await read_policy(connection, workspace_id)
    report = RetentionReport()
    moment = now or (await (await connection.execute("select now()")).fetchone())[0]
    if policy.run_days is not None:
        cutoff = moment - timedelta(days=policy.run_days)
        # By position, not by repeating the query, so runs refused today can't crowd out the rest.
        position: tuple[datetime, UUID] | None = None
        for _ in range(_MAX_BATCHES):
            cursor = await connection.execute(
                "select id, updated_at from public.runs "
                "where workspace_id = %s and content_purged_at is null "
                "and status = any(%s) and updated_at < %s "
                "and (%s::timestamptz is null or (updated_at, id) > (%s::timestamptz, %s::uuid)) "
                "order by updated_at, id limit %s",
                (
                    workspace_id,
                    sorted(TERMINAL),
                    cutoff,
                    position[0] if position else None,
                    position[0] if position else None,
                    position[1] if position else None,
                    _BATCH,
                ),
            )
            rows = await cursor.fetchall()
            if not rows:
                break
            for run_id, updated_at in rows:
                position = (updated_at, run_id)
                result = await (
                    await connection.execute(
                        "select app_private.purge_run_content(%s, %s, %s)",
                        (workspace_id, run_id, cutoff),
                    )
                ).fetchone()
                await _commit(connection)
                outcome = result[0]
                if outcome.get("purged"):
                    report.purged_runs += 1
                else:
                    code = str(outcome.get("refused"))
                    report.refused[code] = report.refused.get(code, 0) + 1
    await _remove_expired_objects(connection, store, workspace_id, report)
    if policy.receipt_days is not None:
        cutoff = moment - timedelta(days=policy.receipt_days)
        row = await (
            await connection.execute(
                "select app_private.expire_idempotency_receipts(%s, %s)", (workspace_id, cutoff)
            )
        ).fetchone()
        report.keys_expired = int(row[0])
        await _commit(connection)
    log_event(
        logger,
        "retention.applied",
        workspace=workspace_id,
        purged_runs=report.purged_runs,
        refused=sum(report.refused.values()),
        keys_expired=report.keys_expired,
        objects_removed=report.objects_removed,
        objects_pending=report.objects_pending,
    )
    return report


async def apply_all(connection: Any, store: Any) -> None:
    """Only workspaces that declared a window, each on its own, so one failure stays its own."""
    cursor = await connection.execute(
        "select workspace_id from app_private.workspace_retention "
        "where run_days is not null or receipt_days is not null"
    )
    for (workspace_id,) in await cursor.fetchall():
        try:
            await apply_retention(connection, store, workspace_id)
        except psycopg.OperationalError:
            raise
        except Exception as error:  # noqa: BLE001 - a failed pass is logged without its message and retried at the next interval
            log_event(
                logger, "retention.failed", logging.WARNING, workspace=workspace_id, error=error
            )
