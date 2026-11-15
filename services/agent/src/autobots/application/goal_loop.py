"""One bounded pass over an admitted goal. New work stops at a limit, and the result is honest."""

import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from autobots.adapters.checkpoints import (
    DURABILITY,
    adapter_qualified,
    fenced_checkpointer,
    graph_config,
    is_stale_owner,
)
from autobots.adapters.loop_middleware import (
    AdmittedModel,
    LoopMiddleware,
    LoopStopped,
    UnadmittedModelCall,
)
from autobots.adapters.result_stream import ResultTap, reset_tap, use_tap
from autobots.adapters.tool_middleware import GatewayMiddleware, visible_tools
from autobots.application.approvals import expire_due
from autobots.application.artifacts import reconcile_run
from autobots.application.assignments import Delegation

# `loop_registry`, `LoopConfig` and `LoopResult` are re-exported for the modules and checks that
# import them from here.
from autobots.application.loop_tools import loop_registry as loop_registry
from autobots.application.plans import load_goal
from autobots.application.recovery import classify_interrupted, open_obligation, outstanding
from autobots.application.run_lifecycle import LoopConfig as LoopConfig
from autobots.application.run_lifecycle import LoopResult as LoopResult
from autobots.application.run_lifecycle import (
    finish,
    lease_heartbeat,
    record_failure,
    result_of,
    run_status,
)
from autobots.application.run_usage import begin_segment, end_segment, ensure_usage
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.tool_gateway import ToolGateway, ToolScope
from autobots.application.verification import verify_candidate
from autobots.application.worker_leases import Lease, claim_next, is_held, reset_failures
from autobots.application.workflow_runner import run_workflow
from autobots.contracts.plans import GoalSpec
from autobots.domain.execution import incompatibility
from autobots.domain.models import ModelRoute
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus
from autobots.domain.stops import PassOutcome, StopCode
from autobots.domain.tools import DELEGATION_TOOL
from autobots.operations.logs import forbid_remote_tracing

SYSTEM_PROMPT = (
    "Work only on the stated goal. First call propose_plan, covering every criterion by its ID. "
    "Use only the tools offered. Call complete_task with real evidence as tasks finish. "
    "When every task is complete, reply without calling a tool."
)


# Bound to no profile, so `run_goal` leaves the run for a person instead of guessing a model.
UNBOUND = ModelRoute("executor", "", "", 0)
JobBinder = Callable[[Any, Lease, LoopConfig], Awaitable[tuple[Callable[[], Any], LoopConfig]]]


class SummarizationOff(AgentMiddleware[Any, Any]):
    """Takes the SDK summarizer's place. `LoopMiddleware` compacts, through admission."""

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"


def build_stage(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
    connection: Any,
    model: Any,
    saver: Any,
    scope: ToolScope,
    config: LoopConfig,
    instructions: str = "",
    delegation: Delegation | None = None,
    goal: GoalSpec | None = None,
    summary_route: ModelRoute | None = None,
) -> Any:
    """Explicit tools and middleware. Skills, memory, subagents and a backend stay unset here."""
    gateway = ToolGateway(
        loop_registry(config.limits, config.object_store, delegation, config.tools)
    )
    # Again here, for any caller that skipped a process entry point.
    forbid_remote_tracing(os.environ)
    return create_deep_agent(
        model=AdmittedModel(delegate=model),
        tools=visible_tools(gateway, scope),
        system_prompt=f"{SYSTEM_PROMPT}\n\n{instructions}".strip(),
        middleware=[
            LoopMiddleware(
                connection,
                scope,
                config.limits,
                config.route,
                sleep=config.sleep,
                slot_wait_seconds=config.slot_wait_seconds,
                model_call_seconds=config.model_call_seconds,
                goal=goal,
                compaction=config.compaction,
                summary_route=summary_route,
            ),
            GatewayMiddleware(gateway, connection, scope),
            SummarizationOff(),
        ],
        subagents=[],
        checkpointer=saver,
    )


