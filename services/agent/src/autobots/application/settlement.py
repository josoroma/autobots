"""Settling a goal's candidate: only recorded checks finish a run, and the verdict commits with the
run's transition, so a worker that lost the run records nothing (LC-12, SP-012)."""

import json
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
from autobots.application.runs import LeaseLost, VersionConflict, apply_worker_command
from autobots.application.verification import verify_candidate
from autobots.application.worker_leases import Lease
from autobots.domain.runs import CommandRefused, RunCommand
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
    try:
        # The verdict and the stop reason commit with the transition, so a worker that lost the run
        # records nothing.
        async with connection.transaction():
            result = await apply_worker_command(
                connection,
                lease,
                RunCommand.COMPLETE if report.passed else RunCommand.FAIL,
                stop_reason=code,
            )
            await connection.execute(
                "insert into app_private.run_verifications (id, run_id, passed, unmet, checks) "
                "values (%s, %s, %s, %s, %s)",
                (uuid4(), lease.run_id, report.passed, json.dumps(report.unmet), report.checks),
            )
    except CommandRefused:
        # A cancel arrived first. It wins, and this worker settles it.
        return await finish(connection, lease, goal, StopCode.RUN_NOT_RUNNING)
    except (LeaseLost, VersionConflict):
        return await result_of(connection, lease, goal, PassOutcome.LOST, StopCode.LEASE_LOST, None)
    outcome = PassOutcome.SUCCEEDED if report.passed else PassOutcome.STOPPED
    return await result_of(connection, lease, goal, outcome, code, result.status)
