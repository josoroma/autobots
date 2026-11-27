"""US-23.2, Decision 0041 A7: US-3.4's suite on a local route at no spend, the route's measurements,
and which local profiles the Local source offers. A fake llama-server on an httpx transport answers
every fixture, through the real `ChatOpenRouter` on the loopback client."""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from autobots.adapters.models.local_server import DEFAULT_PORT, TOOL_CALL_SCHEMA, LoopbackClient
from autobots.application.local_offering import local_offers, offered_locally
from autobots.application.model_policy import validated_choice
from autobots.application.provider_settings import qualification_from_record
from autobots.application.run_admission import WorkspacePolicy
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.settings import RouteQualification
from autobots.domain.models import (
    OFFERED_FOR_NEW_RUNS,
    PROFILES,
    ModelProfile,
    ModelProfileId,
    ProfileNotOffered,
    require_offered,
)
from autobots.operations import local_route_measurements as measurements
from autobots.operations import route_qualification as rq
from autobots.operations.cli import Refused
from autobots.persistence.rows import RouteQualificationRow

BONSAI = PROFILES[ModelProfileId.LOCAL_BONSAI_2_5]
INKLING = PROFILES[ModelProfileId.LOCAL_INKLING_2_MINI]
DECISION = {"choice": "reject", "reason": "Deleting every backup can't be undone."}
PLAN = {
    "place": 'São José, 東京 "quoted"',
    "tasks": [
        {"id": "t1", "title": "Walk", "priority": "low", "criteria": ["walked"]},
        {"id": "t2", "title": "Eat", "priority": "high", "criteria": ["ate"]},
    ],
}


class FakeSuiteServer:
    """llama-server as US-3.4's fixtures need it: text, tool calls, JSON schema output, streams,
    a tool result, truncation and a decline. `fail_required` makes the required tool call answer
    with text instead in those trials (1-based), as a server that ignored its schema would."""

    def __init__(self, served: str, fail_required: frozenset[int] = frozenset()) -> None:
        self.served = served
        self.fail_required = fail_required
        self.required_seen = 0
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self.handle)

    def reply_for(self, body: dict[str, Any]) -> tuple[dict[str, Any], str]:  # noqa: PLR0911 - one branch per fixture's request
        messages = body["messages"]
        last = str(messages[-1].get("content") or "")
        tools = body.get("tools") or []
        if body.get("max_tokens") == 16:
            return {"role": "assistant", "content": "The central valley is"}, "length"
        if body.get("response_format"):
            schema = body["response_format"]["json_schema"]["schema"]
            if body["response_format"]["json_schema"]["name"] == TOOL_CALL_SCHEMA:
                return self.constrained_call(schema, last)
            value = DECISION if "choice" in schema.get("properties", {}) else PLAN
            return {"role": "assistant", "content": json.dumps(value, ensure_ascii=False)}, "stop"
        if messages[-1].get("role") == "tool":
            return {"role": "assistant", "content": "The code for alpha is 73914."}, "stop"
        if tools:
            name = tools[0]["function"]["name"]
            args = {"item": "alpha"} if name == "LookupCode" else {"city": "Heredia"}
            call = {
                "id": f"call-{len(self.requests)}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            return {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"
        if "social security" in last:
            return {"role": "assistant", "content": "Sorry, I can't share that."}, "stop"
        if "Count from 1 to 20" in last:
            return {"role": "assistant", "content": " ".join(str(n) for n in range(1, 21))}, "stop"
        if "volcanoes" in last:
            return {"role": "assistant", "content": "Arenal Poas Irazu Rincon Turrialba"}, "stop"
        return {"role": "assistant", "content": "ready"}, "stop"

    def constrained_call(self, schema: dict[str, Any], last: str) -> tuple[dict[str, Any], str]:
        """A reply held to the tool call schema (Decision 0041 A18): the first tool it allows. A
        trial in `fail_required` answers in text, as a server that ignored the schema would."""
        if "Say hello" in last:
            self.required_seen += 1
            if self.required_seen in self.fail_required:
                return {"role": "assistant", "content": "Hello!"}, "stop"
        name = schema.get("anyOf", [schema])[0]["properties"]["name"]["enum"][0]
        args = {"item": "alpha"} if name == "LookupCode" else {"city": "Heredia"}
        call = json.dumps({"name": name, "arguments": args})
        return {"role": "assistant", "content": call}, "stop"

    def stream(self, message: dict[str, Any], finish: str) -> str:
        chunks: list[dict[str, Any]] = []
        if message.get("tool_calls"):
            call = message["tool_calls"][0]
            arguments = call["function"]["arguments"]
            half = len(arguments) // 2
            first = {
                "index": 0,
                "id": call["id"],
                "type": "function",
                "function": {"name": call["function"]["name"], "arguments": arguments[:half]},
            }
            second = {"index": 0, "function": {"arguments": arguments[half:]}}
            chunks += [{"tool_calls": [first]}, {"tool_calls": [second]}]
        else:
            chunks += [{"content": word + " "} for word in str(message["content"]).split()]
        events: list[dict[str, Any]] = [
            {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]} for delta in chunks
        ]
        events.append({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
        events.append({"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 4}})
        return "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": self.served}]})
        body = json.loads(request.content)
        message, finish = self.reply_for(body)
        if body.get("stream"):
            text = self.stream(message, finish)
            return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
        usage = {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}
        return httpx.Response(
            200,
            json={
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": usage,
            },
        )


