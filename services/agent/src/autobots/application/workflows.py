"""Publishing immutable workflow versions, and binding executions to them exactly, PRD 7.3."""

import json
from typing import Any
from uuid import UUID, uuid4

from autobots.application.runs import existing_receipt, request_hash, store_receipt
from autobots.contracts.workflows import (
    ExecutionBinding,
    WorkflowGraph,
    WorkflowVersionView,
    WorkflowView,
)
from autobots.domain.workflows import (
    GraphError,
    block_versions,
    graph_hash,
    input_errors,
    validate_graph,
)


class WorkflowRefused(Exception):
    def __init__(self, code: str, errors: list[GraphError] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.errors = errors or []


def _plain(graph: WorkflowGraph) -> dict[str, Any]:
    return graph.model_dump(mode="json")


async def _view(connection: Any, workflow_id: UUID, name: str, latest: int) -> WorkflowView:
    cursor = await connection.execute(
        "select version, graph_hash, source, graph, block_versions "
        "from public.workflow_versions where workflow_id = %s order by version",
        (workflow_id,),
    )
    versions = [
        WorkflowVersionView(
            version=row[0],
            graph_hash=row[1],
            source=row[2],
            graph=WorkflowGraph.model_validate(row[3]),
            block_versions=row[4],
        )
        for row in await cursor.fetchall()
    ]
    return WorkflowView(
        schema_version=1, id=workflow_id, name=name, latest_version=latest, versions=versions
    )


async def get_workflow(connection: Any, workspace_id: UUID, workflow_id: UUID) -> WorkflowView:
    cursor = await connection.execute(
        "select id, name, latest_version from public.workflows where id = %s and workspace_id = %s",
        (workflow_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise WorkflowRefused("workflow_not_found")
    return await _view(connection, *row)


async def list_workflows(connection: Any, workspace_id: UUID) -> list[WorkflowView]:
    cursor = await connection.execute(
        "select id, name, latest_version from public.workflows "
        "where workspace_id = %s order by name",
        (workspace_id,),
    )
    return [await _view(connection, *row) for row in await cursor.fetchall()]


async def create_workflow(
    connection: Any, *, workspace_id: UUID, actor_id: UUID, idempotency_key: str, name: str
) -> WorkflowView:
    fingerprint = request_hash({"name": name})
    scope = (workspace_id, actor_id, "create_workflow", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_workflow(connection, workspace_id, UUID(existing["workflow_id"]))
        cursor = await connection.execute(
            "select 1 from public.workflows where workspace_id = %s and name = %s",
            (workspace_id, name),
        )
        if await cursor.fetchone() is not None:
            raise WorkflowRefused("workflow_name_taken")
        workflow_id = uuid4()
        await connection.execute(
            "insert into public.workflows (id, workspace_id, name) values (%s, %s, %s)",
            (workflow_id, workspace_id, name),
        )
        await store_receipt(connection, scope, fingerprint, {"workflow_id": str(workflow_id)})
    return await get_workflow(connection, workspace_id, workflow_id)


async def publish_version(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    expected_version: int,
    graph: WorkflowGraph,
    source: str,
) -> WorkflowView:
    """A model's proposal goes through the same validation, and is marked as what it is."""
    plain = _plain(graph)
    errors = validate_graph(plain)
    if errors:
        raise WorkflowRefused("workflow_invalid", errors)
    digest = graph_hash(plain)
    fingerprint = request_hash({"expected": expected_version, "graph": digest, "source": source})
    scope = (workspace_id, actor_id, "publish_workflow", str(workflow_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_workflow(connection, workspace_id, workflow_id)
        cursor = await connection.execute(
            "select latest_version from public.workflows "
            "where id = %s and workspace_id = %s for update",
            (workflow_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise WorkflowRefused("workflow_not_found")
        if row[0] != expected_version:
            raise WorkflowRefused("workflow_version_conflict")
        version = row[0] + 1
        await connection.execute(
            "insert into public.workflow_versions (workflow_id, version, graph, graph_hash, "
            "block_versions, source, created_by) values (%s, %s, %s, %s, %s, %s, %s)",
            (
                workflow_id,
                version,
                json.dumps(plain),
                digest,
                json.dumps(block_versions(plain)),
                source,
                actor_id,
            ),
        )
        await connection.execute(
            "update public.workflows set latest_version = %s where id = %s", (version, workflow_id)
        )
        await store_receipt(connection, scope, fingerprint, {"version": version})
    return await get_workflow(connection, workspace_id, workflow_id)


async def create_execution(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    workflow_id: UUID,
    idempotency_key: str,
    version: int,
    inputs: dict[str, Any],
) -> ExecutionBinding:
    """An execution always names one exact version and hash. Later versions don't reach it."""
    cursor = await connection.execute(
        "select v.graph, v.graph_hash, v.block_versions from public.workflow_versions v "
        "join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (workflow_id, version, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise WorkflowRefused("workflow_version_not_found")
    graph, digest, blocks = row
    errors = input_errors(graph, inputs)
    if errors:
        raise WorkflowRefused("workflow_inputs_invalid", errors)
    fingerprint = request_hash({"version": version, "inputs": inputs})
    scope = (workspace_id, actor_id, "create_execution", str(workflow_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        execution_id = UUID(existing["execution_id"]) if existing else uuid4()
        if existing is None:
            await connection.execute(
                "insert into public.workflow_executions (id, workspace_id, workflow_id, "
                "workflow_version, graph_hash, block_versions, inputs, created_by) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    execution_id,
                    workspace_id,
                    workflow_id,
                    version,
                    digest,
                    json.dumps(blocks),
                    json.dumps(inputs),
                    actor_id,
                ),
            )
            await store_receipt(connection, scope, fingerprint, {"execution_id": str(execution_id)})
    return ExecutionBinding(
        schema_version=1,
        id=execution_id,
        workflow_id=workflow_id,
        workflow_version=version,
        graph_hash=digest,
        block_versions=blocks,
    )
