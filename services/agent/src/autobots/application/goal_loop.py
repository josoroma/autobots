"""One bounded pass over an admitted goal, and the graph it runs. New work stops at a limit, and the
result is honest.

Job dispatch (`operations/job_dispatch.py`) claims the job and passes in how a child is driven, so
this module imports neither it nor the workflow runner (Decision 0029 F7, PPRD-02).
"""

from dataclasses import replace
from typing import Any
from uuid import UUID

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError

from autobots.adapters.checkpoints import (
    DURABILITY,
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
from autobots.application.artifacts import reconcile_run
from autobots.application.assignments import Delegation
from autobots.application.loop_prompts import SYSTEM_PROMPT, opening, scope_guidance

# `loop_registry` and `LoopConfig` are re-exported for the modules and tests that import them from
# here.
from autobots.application.loop_tools import loop_registry as loop_registry
from autobots.application.plans import load_goal
from autobots.application.recovery import classify_interrupted, open_obligation, outstanding
from autobots.application.run_lifecycle import (
    Drive,
    LoopResult,
    finish,
    lease_heartbeat,
    result_of,
    run_status,
)
from autobots.application.run_lifecycle import LoopConfig as LoopConfig
from autobots.application.run_usage import begin_segment, end_segment, ensure_usage
from autobots.application.runs import LeaseLost, apply_command
from autobots.application.tool_gateway import ToolGateway, ToolScope
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.domain.execution import incompatibility
from autobots.domain.models import ModelRoute
from autobots.domain.runs import Actor, RunCommand, RunStatus
from autobots.domain.stops import PassOutcome, StopCode

# Bound to no profile, so `run_goal` leaves the run for a person instead of guessing a model.
UNBOUND = ModelRoute("executor", "", "", 0)


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
    *,
    instructions: str = "",
    delegation: Delegation | None = None,
    goal: GoalSpec | None = None,
    summary_route: ModelRoute | None = None,
) -> Any:
    """Explicit tools and middleware. Skills, memory, subagents and a backend stay unset here."""
    gateway = ToolGateway(
        loop_registry(config.limits, config.object_store, delegation, config.tools)
    )
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


async def run_goal(
    connection: Any,
    database_url: str,
    lease: Lease,
    model: Any,
    config: LoopConfig,
    *,
    drive: Drive,
) -> LoopResult:
    """One bounded pass over an admitted goal (SP-010, SP-012). A child its assignment starts is
    driven by `drive`, the dispatcher's own (PPRD-02).

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
        return await drive(child_connection, database_url, child_lease, lambda: model, config)

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
            guidance = await scope_guidance(connection, lease.run_id, goal)
            summary_route = await _summary_route(connection, lease, config)
            agent = build_stage(
                connection,
                model,
                saver,
                scope,
                config,
                instructions=f"{goal.instructions}\n\n{guidance}",
                delegation=delegation,
                goal=goal,
                summary_route=summary_route,
            )
            state = await agent.aget_state(run_config)
            payload = None if state.next else {"messages": [HumanMessage(opening(goal))]}
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


async def execution_block(connection: Any, run_id: UUID) -> str | None:
    """Why a saved run can't continue under this release, or None. It stays as it was saved."""
    cursor = await connection.execute(
        "select execution_contract from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    return incompatibility(None if row is None else row[0])


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