async def scope_guidance(connection: Any, run_id: UUID, goal: GoalSpec) -> str:
    """What this run can reach: where it may write, and which Experts it may assign."""
    lines = [f"You may read and write only under: {', '.join(goal.allowed_paths)}."]
    if DELEGATION_TOOL in goal.allowed_tools:
        cursor = await connection.execute(
            "select e.id, e.name from public.runs r join public.sessions s on s.id = r.session_id "
            "cross join lateral jsonb_array_elements(s.experts) pinned "
            "join public.experts e on e.id = (pinned ->> 'expert_id')::uuid "
            "where r.id = %s order by e.name",
            (run_id,),
        )
        experts = [f"{row[1]} (expert_id {row[0]})" for row in await cursor.fetchall()]
        if experts:
            lines.append(f"With {DELEGATION_TOOL} you may assign work to: {', '.join(experts)}.")
    return "\n".join(lines)


def _opening(goal: GoalSpec) -> str:
    criteria = "\n".join(f"- {name}: {text}" for name, text in sorted(goal.criteria.items()))
    # Decision 0023: a plan cites criteria by ID. A model that copied their text, or treated a
    # delivery step as one, had its plan refused as out of scope, and a refusal names only a code.
    ids = ", ".join(sorted(goal.criteria))
    opening = (
        f"Goal: {goal.objective}\n\nCriteria:\n{criteria}\n\n"
        f"In propose_plan, each task's criteria field lists criterion IDs from this list ({ids}) "
        "and nothing else: never their text, and no new criteria."
    )
    if "publish_artifact" not in goal.allowed_tools:
        return opening
    # Verification accepts only published files, so the model has to know that from the start.
    lines = [
        "These are steps, not criteria. Saving a file delivers nothing. Before your final "
        "reply, save it under outputs/ with save_artifact, then call publish_artifact with its "
        "path and version."
    ]
    for required in goal.required_artifacts:
        lines.append(f"- Publish a file named {required.name}.")
        lines.extend(f'  It must contain: "{text}"' for text in required.must_contain)
    return f"{opening}\n\nDelivery:\n" + "\n".join(lines)


async def run_goal(
    connection: Any, database_url: str, lease: Lease, model: Any, config: LoopConfig
) -> LoopResult:
    """One bounded pass over an admitted goal (SP-010, SP-012).

    What an earlier owner left is classified first. A run being cancelled, an open wait re-entered,
    an uncertain model call, an unbound route or a refusal ends the pass before anything is sent.
    Otherwise the agent runs under the lease's keeper and a fenced checkpointer until it stops, and
    `finish` settles the run from the stop code.
    """
    goal = await load_goal(connection, lease.run_id)
    cursor = await connection.execute(
        "select parent_run_id, coalesce(root_run_id, id) from public.runs where id = %s",
        (lease.run_id,),
    )
    parent, root = await cursor.fetchone()

    async def drive_child(child_connection: Any, child_lease: Lease) -> LoopResult:
        return await drive_lease(child_connection, database_url, child_lease, lambda: model, config)

    delegation = Delegation(drive_child, config.limits, config.lease_seconds, config.sleep)
    scope = ToolScope(
        lease.workspace_id,
        lease.run_id,
        lease.generation,
        goal.allowed_tools,
        tuple(goal.allowed_paths),
        root_run_id=root,
        parent_run_id=parent,
    )
    await ensure_usage(connection, lease.run_id)
    await ensure_usage(connection, root)
    # Whatever an earlier owner left is classified first, and nothing is sent until that's done.
    await classify_interrupted(connection, lease.run_id, lease.generation)
    if config.object_store is not None:
        try:
            await reconcile_run(
                connection, config.object_store, lease.workspace_id, lease.run_id, scope
            )
        except LeaseLost:
            return await result_of(
                connection, lease, goal, PassOutcome.LOST, StopCode.LEASE_LOST, None
            )
    status = await run_status(connection, lease)
    if status == RunStatus.CANCELLING.value:
        return await finish(connection, lease, goal, StopCode.RUN_NOT_RUNNING)
    if await _obligation_holds(connection, lease):
        return await result_of(
            connection, lease, goal, PassOutcome.WAITING, None, await run_status(connection, lease)
        )
    if (await outstanding(connection, lease.run_id)).uncertain_calls:
        return await finish(connection, lease, goal, StopCode.UNCERTAIN_MODEL_CALL)
    if not await _route_is_bound(connection, lease, config):
        return await finish(connection, lease, goal, StopCode.ROUTE_NOT_BOUND)
    if config.refusal is not None:
        return await finish(connection, lease, goal, config.refusal)
    await begin_segment(connection, lease.run_id)
    code: str | None = None
    # A bound the SDK enforces too, so a graph that loops without dispatching still stops.
    steps = 3 * (config.limits.model_calls + config.limits.tool_dispatches) + 10
    run_config = {**graph_config(lease), "recursion_limit": steps}
    try:
        # The keeper stops before `end_segment`, while its sleep discounts reach the open segment.
        async with (
            lease_heartbeat(database_url, lease, config),
            fenced_checkpointer(database_url, lease) as saver,
        ):
            agent = build_stage(
                connection,
                model,
                saver,
                scope,
                config,
                f"{goal.instructions}\n\n{await scope_guidance(connection, lease.run_id, goal)}",
                delegation,
                goal,
                await _summary_route(connection, lease, config),
            )
            state = await agent.aget_state(run_config)
            payload = None if state.next else {"messages": [HumanMessage(_opening(goal))]}
            # US-15.24: this run's result text, live, while its model calls stream.
            tap = ResultTap(lease.run_id, database_url)
            tapped = use_tap(tap)
            try:
                await agent.ainvoke(payload, run_config, durability=DURABILITY)
            finally:
                reset_tap(tapped)
                await tap.close()
    except LoopStopped as stopped:
        code = stopped.code
    except GraphRecursionError:
        code = StopCode.STEP_LIMIT
    except UnadmittedModelCall:
        code = StopCode.UNADMITTED_MODEL_CALL
    except Exception as error:
        if not is_stale_owner(error):
            raise
        code = StopCode.LEASE_LOST
    finally:
        await end_segment(connection, lease.run_id)
    return await finish(connection, lease, goal, code)


