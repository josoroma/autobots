"""The app's boundaries in process. Real processes and a browser run in scripts/qualify_web.py."""

import ast
import contextlib
import io
import json
import logging
import time
from collections.abc import Iterator
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from pydantic import SecretStr

from api_session import (
    INTERNAL,
    SECRET,
    SETTINGS,
    USER_A,
    WORKSPACE,
    Membership,
    client,
    headers,
    token,
)
from autobots.api.app import create_app
from autobots.api.main import create_configured_app
from autobots.api.pool import POOL_WAIT_SECONDS, Pool, default_pool
from autobots.api.resources import AppResources, resources_of
from autobots.api.settings import Settings, load_settings
from autobots.application.sql import CommittingConnection
from autobots.logs import JsonFormatter

USER_B = UUID("b2222222-2222-4222-8222-222222222222")


def test_health_needs_the_internal_credential() -> None:
    assert client().get("/v1/health", headers=headers()).json() == {
        "schema_version": 1,
        "status": "ok",
    }
    assert client().get("/v1/health").status_code == 401
    assert client().get("/v1/health", headers=headers(internal="forged")).status_code == 401


def test_an_empty_configured_credential_fails_closed() -> None:
    app = create_app(AppResources(Settings(allowed_hosts=("testserver",))))
    with TestClient(app) as test_client:
        assert test_client.get("/v1/health", headers={"X-Autobots-Internal": ""}).status_code == 401


@pytest.mark.parametrize(
    "bearer",
    [
        token(secret="another-secret-of-sufficient-length-00"),
        token(aud="anon"),
        token(exp=time.time() - 60),
        token(sub="not-a-uuid"),
        "not-a-token",
        jwt.encode({"sub": str(USER_A), "aud": "authenticated"}, SECRET, algorithm="HS256"),
    ],
    ids=["wrong secret", "wrong audience", "expired", "bad subject", "garbage", "no expiry"],
)
def test_a_bad_session_is_refused(bearer: str) -> None:
    reply = client().get(f"/v1/workspaces/{WORKSPACE}", headers=headers(bearer))
    assert reply.status_code == 401
    assert reply.json()["code"] == "unauthorized"


def test_a_none_algorithm_token_is_refused() -> None:
    forged = jwt.encode(
        {"sub": str(USER_A), "aud": "authenticated", "exp": time.time() + 60}, "", algorithm="none"
    )
    assert client().get(f"/v1/workspaces/{WORKSPACE}", headers=headers(forged)).status_code == 401


def test_only_a_member_reaches_a_workspace() -> None:
    reply = client().get(f"/v1/workspaces/{WORKSPACE}", headers=headers(token()))
    assert reply.status_code == 200
    assert reply.json() == {"schema_version": 1, "id": str(WORKSPACE)}
    other = client().get(f"/v1/workspaces/{WORKSPACE}", headers=headers(token(USER_B)))
    assert other.status_code == 403
    assert other.json()["code"] == "forbidden"


def test_the_session_route_reports_verified_identity_and_membership() -> None:
    reply = client().get("/v1/session", headers=headers(token(email="ada@example.com")))
    assert reply.json() == {
        "schema_version": 1,
        "user_id": str(USER_A),
        "workspace_ids": [str(WORKSPACE)],
        "display_name": "ada",
        "display_name_saved": False,
        "email": "ada@example.com",
        "workspaces": [],
    }
    assert client().get("/v1/session", headers=headers(token(USER_B))).json()["workspace_ids"] == []
    assert client().get("/v1/session", headers=headers()).status_code == 401


def test_default_membership_denies_everyone() -> None:
    with TestClient(create_app(AppResources(SETTINGS))) as test_client:
        reply = test_client.get(f"/v1/workspaces/{WORKSPACE}", headers=headers(token()))
        assert reply.status_code == 403


def test_invalid_input_is_not_echoed() -> None:
    reply = client().get("/v1/workspaces/secret-looking-value", headers=headers(token()))
    assert reply.status_code == 422
    assert "secret-looking-value" not in reply.text
    assert reply.json()["code"] == "invalid_request"


