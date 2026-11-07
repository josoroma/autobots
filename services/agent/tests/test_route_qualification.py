"""The paid runner on a fake transport, through the real factory, adapter and SDK."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable
from autobots.adapters.models.factory import default_sdk_client
from autobots.domain.models import PROFILES
from autobots.operations import route_qualification as rq

WIRE_ID = "deepseek/deepseek-v4.1-flash-1017"
CANONICAL = "deepseek/deepseek-v4.1-flash-20261017"
KEY = "sk-or-arranged-not-a-real-key"
PARAMETERS = [
    "max_tokens",
    "tools",
    "tool_choice",
    "response_format",
    "structured_outputs",
    "reasoning",
]


def catalog(prompt: str = "0.00000015", completion: str = "0.0000006") -> dict[str, Any]:
    return {
        "data": [
            {
                "id": WIRE_ID,
                "canonical_slug": CANONICAL,
                "supported_parameters": PARAMETERS,
                "pricing": {"prompt": prompt, "completion": completion},
            }
        ]
    }


def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "call-1",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class Fake:
    """Answers each fixture the way a working route would, unless told otherwise."""

    def __init__(self, cost: float | None = 0.00002, fail_with: int | None = None) -> None:
        self.bodies: list[dict[str, Any]] = []
        self.cost = cost
        self.fail_with = fail_with
        self.authorization: set[str] = set()

    def _message(self, body: dict[str, Any]) -> tuple[dict[str, Any], str]:
        text = json.dumps(body["messages"])
        tools = [tool["function"]["name"] for tool in body.get("tools") or []]
        choice = body.get("tool_choice")
        if body.get("response_format"):
            name = body["response_format"]["json_schema"]["name"]
            content: dict[str, Any]
            if name == "Decision":
                content = {"choice": "reject", "reason": "It is destructive."}
            else:
                task = {"id": "a", "title": "t", "priority": "low", "criteria": ["c"]}
                content = {"place": 'São José, 東京 "quoted"', "tasks": [task, {**task, "id": "b"}]}
            return {"role": "assistant", "content": json.dumps(content)}, "stop"
        if isinstance(choice, dict):
            name = choice["function"]["name"]
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [_tool_call(name, {"city": "Heredia"})],
            }, "tool_calls"
        if "73914" in text:
            return {"role": "assistant", "content": "The code is 73914."}, "stop"
        if tools == ["LookupCode"]:
            call = _tool_call("LookupCode", {"item": "alpha"})
            return {"role": "assistant", "content": "", "tool_calls": [call]}, "tool_calls"
        if tools and (choice in {"required", "any"} or "weather" in text.lower()):
            call = _tool_call("Weather", {"city": "Heredia"})
            return {"role": "assistant", "content": "", "tool_calls": [call]}, "tool_calls"
        if body.get("max_tokens") == 16:
            return {"role": "assistant", "content": "The valley"}, "length"
        if "social security" in text:
            return {"role": "assistant", "content": "Sorry, I can't help with that."}, "stop"
        if "Count from 1" in text:
            numbers = " ".join(str(number) for number in range(1, 21))
            return {"role": "assistant", "content": numbers}, "stop"
        return {"role": "assistant", "content": "ready"}, "stop"

    def _usage(self) -> dict[str, Any]:
        usage: dict[str, Any] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        if self.cost is not None:
            usage["cost"] = self.cost
        return usage

    def _stream(self, body: dict[str, Any], message: dict[str, Any], finish: str) -> bytes:
        base = {
            "id": "gen",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": body["model"],
        }
        lines = []

        def emit(delta: dict[str, Any], reason: str | None = None) -> None:
            choice = {"index": 0, "delta": delta, "finish_reason": reason}
            lines.append(f"data: {json.dumps({**base, 'choices': [choice]})}\n\n")

        if message.get("tool_calls"):
            call = message["tool_calls"][0]
            arguments = call["function"]["arguments"]
            emit(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["function"]["name"], "arguments": ""},
                        }
                    ],
                }
            )
            for start in range(0, len(arguments), 4):
                piece = {"index": 0, "function": {"arguments": arguments[start : start + 4]}}
                emit({"tool_calls": [piece]})
        else:
            for word in str(message["content"]).split(" "):
                emit({"role": "assistant", "content": word + " "})
            # A long request keeps going, so the cancellation fixture has chunks to stop on.
            if "400 word" in json.dumps(body["messages"]):
                for _ in range(3):
                    emit({"content": "more "})
        emit({"content": ""}, finish)
        lines.append(f"data: {json.dumps({**base, 'choices': [], 'usage': self._usage()})}\n\n")
        lines.append("data: [DONE]\n\n")
        return "".join(lines).encode()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.authorization.add(request.headers.get("authorization", ""))
        body = json.loads(request.content)
        self.bodies.append(body)
        if self.fail_with:
            return httpx.Response(
                self.fail_with, json={"error": {"code": self.fail_with, "message": "no"}}
            )
        message, finish = self._message(body)
        if body.get("stream"):
            headers = {"content-type": "text/event-stream"}
            return httpx.Response(200, headers=headers, content=self._stream(body, message, finish))
        return httpx.Response(
            200,
            json={
                "id": "gen",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "provider": "FakeUpstream",
                "system_fingerprint": "fake",
                "choices": [{"index": 0, "finish_reason": finish, "message": message}],
                "usage": self._usage(),
            },
        )


def client_with(fake: Fake) -> Any:
    transport = httpx.MockTransport(fake)

    def make(key: str) -> Any:
        return default_sdk_client(
            key,
            http=httpx.Client(transport=transport),
            async_http=httpx.AsyncClient(transport=transport),
        )

    return make


def run(tmp_path: Path, fake: Fake, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    async def fetch() -> dict[str, Any] | None:
        return catalog() if payload is None else payload

    return asyncio.run(
        rq.qualify(
            "openrouter_deepseek_flash",
            SecretStr(KEY),
            tmp_path,
            fetch,
            make_client=client_with(fake),
        )
    )


def test_a_working_route_passes_every_fixture_and_reports_fake_evidence(tmp_path: Path) -> None:
    fake = Fake()
    report = run(tmp_path, fake)
    assert report["evidence_class"] == "fake_transport"
    assert set(report["summary"]) == {
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
    }
    failed = [t for t in report["trials"] if t["verdict"] != "passed"]
    assert failed == []
    assert report["calls"] == rq.planned_calls() == len(fake.bodies)


def test_every_request_keeps_the_route_rules(tmp_path: Path) -> None:
    fake = Fake()
    run(tmp_path, fake)
    for body in fake.bodies:
        assert body["model"] == WIRE_ID
        assert body["provider"]["allow_fallbacks"] is False
        assert body["provider"]["require_parameters"] is True
        assert body["max_tokens"] <= rq.OUTPUT_TOKENS
    assert fake.authorization == {f"Bearer {KEY}"}


def test_the_named_selector_is_sent_against_the_prompts_preference(tmp_path: Path) -> None:
    fake = Fake()
    run(tmp_path, fake)
    named = [b for b in fake.bodies if "Never use the Weather tool" in json.dumps(b["messages"])]
    assert len(named) == rq.TRIALS
    for body in named:
        assert {tool["function"]["name"] for tool in body["tools"]} == {"Weather", "ClockTime"}
        assert body["tool_choice"]["function"]["name"] == "Weather"


def test_a_call_with_no_reported_charge_stays_at_the_worst_case(tmp_path: Path) -> None:
    report = run(tmp_path, Fake(cost=None))
    worst = report["worst_case_micro_usd_per_call"]
    assert report["reported_micro_usd"] == 0
    assert report["committed_micro_usd"] == worst * rq.planned_calls()


def test_a_cancelled_stream_is_never_counted_as_free(tmp_path: Path) -> None:
    report = run(tmp_path, Fake())
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    cancelled = [e for e in ledger["entries"] if e["label"].startswith("cancellation")]
    assert len(cancelled) == rq.TRIALS
    assert all(e["state"] == "uncertain" and e["reported"] is None for e in cancelled)
    assert report["calls_without_a_reported_charge"] == rq.TRIALS


def test_a_route_error_is_recorded_and_not_retried_or_replaced(tmp_path: Path) -> None:
    fake = Fake(fail_with=404)
    report = run(tmp_path, fake)
    assert {body["model"] for body in fake.bodies} == {WIRE_ID}
    assert len(fake.bodies) <= rq.planned_calls()
    assert all(t["verdict"] != "passed" for t in report["trials"])
    assert report["summary"]["tool_named_conflict"] == {"unsupported": rq.TRIALS}


def test_a_failed_call_stays_charged(tmp_path: Path) -> None:
    report = run(tmp_path, Fake(fail_with=500))
    assert (
        report["committed_micro_usd"] == report["worst_case_micro_usd_per_call"] * report["calls"]
    )


def test_an_unaffordable_plan_is_refused_before_anything_is_sent(tmp_path: Path) -> None:
    fake = Fake()
    with pytest.raises(rq.Refused, match="won't fit"):
        run(tmp_path, fake, catalog(prompt="0.001", completion="0.001"))
    assert fake.bodies == []


def test_spend_from_an_earlier_run_counts_against_the_cap(tmp_path: Path) -> None:
    run(tmp_path, Fake())
    earlier = json.loads((tmp_path / "ledger.json").read_text())["committed"]
    ledger = rq.Ledger(tmp_path / "ledger.json", rq.AUTHORIZED_CAPS["openrouter_deepseek_flash"])
    assert ledger.committed() == earlier
    ledger.reserve("big", ledger.cap - earlier)
    fake = Fake()
    with pytest.raises(rq.Refused, match="won't fit"):
        run(tmp_path, fake)
    assert fake.bodies == []


def test_the_ledger_stops_a_call_that_would_pass_the_cap(tmp_path: Path) -> None:
    ledger = rq.Ledger(tmp_path / "ledger.json", 100)
    ledger.reserve("first", 60)
    with pytest.raises(rq.CapReached):
        ledger.reserve("second", 60)
    assert rq.Ledger(tmp_path / "ledger.json", 100).committed() == 60


def test_the_corpus_stops_cleanly_at_the_cap(tmp_path: Path) -> None:
    fake = Fake(cost=None)
    ledger = rq.Ledger(tmp_path / "ledger.json", 3_000)

    def build(max_tokens: int = rq.OUTPUT_TOKENS) -> Any:
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(
            model=WIRE_ID,
            api_key=SecretStr(KEY),
            client=client_with(fake)(KEY),
            max_tokens=max_tokens,
        )

    results = asyncio.run(rq.Corpus(build, ledger, 1_500).run())
    assert results[-1].verdict == "not_run"
    assert len(fake.bodies) == 2
    assert ledger.committed() <= ledger.cap


def test_only_the_authorized_routes_can_be_paid_for(tmp_path: Path) -> None:
    ledger = rq.Ledger(tmp_path / "ledger.json", 500_000)
    with pytest.raises(rq.Refused, match="isn't authorized"):
        rq.preflight("openrouter_astra", catalog(), ledger)
    assert rq.AUTHORIZED_CAPS == {
        "openrouter_deepseek_flash": 500_000,
        "deepseek_low_reasoning": 600_000,
        "openai_gpt_6_1_terra": 1_200_000,
        "openai_gpt_6_1_sol": 1_200_000,
    }
    assert set(rq.ROUTES) == set(rq.AUTHORIZED_CAPS)


def test_every_approved_profile_has_a_route_to_qualify() -> None:
    """Otherwise "each enabled route" could quietly stop meaning the routes the app uses."""
    routes = {(route.wire_id, route.canonical_id) for route in rq.ROUTES.values()}
    for profile in PROFILES.values():
        assert (profile.wire_id, profile.canonical_id) in routes


def test_no_application_code_asks_for_strict_output() -> None:
    """Decision 0005: a capability that failed qualification stays disabled until it passes."""
    asks = re.compile(r"with_structured_output|response_format|bind_tools\([^)]*strict")
    source = Path(rq.__file__).parents[1]
    found = [
        path.relative_to(source).as_posix()
        for path in source.rglob("*.py")
        if path != Path(rq.__file__) and asks.search(path.read_text())
    ]
    assert found == []


def _with_terra() -> dict[str, Any]:
    payload = catalog()
    payload["data"].append(
        {
            "id": "openai/gpt-6.1-terra",
            "canonical_slug": "openai/gpt-6.1-terra-20261026",
            "supported_parameters": PARAMETERS,
            "pricing": {"prompt": "0.000001", "completion": "0.000005"},
        }
    )
    return payload


def _qualify(tmp_path: Path, fake: Fake, profile: str, only: Any = None) -> dict[str, Any]:
    async def fetch() -> dict[str, Any]:
        return _with_terra()

    return asyncio.run(
        rq.qualify(
            profile, SecretStr(KEY), tmp_path, fetch, make_client=client_with(fake), only=only
        )
    )


def test_terra_runs_the_whole_corpus_at_its_own_price_and_no_other_model(tmp_path: Path) -> None:
    fake = Fake()
    report = _qualify(tmp_path, fake, "openai_gpt_6_1_terra")
    assert {body["model"] for body in fake.bodies} == {"openai/gpt-6.1-terra"}
    assert all(body["provider"]["allow_fallbacks"] is False for body in fake.bodies)
    assert report["worst_case_micro_usd_per_call"] == 10_752
    assert report["calls"] == rq.planned_calls()
    assert (tmp_path / "report-openai_gpt_6_1_terra.json").exists()


def test_low_reasoning_is_sent_and_shares_the_terra_cap(tmp_path: Path) -> None:
    _qualify(tmp_path, Fake(cost=None), "openai_gpt_6_1_terra")
    spent = json.loads((tmp_path / "ledger.json").read_text())["committed"]
    fake = Fake()
    only = {"schema_nested": 3}
    report = _qualify(tmp_path, fake, "deepseek_low_reasoning", only)
    assert len(fake.bodies) == 3
    assert all(body["reasoning"] == {"effort": "low"} for body in fake.bodies)
    assert {body["model"] for body in fake.bodies} == {WIRE_ID}
    assert report["committed_micro_usd"] > spent
    assert report["cap_micro_usd"] == 600_000


def test_an_option_the_catalog_doesnt_list_is_refused_before_sending(tmp_path: Path) -> None:
    payload = catalog()
    payload["data"][0]["supported_parameters"] = ["max_tokens"]
    ledger = rq.Ledger(tmp_path / "ledger.json", 600_000)
    with pytest.raises(ModelUnavailable):
        rq.preflight("deepseek_low_reasoning", payload, ledger, {"schema_nested": 3})


def test_a_catalog_drift_stops_the_run(tmp_path: Path) -> None:
    drifted = catalog()
    drifted["data"][0]["canonical_slug"] = "deepseek/another-model"
    fake = Fake()
    with pytest.raises(ModelUnavailable):
        run(tmp_path, fake, drifted)
    assert fake.bodies == []


def test_the_key_is_read_alone_and_reaches_no_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_file = tmp_path / "keys.env"
    env_file.write_text(f'OTHER=keep-out\nexport OPENROUTER_API_KEY="{KEY}"\n')
    key = rq.read_key(env_file)
    assert key.get_secret_value() == KEY
    assert KEY not in repr(key)
    report = run(tmp_path, Fake())
    captured = capsys.readouterr()
    written = (tmp_path / "report.json").read_text() + (tmp_path / "ledger.json").read_text()
    for text in (captured.out, captured.err, written, json.dumps(report, ensure_ascii=False)):
        assert KEY not in text


def test_a_missing_key_refuses(tmp_path: Path) -> None:
    env_file = tmp_path / "keys.env"
    env_file.write_text("OPENROUTER_API_KEY=\n")
    with pytest.raises(rq.Refused):
        rq.read_key(env_file)


def test_nothing_is_sent_without_the_paid_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = type("Args", (), {"paid": False, "out": str(tmp_path), "key_file": "absent"})()
    assert asyncio.run(rq._main(arguments)) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "not_sent"
    assert list(tmp_path.iterdir()) == []


def test_a_decline_is_recognized_with_either_apostrophe() -> None:
    assert rq.reads_as_declined("I can\u2019t help with that.")
    assert rq.reads_as_declined("I can't help with that.")
    assert not rq.reads_as_declined("Here is the number: 078-05-1120")


def test_a_rerun_sends_only_what_was_named_and_keeps_the_full_report(tmp_path: Path) -> None:
    run(tmp_path, Fake())
    full = (tmp_path / "report.json").read_text()
    committed = json.loads(full)["committed_micro_usd"]
    fake = Fake()

    async def fetch() -> dict[str, Any]:
        return catalog()

    report = asyncio.run(
        rq.qualify(
            "openrouter_deepseek_flash",
            SecretStr(KEY),
            tmp_path,
            fetch,
            make_client=client_with(fake),
            only={"refusal": 3, "schema_nested": 1},
        )
    )
    assert len(fake.bodies) == 4
    assert report["summary"] == {"schema_nested": {"passed": 1}, "refusal": {"passed": 3}}
    assert report["committed_micro_usd"] > committed
    assert (tmp_path / "report.json").read_text() == full


def test_a_refused_request_keeps_its_reason_and_the_constrained_schema_runs_only_if_asked(
    tmp_path: Path,
) -> None:
    fake = Fake(fail_with=400)
    only = {"schema_nested_constrained": 1}
    report = _qualify(tmp_path, fake, "openai_gpt_6_1_terra", only)
    assert len(fake.bodies) == 1
    trial = report["trials"][0]
    assert trial["verdict"] == "unsupported"
    assert trial["observed"]["status"] == 400
    assert "detail" in trial["observed"]
    assert KEY not in json.dumps(report)
    schema = json.dumps(fake.bodies[0]["response_format"])
    assert "minItems" in schema


def test_the_plain_nested_schema_sends_no_length_keywords(tmp_path: Path) -> None:
    fake = Fake()
    _qualify(tmp_path, fake, "openai_gpt_6_1_terra", {"schema_nested": 1})
    assert "minItems" not in json.dumps(fake.bodies[0]["response_format"])


def test_the_closed_schema_closes_every_object(tmp_path: Path) -> None:
    fake = Fake()
    _qualify(tmp_path, fake, "openai_gpt_6_1_terra", {"schema_nested_closed": 1})
    schema = fake.bodies[0]["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["tasks"]["items"]["additionalProperties"] is False


def test_the_worst_case_uses_the_highest_rate_a_time_window_can_charge() -> None:
    payload = catalog()
    payload["data"][0]["pricing"]["overrides"] = [
        {"utc_days": ["monday"], "prompt": "0.0000003", "completion": "0.0000012"},
        {"min_prompt_tokens": 272000, "prompt": "0.01", "completion": "0.01"},
    ]
    price = rq.price_of(payload, WIRE_ID)
    assert (price.prompt_usd, price.completion_usd) == (0.0000003, 0.0000012)