async def process_next(
    connection: Any,
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


async def execution_block(connection: Any, run_id: UUID) -> str | None:
    """Why a saved run can't continue under this release, or None. It stays as it was saved."""
    cursor = await connection.execute(
        "select execution_contract from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    return incompatibility(None if row is None else row[0])


async def drive_lease(
    connection: Any,
    database_url: str,
    lease: Lease,
    model_factory: Callable[[], Any],
    config: LoopConfig,
) -> LoopResult:
    """Takes one claimed lease as far as it can go in one pass: a run this release can't continue
    stops before anything is touched, a workflow goes to its runner, and a goal runs its loop and
    then its verification. A child's assignment drives the child's lease here too."""
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
        result = await run_goal(connection, database_url, lease, model_factory(), config)
        if result.outcome != PassOutcome.CANDIDATE:
            return result
    return await settle_candidate(connection, database_url, lease, config)


async def settle_candidate(
    connection: Any, database_url: str, lease: Lease, config: LoopConfig
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
    version = (await cursor.fetchone())[0]
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


async def _obligation_holds(connection: Any, lease: Lease) -> bool:
    """Re-enters a wait that a pause and resume left open. Nothing else runs until it's answered."""
    obligation = await open_obligation(connection, lease.run_id)
    if obligation is None:
        return False
    kind, detail = obligation
    cursor = await connection.execute(
        "select version from public.runs where id = %s", (lease.run_id,)
    )
    await apply_command(
        connection,
        workspace_id=lease.workspace_id,
        run_id=lease.run_id,
        command=RunCommand.REQUEST_INPUT if kind == "input" else RunCommand.REQUEST_APPROVAL,
        actor=Actor.WORKER,
        expected_version=(await cursor.fetchone())[0],
        generation=lease.generation,
        detail=detail,
    )
    return True


async def _summary_route(connection: Any, lease: Lease, config: LoopConfig) -> ModelRoute | None:
    """Compaction uses the run's frozen summarizer binding. A different one has no route here."""
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (lease.run_id,)
    )
    snapshot = (await cursor.fetchone())[0]
    bound = snapshot.get("bindings", {}).get("summarizer")
    if bound != config.route.profile:
        return None
    return replace(config.route, role="summarizer", profile=bound)


async def _route_is_bound(connection: Any, lease: Lease, config: LoopConfig) -> bool:
    """A resumed run keeps its frozen policy. A changed workspace default doesn't reach it."""
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (lease.run_id,)
    )
    snapshot = (await cursor.fetchone())[0]
    bound: str | None = snapshot.get("bindings", {}).get(config.route.role)
    return bound == config.route.profile
