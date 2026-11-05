"""Workflow validation, publication and execution binding. Publishing changes what can run."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.runs import IdempotencyConflict
from autobots.application.workflows import (
    WorkflowRefused,
    create_execution,
    create_workflow,
    get_workflow,
    list_workflows,
    publish_version,
)
from autobots.contracts.workflows import (
    ExecutionBinding,
    ExecutionCreate,
    WorkflowCreate,
    WorkflowErrorView,
    WorkflowGraph,
    WorkflowList,
    WorkflowPublish,
    WorkflowValidation,
    WorkflowView,
)
from autobots.domain.workflows import GraphError, graph_hash, validate_graph

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
Member = Annotated[UUID, Depends(current_workspace)]
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _views(errors: list[GraphError]) -> list[WorkflowErrorView]:
    return [WorkflowErrorView(code=e.code, node=e.node, port=e.port) for e in errors]


def _error(error: WorkflowRefused | IdempotencyConflict) -> ApiError:
    if isinstance(error, IdempotencyConflict):
        return ApiError(409, error.code, "This key was already used with different content.")
    if error.code.endswith("not_found"):
        return ApiError(404, error.code, "That workflow is not available.")
    if error.code in {"workflow_invalid", "workflow_inputs_invalid"}:
        codes = ", ".join(sorted({item.code for item in error.errors}))
        return ApiError(422, error.code, f"That isn't valid: {codes}.")
    return ApiError(409, error.code, "That conflicts with what is saved. Reload and try again.")


@router.post(
    "/workflows/validate", operation_id="validateWorkflow", response_model=WorkflowValidation
)
async def post_validate(graph: WorkflowGraph, _: Member) -> WorkflowValidation:
    plain = graph.model_dump(mode="json")
    errors = validate_graph(plain)
    return WorkflowValidation(
        schema_version=1,
        valid=not errors,
        errors=_views(errors),
        graph_hash=None if errors else graph_hash(plain),
    )


@router.get("/workflows", operation_id="listWorkflows", response_model=WorkflowList)
async def get_workflows(request: Request, workspace: Member) -> WorkflowList:
    async with _pool(request).connection() as connection:
        return WorkflowList(schema_version=1, workflows=await list_workflows(connection, workspace))


@router.post(
    "/workflows",
    operation_id="createWorkflow",
    response_model=WorkflowView,
    status_code=status.HTTP_201_CREATED,
)
async def post_workflow(
    body: WorkflowCreate, request: Request, key: Key, workspace: Owner, user: User
) -> WorkflowView:
    async with _pool(request).connection() as connection:
        try:
            return await create_workflow(
                connection,
                workspace_id=workspace,
                actor_id=user,
                idempotency_key=key,
                name=body.name,
            )
        except (WorkflowRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.get("/workflows/{workflow_id}", operation_id="getWorkflow", response_model=WorkflowView)
async def read_workflow(workflow_id: UUID, request: Request, workspace: Member) -> WorkflowView:
    async with _pool(request).connection() as connection:
        try:
            return await get_workflow(connection, workspace, workflow_id)
        except WorkflowRefused as error:
            raise _error(error) from None


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
    key: Key,
    workspace: Owner,
    user: User,
) -> WorkflowView:
    async with _pool(request).connection() as connection:
        try:
            return await publish_version(
                connection,
                workspace_id=workspace,
                actor_id=user,
                workflow_id=workflow_id,
                idempotency_key=key,
                expected_version=body.expected_version,
                graph=body.graph,
                source=body.source,
            )
        except (WorkflowRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.post(
    "/workflows/{workflow_id}/executions",
    operation_id="createWorkflowExecution",
    response_model=ExecutionBinding,
    status_code=status.HTTP_201_CREATED,
)
async def post_execution(
    workflow_id: UUID,
    body: ExecutionCreate,
    request: Request,
    key: Key,
    workspace: Member,
    user: User,
) -> ExecutionBinding:
    async with _pool(request).connection() as connection:
        try:
            return await create_execution(
                connection,
                workspace_id=workspace,
                actor_id=user,
                workflow_id=workflow_id,
                idempotency_key=key,
                version=body.version,
                inputs=body.inputs,
                documents=tuple(body.documents),
            )
        except (WorkflowRefused, IdempotencyConflict) as error:
            raise _error(error) from None
