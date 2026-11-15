"""The worker process's step: claim one eligible job, bind it, and drive its lease through one pass
(Decision 0029 F7, SP-012).

`drive_lease` is the one drive function. It sends a workflow to its runner and a goal to its loop
and then its verification, and passes itself to both as how a child is driven, so neither imports
this module (PPRD-02).
"""

import os
from collections.abc import Awaitable, Callable
from typing import Any

from autobots.adapters.checkpoints import adapter_qualified, is_stale_owner
from autobots.application.approvals import expire_due
from autobots.application.goal_loop import run_goal
from autobots.application.plans import load_goal
from autobots.application.recovery import classify_interrupted, execution_block
from autobots.application.run_lifecycle import (
    Connection,
    LoopConfig,
    LoopResult,
    finish,
    record_failure,
)
from autobots.application.runs import LeaseLost
from autobots.application.settlement import settle_candidate
from autobots.application.worker_leases import Lease, claim_next, is_held, reset_failures
from autobots.application.workflow_runner import run_workflow
from autobots.domain.runs import RunStatus
from autobots.domain.stops import PassOutcome, StopCode
from autobots.operations.logs import forbid_remote_tracing

# Replaces the model and route for the job just claimed: (connection, lease, config).
JobBinder = Callable[[Any, Lease, LoopConfig], Awaitable[tuple[Callable[[], Any], LoopConfig]]]


async def process_next(
    connection: Connection,
    database_url: str,
    worker_id: str,
    model_factory: Callable[[], Any],
    config: LoopConfig,
    *,
    bind: JobBinder | None = None,
) -> LoopResult | None:
    """Claims one eligible job and takes it as far as it can go in one pass.

    A worker that serves whatever comes passes `bind`, which replaces the model and route for the
    job it just claimed. Without it, `run_goal` refuses any run that isn't bound to `config.route`.

    A pass that raises an exception no handler classifies is recorded by `record_failure`, which
    requeues the job after a backoff or, at the bound, suspends the run; the exception still
    propagates, so the worker logs the step as failed. Cancellation is a BaseException and a lost
    lease is the next owner's to fence, so neither is recorded. A pass that completes resets the
    count (Decision 0028 E4, SP-012).
    """
    if await is_held(connection) or not await adapter_qualified(connection):
        return None
    await expire_due(connection)
    lease = await claim_next(connection, worker_id=worker_id, lease_seconds=config.lease_seconds)
    if lease is None:
        return None
    try:
        if bind is not None:
            model_factory, config = await bind(connection, lease, config)
        result = await drive_lease(connection, database_url, lease, model_factory, config)
    except Exception as error:
        if not isinstance(error, LeaseLost) and not is_stale_owner(error):
            await record_failure(connection, lease, error)
        raise
    await reset_failures(connection, lease)
    return result


async def drive_lease(
    connection: Connection,
    database_url: str,
    lease: Lease,
    model_factory: Callable[[], Any],
    config: LoopConfig,
) -> LoopResult:
    """Takes one claimed lease as far as it can go in one pass: a run this release can't continue
    stops before anything is touched, a workflow goes to its runner, and a goal runs its loop and
    then its verification. A child's assignment drives the child's lease here too."""
    # Before any agent is built, for any caller that skipped a process entry point.
    forbid_remote_tracing(os.environ)
    if await execution_block(connection, lease.run_id) is not None:
        # Before any model or checkpoint is touched. A migration never swaps these for it.
        goal = await load_goal(connection, lease.run_id)
        await classify_interrupted(connection, lease.run_id, lease.generation)
        return await finish(connection, lease, goal, StopCode.INCOMPATIBLE_VERSION)
    cursor = await connection.execute(
        "select 1 from public.workflow_executions where run_id = %s", (lease.run_id,)
    )
    if await cursor.fetchone() is not None:
        # The runner drives its agent steps' children through this function (PPRD-02).
        return await run_workflow(
            connection, database_url, lease, model_factory(), config, drive=drive_lease
        )
    if lease.run_status != RunStatus.VERIFYING.value:
        result = await run_goal(
            connection, database_url, lease, model_factory(), config, drive=drive_lease
        )
        if result.outcome != PassOutcome.CANDIDATE:
            return result
    return await settle_candidate(connection, database_url, lease, config)
