"""US-14.16 offline: the live trial's refusal to repeat, its model path and its records."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from autobots.adapters.models.factory import default_sdk_client
from autobots.application import browsing_tool
from autobots.application.browsing_loop import ACTION_TOOLS
from autobots.application.tool_definitions import ToolResult
from autobots.application.worker_inference import frozen_policy
from autobots.domain.models import PROFILES, ModelProfileId, ModelRoute
from autobots.domain.tools import ToolOutcome
from autobots.operations import browse_trial
from autobots.operations.browse_trial import (
    LIMIT_MICRO_USD,
    RESULT,
    InvocationRow,
    ToolUseRow,
    TrialModel,
    build_report,
    hosts,
    inside,
    refuse_repeat,
)
from autobots.operations.cli import Refused

SOL = PROFILES[ModelProfileId.SOL]
PAYLOAD = {
    "data": [
        {
            "id": profile.wire_id,
            "canonical_slug": profile.canonical_id,
            "supported_parameters": ["max_tokens", "tools", "tool_choice"],
            "pricing": {"prompt": "0.000002", "completion": "0.00001"},
        }
        for profile in PROFILES.values()
    ]
}
POLICY = frozen_policy(
    {"version": 1, "bindings": {"executor": "openrouter_terra", "researcher": "openrouter_sol"}}
)


def test_a_recorded_trial_refuses_to_run_again_without_the_owner(tmp_path: Path) -> None:
    refuse_repeat(tmp_path, owner_requested=False)
    (tmp_path / RESULT).write_text(json.dumps({"status": "started"}))
    with pytest.raises(Refused, match="owner's request"):
        refuse_repeat(tmp_path, owner_requested=False)
    refuse_repeat(tmp_path, owner_requested=True)


def test_each_step_goes_to_sol_through_the_shared_factory_with_tools_required() -> None:
    bodies: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "finish", "arguments": json.dumps({"summary": "x"})},
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "id": "f",
                "object": "chat.completion",
                "created": 1,
                "model": bodies[-1]["model"],
                "system_fingerprint": "fake",
                "choices": [{"index": 0, "finish_reason": "tool_calls", "message": message}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 7,
                    "total_tokens": 12,
                    "cost": 0.001,
                },
            },
        )

    def client(key: str) -> Any:
        return default_sdk_client(
            key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        )

    model = TrialModel(PAYLOAD, POLICY, SecretStr("arranged"), client)
    route = model.route()
    assert (route.role, route.profile, route.wire_id) == (
        "researcher",
        "openrouter_sol",
        SOL.wire_id,
    )
    assert route.worst_case_micro_usd > 0
    bound = model.bind_tools(ACTION_TOOLS, tool_choice="any")
    reply = asyncio.run(bound.ainvoke([HumanMessage("read")]))
    assert reply.tool_calls[0]["name"] == "finish"
    body = bodies[0]
    assert body["model"] == SOL.wire_id and body["tool_choice"] == "required"
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}


def test_the_proxy_log_gives_hosts_only_and_flags_any_outside_the_domains() -> None:
    log = [
        {"event": "allowed", "host": "example.com", "address": "1.2.3.4"},
        {"event": "allowed", "host": "www.iana.org"},
        {"event": "host_not_allowed", "host": "fonts.example.net"},
    ]
    seen = hosts(log)
    assert seen == {
        "connected": ["example.com", "www.iana.org"],
        "refused": ["fonts.example.net:host_not_allowed"],
    }
    assert all(inside(host) for host in seen["connected"]) and not inside("evil.test")


RUN = UUID("b0000000-0000-4000-8000-000000000001")
ROUTE = ModelRoute("researcher", "openrouter_sol", SOL.wire_id, 300_000)


def calls(*charges: tuple[str, int, int | None]) -> list[InvocationRow]:
    return [
        InvocationRow(
            "researcher",
            "openrouter_sol",
            SOL.wire_id,
            status,
            reserved,
            charged,
            "tool_calls",
            900,
            40,
            ["read_page"],
            "openai",
        )
        for status, reserved, charged in charges
    ]


def test_the_report_is_built_from_the_stored_rows_alone() -> None:
    """POPS-08: the report after the one paid call is a pure function, tested before any repeat."""
    invocations = calls(("succeeded", 300_000, 12_000), ("succeeded", 300_000, 9_000))
    uses = [ToolUseRow("succeeded", None, True, {"task": "t"}, {"summary": "s"})]
    log = [{"event": "allowed", "host": "example.com"}, {"event": "allowed", "host": "iana.org"}]
    result = ToolResult(ToolOutcome.SUCCEEDED, None, {"stopped": "finished"})
    report = build_report(RUN, ROUTE, result, invocations, uses, log, "fake_transport")
    assert report["run_id"] == str(RUN) and report["evidence_class"] == "fake_transport"
    assert (report["charged_micro_usd"], report["open_reservations_micro_usd"]) == (21_000, 0)
    assert report["within_limit"] and report["limit_micro_usd"] == LIMIT_MICRO_USD
    assert (report["outcome"], report["code"], report["output"]) == (
        "succeeded",
        None,
        {"stopped": "finished"},
    )
    assert report["invocations"][0] == {
        "role": "researcher",
        "profile": "openrouter_sol",
        "wire_id": SOL.wire_id,
        "status": "succeeded",
        "reserved_micro_usd": 300_000,
        "charged_micro_usd": 12_000,
        "finish_reason": "tool_calls",
        "input_tokens": 900,
        "output_tokens": 40,
        "tool_names": ["read_page"],
        "upstream_provider": "openai",
    }
    assert report["tool_uses"] == [
        {
            "outcome": "succeeded",
            "code": None,
            "metered": True,
            "input_public": {"task": "t"},
            "output_public": {"summary": "s"},
        }
    ]
    assert report["proxy_hosts"]["connected"] == ["example.com", "iana.org"]
    assert report["only_allowed_hosts"]
    json.dumps(report)


def test_an_unsettled_call_stays_held_and_can_take_the_trial_past_its_limit() -> None:
    invocations = calls(("succeeded", 300_000, 700_000), ("uncertain", 400_000, None))
    result = ToolResult(ToolOutcome.UNKNOWN, "model_call_uncertain")
    log = [{"event": "allowed", "host": "evil.test"}]
    report = build_report(RUN, ROUTE, result, invocations, [], log, "live")
    assert (report["charged_micro_usd"], report["open_reservations_micro_usd"]) == (
        700_000,
        400_000,
    )
    assert not report["within_limit"] and not report["only_allowed_hosts"]
    assert report["output"] is None and report["code"] == "model_call_uncertain"


def test_the_browsing_switch_is_restored_after_the_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(browsing_tool.ENABLE, raising=False)
    with browse_trial._browsing_enabled():
        assert os.environ[browsing_tool.ENABLE] == "enabled"
    assert browsing_tool.ENABLE not in os.environ
    monkeypatch.setenv(browsing_tool.ENABLE, "off")
    with pytest.raises(RuntimeError), browse_trial._browsing_enabled():
        raise RuntimeError("arranged")
    assert os.environ[browsing_tool.ENABLE] == "off"
