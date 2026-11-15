"""LC-23: does reasoning metadata survive a tool continuation? US-11.2.

Run with `python -m autobots.operations.reasoning_trial`. Nothing is sent without `--paid`. Each
call goes through the real factory and SDK, and the comparison reads the actual HTTP bodies. Only
paths, counts and kinds are ever kept, so the metadata itself reaches no report and no log.

The ledger is shared with US-11.3's goals, under Decision 0009's US$1 cap. A call is held at its
worst case until it settles, and one with no reported charge stays there.
"""

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable
from autobots.adapters.models.factory import (
    PROVIDER_ROUTING,
    UnsupportedRequestOption,
    chat_model,
    default_sdk_client,
)
from autobots.adapters.models.openrouter_metadata import catalog_fetcher, http_client
from autobots.domain.models import PROFILES, ModelProfile, ModelProfileId
from autobots.logs import configure_logging, forbid_remote_tracing, log_event
from autobots.operations.cli import Refused, command
from autobots.operations.paid.attempts import CALL_SECONDS, Route, prepare
from autobots.operations.paid.keys import read_key
from autobots.operations.paid.ledger import CapReached, Ledger
from autobots.operations.paid.pricing import reported_micro_usd, trial_worst_case
from autobots.operations.route_fixtures import LookupCode

logger = logging.getLogger("autobots.reasoning_trial")
REPOSITORY = Path(__file__).resolve().parents[5]
# Decision 0009: the whole of what this trial and US-11.3's goals may spend, in micro-USD, and the
# ledger that counts it, relative to the repository root as scripts/persistent_install.py reads it.
SHARED_CAP_MICRO_USD = 1_000_000
SHARED_LEDGER = Path(".checks/decision-0009/ledger.json")
TRIALS = 2
CALLS_PER_TRIAL = 2
METADATA_FIELDS = ("reasoning_details", "reasoning")
SECRET_CODE = "73914"
# Some thought first, since a route with nothing to work out may return no reasoning to preserve.
PROMPT = (
    "Items are named after the Greek letter whose position in the alphabet equals how many prime "
    "numbers are below 10. Work out the item's name, look it up with the tool, then tell me the "
    "code."
)
MAX_KIND_CHARS = 40

Outcome = Literal["survived", "dropped", "not_returned"]


@dataclass(frozen=True)
class Comparison:
    outcome: Outcome
    # Where it differs, never what it held.
    differences: tuple[str, ...] = ()
    details: int = 0
    kinds: tuple[str, ...] = ()


def _differences(path: str, received: Any, sent: Any) -> list[str]:
    if isinstance(received, Mapping) and isinstance(sent, Mapping):
        found: list[str] = []
        for key in received:
            if key not in sent:
                found.append(f"{path}.{key} removed")
            else:
                found.extend(_differences(f"{path}.{key}", received[key], sent[key]))
        found.extend(f"{path}.{key} added" for key in sent if key not in received)
        return found
    if isinstance(received, list) and isinstance(sent, list):
        if len(received) != len(sent):
            return [f"{path} went from {len(received)} entries to {len(sent)}"]
        return [
            difference
            for index, pair in enumerate(zip(received, sent, strict=True))
            for difference in _differences(f"{path}[{index}]", *pair)
        ]
    return [] if received == sent else [f"{path} changed"]


def continuation_result(
    received: Mapping[str, Any], sent: Sequence[Mapping[str, Any]]
) -> Comparison:
    """`received` is the assistant message returned, and `sent` is the next request's messages.

    Survived means unchanged, in content and order. Anything else that was returned is dropped.
    """
    metadata = {name: received[name] for name in METADATA_FIELDS if received.get(name)}
    if not metadata:
        return Comparison("not_returned")
    details = metadata.get("reasoning_details")
    listed = details if isinstance(details, list) else []
    kinds = tuple(
        str(item.get("type"))[:MAX_KIND_CHARS] for item in listed if isinstance(item, Mapping)
    )
    call_ids = {call.get("id") for call in received.get("tool_calls") or []}
    echoed = next(
        (
            message
            for message in sent
            if message.get("role") == "assistant"
            and call_ids & {call.get("id") for call in message.get("tool_calls") or []}
        ),
        None,
    )
    if echoed is None:
        missing = ("the assistant message was not sent back",)
        return Comparison("dropped", missing, len(listed), kinds)
    differences: list[str] = []
    for name, value in metadata.items():
        if name not in echoed:
            differences.append(f"{name} removed")
        else:
            differences.extend(_differences(name, value, echoed[name]))
    outcome: Outcome = "dropped" if differences else "survived"
    return Comparison(outcome, tuple(differences), len(listed), kinds)