def test_a_forged_host_is_refused() -> None:
    assert (
        client().get("/v1/health", headers={**headers(), "Host": "evil.example"}).status_code == 400
    )


def test_an_unexpected_error_exposes_nothing() -> None:
    class Broken:
        async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
            raise RuntimeError("database password leaked here")

        async def workspaces_for(self, user_id: UUID) -> list[UUID]:
            return []

        async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
            return None

    app = create_app(AppResources(SETTINGS, membership=Broken()))
    with api_lines() as lines:
        reply = TestClient(app, raise_server_exceptions=False).get(
            f"/v1/workspaces/{WORKSPACE}", headers=headers(token())
        )
    assert reply.status_code == 500
    assert reply.json() == {"code": "internal_error", "message": "Something went wrong."}
    # R-25, XERR-01: one private line with the route template, the cause's type and frames.
    [line] = lines
    assert (line["event"], line["level"], line["method"], line["route"]) == (
        "api.unhandled",
        "error",
        "GET",
        "/v1/workspaces/{workspace_id}",
    )
    assert line["error_type"] == "builtins.RuntimeError"
    frames = line["frames"]
    assert isinstance(frames, list) and str(frames[-1]).endswith(".Broken.is_member")
    assert "password" not in json.dumps(line)
    assert str(WORKSPACE) not in json.dumps(line)


@contextlib.contextmanager
def api_lines() -> Iterator[list[dict[str, object]]]:
    """The API's private log lines, as the service's own formatter writes them."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("autobots.api")
    logger.addHandler(handler)
    written: list[dict[str, object]] = []
    try:
        yield written
    finally:
        logger.removeHandler(handler)
        written.extend(json.loads(line) for line in stream.getvalue().splitlines())


UNAVAILABLE = {
    "code": "service_unavailable",
    "message": "The database couldn't complete this request. Try again.",
}


def test_a_database_failure_during_a_request_is_a_retryable_503() -> None:
    """XERR-06: the code the no-pool path uses, with wording that doesn't claim an outage."""

    class Lost(Membership):
        async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
            raise psycopg.OperationalError("connection failed: password=hunter2")

    app = create_app(AppResources(SETTINGS, membership=Lost()))
    with api_lines() as lines:
        reply = TestClient(app, raise_server_exceptions=False).get(
            f"/v1/workspaces/{WORKSPACE}", headers=headers(token())
        )
    assert (reply.status_code, reply.json()) == (503, UNAVAILABLE)
    [line] = lines
    assert (line["event"], line["level"], line["route"], line["error_type"]) == (
        "api.database_unavailable",
        "warning",
        "/v1/workspaces/{workspace_id}",
        "psycopg.OperationalError",
    )
    assert "hunter2" not in json.dumps(line)


def test_a_database_error_a_retry_cant_clear_is_a_500_not_a_retry() -> None:
    """A full disk or a program limit stays a 500, so no one is told to try again; a serialization
    conflict or a shutdown is retried."""
    from psycopg import errors

    from autobots.api.errors import transient

    assert not transient(errors.DiskFull("disk full"))
    assert not transient(errors.ProgramLimitExceeded("program limit exceeded"))
    assert transient(errors.SerializationFailure("could not serialize access"))
    assert transient(errors.AdminShutdown("terminating connection"))

    class Full(Membership):
        async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
            raise errors.DiskFull("could not extend file")

    app = create_app(AppResources(SETTINGS, membership=Full()))
    with api_lines() as lines:
        reply = TestClient(app, raise_server_exceptions=False).get(
            f"/v1/workspaces/{WORKSPACE}", headers=headers(token())
        )
    assert reply.status_code == 500
    assert [line["event"] for line in lines][:1] == ["api.unhandled"]


