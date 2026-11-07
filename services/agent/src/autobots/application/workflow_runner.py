"""Runs one bound execution under a lease, committing each instance as it finishes, PRD 7.3.

Effects go through the tool gateway, so a restart replays them by operation identity and receipt.
Emissions are insert-only, so a replay can't replace an output that was already committed.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ConfigDict

from autobots.application.assignments import Delegation
from autobots.application.goal_loop import (
    LoopConfig,
    LoopResult,
    _finish,
    _keep_lease,
    _result,
    _run_status,
    loop_registry,
)
from autobots.application.plans import load_goal
from autobots.application.recovery import classify_interrupted
from autobots.application.run_usage import ensure_usage
from autobots.application.runs import LeaseLost, VersionConflict, apply_command
from autobots.application.tool_gateway import (
    ToolContext,
    ToolDefinition,
    ToolGateway,
    ToolScope,
    hold_lease,
    ownership_refusal,
)
from autobots.application.worker_leases import Lease
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import DELEGATION_TOOL, OperationClass
from autobots.domain.workflow_execution import (
    BlockFailed,
    GraphShape,
    Step,
    next_steps,
    run_predicate,
    run_transform,
    shape_of,
    unsettled_nodes,
)
from autobots.domain.workflows import validate_graph


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    value: Any = None


class ApprovalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Any = None


async def _release(arguments: ApprovalInput, _: ToolContext) -> ApprovalOutput:
    return ApprovalOutput(value=arguments.value)


# Passing through an approval is the gate itself. Replay finds the decision by operation identity.
APPROVAL_GATE = ToolDefinition(
    tool_id="workflow_approval",
    title="Workflow approval",
    group=ToolGroup.PLANNING,
    public_input_fields=("node",),
    public_output_fields=(),
    version=1,
    description="A workflow's explicit approval step.",
    input_model=ApprovalInput,
    output_model=ApprovalOutput,
    operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
    handler=_release,
    approval_reason="This workflow has an approval step, so policy holds it for a person.",
)
# Not this node's failure: it runs again, and any recorded effect comes back from its receipt.
STOPS = frozenset(
    {
        "approval_pending",
        "outcome_unknown",
        "assignment_paused",
        "lease_lost",
        "run_not_running",
        "run_not_found",
        "assignment_lost",
        "assignment_busy",
    }
)


class _Stop(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def _load_state(
    connection: Any, execution_id: Any
) -> tuple[dict[str, str], dict[tuple[str, str, int], Any]]:
    cursor = await connection.execute(
        "select instance_key, status from public.workflow_node_instances where execution_id = %s",
        (execution_id,),
    )
    statuses = {row[0]: row[1] for row in await cursor.fetchall()}
    cursor = await connection.execute(
        "select instance_key, port, sequence, value from public.workflow_emissions "
        "where execution_id = %s",
        (execution_id,),
    )
    emissions = {(row[0], row[1], row[2]): row[3] for row in await cursor.fetchall()}
    return statuses, emissions


async def _commit(
    connection: Any,
    scope: ToolScope,
    execution_id: Any,
    step: Step,
    status: str,
    outputs: list[tuple[str, int, Any]],
    code: str | None = None,
) -> None:
    """One transaction under the lease. An existing emission stays exactly as it was."""
    async with connection.transaction():
        await hold_lease(connection, scope)
        for port, sequence, value in outputs:
            await connection.execute(
                "insert into public.workflow_emissions (execution_id, instance_key, port, "
                "sequence, value) values (%s, %s, %s, %s, %s) on conflict do nothing",
                (execution_id, step.key, port, sequence, json.dumps(value)),
            )
        await connection.execute(
            "insert into public.workflow_node_instances (execution_id, instance_key, node_id, "
            "iteration, status, error_code) values (%s, %s, %s, %s, %s, %s) "
            "on conflict (execution_id, instance_key) do update set status = excluded.status, "
            "error_code = excluded.error_code, updated_at = now()",
            (execution_id, step.key, step.node_id, step.iteration, status, code),
        )


async def _tool(
    gateway: ToolGateway, connection: Any, scope: ToolScope, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """A stop leaves the instance to run again. Any other refusal is this instance's failure."""
    result = await gateway.execute(connection, scope, name, arguments)
    if result.code in STOPS:
        raise _Stop(str(result.code))
    if result.outcome.value != "succeeded":
        raise BlockFailed(str(result.code or "tool_failed"))
    return result.output or {}


