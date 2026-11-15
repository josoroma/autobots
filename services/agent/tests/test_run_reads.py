"""A run's reads through the API in process: its summary, the run preview's Expert and the stream's
end (refactor plan R-55, PAPI-01; PRD-Studio HM-03, US-15.24).

A run outside the workspace reads as not found. The preview takes an Expert's tools and bindings
from its latest version, and an Expert outside the workspace is not found. A stream whose run has
finished ends once every event is sent. No database, socket or model is used.
"""

from uuid import UUID

import psycopg
import pytest

from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS
from fake_api import RUN_ROW, ApiClient, run_row

RUN = UUID("0b000000-0000-4000-8000-0000000000c1")
EXPERT = UUID("0b000000-0000-4000-8000-0000000000e1")
LATEST_CONFIG = (
    "select v.config from public.experts e join public.expert_versions v "
    "on v.expert_id = e.id and v.version = e.latest_version "
    "where e.id = %s and e.workspace_id = %s"
)
RUN_STATUS = "select status from public.runs where id = %s"


def test_a_run_not_in_this_workspace_reads_as_not_found(api_client: ApiClient) -> None:
    reply = api_client.http.get(f"/v1/runs/{RUN}", headers=api_client.headers())
    assert (reply.status_code, reply.json()) == (
        404,
        {"code": "run_not_found", "message": "That run is not available."},
    )


def preview(client: ApiClient, **params: str) -> tuple[int, dict[str, object]]:
    reply = client.http.get("/v1/run-preview", params=params, headers=client.headers())
    return reply.status_code, reply.json()


def test_the_preview_without_an_expert_shows_the_loops_own_tools(api_client: ApiClient) -> None:
    status, body = preview(api_client)
    assert status == 200
    assert body["tools"] == sorted(tool for tool in LOOP_TOOL_GRANTS if tool not in PLAN_TOOLS)
    assert LATEST_CONFIG not in api_client.log


def test_the_preview_takes_an_experts_tools_from_its_latest_version(api_client: ApiClient) -> None:
    api_client.database.answer(
        LATEST_CONFIG, ({"tools": ["web_search", "calculate"], "role_bindings": {}},)
    )
    status, body = preview(api_client, expert_id=str(EXPERT))
    assert (status, body["tools"]) == (200, ["calculate", "web_search"])
    assert [values for text, values in api_client.database.statements if text == LATEST_CONFIG] == [
        (EXPERT, UUID("0b000000-0000-4000-8000-0000000000aa"))
    ]


def test_an_expert_not_in_this_workspace_isnt_previewed(api_client: ApiClient) -> None:
    assert preview(api_client, expert_id=str(EXPERT)) == (
        404,
        {"code": "expert_not_found", "message": "That Expert is not available."},
    )


def test_a_finished_runs_stream_ends_once_every_event_is_sent(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreachable(*_args: object, **_kwargs: object) -> psycopg.AsyncConnection[object]:
        raise psycopg.OperationalError("no listener in this test")

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", unreachable)
    api_client.database.answer(RUN_ROW, run_row(RUN))
    api_client.database.answer(RUN_STATUS, ("succeeded",))
    with api_client.http.stream(
        "GET", f"/v1/runs/{RUN}/events/stream", headers=api_client.headers()
    ) as reply:
        text = reply.read().decode()
    assert reply.status_code == 200
    assert text == ": connected\n\nevent: end\ndata: {}\n\n"
    assert [values for text, values in api_client.database.statements if text == RUN_STATUS] == [
        (RUN,)
    ]
