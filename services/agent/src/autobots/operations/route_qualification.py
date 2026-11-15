"""Paid qualification of one OpenRouter route, US-3.4.

Run with `python -m autobots.operations.route_qualification`.

Nothing is sent without `--paid`. Each call is written down at its worst-case price before it goes,
so a crash can't lose track of spend, and an unclear outcome stays charged at that price. Calls are
never retried and no other model is ever tried. Fixtures (`route_fixtures.py`) record what the route
did, and a capability that fails or isn't supported stays recorded as such. The ledger, key and
pricing are shared with the other paid entry points (`paid/`, POPS-05).

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
from autobots.adapters.models.factory import chat_model
from autobots.adapters.models.openrouter_metadata import catalog_fetcher
from autobots.logs import configure_logging, forbid_remote_tracing
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


async def _main(arguments: argparse.Namespace) -> int:
    forbid_remote_tracing(os.environ)
    configure_logging()
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