def client_on(server: FakeSuiteServer) -> rq.LocalClient:
    def build(profile: ModelProfile, port: int) -> LoopbackClient:
        return LoopbackClient(
            profile, port, 30.0, transport=server.transport, async_transport=server.transport
        )

    return build


async def qualified(
    server: FakeSuiteServer, out: Path, profile: str = BONSAI.id.value
) -> dict[str, Any]:
    return await rq.qualify_local(
        profile, out, DEFAULT_PORT, client=client_on(server), transport=server.transport
    )


@pytest.mark.asyncio
async def test_a_local_route_qualifies_in_three_trials_with_nothing_spent(tmp_path: Path) -> None:
    server = FakeSuiteServer(BONSAI.wire_id)
    report = await qualified(server, tmp_path)
    assert report["evidence_class"] == "fake_server"
    assert report["calls"] == 39 and report["spent_usd"] == "0.00"
    assert report["committed_micro_usd"] == 0
    assert set(report["summary"]) == {name for name, _ in _fixture_names()}
    assert all(counts == {"passed": 3} for counts in report["summary"].values()), report["summary"]
    assert report["offerable"] is True and report["recorded_status"] == "qualified_with_limits"
    assert report["limits_text"] == "Every fixture passed in all three trials."
    assert all(trial["first_token_seconds"] is not None for trial in report["trials"])
    assert report["served_model_id"] == BONSAI.wire_id
    assert report["pins"]["sha256"] == BONSAI.local.sha256 if BONSAI.local else False
    # Every request went to the loopback, none carried a key, and nothing was ever held.
    assert {(r.url.host, r.url.port) for r in server.requests} == {("127.0.0.1", DEFAULT_PORT)}
    assert all("authorization" not in r.headers for r in server.requests)
    ledger = json.loads((tmp_path / f"ledger-{BONSAI.id.value}.json").read_text())
    assert ledger["cap_micro_usd"] == 0 and ledger["committed"] == 0
    assert {entry["worst_case"] for entry in ledger["entries"]} == {0}
    assert (tmp_path / f"report-{BONSAI.id.value}.json").exists()


@pytest.mark.asyncio
async def test_the_suite_sends_required_and_named_calls_through_the_routes_constraint(
    tmp_path: Path,
) -> None:
    """US-23.7, Decision 0041 A18: the suite qualifies the route as runs send it. Each required or
    named call reaches the server held to the tool call schema, with no tool choice of its own, and
    passes in all three trials only because the fake answers within that schema."""
    server = FakeSuiteServer(BONSAI.wire_id)
    report = await qualified(server, tmp_path)
    assert report["summary"]["tool_required"] == {"passed": 3}
    assert report["summary"]["tool_named_conflict"] == {"passed": 3}
    assert report["evidence_class"] == "fake_server" and report["committed_micro_usd"] == 0
    chats = [json.loads(r.content) for r in server.requests if r.url.path.endswith("/completions")]
    constrained = [
        chat
        for chat in chats
        if (chat.get("response_format") or {}).get("json_schema", {}).get("name")
        == TOOL_CALL_SCHEMA
    ]
    asked = [chat["messages"][-1]["content"] for chat in constrained]
    # tool_required and tool_named_conflict, and the streamed named call, in each of three trials.
    assert sum("Say hello" in text for text in asked) == 3
    assert sum("What time is it in Heredia?" in text for text in asked) == 3
    assert all(chat["tool_choice"] == "none" and "stream" not in chat for chat in constrained)
    assert not any(chat.get("tool_choice") == "required" for chat in chats)
    # Nothing reached OpenRouter: every request went to the loopback, and none carried a key.
    assert {(r.url.host, r.url.port) for r in server.requests} == {("127.0.0.1", DEFAULT_PORT)}
    assert all("authorization" not in r.headers for r in server.requests)


