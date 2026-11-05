"""One bounded pass over an admitted goal. New work stops at a limit, and the result is honest."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import psycopg
from deepagents import create_deep_agent
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
    ModelRoute,
)
from autobots.adapters.tool_middleware import GatewayMiddleware, visible_tools
from autobots.application.artifacts import publish_tool, reconcile_run
from autobots.application.plans import load_goal, plan_tools, plan_view
from autobots.application.recovery import classify_interrupted, open_obligation, outstanding
from autobots.application.run_usage import (
    RootLimits,
    begin_segment,
    end_segment,
    ensure_usage,
    usage_view,
)
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.tools import CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT
from autobots.application.worker_leases import (
    DEFAULT_LEASE_SECONDS,
    Lease,
    claim_next,
    heartbeat,
)
from autobots.contracts.plans import GoalSpec
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus

# Waiting can resolve these: a person adds budget or a key, or reconciles an uncertain call.
PAUSE_FOR = frozenset(
    {
        "budget_exceeded",
        "no_inference_slot",
        "cost_unavailable",
        "invalid_credential",
        "insufficient_credits",
        "partial_stream",
        "uncertain_acceptance",
        "uncertain_model_call",
    }
)
NOT_OURS = frozenset({"lease_lost", "run_not_running", "run_not_found"})
SYSTEM_PROMPT = (
    "Work only on the stated goal. First call propose_plan, covering every criterion. "
    "Use only the tools offered. Call complete_task with real evidence as tasks finish. "
    "When every task is complete, reply without calling a tool."
)


@dataclass(frozen=True)
class LoopConfig:
    route: ModelRoute
    limits: RootLimits = RootLimits()  # noqa: RUF009 - frozen, so sharing the default is safe.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    slot_wait_seconds: float = 30.0
    object_store: Any = None
    heartbeat_seconds: float = 20.0
    lease_seconds: float = DEFAULT_LEASE_SECONDS


@dataclass(frozen=True)
class LoopResult:
    """What really happened, whatever the model said at the end."""

    outcome: str
    code: str | None
    run_status: str | None
    plan_version: int | None
    completed: tuple[str, ...]
    remaining: tuple[str, ...]
    uncovered_criteria: tuple[str, ...]
    usage: dict[str, Any]


def loop_registry(limits: RootLimits, object_store: Any = None) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT, *plan_tools(limits)):
        registry.register(tool)
    if object_store is not None:
        registry.register(publish_tool(object_store))
    return registry


def build_stage(
    connection: Any, model: Any, saver: Any, scope: ToolScope, config: LoopConfig
) -> Any:
    """Explicit tools and middleware. Skills, memory, subagents and a backend stay unset here."""
    gateway = ToolGateway(loop_registry(config.limits, config.object_store))
    return create_deep_agent(
        model=AdmittedModel(delegate=model),
        tools=visible_tools(gateway, scope),
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            LoopMiddleware(
                connection,
                scope,
                config.limits,
                config.route,
                sleep=config.sleep,
                slot_wait_seconds=config.slot_wait_seconds,
            ),
            GatewayMiddleware(gateway, connection, scope),
        ],
        subagents=[],
        checkpointer=saver,
    )


def _opening(goal: GoalSpec) -> str:
    criteria = "\n".join(f"- {name}: {text}" for name, text in sorted(goal.criteria.items()))
    return f"Goal: {goal.objective}\n\nCriteria:\n{criteria}"


async def run_goal(
    connection: Any, database_url: str, lease: Lease, model: Any, config: LoopConfig
) -> LoopResult:
    goal = await load_goal(connection, lease.run_id)
    scope = ToolScope(
        lease.workspace_id,
        lease.run_id,
        lease.generation,
        goal.allowed_tools,
        tuple(goal.allowed_paths),
    )
    await ensure_usage(connection, lease.run_id)
    # Whatever an earlier owner left is classified first, and nothing is sent until that's done.
    await classify_interrupted(connection, lease.run_id, lease.generation)
    if config.object_store is not None:
        await reconcile_run(connection, config.object_store, lease.workspace_id, lease.run_id)
    status = await _run_status(connection, lease)
    if status == RunStatus.CANCELLING.value:
        return await _finish(connection, lease, goal, "run_not_running")
    if await _obligation_holds(connection, lease):
        return await _result(
            connection, lease, goal, "waiting", None, await _run_status(connection, lease)
        )
    if (await outstanding(connection, lease.run_id)).uncertain_calls:
        return await _finish(connection, lease, goal, "uncertain_model_call")
    if not await _route_is_bound(connection, lease, config):
        return await _finish(connection, lease, goal, "route_not_bound")
    await begin_segment(connection, lease.run_id)
    code: str | None = None
    beating = asyncio.create_task(_keep_lease(database_url, lease, config))
    # A bound the SDK enforces too, so a graph that loops without dispatching still stops.
    steps = 3 * (config.limits.model_calls + config.limits.tool_dispatches) + 10
    run_config = {**graph_config(lease), "recursion_limit": steps}
    try:
        async with fenced_checkpointer(database_url, lease) as saver:
            agent = build_stage(connection, model, saver, scope, config)
            state = await agent.aget_state(run_config)
            payload = None if state.next else {"messages": [HumanMessage(_opening(goal))]}
            await agent.ainvoke(payload, run_config, durability=DURABILITY)
    except LoopStopped as stopped:
        code = stopped.code
    except GraphRecursionError:
        code = "step_limit"
    except Exception as error:
        if not is_stale_owner(error):
            raise
        code = "lease_lost"
    finally:
        beating.cancel()
        await end_segment(connection, lease.run_id)
    return await _finish(connection, lease, goal, code)


async def process_next(
    connection: Any,
    database_url: str,
    worker_id: str,
    model_factory: Callable[[], Any],
    config: LoopConfig,
) -> LoopResult | None:
    """Claims one eligible job and takes it as far as it can go in one pass."""
    lease = await claim_next(connection, worker_id=worker_id, lease_seconds=config.lease_seconds)
    if lease is None:
        return None
    return await run_goal(connection, database_url, lease, model_factory(), config)


async def _keep_lease(database_url: str, lease: Lease, config: LoopConfig) -> None:
    """On its own connection, since the loop's may be mid-transaction or waiting on a model."""
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as connection:
        while True:
            await asyncio.sleep(config.heartbeat_seconds)
            try:
                await heartbeat(connection, lease, lease_seconds=config.lease_seconds)
            except LeaseLost:
                return


