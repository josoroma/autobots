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
        "/v1/runs",
        "/v1/runs/intent",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/artifacts",
        "/v1/runs/{run_id}/cancel",
        "/v1/runs/{run_id}/events",
        "/v1/runs/{run_id}/input",
        "/v1/runs/{run_id}/model-calls/reconcile",
        "/v1/runs/{run_id}/pause",
        "/v1/runs/{run_id}/resume",
        "/v1/runs/{run_id}/workspace",
        "/v1/session",
        "/v1/settings/model-policy",
        "/v1/settings/model-providers",
        "/v1/settings/model-providers/openrouter/credential",
        "/v1/settings/model-providers/openrouter/validate",
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