@dataclass
class Exchanges:
    """Parsed bodies of the last request and reply, in memory only, for one comparison."""

    requests: list[dict[str, Any]] = field(default_factory=list)
    replies: list[dict[str, Any]] = field(default_factory=list)

    async def on_request(self, request: httpx.Request) -> None:
        self.requests.append(json.loads(request.content))

    async def on_response(self, response: httpx.Response) -> None:
        await response.aread()
        try:
            self.replies.append(response.json())
        except ValueError:
            self.replies.append({})


HttpFactory = Callable[[Exchanges], httpx.AsyncClient]


def real_http(exchanges: Exchanges) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        event_hooks={"request": [exchanges.on_request], "response": [exchanges.on_response]}
    )


@dataclass
class TrialResult:
    profile: str
    wire_id: str
    canonical_id: str
    trial: int
    outcome: Literal["survived", "lost", "not_exercised", "not_run"]
    reason: str = ""
    differences: tuple[str, ...] = ()
    details: int = 0
    kinds: tuple[str, ...] = ()
    continued_with_the_tool_value: bool | None = None
    reasoning_tokens: list[int | None] = field(default_factory=list)
    reported_micro_usd: list[int | None] = field(default_factory=list)


def ledger_path(argument: str) -> Path:
    """`--ledger` from the repository root, so the shared cap's ledger is the same file wherever
    the trial starts (POPS-07). An absolute path stays as given."""
    return REPOSITORY / argument


async def _paid_call(
    ledger: Ledger, label: str, worst: int, send: Callable[[], Awaitable[Any]]
) -> tuple[Any, int | None]:
    """Written down at its worst case first. A failed, cancelled or unreported call stays held
    there (Decision 0009)."""
    async with ledger.charge(label, worst) as charge:
        message = await asyncio.wait_for(send(), timeout=CALL_SECONDS)
        charge.reported = reported_micro_usd(message)
    return message, charge.reported


def _reasoning_tokens(message: Any) -> int | None:
    usage = message.usage_metadata or {}
    details = usage.get("output_token_details") or {}
    value = details.get("reasoning")
    return value if isinstance(value, int) else None


async def run_trial(
    profile: ModelProfile,
    number: int,
    key: SecretStr,
    payload: Mapping[str, Any],
    ledger: Ledger,
    make_http: HttpFactory = real_http,
) -> TrialResult:
    result = TrialResult(profile.id, profile.wire_id, profile.canonical_id, number, "not_exercised")
    attempt, entry = prepare(Route(profile.wire_id, profile.canonical_id), payload)
    worst = trial_worst_case(entry)
    if ledger.committed() + worst * CALLS_PER_TRIAL > ledger.cap:
        result.outcome = "not_run"
        result.reason = "the worst case would pass the shared cap, so nothing was sent"
        return result
    exchanges = Exchanges()

    def make_client(api_key: str) -> Any:
        return default_sdk_client(api_key, async_http=make_http(exchanges))

    model = chat_model(attempt, key, client_factory=make_client).bind_tools(
        [LookupCode], tool_choice="auto"
    )
    history: list[Any] = [HumanMessage(PROMPT)]
    label = f"reasoning-trial:{profile.id}:{number}"
    try:
        first, reported = await _paid_call(
            ledger, f"{label}/1", worst, lambda: model.ainvoke(history)
        )
    except CapReached:
        result.outcome = "not_run"
        result.reason = "the shared cap was reached before the first call"
        return result
    except Exception as error:  # noqa: BLE001 - a paid trial's result names the failure's type
        result.reason = f"the first call failed: {type(error).__name__}"
        return result
    result.reported_micro_usd.append(reported)
    result.reasoning_tokens.append(_reasoning_tokens(first))
    choices = exchanges.replies[-1].get("choices") if exchanges.replies else None
    received = choices[0].get("message", {}) if choices else {}
    if not first.tool_calls:
        result.reason = "the route made no tool call, so there was nothing to continue"
        return result
    if not any(received.get(name) for name in METADATA_FIELDS):
        result.reason = "the route returned no reasoning metadata to preserve"
        return result
    history.append(first)
    history.append(ToolMessage(content='{"code": 73914}', tool_call_id=first.tool_calls[0]["id"]))
    try:
        second, reported = await _paid_call(
            ledger, f"{label}/2", worst, lambda: model.ainvoke(history)
        )
    except CapReached:
        result.outcome = "not_run"
        result.reason = "the shared cap was reached before the continuation"
        return result
    except Exception as error:  # noqa: BLE001 - a paid trial's result names the failure's type
        # What was sent can still be compared, since the request left before it failed.
        result.reason = f"the continuation failed: {type(error).__name__}"
        second, reported = None, None
    result.reported_micro_usd.append(reported)
    if second is not None:
        result.reasoning_tokens.append(_reasoning_tokens(second))
        result.continued_with_the_tool_value = SECRET_CODE in str(second.content)
    if len(exchanges.requests) < CALLS_PER_TRIAL:
        result.reason = result.reason or "the continuation request was never built"
        return result
    comparison = continuation_result(received, exchanges.requests[-1].get("messages", []))
    result.differences = comparison.differences
    result.details = comparison.details
    result.kinds = comparison.kinds
    result.outcome = "survived" if comparison.outcome == "survived" else "lost"
    return result