async def _run_status(connection: Any, lease: Lease) -> str:
    cursor = await connection.execute(
        "select status from public.runs where id = %s", (lease.run_id,)
    )
    status: str = (await cursor.fetchone())[0]
    return status


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


async def _route_is_bound(connection: Any, lease: Lease, config: LoopConfig) -> bool:
    """A resumed run keeps its frozen policy. A changed workspace default doesn't reach it."""
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (lease.run_id,)
    )
    snapshot = (await cursor.fetchone())[0]
    bound: str | None = snapshot.get("bindings", {}).get(config.route.role)
    return bound == config.route.profile


async def _result(
    connection: Any,
    lease: Lease,
    goal: GoalSpec,
    outcome: str,
    code: str | None,
    status: str | None,
) -> LoopResult:
    view = await plan_view(connection, lease.run_id, goal)
    return LoopResult(
        outcome,
        code,
        status,
        view.version,
        view.completed,
        view.remaining,
        view.uncovered_criteria,
        await usage_view(connection, lease.run_id),
    )


async def _finish(
    connection: Any, lease: Lease, goal: GoalSpec, stop_code: str | None
) -> LoopResult:
    view = await plan_view(connection, lease.run_id, goal)
    code = stop_code
    if code is None and not view.finished:
        code = "plan_missing" if view.version is None else "plan_incomplete"
    command: RunCommand | None
    if code == "run_not_running" and await _run_status(connection, lease) == "cancelling":
        # This worker still owns it, and it is the one who settles the cancellation.
        await classify_interrupted(connection, lease.run_id, lease.generation + 1)
        left = await outstanding(connection, lease.run_id)
        code = (
            "cancelled_with_unknown_outcomes"
            if left.uncertain_calls or left.unknown_effects
            else "cancelled"
        )
        command = RunCommand.FINISH_CANCEL
    elif code in NOT_OURS:
        command = None
    elif code is None:
        command = RunCommand.VERIFY
    elif code in PAUSE_FOR:
        command = RunCommand.SUSPEND
    else:
        command = RunCommand.FAIL
    status = None
    if command is not None:
        await connection.execute(
            "update app_private.run_usage set stop_reason = %s where run_id = %s",
            (code, lease.run_id),
        )
        cursor = await connection.execute(
            "select version from public.runs where id = %s", (lease.run_id,)
        )
        version = (await cursor.fetchone())[0]
        try:
            result = await apply_command(
                connection,
                workspace_id=lease.workspace_id,
                run_id=lease.run_id,
                command=command,
                actor=Actor.WORKER,
                expected_version=version,
                generation=lease.generation,
            )
            status = result.status
        except (LeaseLost, VersionConflict, CommandRefused):
            code = "lease_lost"
    outcome = "candidate" if code is None else ("lost" if code in NOT_OURS else "stopped")
    return await _result(connection, lease, goal, outcome, code, status)
