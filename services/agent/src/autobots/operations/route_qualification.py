"""Qualification of one route, US-3.4: paid for an OpenRouter route, and free for a local one.

Run with `python -m autobots.operations.route_qualification`.

An OpenRouter route sends nothing without `--paid`. Each call is written down at its worst-case
price before it goes, so a crash can't lose track of spend, and an unclear outcome stays charged
at that price. Calls are never retried and no other model is ever tried. Fixtures
(`route_fixtures.py`) record what the route did, and a capability that fails or isn't supported
stays recorded as such. The ledger, key and pricing are shared with the other paid entry points
(`paid/`, POPS-05).

A local route (`--profile local_...`, Decision 0041 A7, US-23.2) runs the same fixtures against the
owner's llama-server on 127.0.0.1 on request, with no flag, cap, key or catalog. It checks the
served model first, writes every call down at a worst case of 0, and its report says whether the
five capabilities that gate offering passed in every trial.

Exit codes: 0 done or not sent, 1 refused with nothing sent, 2 a malformed argument (`cli.py`).
"""

import argparse
import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import SecretStr, ValidationError

from autobots.adapters.models.catalog import CatalogEntry, ModelUnavailable
from autobots.adapters.models.factory import (
    LocalServerUnavailable,
    LoopbackClient,
    PreparedAttempt,
    chat_model,
    check_served,
    local_chat_model,
)
from autobots.adapters.models.local_server import local_port
from autobots.adapters.models.openrouter_metadata import catalog_fetcher
from autobots.domain.models import PROFILES, ModelProfile, ModelRole
from autobots.logs import configure_logging, forbid_remote_tracing
from autobots.operations import local_route_measurements
from autobots.operations.cli import Refused, command, counts_argument
from autobots.operations.paid.attempts import Route, prepare
from autobots.operations.paid.keys import read_key
from autobots.operations.paid.ledger import Ledger
from autobots.operations.paid.pricing import OUTPUT_TOKENS, trial_worst_case
from autobots.operations.route_fixtures import TRIALS, QualificationRun, Trial

ROUTES = {
    "openrouter_deepseek_flash": Route(
        "deepseek/deepseek-v4.1-flash-1017", "deepseek/deepseek-v4.1-flash-20261017"
    ),
    "deepseek_low_reasoning": Route(
        "deepseek/deepseek-v4.1-flash-1017",
        "deepseek/deepseek-v4.1-flash-20261017",
        {"reasoning": {"effort": "low"}},
    ),
    "openai_gpt_6_1_terra": Route("openai/gpt-6.1-terra", "openai/gpt-6.1-terra-20261026"),
    "openai_gpt_6_1_sol": Route("openai/gpt-6.1-sol", "openai/gpt-6.1-sol-20260929"),
}
# What the owner approved, in micro-USD. Another route or a higher figure is a reviewed code change.
# The last two share one ledger, so together they can't pass that cap.
AUTHORIZED_CAPS = {
    "openrouter_deepseek_flash": 500_000,
    "deepseek_low_reasoning": 600_000,
    "openai_gpt_6_1_terra": 1_200_000,
    # Decision 0019 S4.
    "openai_gpt_6_1_sol": 1_200_000,
}


# Decision 0041 A7: what a local route must pass in all three trials before it is offered.
GATING = ("plain_text", "tool_auto", "tool_required", "schema_flat", "stream_text")
# Decision 0041's measurements table: how long one call on a local route may take.
LOCAL_CALL_SECONDS = 1_800.0
LOCAL_PROFILES: Mapping[str, ModelProfile] = {
    profile.id.value: profile for profile in PROFILES.values() if profile.local is not None
}
LocalClient = Callable[[ModelProfile, int], LoopbackClient]
Measure = Callable[[int, ModelProfile], Awaitable[dict[str, Any]]]