def test_a_pool_that_runs_out_of_time_answers_503_too() -> None:
    class Exhausted:
        async def open(self) -> None:
            return None

        async def close(self) -> None:
            return None

        def connection(self) -> AbstractAsyncContextManager[CommittingConnection]:
            raise PoolTimeout("couldn't get a connection after 10.00 sec")

    settings = Settings(
        internal_token=SecretStr(INTERNAL),
        jwt_secret=SecretStr(SECRET),
        database_url=SecretStr("postgresql://fixture"),
        allowed_hosts=("testserver",),
    )
    app = create_app(
        AppResources(settings, membership=Membership()), pool_factory=lambda _url: Exhausted()
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        reply = test_client.get(f"/v1/runs/{uuid4()}", headers=headers(token()))
    assert (reply.status_code, reply.json()) == (503, UNAVAILABLE)


def test_the_pool_gives_up_before_the_bffs_own_abort() -> None:
    """psycopg_pool's default wait is 30 s, the same as the BFF's abort (XERR-06)."""
    assert POOL_WAIT_SECONDS < 30
    pool = default_pool("postgresql://fixture")
    assert pool.timeout == POOL_WAIT_SECONDS  # type: ignore[attr-defined]  # Pool is the lifespan's protocol; the default is psycopg_pool's


def test_the_pool_belongs_to_the_lifespan() -> None:
    events: list[str] = []

    class FakePool:
        async def open(self) -> None:
            events.append("open")

        async def close(self) -> None:
            events.append("close")

        def connection(self) -> AbstractAsyncContextManager[CommittingConnection]:
            raise AssertionError("no request connects in this test")

    def factory(_url: str) -> Pool:
        events.append("created")
        return FakePool()

    settings = Settings(
        database_url=SecretStr("postgresql://fixture"), allowed_hosts=("testserver",)
    )
    app = create_app(AppResources(settings), pool_factory=factory)
    assert events == [], "building the app opens nothing"
    with TestClient(app):
        assert events == ["created", "open"]
        assert resources_of(app).pool is not None
    assert events == ["created", "open", "close"]
    assert resources_of(app).pool is None


def test_settings_hide_their_values() -> None:
    settings = load_settings(
        {"AUTOBOTS_INTERNAL_TOKEN": "fixture-private", "AUTOBOTS_JWT_SECRET": "fixture-private"}
    )
    assert "fixture-private" not in repr(settings)
    assert settings.internal_token.get_secret_value() == "fixture-private"
    assert load_settings({}).allowed_hosts == ("127.0.0.1", "localhost")


def test_the_entry_point_reads_the_environment_only_when_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTOBOTS_INTERNAL_TOKEN", "from-the-environment")
    assert (
        resources_of(create_configured_app()).settings.internal_token.get_secret_value()
        == "from-the-environment"
    )


def test_requests_cannot_own_long_running_work() -> None:
    forbidden = {"BackgroundTasks", "create_task", "run_in_executor", "add_task", "Thread"}
    for path in Path(__file__).resolve().parents[1].joinpath("src/autobots/api").glob("*.py"):
        names = {
            node.attr if isinstance(node, ast.Attribute) else node.id
            for node in ast.walk(ast.parse(path.read_text()))
            if isinstance(node, ast.Attribute | ast.Name)
        }
        assert not (names & forbidden), path.name


def test_a_name_falls_back_to_the_email_then_member() -> None:
    """US-15.2: without a saved name, the email's local part, and "Member" without an email."""
    with_email = client().get("/v1/profile", headers=headers(token(email="ada@example.com")))
    assert with_email.json() == {
        "schema_version": 1,
        "display_name": "ada",
        "saved": False,
        "email": "ada@example.com",
    }
    without = client().get("/v1/profile", headers=headers(token()))
    assert without.json()["display_name"] == "Member"
    assert without.json()["email"] is None


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_an_invalid_display_name_is_refused_with_a_typed_code(name: str) -> None:
    reply = client().put("/v1/profile", headers=headers(token()), json={"display_name": name})
    assert reply.status_code == 422
    assert reply.json()["code"] == "display_name_invalid"


def test_saving_a_name_needs_the_database_and_a_session() -> None:
    body = {"display_name": "Ada"}
    assert client().put("/v1/profile", headers=headers(token()), json=body).status_code == 503
    assert client().put("/v1/profile", headers=headers(), json=body).status_code == 401
