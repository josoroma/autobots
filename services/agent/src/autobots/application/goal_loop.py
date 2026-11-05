"""One bounded pass over an admitted goal. New work stops at a limit, and the result is honest."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

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
from autobots.application.plans import load_goal, plan_tools, plan_view
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
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.domain.runs import Actor, CommandRefused, RunCommand

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


def loop_registry(limits: RootLimits) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT, *plan_tools(limits)):
        registry.register(tool)
    return registry


def build_stage(
    connection: Any, model: Any, saver: Any, scope: ToolScope, config: LoopConfig
) -> Any:
    """Explicit tools and middleware. Skills, memory, subagents and a backend stay unset here."""
    gateway = ToolGateway(loop_registry(config.limits))
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
    await begin_segment(connection, lease.run_id)
    code: str | None = None
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
        await end_segment(connection, lease.run_id)
    return await _finish(connection, lease, goal, code)


async def _finish(
    connection: Any, lease: Lease, goal: GoalSpec, stop_code: str | None
) -> LoopResult:
    view = await plan_view(connection, lease.run_id, goal)
    code = stop_code
    if code is None and not view.finished:
        code = "plan_missing" if view.version is None else "plan_incomplete"
    if code in NOT_OURS:
        command = None
    elif code is None:
        command = RunCommand.VERIFY
    elif code in PAUSE_FOR:
        command = RunCommand.SUSPEND
    else:
        command = RunCommand.FAIL
    await connection.execute(
        "update app_private.run_usage set stop_reason = %s where run_id = %s",
        (code, lease.run_id),
    )
    status = None
    if command is not None:
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
