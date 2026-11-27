"""LC-23's comparison and the capped runner, through the real factory and SDK, faked at HTTP."""

import asyncio
import json
import logging
import logging.config
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from autobots.application.model_admission import Pricing, worst_case_cost
from autobots.domain.models import OPENROUTER_PROFILES, PROFILES, ModelProfileId
from autobots.operations import reasoning_trial as trial
from autobots.operations.paid.ledger import Ledger
from autobots.operations.paid.pricing import CONTEXT_TOKENS, OUTPUT_TOKENS

KEY = SecretStr("sk-or-arranged-not-a-real-key")
TERRA = PROFILES[ModelProfileId.TERRA]
# The catalog's rates below, in micro-USD per million tokens, and one call's worst case at them.
LISTED = Pricing(1_000_000, 5_000_000)
WORST = worst_case_cost(LISTED, CONTEXT_TOKENS, OUTPUT_TOKENS)
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


def catalog(**terra: str) -> dict[str, Any]:
    """Every profile at LISTED's rates. Terra's pricing takes `terra` on top."""
    return {
        "data": [
            {
                "id": profile.wire_id,
                "canonical_slug": profile.canonical_id,
                "supported_parameters": ["max_tokens", "tools", "tool_choice"],
                "pricing": {
                    "prompt": "0.000001",
                    "completion": "0.000005",
                    **(terra if profile == TERRA else {}),
                },
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

    def __init__(
        self,
        reply_extra: dict[str, Any] | None = None,
        tool_call: bool = True,
        cost: float | None = 0.0001,
    ) -> None:
        self.reply_extra = reply_extra or {}
        self.tool_call = tool_call
        self.cost = cost
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
        usage: dict[str, Any] = {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
        if self.cost is not None:
            usage["cost"] = self.cost
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
    book = ledger(tmp_path, cap=WORST * trial.CALLS_PER_TRIAL - 1)
    result = run(route, book)
    assert result.outcome == "not_run"
    assert route.sent == []
    assert book.entries == []


def test_earlier_spend_counts_against_the_shared_cap(tmp_path: Path) -> None:
    book = ledger(tmp_path, cap=WORST * trial.CALLS_PER_TRIAL)
    book.reserve("earlier", 1)
    route = FakeRoute({"reasoning_details": DETAILS})
    assert run(route, book).outcome == "not_run"
    assert route.sent == []


@pytest.mark.asyncio
async def test_the_shared_cap_counts_the_reasoning_rate(tmp_path: Path) -> None:
    """A route can bill reasoning above its completion rate (POPS-01, Decision 0009)."""
    worst = worst_case_cost(Pricing(1_000_000, 20_000_000), CONTEXT_TOKENS, OUTPUT_TOKENS)
    route = FakeRoute({"reasoning_details": DETAILS})
    book = ledger(tmp_path, cap=worst * trial.CALLS_PER_TRIAL - 1)
    payload = catalog(internal_reasoning="0.00002")
    result = await trial.run_trial(TERRA, 1, KEY, payload, book, route.http)
    assert result.outcome == "not_run"
    assert route.sent == []
    assert book.entries == []


@pytest.mark.parametrize(
    "terra",
    [
        pytest.param({"prompt": "-1", "completion": "-1"}, id="variable"),
        pytest.param({"request": "-1"}, id="variable-request-fee"),
    ],
)
@pytest.mark.asyncio
async def test_a_route_with_no_bounded_price_is_not_run(
    tmp_path: Path, terra: dict[str, str]
) -> None:
    route = FakeRoute({"reasoning_details": DETAILS})
    book = ledger(tmp_path)
    results = await trial.run_all(
        KEY, catalog(**terra), book, 1, route.http, [ModelProfileId.TERRA]
    )
    assert [(result.outcome, result.reason) for result in results] == [("not_run", "Refused")]
    assert route.sent == []
    assert book.entries == []


def test_a_call_with_no_reported_charge_stays_held_under_one_name(tmp_path: Path) -> None:
    """The shared ledger names this outcome as the route qualification does (POPS-06)."""
    book = ledger(tmp_path)
    result = run(FakeRoute({"reasoning_details": DETAILS}, cost=None), book)
    assert result.reported_micro_usd == [None, None]
    assert [entry["state"] for entry in book.entries] == ["usage_unreported"] * 2
    assert book.committed() == WORST * trial.CALLS_PER_TRIAL


@pytest.mark.asyncio
async def test_a_cancelled_call_stays_held_as_uncertain_and_the_cancellation_propagates(
    tmp_path: Path,
) -> None:
    book = ledger(tmp_path)

    async def send() -> Any:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await trial._paid_call(book, "arranged", WORST, send)
    assert [(entry["state"], entry["reported"]) for entry in book.entries] == [("uncertain", None)]
    assert book.committed() == WORST


@pytest.mark.parametrize("given", ["absolute", "default"])
def test_the_shared_ledger_does_not_depend_on_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str, restore_logging: None
) -> None:
    """Decision 0009's cap is counted in one file wherever the trial starts (POPS-07)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "keys.env").write_text(f"OPENROUTER_API_KEY={KEY.get_secret_value()}\n")
    opened: list[Path] = []

    def record(path: Path, cap: int) -> Ledger:
        opened.append(path)
        return Ledger(tmp_path / "arranged-ledger.json", cap)

    async def fetch() -> dict[str, Any]:
        return catalog()

    async def no_usage(_: SecretStr) -> None:
        return None

    async def nothing_sent(*_: Any, **__: Any) -> list[trial.TrialResult]:
        return []

    monkeypatch.setattr(trial, "catalog_fetcher", lambda: fetch)
    monkeypatch.setattr(trial, "Ledger", record)
    monkeypatch.setattr(trial, "key_usage", no_usage)
    monkeypatch.setattr(trial, "run_all", nothing_sent)
    elsewhere = tmp_path / "elsewhere/ledger.json"
    chosen = ["--ledger", str(elsewhere)] if given == "absolute" else []
    arguments = ["--paid", "--key-file", "keys.env", "--out", str(tmp_path / "out"), *chosen]
    monkeypatch.setattr("sys.argv", ["reasoning_trial", *arguments])
    assert trial.main() == 0
    repository = Path(__file__).resolve().parents[3]
    shared = repository / ".checks/decision-0009/ledger.json"
    assert opened == [elsewhere if given == "absolute" else shared]


@pytest.mark.asyncio
async def test_a_failed_call_stays_held_at_its_worst_case(tmp_path: Path) -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"code": 500, "message": "arranged"}})

    def http(exchanges: trial.Exchanges) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(refuse),
            event_hooks={"request": [exchanges.on_request], "response": [exchanges.on_response]},
        )

    book = ledger(tmp_path)
    result = await trial.run_trial(TERRA, 1, KEY, catalog(), book, http)
    assert result.outcome == "not_exercised"
    assert book.committed() == WORST
    assert book.entries[0]["state"] == "uncertain"


@pytest.mark.asyncio
async def test_no_metadata_or_key_reaches_the_report_or_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    route = FakeRoute({"reasoning": f"{MARKER}-text", "reasoning_details": DETAILS})
    book = ledger(tmp_path)
    results = await trial.run_all(KEY, catalog(), book, 1, route.http)
    assert {result.outcome for result in results} == {"survived"}
    # The paid trial covers the profiles OpenRouter answers (Decision 0041 A2).
    assert {result.profile for result in results} == set(OPENROUTER_PROFILES)
    trial.write_report(tmp_path, results, book, {"usage": 1.0}, {"usage": 1.1})
    written = (tmp_path / "report.json").read_text() + (tmp_path / "ledger.json").read_text()
    assert MARKER not in written
    assert KEY.get_secret_value() not in written
    assert MARKER not in caplog.text


@pytest.mark.asyncio
async def test_key_usage_keeps_only_the_three_figures() -> None:
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

    assert await trial.key_usage(KEY, client) == {
        "usage": 0.5,
        "limit": 1,
        "limit_remaining": 0.5,
    }


def test_nothing_is_sent_without_paid(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, restore_logging: None
) -> None:
    monkeypatch.setattr("sys.argv", ["reasoning_trial"])
    assert trial.main() == 0
    assert "not_sent" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_a_network_error_reading_usage_isnt_reported_as_a_figure() -> None:
    from autobots.operations.reasoning_trial import key_usage

    def client() -> httpx.AsyncClient:
        def fail(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route")

        return httpx.AsyncClient(base_url="https://x.invalid", transport=httpx.MockTransport(fail))

    from pydantic import SecretStr

    assert await key_usage(SecretStr("sk-or-arranged"), client) is None


@pytest.mark.asyncio
async def test_a_usage_reply_that_isnt_json_isnt_reported_as_a_figure() -> None:
    from pydantic import SecretStr

    from autobots.operations.reasoning_trial import key_usage

    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://x.invalid",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>")),
        )

    assert await key_usage(SecretStr("sk-or-arranged"), client) is None
