"""US-14.16 offline: the live trial's refusal to repeat, its model path and its records."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import HumanMessage
from pydantic import SecretStr

from autobots.adapters.models.factory import default_sdk_client
from autobots.application.browsing_loop import ACTION_TOOLS
from autobots.application.worker_inference import frozen_policy
from autobots.domain.models import PROFILES, ModelProfileId
from autobots.operations.browse_trial import RESULT, TrialModel, hosts, inside, refuse_repeat
from autobots.operations.route_qualification import Refused

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