async def _run_block(
    gateway: ToolGateway,
    connection: Any,
    scope: ToolScope,
    node: Any,
    step: Step,
    inputs: dict[str, Any],
) -> list[tuple[str, int, Any]]:
    block, config = node["block"], node.get("config", {})
    value = step.inputs.get("value")
    # Each node instance is its own work, even with the same tool and arguments as another.
    scope = replace(scope, instance=step.key)
    if block == "input":
        return [("value", 0, inputs[step.node_id])]
    if block in {"output", "join"}:
        port = "items" if block == "join" else "value"
        return [(port, 0, value)]
    if block == "transform":
        return [("value", 0, run_transform(config["operation"], value))]
    if block == "condition":
        taken = run_predicate(config["predicate"], value, config["operand"])
        return [("true" if taken else "false", 0, value)]
    if block == "foreach":
        items = step.inputs["items"]
        if len(items) > config["max_items"]:
            raise BlockFailed("foreach_over_bound")
        return [("item", index, item) for index, item in enumerate(items)]
    if block == "read":
        output = await _tool(
            gateway, connection, scope, "read_run_file", {"path": step.inputs["path"]}
        )
        return [("content", 0, output["content"])]
    if block == "artifact":
        path = config["path"]
        if step.iteration is not None:
            stem, dot, suffix = path.rpartition(".")
            path = f"{stem}-{step.iteration}.{suffix}" if dot else f"{path}-{step.iteration}"
        saved = await _tool(
            gateway,
            connection,
            scope,
            "save_artifact",
            {"path": path, "content": step.inputs["content"]},
        )
        published = await _tool(
            gateway,
            connection,
            scope,
            "publish_artifact",
            {"path": path, "version": saved["version"]},
        )
        return [("artifact_id", 0, published["artifact_id"])]
    if block == "approval":
        released = await _tool(
            gateway, connection, scope, "workflow_approval", {"node": step.key, "value": value}
        )
        return [("value", 0, released["value"])]
    if block == "agent":
        result = await _tool(
            gateway,
            connection,
            scope,
            DELEGATION_TOOL,
            {"expert_id": config["expert_id"], "goal": step.inputs["goal"]},
        )
        if result["outcome"] != "succeeded":
            raise BlockFailed(f"agent_{result['outcome']}")
        return [("result", 0, result)]
    raise BlockFailed("unknown_block")


async def _pass(
    gateway: ToolGateway,
    connection: Any,
    scope: ToolScope,
    shape: GraphShape,
    execution_id: Any,
    inputs: dict[str, Any],
    after_commit: Callable[[Step], None],
) -> bool:
    """Decides and runs what can move now. True if anything moved."""
    statuses, emissions = await _load_state(connection, execution_id)
    steps = next_steps(shape, statuses, emissions)
    for step in steps:
        refusal = await ownership_refusal(connection, scope)
        if refusal is not None:
            raise _Stop(refusal)
        if step.decision != "run":
            await _commit(connection, scope, execution_id, step, step.decision, [])
            continue
        node = shape.nodes[step.node_id]
        await connection.execute(
            "update public.workflow_executions set current_instance = %s where id = %s",
            (step.key, execution_id),
        )
        try:
            outputs = await _run_block(gateway, connection, scope, node, step, inputs)
        except BlockFailed as failed:
            await _commit(connection, scope, execution_id, step, "failed", [], failed.code)
            continue
        await _commit(connection, scope, execution_id, step, "succeeded", outputs)
        after_commit(step)
    return bool(steps)


