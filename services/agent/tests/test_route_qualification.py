"""The paid runner on a fake transport, through the real factory, adapter and SDK."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable
from autobots.adapters.models.factory import default_sdk_client
from autobots.operations import route_qualification as rq

WIRE_ID = "deepseek/deepseek-v4.1-flash-1017"
CANONICAL = "deepseek/deepseek-v4.1-flash-20261017"
KEY = "sk-or-arranged-not-a-real-key"
PARAMETERS = ["max_tokens", "tools", "tool_choice", "response_format", "structured_outputs"]


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


def test_only_the_authorized_route_can_be_paid_for(tmp_path: Path) -> None:
    ledger = rq.Ledger(tmp_path / "ledger.json", 500_000)
    with pytest.raises(rq.Refused, match="isn't authorized"):
        rq.preflight("openrouter_astra", catalog(), ledger)
    assert rq.AUTHORIZED_CAPS == {"openrouter_deepseek_flash": 500_000}


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
