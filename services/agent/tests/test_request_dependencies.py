"""The request plumbing every router shares, through the API in process (refactor plan R-55,
PAPI-06, PAPI-13 and PAPI-16).

The workspace is the verified header's, or the user's only one. The owner gate words its refusal
for a change, and Local Operations words its own for a read. Local Operations answers with the
database down, when a signed-in user is enough, and Readiness takes the chosen workspace or the
session's first (PRD-Studio SH-04). The session token is decoded once per request. No database,
socket or model is used.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import jwt
import pytest

from autobots.application import readiness
from autobots.application.operations import Condition, ProbeTimes
from fake_api import MEMBER, OUTSIDER, OWNER, ApiClient, token

ELSEWHERE = UUID("0b000000-0000-4000-8000-0000000000bb")
FORBIDDEN = {"code": "forbidden", "message": "This workspace is not available."}
UP = (
    Condition("database", "ok", "database_ready"),
    Condition("schema", "ok", "schema_ready"),
    Condition("hold", "ok", "no_hold"),
    Condition("adapter", "ok", "adapter_qualified"),
)
DOWN = (
    Condition("database", "unavailable", "database_unreachable"),
    Condition("schema", "unavailable", "schema_unknown"),
    Condition("hold", "unavailable", "hold_unknown"),
    Condition("adapter", "unavailable", "adapter_unknown"),
)


def get(client: ApiClient, path: str, user: UUID = OWNER, **extra: str) -> tuple[int, Any]:
    reply = client.http.get(path, headers=client.headers(user, **extra))
    return reply.status_code, reply.json()


def test_the_only_workspace_is_chosen_without_a_header(api_client: ApiClient) -> None:
    assert get(api_client, "/v1/settings/model-policy", MEMBER)[0] == 200


def test_a_chosen_workspace_the_user_isnt_in_is_refused(api_client: ApiClient) -> None:
    chosen = {"X-Autobots-Workspace": str(ELSEWHERE)}
    assert get(api_client, "/v1/settings/model-policy", MEMBER, **chosen) == (403, FORBIDDEN)
    assert "connect" not in api_client.log


def test_a_user_without_a_workspace_is_asked_to_choose_one(api_client: ApiClient) -> None:
    assert get(api_client, "/v1/settings/model-policy", OUTSIDER) == (
        403,
        {"code": "workspace_required", "message": "Choose a workspace."},
    )


def test_the_owner_gate_refuses_a_member_for_a_change(api_client: ApiClient) -> None:
    reply = api_client.http.post(
        "/v1/memory", headers=api_client.headers(MEMBER), json={"title": "A", "content": "B"}
    )
    assert (reply.status_code, reply.json()) == (
        403,
        {"code": "owner_required", "message": "Only the workspace owner can change this."},
    )


def conditions_are(
    monkeypatch: pytest.MonkeyPatch, arranged: tuple[Condition, ...]
) -> Callable[[], int]:
    """The database answers `arranged`; returns how many times it was asked."""
    asked: list[object] = []

    async def database(_pool: object, _probes: ProbeTimes | None = None) -> tuple[Condition, ...]:
        asked.append(_pool)
        return arranged

    async def storage(_store: object) -> Condition:
        return Condition("storage", "ok", "storage_ready")

    monkeypatch.setattr(readiness, "database_conditions", database)
    monkeypatch.setattr(readiness, "storage_condition", storage)
    return lambda: len(asked)


def test_with_the_database_down_local_operations_answers_any_signed_in_user(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = conditions_are(monkeypatch, DOWN)
    status, body = get(api_client, "/v1/operations/local-status", OUTSIDER)
    assert (status, body["scope"], body["queue"], body["retention"]) == (
        200,
        "installation",
        None,
        None,
    )
    assert asked() == 1
    assert "role_in" not in api_client.log and "connect" not in api_client.log


def test_with_the_database_up_only_the_owner_reads_local_operations(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    conditions_are(monkeypatch, UP)
    assert get(api_client, "/v1/operations/local-status", MEMBER) == (
        403,
        {"code": "owner_required", "message": "Only the workspace owner can see this."},
    )
    chosen = {"X-Autobots-Workspace": str(ELSEWHERE)}
    assert get(api_client, "/v1/operations/local-status", OWNER, **chosen) == (403, FORBIDDEN)
    assert "connect" not in api_client.log


def test_readiness_refuses_a_chosen_workspace_the_user_isnt_in_or_no_workspace(
    api_client: ApiClient,
) -> None:
    chosen = {"X-Autobots-Workspace": str(ELSEWHERE)}
    assert get(api_client, "/v1/readiness", MEMBER, **chosen) == (403, FORBIDDEN)
    assert get(api_client, "/v1/readiness", OUTSIDER) == (403, FORBIDDEN)


def test_the_session_token_is_decoded_once_per_request(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoded = Mock(wraps=jwt.decode)
    monkeypatch.setattr(jwt, "decode", decoded)
    session = token(OWNER, email="ada@example.com")
    reply = api_client.http.get(
        "/v1/session",
        headers={**api_client.headers(None), "Authorization": f"Bearer {session}"},
    )
    assert reply.status_code == 200
    assert reply.json()["email"] == "ada@example.com"
    assert [call.args[0] for call in decoded.call_args_list] == [session]