KeyUsage = Callable[[SecretStr], Awaitable[dict[str, Any] | None]]


async def key_usage(
    key: SecretStr, make_client: Callable[[], Any] = http_client
) -> dict[str, Any] | None:
    """Only the three figures. The rest of this reply names the key, so it goes no further."""
    headers = {"Authorization": f"Bearer {key.get_secret_value()}"}
    try:
        async with make_client() as client:
            reply = await client.get("/key", headers=headers)
    except httpx.HTTPError:
        return None
    if reply.status_code != httpx.codes.OK:
        return None
    try:
        data = reply.json().get("data") or {}
    except (ValueError, AttributeError):
        return None
    return {name: data.get(name) for name in ("usage", "limit", "limit_remaining")}


async def run_all(
    key: SecretStr,
    payload: Mapping[str, Any],
    ledger: Ledger,
    trials: int = TRIALS,
    make_http: HttpFactory = real_http,
    profiles: Sequence[ModelProfileId] = tuple(ModelProfileId),
) -> list[TrialResult]:
    results = []
    for profile_id in profiles:
        profile = PROFILES[profile_id]
        for number in range(1, trials + 1):
            try:
                results.append(await run_trial(profile, number, key, payload, ledger, make_http))
            except (Refused, ModelUnavailable, UnsupportedRequestOption) as refusal:
                # This route is refused, and the others' results still get reported.
                results.append(
                    TrialResult(
                        profile.id,
                        profile.wire_id,
                        profile.canonical_id,
                        number,
                        "not_run",
                        type(refusal).__name__,
                    )
                )
    return results


def write_report(
    out: Path,
    results: Sequence[TrialResult],
    ledger: Ledger,
    usage_before: Mapping[str, Any] | None,
    usage_after: Mapping[str, Any] | None,
) -> dict[str, Any]:
    report = {
        "schema_version": "autobots.reasoning-trial/v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "configuration": {
            "max_tokens": 512,
            "routing": dict(PROVIDER_ROUTING),
            "tool": "LookupCode",
        },
        "cap_micro_usd": ledger.cap,
        "committed_micro_usd": ledger.committed(),
        "key_usage_before": usage_before,
        "key_usage_after": usage_after,
        "results": [asdict(result) for result in results],
        "not_established": ["H1", "product acceptance", "LC-23 for any other reply shape"],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


async def _main(arguments: argparse.Namespace) -> int:
    forbid_remote_tracing(os.environ)
    configure_logging()
    if not arguments.paid:
        print(json.dumps({"status": "not_sent", "reason": "nothing is sent without --paid"}))
        return 0
    try:
        key = read_key(Path(arguments.key_file))
        payload = await catalog_fetcher()()
        if payload is None:
            raise Refused("the catalog couldn't be read, so nothing was sent")
        ledger = Ledger(ledger_path(arguments.ledger), SHARED_CAP_MICRO_USD)
        before = await key_usage(key)
        results = await run_all(
            key,
            payload,
            ledger,
            arguments.trials,
            profiles=[ModelProfileId(arguments.profile)]
            if arguments.profile
            else tuple(ModelProfileId),
        )
        after = await key_usage(key)
    except (Refused, ModelUnavailable, UnsupportedRequestOption) as refusal:
        raise Refused(f"nothing further was sent: {refusal}") from None
    write_report(Path(arguments.out), results, ledger, before, after)
    log_event(logger, "reasoning_trial.finished", calls=len(ledger.entries))
    print(
        json.dumps(
            {
                "results": [
                    {
                        name: getattr(result, name)
                        for name in (
                            "profile",
                            "trial",
                            "outcome",
                            "reason",
                            "differences",
                            "kinds",
                            "continued_with_the_tool_value",
                            "reasoning_tokens",
                            "reported_micro_usd",
                        )
                    }
                    for result in results
                ],
                "committed_micro_usd": ledger.committed(),
                "key_usage_before": before,
                "key_usage_after": after,
            },
            indent=1,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paid", action="store_true", help="really send requests")
    parser.add_argument("--key-file", default=".env")
    parser.add_argument("--ledger", default=str(SHARED_LEDGER))
    parser.add_argument("--out", default=".checks/reasoning-trial")
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--profile", choices=[profile.value for profile in ModelProfileId])
    arguments = parser.parse_args()
    return command(lambda: asyncio.run(_main(arguments)))


if __name__ == "__main__":
    raise SystemExit(main())
