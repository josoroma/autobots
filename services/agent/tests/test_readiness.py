"""US-15.3: member-readable readiness, with states and codes only and no model call."""

import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from autobots.api import operation_routes
from autobots.api.app import create_app
from autobots.api.settings import Settings
from autobots.application.operations import Condition
from autobots.application.provider_settings import ProviderSettings
from fake_openrouter import provider_context

INTERNAL = "fixture-internal"
SECRET = "fixture-jwt-secret-with-enough-length"
MEMBER = UUID("c1111111-1111-4111-8111-111111111111")
OUTSIDER = UUID("d2222222-2222-4222-8222-222222222222")
WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
SETTINGS = Settings(
    internal_token=SecretStr(INTERNAL),
    jwt_secret=SecretStr(SECRET),
    allowed_hosts=("testserver",),
)
OK = (
    Condition("database", "ok", "database_ready"),
    Condition("schema", "ok", "schema_ready"),
    Condition("hold", "ok", "no_hold"),
    Condition("adapter", "ok", "adapter_qualified"),
)
WORKER_READY = Condition("worker", "ok", "worker_ready")


class Membership:
    """A member who isn't the owner, of one workspace."""

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return user_id == MEMBER and workspace_id == WORKSPACE

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [WORKSPACE] if user_id == MEMBER else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return "member" if user_id == MEMBER else None


class Pool:
    @asynccontextmanager
    async def connection(self) -> Any:
        yield object()


def headers(user: UUID = MEMBER) -> dict[str, str]:
    claims = {"sub": str(user), "aud": "authenticated", "exp": time.time() + 60}
    return {
        "X-Autobots-Internal": INTERNAL,
        "Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}",
    }


def arranged(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database: tuple[Condition, ...] = OK,
    worker: Condition = WORKER_READY,
    auth: str = "configured",
) -> TestClient:
    async def conditions(_pool: object, _probes: object = None) -> tuple[Condition, ...]:
        return database

    async def worker_state(_connection: object, _counts: object) -> Condition:
        return worker

    async def auth_status(_self: object, _workspace: UUID) -> str:
        return auth

    monkeypatch.setattr(operation_routes, "database_conditions", conditions)
    monkeypatch.setattr(operation_routes, "worker_condition", worker_state)
    monkeypatch.setattr(ProviderSettings, "auth_status", auth_status)
    app = create_app(SETTINGS, membership=Membership())
    client = TestClient(app, raise_server_exceptions=False)
    app.state.pool = Pool()
    app.state.provider_context = provider_context()
    return client


def states(reply: Any) -> dict[str, str]:
    return {item["name"]: item["state"] for item in reply.json()["services"]}


def test_all_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = arranged(monkeypatch).get("/v1/readiness", headers=headers())
    assert reply.status_code == 200
    assert reply.json()["ready"] is True
    assert states(reply) == {
        "api": "ready",
        "worker": "ready",
        "database": "ready",
        "openrouter": "ready",
    }


def test_a_worker_without_a_heartbeat_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    client = arranged(monkeypatch, worker=Condition("worker", "degraded", "worker_absent"))
    reply = client.get("/v1/readiness", headers=headers())
    assert reply.json()["ready"] is False
    worker = next(item for item in reply.json()["services"] if item["name"] == "worker")
    assert worker == {"name": "worker", "state": "not_ready", "code": "worker_absent"}
    assert states(reply)["database"] == "ready"


def test_a_missing_key_and_a_down_database(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = arranged(monkeypatch, auth="missing").get("/v1/readiness", headers=headers())
    openrouter = next(i for i in missing.json()["services"] if i["name"] == "openrouter")
    assert openrouter["state"] == "not_ready" and openrouter["code"] == "auth_missing"
    down = (
        Condition("database", "unavailable", "database_unreachable"),
        *OK[1:],
    )
    reply = arranged(monkeypatch, database=down).get("/v1/readiness", headers=headers())
    assert states(reply) == {
        "api": "ready",
        "worker": "unknown",
        "database": "not_ready",
        "openrouter": "unknown",
    }


def test_the_read_holds_states_only_and_needs_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = arranged(monkeypatch)
    body = client.get("/v1/readiness", headers=headers()).json()
    assert set(body) == {"schema_version", "ready", "services"}
    for item in body["services"]:
        assert set(item) == {"name", "state", "code"}
        assert not any(character.isdigit() for character in item["code"])
    assert client.get("/v1/readiness", headers=headers(OUTSIDER)).status_code == 403
    other = {**headers(), "X-Autobots-Workspace": str(OUTSIDER)}
    assert client.get("/v1/readiness", headers=other).status_code == 403
