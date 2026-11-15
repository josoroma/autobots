"""Settling a goal's candidate: only recorded checks finish a run, and the verdict commits with the
run's transition, so a worker that lost the run records nothing (LC-12, SP-012)."""

import json
from typing import Any, cast
from uuid import uuid4

from autobots.application.plans import load_goal
from autobots.application.run_lifecycle import (
    Connection,
    LoopConfig,
    LoopResult,
    finish,
    lease_heartbeat,
    result_of,
)
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.verification import verify_candidate
from autobots.application.worker_leases import Lease
from autobots.domain.runs import Actor, CommandRefused, RunCommand
from autobots.domain.stops import PassOutcome, StopCode


async def settle_candidate(
    connection: Connection, database_url: str, lease: Lease, config: LoopConfig
) -> LoopResult:
    """Only recorded checks finish a run. Also picks up a candidate whose worker died."""
    goal = await load_goal(connection, lease.run_id)
    async with lease_heartbeat(database_url, lease, config):
        try:
            report = await verify_candidate(connection, config.object_store, lease, goal)
        except LeaseLost:
            return await result_of(
                connection, lease, goal, PassOutcome.LOST, StopCode.LEASE_LOST, None
            )
    code = None if report.passed else StopCode.CRITERIA_UNMET
    cursor = await connection.execute(
        "select version from public.runs where id = %s", (lease.run_id,)
    )
    # The run this worker holds has its row. Rows stay untyped until the SQL boundary is (R-54).
    version = cast(tuple[Any, ...], await cursor.fetchone())[0]
    try:
        # The verdict commits with the transition, so a worker that lost the run records nothing.
        async with connection.transaction():
            result = await apply_command(
                connection,
                workspace_id=lease.workspace_id,
                run_id=lease.run_id,
                command=RunCommand.COMPLETE if report.passed else RunCommand.FAIL,
                actor=Actor.WORKER,
                expected_version=version,
                generation=lease.generation,
            )
            await connection.execute(
                "insert into app_private.run_verifications (id, run_id, passed, unmet, checks) "
                "values (%s, %s, %s, %s, %s)",
                (uuid4(), lease.run_id, report.passed, json.dumps(report.unmet), report.checks),
            )
            await connection.execute(
                "update app_private.run_usage set stop_reason = %s where run_id = %s",
                (code, lease.run_id),
            )
    except CommandRefused:
        # A cancel arrived first. It wins, and this worker settles it.
        return await finish(connection, lease, goal, StopCode.RUN_NOT_RUNNING)
    except (LeaseLost, VersionConflict):
        return await result_of(connection, lease, goal, PassOutcome.LOST, StopCode.LEASE_LOST, None)
    outcome = PassOutcome.SUCCEEDED if report.passed else PassOutcome.STOPPED
    return await result_of(connection, lease, goal, outcome, code, result.status)