def _fixture_names() -> list[tuple[str, object]]:
    return [
        (name, None)
        for name in (
            "plain_text",
            "tool_auto",
            "tool_required",
            "tool_named_conflict",
            "schema_flat",
            "schema_nested",
            "stream_text",
            "stream_tool_arguments",
            "continuation",
            "truncation",
            "refusal",
            "cancellation",
        )
    ]


@pytest.mark.asyncio
async def test_a_required_tool_call_that_fails_once_keeps_the_profile_from_being_offered(
    tmp_path: Path,
) -> None:
    server = FakeSuiteServer(INKLING.wire_id, fail_required=frozenset({2}))
    report = await qualified(server, tmp_path, INKLING.id.value)
    assert report["summary"]["tool_required"] == {"passed": 2, "failed": 1}
    failed = [t for t in report["trials"] if t["fixture"] == "tool_required" and t["trial"] == 2]
    assert failed[0]["verdict"] == "failed"
    assert report["offerable"] is False and report["recorded_status"] == "not_qualified"
    assert "tool_required" in report["limits"]
    assert "tool_required passed 2 of 3" in report["limits_text"]
    # Recorded as the report says, the profile isn't offered, and the reason says what failed.
    stored = RouteQualification(
        profile=INKLING.id,
        canonical_id=INKLING.canonical_id,
        status="not_qualified",
        qualified_on=date(2026, 11, 27),
        configuration="fake",
        limits=report["limits_text"],
    )
    (offer,) = [o for o in local_offers([stored]) if o.profile == INKLING.id]
    assert offer.offered is False and offer.reason is not None and "tool_required" in offer.reason


@pytest.mark.asyncio
@pytest.mark.parametrize("served", ["another-model", None])
async def test_a_wrong_or_stopped_server_refuses_with_nothing_sent(
    tmp_path: Path, served: str | None
) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    server = FakeSuiteServer(served or BONSAI.wire_id)
    transport = server.transport if served else httpx.MockTransport(down)
    with pytest.raises(Refused, match="nothing was sent"):
        await rq.qualify_local(BONSAI.id.value, tmp_path, DEFAULT_PORT, transport=transport)
    assert [r.url.path for r in server.requests] in ([], ["/v1/models"])
    assert list(tmp_path.iterdir()) == []  # noqa: ASYNC240 - the test reads its own temporary folder, after the run


@pytest.mark.asyncio
async def test_an_openrouter_profile_isnt_a_local_route(tmp_path: Path) -> None:
    with pytest.raises(Refused, match="isn't a local profile"):
        await rq.qualify_local("openrouter_terra", tmp_path, DEFAULT_PORT)


def _record(profile: ModelProfile, status: str, canonical: str | None = None) -> RouteQualification:
    row = RouteQualificationRow(
        profile=profile.id.value,
        canonical_id=canonical or profile.canonical_id,
        status=status,
        qualified_on=date(2026, 11, 27),
        configuration="llama-server 1.1.0, three trials",
        limits="Every fixture passed in all three trials.",
    )
    return qualification_from_record(profile.id, profile.canonical_id, row)


def test_only_a_stored_passing_qualification_offers_a_local_profile() -> None:
    offers = {o.profile: o for o in local_offers([_record(BONSAI, "qualified_with_limits")])}
    bonsai, inkling = offers[BONSAI.id], offers[INKLING.id]
    assert bonsai.offered and bonsai.qualified_on == date(2026, 11, 27)
    assert bonsai.configuration and bonsai.limits and bonsai.reason is None
    assert not inkling.offered and inkling.reason is not None
    assert "Inkling 2 Mini" in inkling.reason and "no qualification is stored" in inkling.reason
    assert offered_locally([_record(BONSAI, "qualified_with_limits")]) == {BONSAI.id}