def summarize(results: list[Trial]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for result in results:
        counts = summary.setdefault(result.fixture, {})
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    return summary


def planned_calls(reruns: Mapping[str, int] | None = None) -> int:
    # Twelve fixtures, and continuation takes two calls.
    if not reruns:
        return 13 * TRIALS
    return sum(count * (2 if name == "continuation" else 1) for name, count in reruns.items())


def preflight(
    profile: str,
    payload: Mapping[str, Any],
    ledger: Ledger,
    reruns: Mapping[str, int] | None = None,
) -> tuple[CatalogEntry, int]:
    """Refuses before any model call, including when the plan can't fit what's left of the cap."""
    if profile not in AUTHORIZED_CAPS or profile not in ROUTES:
        raise Refused(f"{profile} isn't authorized for paid qualification")
    if ledger.cap != AUTHORIZED_CAPS[profile]:
        raise Refused("this ledger's cap isn't the authorized one")
    _, entry = prepare(ROUTES[profile], payload)
    worst = trial_worst_case(entry)
    calls = planned_calls(reruns)
    if ledger.committed() + worst * calls > ledger.cap:
        raise Refused(
            f"{calls} calls at {worst} micro-USD each won't fit in what's left of the cap"
        )
    return entry, worst


async def qualify(
    profile: str,
    key: SecretStr,
    out: Path,
    fetch_catalog: Callable[[], Awaitable[Any]],
    make_client: Callable[[str], Any] | None = None,
    reruns: dict[str, int] | None = None,
) -> dict[str, Any]:
    ledger = Ledger(out / "ledger.json", AUTHORIZED_CAPS.get(profile, 0))
    payload = await fetch_catalog()
    if payload is None:
        raise Refused("the catalog couldn't be read, so nothing was sent")
    entry, worst = preflight(profile, payload, ledger, reruns)
    built_at = time.monotonic()
    route = ROUTES[profile]

    def build(max_tokens: int = OUTPUT_TOKENS) -> Any:
        prepared, _ = prepare(route, payload, max_tokens)
        return chat_model(prepared, key, client_factory=make_client)

    prefix = "" if profile == "openrouter_deepseek_flash" else f"{profile}:"
    run = QualificationRun(build, ledger, worst, reruns=reruns or {}, prefix=prefix)
    results = await run.run()
    report = {
        "schema_version": "autobots.route-qualification/v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": "live" if make_client is None else "fake_transport",
        "profile": profile,
        "wire_id": route.wire_id,
        "canonical_id": route.canonical_id,
        "options": dict(route.options),
        # The rates each call was reserved at, in micro-USD per 1M tokens and per request.
        "catalog_price": asdict(entry.pricing) if entry.pricing else None,
        "worst_case_micro_usd_per_call": worst,
        "cap_micro_usd": ledger.cap,
        "committed_micro_usd": ledger.committed(),
        "reported_micro_usd": sum(held["reported"] or 0 for held in ledger.entries),
        "calls": len(ledger.entries),
        "calls_without_a_reported_charge": sum(
            1 for held in ledger.entries if held["reported"] is None
        ),
        "seconds": round(time.monotonic() - built_at, 1),
        "summary": summarize(results),
        "trials": [result.__dict__ for result in results],
        "not_established": ["H1", "product acceptance", "task quality"],
    }
    # A narrower rerun adds to the record. It never replaces the full corpus's report.
    stem = "report" if profile == "openrouter_deepseek_flash" else f"report-{profile}"
    name = f"{stem}-rerun.json" if reruns else f"{stem}.json"
    (out / name).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def gate(results: list[Trial]) -> tuple[bool, list[str]]:
    """Whether every gating fixture passed in each of the three trials, and each fixture that
    failed or wasn't supported in any trial, which stays disabled and listed in the limits."""
    verdicts: dict[str, list[str]] = {}
    for result in results:
        verdicts.setdefault(result.fixture, []).append(result.verdict)
    limits = sorted(
        name for name, seen in verdicts.items() if any(verdict != "passed" for verdict in seen)
    )
    offerable = all(
        len(verdicts.get(name, [])) == TRIALS and set(verdicts[name]) == {"passed"}
        for name in GATING
    )
    return offerable, limits


def limits_text(limits: list[str], summary: Mapping[str, Mapping[str, int]]) -> str:
    """The sentence a migration stores, from the report itself, so the two can't disagree."""
    if not limits:
        return "Every fixture passed in all three trials."
    parts = [
        f"{name} passed {summary[name].get('passed', 0)} of {sum(summary[name].values())}"
        for name in limits
    ]
    return "Not passed in every trial, so disabled: " + "; ".join(parts) + "."


async def measure_route(port: int, profile: ModelProfile) -> dict[str, Any]:
    """The live measurements, with the profile's thinking switch as the route sends it."""
    thinking = dict(profile.local.thinking) if profile.local is not None else {}
    extra = {"chat_template_kwargs": thinking} if thinking else {}
    return await local_route_measurements.measure(port, profile.wire_id, extra)


async def qualify_local(
    profile_id: str,
    out: Path,
    port: int,
    *,
    client: LocalClient | None = None,
    transport: Any = None,
    measure: Measure | None = None,
) -> dict[str, Any]:
    """US-3.4's suite on a local route at no spend. `client` and `transport` are for a fake
    server in tests. Nothing reads OpenRouter's catalog or a key."""
    profile = LOCAL_PROFILES.get(profile_id)
    if profile is None or profile.local is None:
        raise Refused(f"{profile_id} isn't a local profile")
    try:
        await check_served(profile, port, transport=transport)
    except LocalServerUnavailable:
        raise Refused("the local model server isn't running, so nothing was sent") from None
    except ModelUnavailable:
        raise Refused(
            "the local model server is serving another model, so nothing was sent"
        ) from None
    ledger = Ledger(out / f"ledger-{profile_id}.json", 0)
    built_at = time.monotonic()

    def build(max_tokens: int = OUTPUT_TOKENS) -> Any:
        attempt = PreparedAttempt(profile, ModelRole.EXECUTOR, "local", {"max_tokens": max_tokens})
        loopback = client(profile, port) if client is not None else None
        return local_chat_model(attempt, port, client=loopback)

    run = QualificationRun(
        build, ledger, 0, prefix=f"{profile_id}:", call_seconds=LOCAL_CALL_SECONDS
    )
    results = await run.run()
    summary = summarize(results)
    offerable, limits = gate(results)
    report: dict[str, Any] = {
        "schema_version": "autobots.route-qualification/v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": "live_local" if client is None else "fake_server",
        "profile": profile_id,
        "served_model_id": profile.wire_id,
        "canonical_id": profile.canonical_id,
        # Field by field, as the thinking switch is a read-only mapping that can't be copied.
        "pins": {
            "repository": profile.local.repository,
            "revision": profile.local.revision,
            "file": profile.local.file,
            "sha256": profile.local.sha256,
            "chat_template_sha256": profile.local.chat_template_sha256,
            "thinking": dict(profile.local.thinking),
        },
        "port": port,
        "call_seconds": LOCAL_CALL_SECONDS,
        "spent_usd": "0.00",
        "committed_micro_usd": ledger.committed(),
        "calls": len(ledger.entries),
        "seconds": round(time.monotonic() - built_at, 1),
        "summary": summary,
        # A whole reply arrives at once, so its first token comes with it. A stream says its own.
        "trials": [
            {
                **result.__dict__,
                "first_token_seconds": result.observed.get("first_chunk_seconds") or result.seconds,
            }
            for result in results
        ],
        "gating": list(GATING),
        "offerable": offerable,
        "recorded_status": "qualified_with_limits" if offerable else "not_qualified",
        "limits": limits,
        "limits_text": limits_text(limits, summary),
        "not_established": [
            "H1",
            "product acceptance",
            "task quality",
            "that a run on this route completes",
        ],
    }
    if measure is not None:
        report["measurements"] = await measure(port, profile)
    (out / f"report-{profile_id}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


async def _local_main(arguments: argparse.Namespace) -> int:
    out = Path(arguments.out)
    await asyncio.to_thread(out.mkdir, parents=True, exist_ok=True)
    port = arguments.port if arguments.port is not None else local_port(os.environ)
    try:
        report = await qualify_local(
            arguments.profile,
            out,
            port,
            measure=None if arguments.no_measure else measure_route,
        )
    except (ModelUnavailable, ValidationError) as refusal:
        raise Refused(f"nothing was sent: {refusal}") from None
    names = ("evidence_class", "calls", "spent_usd", "summary", "offerable", "limits_text")
    print(json.dumps({name: report[name] for name in names}, indent=1))
    return 0


async def _main(arguments: argparse.Namespace) -> int:
    forbid_remote_tracing(os.environ)
    configure_logging()
    # A local route needs no flag: it spends nothing (Decision 0041 A7).
    if getattr(arguments, "profile", None) in LOCAL_PROFILES:
        return await _local_main(arguments)
    out = Path(arguments.out)
    if not arguments.paid:
        print(
            json.dumps(
                {
                    "status": "not_sent",
                    "authorized_caps_micro_usd": AUTHORIZED_CAPS,
                    "planned_calls": planned_calls(),
                    "reason": "nothing is sent without --paid",
                }
            )
        )
        return 0
    try:
        key = read_key(Path(arguments.key_file))
        report = await qualify(
            arguments.profile, key, out, catalog_fetcher(), reruns=arguments.reruns
        )
    except (Refused, ModelUnavailable, ValidationError) as refusal:
        raise Refused(f"nothing was sent: {refusal}") from None
    print(
        json.dumps(
            {
                key_name: report[key_name]
                for key_name in (
                    "committed_micro_usd",
                    "reported_micro_usd",
                    "calls",
                    "calls_without_a_reported_charge",
                    "summary",
                )
            },
            indent=1,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="openrouter_deepseek_flash")
    parser.add_argument("--key-file", default=".env")
    parser.add_argument("--out", required=True)
    parser.add_argument("--paid", action="store_true", help="Actually send paid model calls.")
    parser.add_argument(
        "--port", type=int, default=None, help="A local route's server port (default 9931)."
    )
    parser.add_argument(
        "--no-measure", action="store_true", help="A local route: skip the speed and memory runs."
    )
    parser.add_argument(
        "--only",
        dest="reruns",
        type=counts_argument,
        default={},
        help="Rerun fixtures, as refusal=3,schema_nested=1.",
    )
    arguments = parser.parse_args()
    return command(lambda: asyncio.run(_main(arguments)))


if __name__ == "__main__":
    raise SystemExit(main())
