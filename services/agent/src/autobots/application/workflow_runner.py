"""Runs one bound execution under a lease, committing each instance as it finishes, PRD 7.3.

Effects go through the tool gateway, so a restart replays them by operation identity and receipt.
Emissions are insert-only, so a replay can't replace an output that was already committed. It
builds on the shared run lifecycle and never imports the goal loop, which passes in how an agent
step's child is driven (PPRD-02). Each block kind runs from one of two tables: the domain's pure
blocks, or this module's tool-backed ones (PPRD-06).
"""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any
from uuid import UUID

from autobots.application.assignments import Delegation
from autobots.application.plans import load_goal
from autobots.application.recovery import classify_interrupted
from autobots.application.run_lifecycle import (
    Drive,
    LoopConfig,
    LoopResult,
    finish,
    lease_heartbeat,
    pass_registry,
    result_of,
    run_status,
)
from autobots.application.run_usage import ensure_usage
from autobots.application.runs import LeaseLost, VersionConflict, apply_worker_command
from autobots.application.sql import SqlConnection, all_rows, required_row
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ToolGateway, hold_lease, ownership_refusal
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.domain.runs import CommandRefused, RunCommand, RunStatus
from autobots.domain.stops import STOPS, GatewayCode, PassOutcome, StopCode
from autobots.domain.tools import (
    DELEGATION_TOOL,
    PUBLISH_ARTIFACT_TOOL,
    READ_RUN_FILE_TOOL,
    SAVE_ARTIFACT_TOOL,
    WORKFLOW_APPROVAL_TOOL,
    ToolOutcome,
)
from autobots.domain.workflow_execution import (
    PURE_BLOCKS,
    BlockFailed,
    Emission,
    GraphShape,
    InstanceStatus,
    Step,
    next_steps,
    shape_of,
    typed_config,
    unsettled_nodes,
)
from autobots.domain.workflows import (
    AgentConfig,
    ArtifactConfig,
    Block,
    BlockConfig,
    Node,
    validate_graph,
)
from autobots.persistence.rows import EmittedValueRow, RunExecutionRow


class InstanceStopped(Exception):
    """A node instance stopped without failing, so it runs again once the run continues. `code`
    is the run's stop code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def _load_state(
    connection: SqlConnection, execution_id: UUID
) -> tuple[dict[str, str], dict[tuple[str, str, int], Any]]:
    cursor = await connection.execute(
        "select instance_key, status from public.workflow_node_instances where execution_id = %s",
        (execution_id,),
    )
    statuses = {row[0]: row[1] for row in await cursor.fetchall()}
    emitted = await all_rows(
        connection,
        EmittedValueRow,
        "select instance_key, port, sequence, value from public.workflow_emissions "
        "where execution_id = %s",
        (execution_id,),
    )
    emissions = {(row.instance_key, row.port, row.sequence): row.value for row in emitted}
    return statuses, emissions


async def commit_instance(
    connection: SqlConnection,
    scope: ToolScope,
    execution_id: UUID,
    step: Step,
    status: str,
    outputs: Sequence[tuple[str, int, object]],
    code: str | None = None,
) -> None:
    """Commits one node instance's status and emissions in one transaction under the lease, which a
    stale generation can't pass (SP-012). An existing emission stays exactly as it was."""
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


