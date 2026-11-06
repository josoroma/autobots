"""One bounded pass over an admitted goal. New work stops at a limit, and the result is honest."""

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
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
from autobots.adapters.github_issues import GITHUB_ISSUE
from autobots.adapters.loop_middleware import (
    AdmittedModel,
    LoopMiddleware,
    LoopStopped,
    ModelRoute,
    UnadmittedModelCall,
)
from autobots.adapters.tool_middleware import GatewayMiddleware, visible_tools
from autobots.application.approvals import expire_due
from autobots.application.artifacts import publish_tool, reconcile_run
from autobots.application.assignments import Delegation, assign_tool
from autobots.application.compaction import CompactionPolicy
from autobots.application.improvements import PROPOSE_IMPROVEMENT
from autobots.application.memory import READ_OFFLOAD, SEARCH_MEMORY
from autobots.application.plans import load_goal, plan_tools, plan_view
from autobots.application.recovery import classify_interrupted, open_obligation, outstanding
from autobots.application.run_usage import (
    RootLimits,
    begin_segment,
    discount_sleep,
    end_segment,
    ensure_usage,
    usage_view,
)
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.tool_gateway import (
    ToolDefinition,
    ToolGateway,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tools import CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT
from autobots.application.verification import verify_candidate
from autobots.application.worker_leases import (
    DEFAULT_LEASE_SECONDS,
    Lease,
    WakeClock,
    claim_next,
    claim_run,
    heartbeat,
    is_held,
    revive_lease,
)
from autobots.contracts.plans import GoalSpec
from autobots.domain.execution import INCOMPATIBLE, incompatibility
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus
from autobots.domain.tools import DELEGATION_TOOL
from autobots.operations.logs import forbid_remote_tracing, log_event

# Waiting can resolve these: a person adds budget or a key, or reconciles an uncertain call.
PAUSE_FOR = frozenset(
    {
        "budget_exceeded",
        "no_inference_slot",
        "cost_unavailable",
        "credentials_required",
        "credential_unavailable",
        "model_unavailable",
        "network_before_acceptance",
        "invalid_credential",
        "insufficient_credits",
        "partial_stream",
        "uncertain_acceptance",
        "uncertain_model_call",
        "assignment_paused",
        "assignment_lost",
        "assignment_busy",
        "parent_not_running",
        "outcome_unknown",
        INCOMPATIBLE,
        # A worker on another model, say after a release, leaves the saved run for the right one.
        "route_not_bound",
    }
)
NOT_OURS = frozenset({"lease_lost", "run_not_running", "run_not_found", "approval_pending"})
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
    tools: tuple[ToolDefinition, ...] = ()
    compaction: CompactionPolicy = CompactionPolicy()  # noqa: RUF009 - frozen, so sharing is safe.
    heartbeat_seconds: float = 20.0
    model_call_seconds: float = 120.0
    lease_seconds: float = DEFAULT_LEASE_SECONDS
    # Why this job can't dispatch, known before it reserves anything. A cancel or a verification
    # that needs no model still goes first, so it's checked with the route, not at claim.
    refusal: str | None = None


logger = logging.getLogger("autobots.worker")
WAKE_LOOK_SECONDS = 1.0
# Bound to no profile, so `run_goal` leaves the run for a person instead of guessing a model.
UNBOUND = ModelRoute("executor", "", "", 0)
JobBinder = Callable[[Any, Lease, LoopConfig], Awaitable[tuple[Callable[[], Any], LoopConfig]]]


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


def loop_registry(
    limits: RootLimits,
    object_store: Any = None,
    delegation: Delegation | None = None,
    extra: tuple[ToolDefinition, ...] = (),
) -> ToolRegistry:
    registry = ToolRegistry()
    tools = (
        CALCULATE,
        READ_RUN_FILE,
        SAVE_ARTIFACT,
        SEARCH_MEMORY,
        READ_OFFLOAD,
        PROPOSE_IMPROVEMENT,
        GITHUB_ISSUE,
    )
    for tool in (*tools, *plan_tools(limits)):
        registry.register(tool)
    if object_store is not None:
        registry.register(publish_tool(object_store))
    if delegation is not None:
        registry.register(assign_tool(delegation))
    for tool in extra:
        registry.register(tool)
    return registry


class SummarizationOff(AgentMiddleware[Any, Any]):
    """Takes the SDK summarizer's place. `LoopMiddleware` compacts, through admission."""

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"


def build_stage(
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


async def _scope_guidance(connection: Any, run_id: UUID, goal: GoalSpec) -> str:
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
    opening = f"Goal: {goal.objective}\n\nCriteria:\n{criteria}"
    if "publish_artifact" not in goal.allowed_tools:
        return opening
    # Verification accepts only published files, so the model has to know that from the start.
    lines = [
        "Saving a file delivers nothing. Before your final reply, save it under outputs/ with "
        "save_artifact, then call publish_artifact with its path and version."
    ]
    for required in goal.required_artifacts:
        lines.append(f"- Publish a file named {required.name}.")
        lines.extend(f'  It must contain: "{text}"' for text in required.must_contain)
    return f"{opening}\n\nDelivery:\n" + "\n".join(lines)


async def run_goal(
    connection: Any, database_url: str, lease: Lease, model: Any, config: LoopConfig
) -> LoopResult:
    goal = await load_goal(connection, lease.run_id)
    cursor = await connection.execute(
        "select parent_run_id, coalesce(root_run_id, id) from public.runs where id = %s",
        (lease.run_id,),
    )
    parent, root = await cursor.fetchone()

    async def drive_child(child_connection: Any, child_lease: Lease) -> LoopResult:
        return await _drive(child_connection, database_url, child_lease, lambda: model, config)

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
            return await _result(connection, lease, goal, "lost", "lease_lost", None)
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
    if config.refusal is not None:
        return await _finish(connection, lease, goal, config.refusal)
    await begin_segment(connection, lease.run_id)
    code: str | None = None
    beating = asyncio.create_task(_keep_lease(database_url, lease, config))
    # A bound the SDK enforces too, so a graph that loops without dispatching still stops.
    steps = 3 * (config.limits.model_calls + config.limits.tool_dispatches) + 10
    run_config = {**graph_config(lease), "recursion_limit": steps}
    try:
        async with fenced_checkpointer(database_url, lease) as saver:
            agent = build_stage(
                connection,
                model,
                saver,
                scope,
                config,
                f"{goal.instructions}\n\n{await _scope_guidance(connection, lease.run_id, goal)}",
                delegation,
                goal,
                await _summary_route(connection, lease, config),
            )
            state = await agent.aget_state(run_config)
            payload = None if state.next else {"messages": [HumanMessage(_opening(goal))]}
            await agent.ainvoke(payload, run_config, durability=DURABILITY)
    except LoopStopped as stopped:
        code = stopped.code
    except GraphRecursionError:
        code = "step_limit"
    except UnadmittedModelCall:
        code = "unadmitted_model_call"
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
    *,
    bind: JobBinder | None = None,
) -> LoopResult | None:
    """Claims one eligible job and takes it as far as it can go in one pass.

    A worker that serves whatever comes passes `bind`, which replaces the model and route for the
    job it just claimed. Without it, `run_goal` refuses any run that isn't bound to `config.route`.
    """
    if await is_held(connection) or not await adapter_qualified(connection):
        return None
    await expire_due(connection)
    lease = await claim_next(connection, worker_id=worker_id, lease_seconds=config.lease_seconds)
    if lease is None:
        return None
    if bind is not None:
        model_factory, config = await bind(connection, lease, config)
    return await _drive(connection, database_url, lease, model_factory, config)


async def execution_block(connection: Any, run_id: UUID) -> str | None:
    """Why a saved run can't continue under this release, or None. It stays as it was saved."""
    cursor = await connection.execute(
        "select execution_contract from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    return incompatibility(None if row is None else row[0])


async def _drive(
    connection: Any,
    database_url: str,
    lease: Lease,
    model_factory: Callable[[], Any],
    config: LoopConfig,
) -> LoopResult:
    if await execution_block(connection, lease.run_id) is not None:
        # Before any model or checkpoint is touched. A migration never swaps these for it.
        goal = await load_goal(connection, lease.run_id)
        await classify_interrupted(connection, lease.run_id, lease.generation)
        return await _finish(connection, lease, goal, INCOMPATIBLE)
    cursor = await connection.execute(
        "select 1 from public.workflow_executions where run_id = %s", (lease.run_id,)
    )
    if await cursor.fetchone() is not None:
        # Imported here because the runner builds on this module's lifecycle.
        from autobots.application.workflow_runner import run_workflow

        return await run_workflow(connection, database_url, lease, model_factory(), config)
    if lease.run_status != RunStatus.VERIFYING.value:
        result = await run_goal(connection, database_url, lease, model_factory(), config)
        if result.outcome != "candidate":
            return result
    return await _settle_candidate(connection, database_url, lease, config)


async def _settle_candidate(
    connection: Any, database_url: str, lease: Lease, config: LoopConfig
) -> LoopResult:
    """Only recorded checks finish a run. Also picks up a candidate whose worker died."""
    goal = await load_goal(connection, lease.run_id)
    beating = asyncio.create_task(_keep_lease(database_url, lease, config))
    try:
        report = await verify_candidate(connection, config.object_store, lease, goal)
    except LeaseLost:
        return await _result(connection, lease, goal, "lost", "lease_lost", None)
    finally:
        beating.cancel()
    code = None if report.passed else "criteria_unmet"
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
        return await _finish(connection, lease, goal, "run_not_running")
    except (LeaseLost, VersionConflict):
        return await _result(connection, lease, goal, "lost", "lease_lost", None)
    outcome = "succeeded" if report.passed else "stopped"
    return await _result(connection, lease, goal, outcome, code, result.status)


async def _keep_lease(
    database_url: str, lease: Lease, config: LoopConfig, clock: WakeClock | None = None
) -> None:
    """On its own connection, since the loop's may be mid-transaction or waiting on a model.

    It looks every second for a Mac having slept, as a lease runs out during any sleep longer than
    it. Right after one, it beats every look too, because Docker's clock can jump again later.
    """
    wake = clock or WakeClock()
    look = min(WAKE_LOOK_SECONDS, config.heartbeat_seconds)
    since_beat = 0.0
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as connection:
        while True:
            await asyncio.sleep(look)
            since_beat += look
            slept = wake.check()
            if slept:
                log_event(logger, "worker.woke", seconds=round(slept, 1))
                await discount_sleep(connection, lease.run_id, slept)
            if since_beat < config.heartbeat_seconds and not wake.just_woke():
                continue
            since_beat = 0.0
            try:
                await heartbeat(connection, lease, lease_seconds=config.lease_seconds)
            except LeaseLost:
                if not wake.just_woke():
                    return
                try:
                    await revive_lease(connection, lease, lease_seconds=config.lease_seconds)
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


async def _summary_route(connection: Any, lease: Lease, config: LoopConfig) -> ModelRoute | None:
    """Compaction uses the run's frozen summarizer binding. A different one has no route here."""
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (lease.run_id,)
    )
    snapshot = (await cursor.fetchone())[0]
    bound = snapshot.get("bindings", {}).get("summarizer")
    if bound != config.route.profile:
        return None
    return ModelRoute("summarizer", bound, config.route.wire_id, config.route.worst_case_micro_usd)


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


async def _cancel_stray_child(connection: Any, lease: Lease, child: UUID) -> str:
    cursor = await connection.execute(
        "select status, version from public.runs where id = %s", (child,)
    )
    status, version = await cursor.fetchone()
    try:
        result = await apply_command(
            connection,
            workspace_id=lease.workspace_id,
            run_id=child,
            command=RunCommand.CANCEL,
            actor=Actor.USER,
            expected_version=version,
        )
    except (CommandRefused, VersionConflict):
        # It moved under us. The parent stays queued and looks again.
        return str(status)
    return str(result.status)


async def _settle_children(connection: Any, lease: Lease) -> datetime | None:
    """A cancelled parent's children finish too, and their open assignments close.

    Returns when to try again, if a child still has a live owner. A parent that finished without it
    would leave nothing able to settle that child, as `claim_next` leaves children to their parent.
    """
    cursor = await connection.execute(
        "select a.id, a.child_run_id, r.status from app_private.assignments a "
        "join public.runs r on r.id = a.child_run_id "
        "where a.parent_run_id = %s and a.status = 'open'",
        (lease.run_id,),
    )
    terminal = {RunStatus.CANCELLED.value, RunStatus.FAILED.value, RunStatus.SUCCEEDED.value}
    retry_at: datetime | None = None
    for assignment_id, child, status in await cursor.fetchall():
        if status != RunStatus.CANCELLING.value and status not in terminal:
            # Admitted as the cancel landed, so the cascade missed it. Nothing else would reach it.
            status = await _cancel_stray_child(connection, lease, child)
        if status not in terminal:
            child_lease = await claim_run(connection, child, worker_id=lease.worker_id)
            settled = None
            if child_lease is not None:
                settled = await _finish(
                    connection, child_lease, await load_goal(connection, child), "run_not_running"
                )
            if settled is None or settled.run_status not in terminal:
                # Still owned, or it has children of its own to wait for.
                expiry = await connection.execute(
                    "select greatest(available_at, coalesce(lease_expires_at, available_at), "
                    "clock_timestamp() + interval '5 seconds') "
                    "from app_private.run_jobs where run_id = %s",
                    (child,),
                )
                moment = (await expiry.fetchone())[0]
                retry_at = moment if retry_at is None else max(retry_at, moment)
                continue
        await connection.execute(
            "update app_private.assignments set status = 'finished', outcome = 'cancelled', "
            "finished_at = now() where id = %s",
            (assignment_id,),
        )
    return retry_at


async def _holds_lease(connection: Any, lease: Lease) -> bool:
    cursor = await connection.execute(
        "select 1 from app_private.run_jobs where run_id = %s and generation = %s "
        "and status = 'claimed' and lease_expires_at > clock_timestamp()",
        (lease.run_id, lease.generation),
    )
    return await cursor.fetchone() is not None


async def _finish(
    connection: Any, lease: Lease, goal: GoalSpec, stop_code: str | None
) -> LoopResult:
    view = await plan_view(connection, lease.run_id, goal)
    code = stop_code
    # Whatever stopped this pass, a run being cancelled finishes that. Anything else is refused.
    if code != "lease_lost" and await _run_status(connection, lease) == RunStatus.CANCELLING.value:
        # Settling classifies what's in flight, so a worker that lost the run must not start it.
        code = "run_not_running" if await _holds_lease(connection, lease) else "lease_lost"
    if code is None and not view.finished:
        code = "plan_missing" if view.version is None else "plan_incomplete"
    command: RunCommand | None
    if code == "run_not_running" and await _run_status(connection, lease) == "cancelling":
        # This worker still owns it, and it is the one who settles the cancellation.
        retry_at = await _settle_children(connection, lease)
        if retry_at is not None:
            await connection.execute(
                "update app_private.run_jobs set status = 'queued', lease_owner = null, "
                "lease_expires_at = null, available_at = %s "
                "where run_id = %s and generation = %s and status = 'claimed'",
                (retry_at, lease.run_id, lease.generation),
            )
            return await _result(
                connection, lease, goal, "waiting", "children_settling", RunStatus.CANCELLING.value
            )
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
        if code == "run_not_running" and await _run_status(connection, lease) == "paused":
            # Stopped at a safe boundary. The run waits for a resume with nobody holding it.
            await connection.execute(
                "update app_private.run_jobs set status = 'done', lease_owner = null, "
                "lease_expires_at = null where run_id = %s and generation = %s "
                "and status = 'claimed'",
                (lease.run_id, lease.generation),
            )
    elif code is None:
        command = RunCommand.VERIFY
    elif code in PAUSE_FOR:
        command = RunCommand.SUSPEND
    else:
        command = RunCommand.FAIL
    status = None
    if command is not None:
        cursor = await connection.execute(
            "select version from public.runs where id = %s", (lease.run_id,)
        )
        version = (await cursor.fetchone())[0]
        try:
            # The reason commits with the transition, so a worker that lost the run writes nothing.
            async with connection.transaction():
                result = await apply_command(
                    connection,
                    workspace_id=lease.workspace_id,
                    run_id=lease.run_id,
                    command=command,
                    actor=Actor.WORKER,
                    expected_version=version,
                    generation=lease.generation,
                )
                # A run can stop before its first segment, so the row may not exist yet.
                await connection.execute(
                    "insert into app_private.run_usage (run_id, stop_reason) values (%s, %s) "
                    "on conflict (run_id) do update set stop_reason = excluded.stop_reason",
                    (lease.run_id, code),
                )
            status = result.status
        except (LeaseLost, VersionConflict, CommandRefused):
            code = "lease_lost"
    outcome = (
        "candidate"
        if code is None
        else "waiting"
        if code == "approval_pending"
        else "lost"
        if code in NOT_OURS
        else "stopped"
    )
    return await _result(connection, lease, goal, outcome, code, status)
