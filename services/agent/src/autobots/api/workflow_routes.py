"""Workflow validation, publication and execution binding. Publishing changes what can run."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from autobots.api.dependencies import (
    CurrentUser,
    IdempotencyKey,
    MemberWorkspace,
    ModelKeyCheck,
    OwnerWorkspace,
    require_ready,
)
from autobots.api.errors import ApiError, reworded
from autobots.api.pool import request_pool
from autobots.api.security import require_internal
from autobots.application.run_admission import ModelNotReady, chosen_limit, require_model_ready
from autobots.application.workflow_overview import preview_steps, recent_executions
from autobots.application.workflows import (
    DEFAULT_LIMIT_MICRO_USD,
    create_execution,
    create_workflow,
    discard_draft,
    get_workflow,
    list_workflows,
    needs_model,
    publish_draft,
    publish_version,
    read_execution,
    save_draft,
    set_description,
)
from autobots.contracts.workflows import (
    BlockCatalog,
    BlockView,
    ExecutionBinding,
    ExecutionCreate,
    ExecutionView,
    WorkflowCreate,
    WorkflowDescription,
    WorkflowDraftPublish,
    WorkflowDraftSave,
    WorkflowErrorView,
    WorkflowExecutionList,
    WorkflowGraph,
    WorkflowList,
    WorkflowPreview,
    WorkflowPublish,
    WorkflowValidation,
    WorkflowView,
)
from autobots.domain.workflows import (
    BLOCKS,
    GraphError,
    graph_hash,
    ir_normalized,
    validate_graph,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def _views(errors: list[GraphError]) -> list[WorkflowErrorView]:
    return [WorkflowErrorView(code=e.code, node=e.node, port=e.port) for e in errors]


DRAFT_NOT_RUNNABLE = "draft_not_runnable"


@router.get("/workflow-blocks", operation_id="listWorkflowBlocks", response_model=BlockCatalog)
async def get_blocks(_: MemberWorkspace) -> BlockCatalog:
    return BlockCatalog(
        schema_version=1,
        blocks=[
            BlockView(
                block=block,
                version=version,
                inputs=[f"{name}: {kind}" for name, kind in spec.inputs.items()],
                outputs=[
                    f"{name}: {'declared in config' if kind.startswith('config') else kind}"
                    for name, kind in spec.outputs.items()
                ],
            )
            for block, versions in BLOCKS.items()
            for version, spec in versions.items()
        ],
    )


@router.get(
    "/workflow-executions/{execution_id}",
    operation_id="getWorkflowExecution",
    response_model=ExecutionView,
)
async def get_execution(
    execution_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> ExecutionView:
    async with request_pool(request).connection() as connection:
        return await read_execution(connection, workspace_id, execution_id)


@router.post(
    "/workflows/validate", operation_id="validateWorkflow", response_model=WorkflowValidation
)
async def post_validate(graph: WorkflowGraph, _: MemberWorkspace) -> WorkflowValidation:
    plain = ir_normalized(graph.model_dump(mode="json"))
    errors = validate_graph(plain)
    return WorkflowValidation(
        schema_version=1,
        valid=not errors,
        errors=_views(errors),
        graph_hash=None if errors else graph_hash(plain),
    )


@router.get("/workflows", operation_id="listWorkflows", response_model=WorkflowList)
async def get_workflows(request: Request, workspace_id: MemberWorkspace) -> WorkflowList:
    async with request_pool(request).connection() as connection:
        return WorkflowList(
            schema_version=1, workflows=await list_workflows(connection, workspace_id)
        )


@router.post(
    "/workflows",
    operation_id="createWorkflow",
    response_model=WorkflowView,
    status_code=status.HTTP_201_CREATED,
)
async def post_workflow(
    body: WorkflowCreate,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await create_workflow(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            idempotency_key=idempotency_key,
            name=body.name,
            description=body.description,
        )


@router.get(
    "/workflows/{workflow_id}/executions",
    operation_id="listWorkflowExecutions",
    response_model=WorkflowExecutionList,
)
async def get_executions(
    workflow_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> WorkflowExecutionList:
    """WF-04: the ten newest executions, with version, state, spend and duration."""
    async with request_pool(request).connection() as connection:
        await get_workflow(connection, workspace_id, workflow_id)
        executions = await recent_executions(connection, workspace_id, workflow_id)
    return WorkflowExecutionList(schema_version=1, executions=executions)


@router.get(
    "/workflows/{workflow_id}/preview",
    operation_id="previewWorkflowVersion",
    response_model=WorkflowPreview,
)
async def get_preview(
    workflow_id: UUID, version: str, request: Request, workspace_id: MemberWorkspace
) -> WorkflowPreview:
    """WF-03: a published version's steps, or the draft's, with `version=draft`."""
    async with request_pool(request).connection() as connection:
        view = await get_workflow(connection, workspace_id, workflow_id)
        if version == "draft":
            if view.draft is None:
                raise ApiError(404, "workflow_draft_not_found", "This workflow has no saved draft.")
            graph = view.draft.graph
            shown: int | Literal["draft"] = "draft"
        else:
            found = next((item for item in view.versions if str(item.version) == version), None)
            if found is None:
                raise ApiError(404, "workflow_version_not_found", "That version doesn't exist.")
            graph, shown = found.graph, found.version
        steps = await preview_steps(
            connection, workspace_id, ir_normalized(graph.model_dump(mode="json"))
        )
    return WorkflowPreview(schema_version=1, version=shown, steps=steps)


@router.put(
    "/workflows/{workflow_id}/draft", operation_id="saveWorkflowDraft", response_model=WorkflowView
)
async def put_draft(
    workflow_id: UUID,
    body: WorkflowDraftSave,
    request: Request,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> WorkflowView:
    """WF-02: an owner keeps one draft, replaced by each save."""
    async with request_pool(request).connection() as connection:
        return await save_draft(connection, workspace_id, user_id, workflow_id, body.graph)


@router.delete(
    "/workflows/{workflow_id}/draft",
    operation_id="discardWorkflowDraft",
    response_model=WorkflowView,
)
async def delete_draft(
    workflow_id: UUID, request: Request, workspace_id: OwnerWorkspace
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await discard_draft(connection, workspace_id, workflow_id)


@router.post(
    "/workflows/{workflow_id}/draft/publish",
    operation_id="publishWorkflowDraft",
    response_model=WorkflowView,
    status_code=status.HTTP_201_CREATED,
)
async def post_draft_publish(
    workflow_id: UUID,
    body: WorkflowDraftPublish,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await publish_draft(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            expected_version=body.expected_version,
        )


@router.put(
    "/workflows/{workflow_id}/description",
    operation_id="setWorkflowDescription",
    response_model=WorkflowView,
)
async def put_description(
    workflow_id: UUID, body: WorkflowDescription, request: Request, workspace_id: OwnerWorkspace
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await set_description(connection, workspace_id, workflow_id, body.description)


@router.get("/workflows/{workflow_id}", operation_id="getWorkflow", response_model=WorkflowView)
async def read_workflow(
    workflow_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await get_workflow(connection, workspace_id, workflow_id)


@router.post(
    "/workflows/{workflow_id}/versions",
    operation_id="publishWorkflowVersion",
    response_model=WorkflowView,
    status_code=status.HTTP_201_CREATED,
)
async def post_version(
    workflow_id: UUID,
    body: WorkflowPublish,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> WorkflowView:
    async with request_pool(request).connection() as connection:
        return await publish_version(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            expected_version=body.expected_version,
            graph=body.graph,
            source=body.source,
        )


@router.post(
    "/workflows/{workflow_id}/executions",
    operation_id="createWorkflowExecution",
    response_model=ExecutionBinding,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ready)],
)
async def post_execution(
    workflow_id: UUID,
    body: ExecutionCreate,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: MemberWorkspace,
    user_id: CurrentUser,
    model_key: ModelKeyCheck,
) -> ExecutionBinding:
    if body.version == "draft":
        raise ApiError(409, DRAFT_NOT_RUNNABLE, "Only a published version can run.")
    pool = request_pool(request)
    async with pool.connection() as connection:
        # WF-05: the same budget rules as a goal run (Decision 0022 D11).
        limit = await chosen_limit(
            connection, workspace_id, body.budget_micro_usd, otherwise=DEFAULT_LIMIT_MICRO_USD
        )
        # A workflow with no agent step calls no model, so it needs no key.
        needed = await needs_model(connection, workspace_id, workflow_id, body.version)
    # Between this request's connections, which it holds one at a time (PAPI-11).
    try:
        await require_model_ready(model_key, workspace_id, needed=needed)
    except ModelNotReady as refused:
        raise reworded(refused, "An agent step needs a usable OpenRouter key.") from None
    async with pool.connection() as connection:
        return await create_execution(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            started_by=user_id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            version=body.version,
            inputs=body.inputs,
            documents=tuple(body.documents),
            limit_micro_usd=limit,
        )