def test_a_record_for_another_model_offers_nothing() -> None:
    stale = _record(BONSAI, "qualified_with_limits", canonical="prism-ml/older@abc/old.gguf")
    assert offered_locally([stale]) == frozenset()


@pytest.mark.parametrize(
    "where", ["a new run", "the workspace default", "a role override", "an Expert's binding"]
)
def test_a_profile_offered_locally_is_still_refused_on_openrouter(where: str) -> None:
    assert BONSAI.id in offered_locally([_record(BONSAI, "qualified_with_limits")])
    assert BONSAI.id not in OFFERED_FOR_NEW_RUNS
    with pytest.raises(ProfileNotOffered) as refused:
        if where == "a new run":
            WorkspacePolicy().for_new_work(run_profile=BONSAI.id, require_offer=True)
        elif where == "the workspace default":
            validated_choice(BONSAI.id, {})
        elif where == "a role override":
            validated_choice(None, {"executor": BONSAI.id})
        else:
            require_offered(
                ExpertConfig(role_bindings={"executor": BONSAI.id}).role_bindings.values()
            )
    assert refused.value.code == "model_not_offered"


class FakeMeasuredServer:
    """llama-server's tokenizer, props and a streamed reply, for the measurements."""

    def __init__(self) -> None:
        self.prompts: list[int] = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tokenize":
            text = json.loads(request.content)["content"]
            return httpx.Response(200, json={"tokens": list(range(len(text.split())))})
        if request.url.path == "/props":
            return httpx.Response(
                200,
                json={
                    "build_info": "b12774-171527522",
                    "default_generation_settings": {"n_ctx": 65536},
                    "model_path": "/x",
                },
            )
        body = json.loads(request.content)
        prompt = len(body["messages"][0]["content"].split())
        self.prompts.append(prompt)
        events = [
            {"choices": [{"index": 0, "delta": {"content": "Words "}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {"content": "repeat."}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": prompt, "completion_tokens": 2}},
        ]
        text = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_each_size_is_timed_and_the_server_is_named_by_its_build_only() -> None:
    server = FakeMeasuredServer()
    result = await measurements.measure(
        DEFAULT_PORT,
        BONSAI.wire_id,
        {"chat_template_kwargs": {"enable_thinking": False}},
        transport=server.transport,
        sizes=(("8k", 80), ("32k", 320)),
    )
    assert set(result["sizes"]) == {"8k", "32k"}
    small, large = result["sizes"]["8k"], result["sizes"]["32k"]
    assert small["prompt_tokens"] and large["prompt_tokens"] > small["prompt_tokens"]
    # The larger prompt's reading speed counts only what the smaller one hadn't read.
    assert large["new_prompt_tokens"] == large["prompt_tokens"] - small["prompt_tokens"]
    for size in (small, large):
        assert size["first_content_seconds"] >= 0 and size["completion_tokens"] == 2
    assert result["server"] == {"build_info": "b12774-171527522", "n_ctx": 65536}
    assert result["peak_footprint_mb"] is None and result["peak_footprint_note"]


@pytest.mark.asyncio
async def test_the_cli_runs_a_local_route_with_no_paid_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    async def qualify(profile: str, out: Path, port: int, **options: object) -> dict[str, Any]:
        seen.update(profile=profile, port=port, measure=options.get("measure"))
        return {
            "evidence_class": "live_local",
            "calls": 39,
            "spent_usd": "0.00",
            "summary": {},
            "offerable": True,
            "limits_text": "Every fixture passed in all three trials.",
        }

    monkeypatch.setattr(rq, "qualify_local", qualify)
    arguments = argparse.Namespace(
        profile=BONSAI.id.value,
        out=str(tmp_path),
        paid=False,
        port=None,
        no_measure=True,
        reruns={},
        key_file="absent",
    )
    assert await rq._main(arguments) == 0
    assert seen == {"profile": BONSAI.id.value, "port": DEFAULT_PORT, "measure": None}
    assert json.loads(capsys.readouterr().out)["spent_usd"] == "0.00"
