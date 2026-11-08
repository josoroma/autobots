"""The factory stays pure: no resources, no network and no credential."""

import socket

import pytest

from autobots.api.app import create_app
from conftest import SocketBlockedError


def test_sockets_are_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.create_connection(("127.0.0.1", 9))
    with socket.socket() as probe, pytest.raises(SocketBlockedError):
        probe.connect(("127.0.0.1", 9))


def test_the_schema_builds_without_any_connection() -> None:
    assert set(create_app().openapi()["paths"]) == {
        "/v1/health",
        "/v1/models",
        "/v1/approvals",
        "/v1/approvals/count",
        "/v1/approvals/{approval_id}/decision",
        "/v1/improvements",
        "/v1/operations/local-status",
        "/v1/operations/retention",
        "/v1/operations/retention/apply",
        "/v1/improvements/{candidate_id}/decision",
        "/v1/improvements/{candidate_id}/regression",
        "/v1/improvements/{candidate_id}/replay",
        "/v1/knowledge/rollback",
        "/v1/memory",
        "/v1/memory/search",
        "/v1/routines",
        "/v1/routines/{routine_id}",
        "/v1/routines/{routine_id}/enabled",
        "/v1/routines/{routine_id}/versions",
        "/v1/workflow-blocks",
        "/v1/workflow-executions/{execution_id}",
        "/v1/workflows",
        "/v1/workflows/validate",
        "/v1/workflows/{workflow_id}",
        "/v1/workflows/{workflow_id}/executions",
        "/v1/workflows/{workflow_id}/versions",
        "/v1/experts",
        "/v1/experts/{expert_id}",
        "/v1/experts/{expert_id}/versions",
        "/v1/sessions",
        "/v1/sessions/{session_id}",
        "/v1/runs",
        "/v1/runs/intent",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/artifacts",
        "/v1/runs/{run_id}/cancel",
        "/v1/runs/{run_id}/effects/{operation_id}/reconcile",
        "/v1/runs/{run_id}/events",
        "/v1/runs/{run_id}/input",
        "/v1/runs/{run_id}/model-calls/reconcile",
        "/v1/runs/{run_id}/pause",
        "/v1/runs/{run_id}/resume",
        "/v1/runs/{run_id}/inspector",
        "/v1/runs/{run_id}/tool-uses",
        "/v1/runs/{run_id}/workspace",
        "/v1/profile",
        "/v1/readiness",
        "/v1/session",
        "/v1/settings/model-policy",
        "/v1/settings/model-policy/reset",
        "/v1/settings/model-providers",
        "/v1/settings/model-providers/openrouter/credential",
        "/v1/settings/model-providers/openrouter/validate",
        "/v1/tools",
        "/v1/tools/{tool_id}",
        "/v1/tools/{tool_id}/grants",
        "/v1/tools/{tool_id}/versions/{version}",
        "/v1/workspaces/{workspace_id}",
    }


def test_each_call_builds_a_new_app() -> None:
    assert create_app() is not create_app()


@pytest.mark.asyncio
async def test_lifespan_enters_and_leaves() -> None:
    app = create_app()
    stages = []
    async with app.router.lifespan_context(app):
        stages.append("entered")
    stages.append("left")
    assert stages == ["entered", "left"]