async def call_tool(
    gateway: ToolGateway,
    connection: SqlConnection,
    scope: ToolScope,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """A stop leaves the instance to run again, and any recorded effect comes back from its receipt.
    A code that would release or suspend the run is a stop, parent_not_running included, so a pause
    inside an assignment's creation never fails the node (PPRD-03). Any other refusal is this
    instance's failure."""
    result = await gateway.execute(connection, scope, name, arguments)
    if result.code in STOPS:
        raise InstanceStopped(str(result.code))
    if result.outcome is not ToolOutcome.SUCCEEDED:
        raise BlockFailed(str(result.code or GatewayCode.TOOL_FAILED))
    return result.output or {}


@dataclass(frozen=True)
class BlockExecution:
    """What a tool-backed block needs of its execution: the gateway, the connection and the
    run's scope, keyed to the instance it runs for."""

    gateway: ToolGateway
    connection: SqlConnection
    scope: ToolScope
    inputs: Mapping[str, object]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await call_tool(self.gateway, self.connection, self.scope, name, arguments)


async def _read(execution: BlockExecution, _config: BlockConfig, step: Step) -> list[Emission]:
    output = await execution.call(READ_RUN_FILE_TOOL, {"path": step.inputs["path"]})
    return [Emission("content", 0, output["content"])]


async def _artifact(execution: BlockExecution, config: BlockConfig, step: Step) -> list[Emission]:
    """An iteration's file is its own, named with its iteration before the suffix."""
    path = typed_config(config, ArtifactConfig).path
    if step.iteration is not None:
        stem, dot, suffix = path.rpartition(".")
        path = f"{stem}-{step.iteration}.{suffix}" if dot else f"{path}-{step.iteration}"
    saved = await execution.call(
        SAVE_ARTIFACT_TOOL, {"path": path, "content": step.inputs["content"]}
    )
    published = await execution.call(
        PUBLISH_ARTIFACT_TOOL, {"path": path, "version": saved["version"]}
    )
    return [Emission("artifact_id", 0, published["artifact_id"])]


async def _approval(execution: BlockExecution, _config: BlockConfig, step: Step) -> list[Emission]:
    released = await execution.call(
        WORKFLOW_APPROVAL_TOOL, {"node": step.key, "value": step.inputs.get("value")}
    )
    return [Emission("value", 0, released["value"])]


async def _agent(execution: BlockExecution, config: BlockConfig, step: Step) -> list[Emission]:
    expert_id = typed_config(config, AgentConfig).expert_id
    result = await execution.call(
        DELEGATION_TOOL, {"expert_id": expert_id, "goal": step.inputs["goal"]}
    )
    if result["outcome"] != PassOutcome.SUCCEEDED:
        raise BlockFailed(f"agent_{result['outcome']}")
    return [Emission("result", 0, result)]


# The tool-backed blocks. The pure rest are the domain's PURE_BLOCKS, and together the two cover
# BLOCKS exactly (tests/test_workflow_block_rules.py).
ToolBlock = Callable[[BlockExecution, BlockConfig, Step], Awaitable[list[Emission]]]
TOOL_BLOCKS: Mapping[Block, ToolBlock] = MappingProxyType(
    {
        Block.READ: _read,
        Block.ARTIFACT: _artifact,
        Block.APPROVAL: _approval,
        Block.AGENT: _agent,
    }
)


async def run_block(execution: BlockExecution, node: Node, step: Step) -> list[Emission]:
    pure = PURE_BLOCKS.get(node.block)
    if pure is not None:
        return pure(node.config, step, execution.inputs)
    run = TOOL_BLOCKS.get(node.block)
    if run is None:
        raise BlockFailed("unknown_block")
    # Each node instance is its own work, even with the same tool and arguments as another.
    keyed = replace(execution, scope=replace(execution.scope, instance=step.key))
    return await run(keyed, node.config, step)


async def run_pass(
    execution: BlockExecution,
    shape: GraphShape,
    execution_id: UUID,
    after_commit: Callable[[Step], None],
) -> bool:
    """Decides and runs what can move now. True if anything moved."""
    connection, scope = execution.connection, execution.scope
    statuses, emissions = await _load_state(connection, execution_id)
    steps = next_steps(shape, statuses, emissions)
    for step in steps:
        refusal = await ownership_refusal(connection, scope)
        if refusal is not None:
            raise InstanceStopped(refusal)
        if step.decision != "run":
            await commit_instance(connection, scope, execution_id, step, step.decision, [])
            continue
        await connection.execute(
            "update public.workflow_executions set current_instance = %s where id = %s",
            (step.key, execution_id),
        )
        try:
            outputs = await run_block(execution, shape.nodes[step.node_id], step)
        except BlockFailed as failed:
            await commit_instance(
                connection, scope, execution_id, step, InstanceStatus.FAILED.value, [], failed.code
            )
            continue
        await commit_instance(
            connection, scope, execution_id, step, InstanceStatus.SUCCEEDED.value, outputs
        )
        after_commit(step)
    return bool(steps)


async def run_workflow(
    connection: SqlConnection,
    database_url: str,
    lease: Lease,
    model: Any,
    config: LoopConfig,
    *,
    drive: Drive,
    after_commit: Callable[[Step], None] = lambda _: None,
) -> LoopResult:
    """Runs what can move until nothing can, then finishes the run through `finish` or
    `complete_workflow`. `drive` is how an agent step's child is driven, and the worker's job
    dispatch passes its own. It is required, so no caller can leave an agent step without one and
    fail its run for good (SP-010)."""

    async def drive_child(child_connection: SqlConnection, child_lease: Lease) -> LoopResult:
        return await drive(child_connection, database_url, child_lease, lambda: model, config)

    delegation = Delegation(drive_child, config.limits, config.lease_seconds, config.sleep)
    # The process's tool set, with this workflow's approval step (workflow_approval.py). Built
    # first, so a process that composed no tools stops before anything is written.
    gateway = ToolGateway(pass_registry(config, delegation, workflow=True))
    bound = await required_row(
        connection,
        RunExecutionRow,
        "select e.id, e.inputs, v.graph from public.workflow_executions e "
        "join public.workflow_versions v on v.workflow_id = e.workflow_id "
        "and v.version = e.workflow_version where e.run_id = %s",
        (lease.run_id,),
    )
    execution_id, inputs, graph = bound.id, bound.inputs, bound.graph
    goal = await load_goal(connection, lease.run_id)
    await ensure_usage(connection, lease.run_id)
    if validate_graph(graph):
        # Published under older rules. Some shapes lose data, so it fails rather than running.
        await classify_interrupted(connection, lease.run_id, lease.generation)
        return await finish(connection, lease, goal, StopCode.WORKFLOW_INVALID)
    scope = ToolScope(
        lease.workspace_id,
        lease.run_id,
        lease.generation,
        goal.allowed_tools,
        tuple(goal.allowed_paths),
    )

    shape = shape_of(graph)
    execution = BlockExecution(gateway, connection, scope, inputs)
    code: str | None = None
    try:
        async with lease_heartbeat(database_url, lease, config):
            while await run_pass(execution, shape, execution_id, after_commit):
                pass
    except InstanceStopped as stop:
        code = stop.code
    except LeaseLost:
        code = StopCode.LEASE_LOST
    if code is not None:
        return await finish(connection, lease, goal, code)
    statuses, _ = await _load_state(connection, execution_id)
    if any(status == InstanceStatus.FAILED for status in statuses.values()):
        return await finish(connection, lease, goal, StopCode.WORKFLOW_NODE_FAILED)
    if unsettled_nodes(shape, statuses):
        # Nothing can move, and this isn't finished. That's a failure, never a success.
        return await finish(connection, lease, goal, StopCode.WORKFLOW_STALLED)
    return await complete_workflow(connection, lease, goal)


async def complete_workflow(connection: SqlConnection, lease: Lease, goal: GoalSpec) -> LoopResult:
    """A workflow finishes when every instance is settled, through the normal transitions.

    A worker can die between the two, so a run already verifying only needs the second.
    """
    status = await run_status(connection, lease)
    if status == RunStatus.CANCELLING.value:
        return await finish(connection, lease, goal, StopCode.RUN_NOT_RUNNING)
    commands = (
        (RunCommand.COMPLETE,)
        if status == RunStatus.VERIFYING.value
        else (RunCommand.VERIFY, RunCommand.COMPLETE)
    )
    try:
        for command in commands:
            result = await apply_worker_command(connection, lease, command)
    except LeaseLost:
        return await result_of(connection, lease, goal, PassOutcome.LOST, StopCode.LEASE_LOST, None)
    except (CommandRefused, VersionConflict):
        # Someone cancelled or paused after that check. `finish` settles whichever it was.
        return await finish(connection, lease, goal, StopCode.RUN_NOT_RUNNING)
    return await result_of(connection, lease, goal, PassOutcome.SUCCEEDED, None, result.status)
