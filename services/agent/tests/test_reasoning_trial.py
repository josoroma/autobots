"""LC-23's comparison and the capped runner, through the real factory and SDK, faked at HTTP."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from autobots.domain.models import PROFILES, ModelProfileId
from autobots.operations import reasoning_trial as trial
from autobots.operations.route_qualification import Ledger, price_of

KEY = SecretStr("sk-or-arranged-not-a-real-key")
TERRA = PROFILES[ModelProfileId.TERRA]
MARKER = "ARRANGED-METADATA"
DETAILS = [
    {
        "type": "reasoning.encrypted",
        "data": f"{MARKER}-1",
        "format": "openai-responses-v1",
        "index": 1,
    },
    {"type": "reasoning.text", "text": f"{MARKER}-2", "format": "openai-responses-v1", "index": 0},
]


def catalog() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": profile.wire_id,
                "canonical_slug": profile.canonical_id,
                "supported_parameters": ["max_tokens", "tools", "tool_choice"],
                "pricing": {"prompt": "0.000001", "completion": "0.000005"},
            }
            for profile in PROFILES.values()
        ]
    }


def message(**extra: Any) -> dict[str, Any]:
    call = {"id": "call-1", "type": "function", "function": {"name": "n", "arguments": "{}"}}
    return {"role": "assistant", "content": None, "tool_calls": [call], **extra}


def test_unchanged_metadata_survives() -> None:
    result = trial.continuation_result(
        message(reasoning="r", reasoning_details=DETAILS),
        [{"role": "user"}, message(reasoning="r", reasoning_details=DETAILS)],
    )
    assert result.outcome == "survived"
    assert result.details == 2
    assert result.kinds == ("reasoning.encrypted", "reasoning.text")


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        (message(reasoning="r"), "reasoning_details removed"),
        (message(reasoning="r", reasoning_details=DETAILS[:1]), "went from 2 entries to 1"),
        (
            message(reasoning="r", reasoning_details=DETAILS[::-1]),
            "reasoning_details[0].type changed",
        ),
        (message(reasoning="other", reasoning_details=DETAILS), "reasoning changed"),
        (
            message(
                reasoning="r",
                reasoning_details=[{**DETAILS[0], "data": "altered"}, DETAILS[1]],
            ),
            "reasoning_details[0].data changed",
        ),
        ({"role": "assistant", "content": "x"}, "not sent back"),
    ],
)
def test_dropped_altered_or_reordered_is_reported_with_no_content(
    sent: dict[str, Any], expected: str
) -> None:
    result = trial.continuation_result(message(reasoning="r", reasoning_details=DETAILS), [sent])
    assert result.outcome == "dropped"
    assert any(expected in difference for difference in result.differences)
    assert MARKER not in json.dumps(result.differences)


def test_nothing_returned_is_not_survived() -> None:
    assert trial.continuation_result(message(), [message()]).outcome == "not_returned"


class FakeRoute:
    """Replies with a tool call, then an answer, and logs the requests it was sent."""

    def __init__(self, reply_extra: dict[str, Any] | None = None, tool_call: bool = True) -> None:
        self.reply_extra = reply_extra or {}
        self.tool_call = tool_call
        self.sent: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.sent.append(body)
        first = len(self.sent) % 2 == 1 and self.tool_call
        choice: dict[str, Any] = {
            "index": 0,
            "finish_reason": "tool_calls" if first else "stop",
            "message": message(**self.reply_extra)
            if first
            else {"role": "assistant", "content": "The code is 73914."},
        }
        if first:
            call = choice["message"]["tool_calls"][0]
            call["function"]["name"] = "LookupCode"
            call["function"]["arguments"] = '{"item": "alpha"}'
        usage = {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12, "cost": 0.0001}
        return httpx.Response(
            200,
            json={
                "id": "fake",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "system_fingerprint": "fake",
                "choices": [choice],
                "usage": usage,
            },
        )

    def http(self, exchanges: trial.Exchanges) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self),
            event_hooks={"request": [exchanges.on_request], "response": [exchanges.on_response]},
        )


def run(route: FakeRoute, ledger: Ledger) -> trial.TrialResult:
    return asyncio.run(trial.run_trial(TERRA, 1, KEY, catalog(), ledger, route.http))


def ledger(tmp_path: Path, cap: int = trial.SHARED_CAP_MICRO_USD) -> Ledger:
    return Ledger(tmp_path / "ledger.json", cap)


def test_the_real_sdk_sends_plain_metadata_back_unchanged(tmp_path: Path) -> None:
    route = FakeRoute({"reasoning": "r", "reasoning_details": DETAILS})
    book = ledger(tmp_path)
    result = run(route, book)
    assert result.outcome == "survived"
    assert result.continued_with_the_tool_value is True
    assert result.reported_micro_usd == [100, 100]
    assert book.committed() == 200
    assert len(route.sent) == 2


def test_an_altered_id_reads_as_lost_and_names_where(tmp_path: Path) -> None:
    """The pinned SDK strips OpenAI Responses `rs_` ids, so this is what such a route would see."""
    details = [{**DETAILS[0], "id": "rs_arranged"}]
    result = run(FakeRoute({"reasoning_details": details}), ledger(tmp_path))
    assert result.outcome == "lost"
    assert result.differences == ("reasoning_details[0].id removed",)


def test_a_route_returning_no_metadata_is_not_exercised(tmp_path: Path) -> None:
    route = FakeRoute()
    result = run(route, ledger(tmp_path))
    assert result.outcome == "not_exercised"
    assert "no reasoning metadata" in result.reason
    assert len(route.sent) == 1


def test_no_tool_call_is_not_exercised(tmp_path: Path) -> None:
    result = run(FakeRoute(tool_call=False), ledger(tmp_path))
    assert result.outcome == "not_exercised"
    assert "no tool call" in result.reason


def test_the_cap_stops_the_trial_before_any_request(tmp_path: Path) -> None:
    route = FakeRoute({"reasoning_details": DETAILS})
    worst = price_of(catalog(), TERRA.wire_id).worst_case_micro_usd()
    book = ledger(tmp_path, cap=worst * trial.CALLS_PER_TRIAL - 1)
    result = run(route, book)
    assert result.outcome == "not_run"
    assert route.sent == []
    assert book.entries == []


def test_earlier_spend_counts_against_the_shared_cap(tmp_path: Path) -> None:
    worst = price_of(catalog(), TERRA.wire_id).worst_case_micro_usd()
    book = ledger(tmp_path, cap=worst * trial.CALLS_PER_TRIAL)
    book.reserve("earlier", 1)
    route = FakeRoute({"reasoning_details": DETAILS})
    assert run(route, book).outcome == "not_run"
    assert route.sent == []


def test_a_failed_call_stays_held_at_its_worst_case(tmp_path: Path) -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"code": 500, "message": "arranged"}})

    def http(exchanges: trial.Exchanges) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(refuse),
            event_hooks={"request": [exchanges.on_request], "response": [exchanges.on_response]},
        )

    book = ledger(tmp_path)
    result = asyncio.run(trial.run_trial(TERRA, 1, KEY, catalog(), book, http))
    assert result.outcome == "not_exercised"
    assert book.committed() == price_of(catalog(), TERRA.wire_id).worst_case_micro_usd()
    assert book.entries[0]["state"] == "uncertain"


def test_no_metadata_or_key_reaches_the_report_or_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    route = FakeRoute({"reasoning": f"{MARKER}-text", "reasoning_details": DETAILS})
    book = ledger(tmp_path)
    results = asyncio.run(trial.run_all(KEY, catalog(), book, 1, route.http))
    assert {result.outcome for result in results} == {"survived"}
    assert {result.profile for result in results} == set(ModelProfileId)
    trial.write_report(tmp_path, results, book, {"usage": 1.0}, {"usage": 1.1})
    written = (tmp_path / "report.json").read_text() + (tmp_path / "ledger.json").read_text()
    assert MARKER not in written
    assert KEY.get_secret_value() not in written
    assert MARKER not in caplog.text


def test_key_usage_keeps_only_the_three_figures() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "label": "sk-or-v1-abc...xyz",
                    "usage": 0.5,
                    "limit": 1,
                    "limit_remaining": 0.5,
                }
            },
        )

    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://x.invalid", transport=httpx.MockTransport(handle)
        )

    assert asyncio.run(trial.key_usage(KEY, client)) == {
        "usage": 0.5,
        "limit": 1,
        "limit_remaining": 0.5,
    }


def test_nothing_is_sent_without_paid(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["reasoning_trial"])
    assert trial.main() == 0
    assert "not_sent" in capsys.readouterr().out