async def run_workflow(
    connection: Any,
    database_url: str,
    lease: Lease,
    model: Any,
    config: LoopConfig,
    *,
    after_commit: Callable[[Step], None] = lambda _: None,
) -> LoopResult:
    cursor = await connection.execute(
        "select e.id, e.inputs, v.graph from public.workflow_executions e "
        "join public.workflow_versions v on v.workflow_id = e.workflow_id "
        "and v.version = e.workflow_version where e.run_id = %s",
        (lease.run_id,),
    )
    execution_id, inputs, graph = await cursor.fetchone()
    goal = await load_goal(connection, lease.run_id)
    await ensure_usage(connection, lease.run_id)
    if validate_graph(graph):
        # Published under older rules. Some shapes lose data, so it fails rather than running.
        await classify_interrupted(connection, lease.run_id, lease.generation)
        return await _finish(connection, lease, goal, "workflow_invalid")
    scope = ToolScope(
        lease.workspace_id,
        lease.run_id,
        lease.generation,
        goal.allowed_tools,
        tuple(goal.allowed_paths),
    )

    async def drive_child(child_connection: Any, child_lease: Lease) -> LoopResult:
        from autobots.application.goal_loop import _drive

        return await _drive(child_connection, database_url, child_lease, lambda: model, config)

    delegation = Delegation(drive_child, config.limits, config.lease_seconds, config.sleep)
    registry = loop_registry(
        config.limits, config.object_store, delegation, (*config.tools, APPROVAL_GATE)
    )
    gateway = ToolGateway(registry)
    shape = shape_of(graph)
    beating = asyncio.create_task(_keep_lease(database_url, lease, config))
    code: str | None = None
    try:
        while await _pass(gateway, connection, scope, shape, execution_id, inputs, after_commit):
            pass
    except _Stop as stop:
        code = stop.code
    except LeaseLost:
        code = "lease_lost"
    finally:
        beating.cancel()
    if code is not None:
        return await _finish(connection, lease, goal, code)
    statuses, _ = await _load_state(connection, execution_id)
    if any(status == "failed" for status in statuses.values()):
        return await _finish(connection, lease, goal, "workflow_node_failed")
    if unsettled_nodes(shape, statuses):
        # Nothing can move, and this isn't finished. That's a failure, never a success.
        return await _finish(connection, lease, goal, "workflow_stalled")
    return await _complete(connection, lease, goal)


async def _complete(connection: Any, lease: Lease, goal: Any) -> LoopResult:
    """A workflow finishes when every instance is settled, through the normal transitions.

    A worker can die between the two, so a run already verifying only needs the second.
    """
    status = await _run_status(connection, lease)
    if status == RunStatus.CANCELLING.value:
        return await _finish(connection, lease, goal, "run_not_running")
    commands = (
        (RunCommand.COMPLETE,)
        if status == RunStatus.VERIFYING.value
        else (RunCommand.VERIFY, RunCommand.COMPLETE)
    )
    try:
        for command in commands:
            cursor = await connection.execute(
                "select version from public.runs where id = %s", (lease.run_id,)
            )
            result = await apply_command(
                connection,
                workspace_id=lease.workspace_id,
                run_id=lease.run_id,
                command=command,
                actor=Actor.WORKER,
                expected_version=(await cursor.fetchone())[0],
                generation=lease.generation,
            )
    except LeaseLost:
        return await _result(connection, lease, goal, "lost", "lease_lost", None)
    except (CommandRefused, VersionConflict):
        # Someone cancelled or paused after that check. `_finish` settles whichever it was.
        return await _finish(connection, lease, goal, "run_not_running")
    return await _result(connection, lease, goal, "succeeded", None, result.status)
