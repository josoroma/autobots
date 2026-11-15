"""Each request holds at most one of the pool's connections at a time (refactor plan R-55, PAPI-11).

The routes that check the OpenRouter key before model-backed work read it on a connection of their
own, released before the handler opens another. Settings open theirs in the handler, after the
workspace and owner checks, and admission asks for a role before it opens its own. So five such
requests can't each hold one connection and wait for a second. Membership borrows from the pool,
as `PostgresMembership` does, and the real key check runs over an installation key granted to the
workspace. No database, socket or model is used.
"""

from collections.abc import Iterator
from uuid import UUID

import pytest

from autobots.api.dependencies import require_ready
from autobots.api.resources import resources_of
from fake_api import OWNER, ApiClient, PooledMembership
from fake_openrouter import provider_context

RUN = UUID("0b000000-0000-4000-8000-0000000000c1")
CANDIDATE = UUID("0b000000-0000-4000-8000-0000000000c7")
FLOW = UUID("0b000000-0000-4000-8000-0000000000d1")
EXPERT = UUID("0b000000-0000-4000-8000-0000000000e1")
SESSION = UUID("0b000000-0000-4000-8000-000000000051")
GRANT = "from app_private.installation_credential_grants"
AGENT_GRAPH = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "ask", "block": "agent", "version": 1, "config": {"expert_id": str(EXPERT)}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [
        {"source": "in", "source_port": "value", "target": "ask", "target_port": "goal"},
        {"source": "ask", "source_port": "result", "target": "out", "target_port": "value"},
    ],
}
REPLAY = {
    "tasks": [{"goal_text": "Find the figure", "criteria": ["States it"]}],
    "limit_micro_usd": 1,
}


def most_held(log: list[str]) -> int:
    """The most connections held at once, by the order the pool lent and took them back."""
    held = most = 0
    for entry in log:
        if entry == "connect":
            held += 1
            most = max(most, held)
        elif entry == "release":
            held -= 1
    return most


@pytest.fixture
def client(api_client: ApiClient) -> Iterator[ApiClient]:
    """Readiness passes, membership borrows from the pool, and the workspace may use the
    installation's usable key."""
    resources = resources_of(api_client.app)
    resources.membership = PooledMembership(api_client.log, api_client.database)
    api_client.app.dependency_overrides[require_ready] = lambda: None
    resources.provider_context = provider_context(
        environment={"OPENROUTER_API_KEY": "sk-or-fixture-installation-key"}
    )
    api_client.database.answer(GRANT, (1,))
    api_client.database.answer("event_sequence = event_sequence + 1", (1,))
    yield api_client


def post(client: ApiClient, path: str, body: dict[str, object] | None = None) -> int:
    reply = client.http.post(
        path, headers=client.headers(OWNER, **{"Idempotency-Key": "key-1"}), json=body
    )
    return reply.status_code


def key_checked(client: ApiClient) -> bool:
    return any(GRANT in entry for entry in client.log)


def test_the_run_intent_check_holds_one_connection_at_a_time(client: ApiClient) -> None:
    assert post(client, "/v1/runs/intent") == 200
    assert key_checked(client) and most_held(client.log) == 1


def test_admitting_a_pinned_expert_version_holds_one_connection_at_a_time(
    client: ApiClient,
) -> None:
    client.database.answer("from public.sessions", ("direct", [{"expert_id": str(EXPERT)}]))
    client.database.answer("from public.expert_versions", ({"tools": ["calculate"]},))
    body = {"goal_text": "Write it", "session_id": str(SESSION), "expert_version": 2}
    assert post(client, "/v1/runs", body) == 202
    assert "role_in" in client.log and most_held(client.log) == 1


@pytest.mark.parametrize("path", ["/v1/settings/model-providers", "/v1/settings/keys-and-vars"])
def test_reading_settings_holds_one_connection_at_a_time(client: ApiClient, path: str) -> None:
    client.database.answer("select version from app_private.tool_key_settings", (0,))
    reply = client.http.get(path, headers=client.headers(OWNER))
    assert reply.status_code == 200
    assert most_held(client.log) == 1


def test_admitting_a_run_with_a_budget_holds_one_connection_at_a_time(client: ApiClient) -> None:
    body = {"goal_text": "Write the report", "budget_micro_usd": 1_000_000}
    assert post(client, "/v1/runs", body) == 202
    assert key_checked(client) and most_held(client.log) == 1


def test_a_resume_holds_one_connection_at_a_time(client: ApiClient) -> None:
    assert post(client, f"/v1/runs/{RUN}/resume", {"expected_version": 1}) == 404
    assert key_checked(client) and most_held(client.log) == 1


def test_a_replay_holds_one_connection_at_a_time(client: ApiClient) -> None:
    assert post(client, f"/v1/improvements/{CANDIDATE}/replay", REPLAY) == 404
    assert key_checked(client) and most_held(client.log) == 1


def test_a_workflow_execution_holds_one_connection_at_a_time(client: ApiClient) -> None:
    client.database.answer("select v.graph from public.workflow_versions", (AGENT_GRAPH,))
    body = {"version": 1, "inputs": {"in": "x"}}
    # Past the key check, the version's own row isn't arranged.
    assert post(client, f"/v1/workflows/{FLOW}/executions", body) == 404
    assert key_checked(client) and most_held(client.log) == 1
