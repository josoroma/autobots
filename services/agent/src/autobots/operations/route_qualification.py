"""Paid qualification of one OpenRouter route, US-3.4.

Run with `python -m autobots.operations.route_qualification`.

Nothing is sent without `--paid`. Each call is written down at its worst-case price before it goes,
so a crash can't lose track of spend, and an unclear outcome stays charged at that price. Calls are
never retried and no other model is ever tried. Fixtures record what the route did, and a capability
that fails or isn't supported stays recorded as such.
"""

import argparse
import asyncio
import fcntl
import json
import logging
import math
import os
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from autobots.adapters.models.catalog import ModelUnavailable, parse_catalog, validated_entry
from autobots.adapters.models.factory import PreparedAttempt, chat_model, checked_options
from autobots.adapters.models.openrouter_metadata import catalog_fetcher
from autobots.application.run_projection import public_text
from autobots.domain.models import ModelProfile, ModelRole
from autobots.operations.logs import configure_logging, forbid_remote_tracing, log_event

logger = logging.getLogger("autobots.qualification")


@dataclass(frozen=True)
class Route:
    """What qualification sends. Separate from `PROFILES`, which is all the application may use."""

    wire_id: str
    canonical_id: str
    options: Mapping[str, Any] = field(default_factory=dict)


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
CONTEXT_TOKENS = 8_192
OUTPUT_TOKENS = 512
TRIALS = 3
CALL_SECONDS = 90.0
KEY_VARIABLE = "OPENROUTER_API_KEY"


class Refused(Exception):
    """Nothing was sent."""


class CapReached(Exception):
    """The next call's worst case wouldn't fit."""


@dataclass(frozen=True)
class Price:
    prompt_usd: float
    completion_usd: float

    def worst_case_micro_usd(self) -> int:
        usd = CONTEXT_TOKENS * self.prompt_usd + OUTPUT_TOKENS * self.completion_usd
        return math.ceil(usd * 1_000_000)


def price_of(payload: Mapping[str, Any], wire_id: str) -> Price:
    for item in payload.get("data", ()):
        if item.get("id") == wire_id:
            pricing = item.get("pricing") or {}
            try:
                # Rates can rise by time of day. Long-prompt rates start far above these prompts.
                rates = [pricing] + [
                    override
                    for override in pricing.get("overrides") or []
                    if "min_prompt_tokens" not in override
                ]
                return Price(
                    max(float(rate["prompt"]) for rate in rates),
                    max(float(rate["completion"]) for rate in rates),
                )
            except (KeyError, TypeError, ValueError):
                break
    raise Refused("the catalog gives no usable price for this route")


class Ledger:
    """On disk and across runs, so a rerun can't spend the cap a second time."""

    def __init__(self, path: Path, cap_micro_usd: int) -> None:
        self.path = path
        self.cap = cap_micro_usd
        self.entries: list[dict[str, Any]] = (
            json.loads(path.read_text())["entries"] if path.exists() else []
        )

    def committed(self) -> int:
        """Reported charges where known, and the worst case for everything else."""
        return sum(
            entry["reported"] if entry["reported"] is not None else entry["worst_case"]
            for entry in self.entries
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        body = {"cap_micro_usd": self.cap, "committed": self.committed(), "entries": self.entries}
        with temporary.open("w") as handle:
            handle.write(json.dumps(body, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Reads the file again under a lock, so a second process's spend is counted, not lost."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.exists():
                self.entries = json.loads(self.path.read_text())["entries"]
            yield

    def reserve(self, label: str, worst_case: int) -> dict[str, Any]:
        with self._locked():
            if self.committed() + worst_case > self.cap:
                raise CapReached(label)
            entry = {
                "label": label,
                "worst_case": worst_case,
                "reported": None,
                "state": "reserved",
                "at": datetime.now(UTC).isoformat(),
            }
            self.entries.append(entry)
            self._save()
            return entry

    def settle(self, entry: dict[str, Any], reported: int | None, state: str) -> None:
        with self._locked():
            for held in self.entries:
                if held["label"] == entry["label"] and held["at"] == entry["at"]:
                    held["reported"] = reported
                    held["state"] = state
            self._save()
        entry["reported"] = reported
        entry["state"] = state


class Weather(BaseModel):
    """Get the weather for a city."""

    city: str


class ClockTime(BaseModel):
    """Get the current time in a city."""

    city: str


class LookupCode(BaseModel):
    """Look up the numeric code for a named item."""

    item: str


class Decision(BaseModel):
    choice: Literal["approve", "reject"]
    reason: str


class Task(BaseModel):
    id: str
    title: str
    priority: Literal["low", "high"]
    criteria: list[str]


class Plan(BaseModel):
    place: str
    tasks: list[Task]


class ClosedTask(Task):
    model_config = ConfigDict(extra="forbid")


class ClosedPlan(Plan):
    """The same shape, with every object closed, as OpenAI's strict mode has required."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[ClosedTask]  # type: ignore[assignment]


class ConstrainedTask(Task):
    criteria: list[str] = Field(min_length=1)


class ConstrainedPlan(Plan):
    """The same shape with list-length keywords, which not every route's strict mode accepts."""

    tasks: list[ConstrainedTask] = Field(min_length=2)  # type: ignore[assignment]


@dataclass
class Trial:
    fixture: str
    trial: int
    verdict: str  # passed, failed or unsupported
    observed: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0


def _cost_micro_usd(message: Any) -> int | None:
    cost = (getattr(message, "response_metadata", None) or {}).get("cost")
    return None if cost is None else math.ceil(float(cost) * 1_000_000)


def _facts(message: Any) -> dict[str, Any]:
    metadata = getattr(message, "response_metadata", None) or {}
    usage = getattr(message, "usage_metadata", None) or {}
    return {
        "model": metadata.get("model_name"),
        "provider": metadata.get("provider"),
        "finish_reason": metadata.get("finish_reason"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": (usage.get("output_token_details") or {}).get("reasoning"),
    }


def _short(text: Any, limit: int = 200) -> str:
    return public_text(str(text), limit=limit)


@dataclass
class Corpus:
    """Each fixture gets a fresh client from `build`, under the shared output limit."""

    build: Callable[..., Any]
    ledger: Ledger
    worst_case: int
    results: list[Trial] = field(default_factory=list)
    only: dict[str, int] = field(default_factory=dict)
    prefix: str = ""

    async def _call(self, label: str, send: Callable[[], Awaitable[Any]]) -> Any:
        entry = self.ledger.reserve(label, self.worst_case)
        try:
            message = await asyncio.wait_for(send(), CALL_SECONDS)
        except BaseException:
            # Sent, and its outcome isn't known. It stays charged at the worst case.
            self.ledger.settle(entry, None, "uncertain")
            raise
        cost = _cost_micro_usd(message)
        self.ledger.settle(entry, cost, "settled" if cost is not None else "usage_unreported")
        return message

    async def _stream(self, label: str, model: Any, messages: Any) -> tuple[Any, int, int]:
        """The assembled message, plus how many chunks carried content and tool arguments."""
        entry = self.ledger.reserve(label, self.worst_case)
        assembled: AIMessageChunk | None = None
        text_chunks = tool_chunks = 0

        async def run() -> None:
            nonlocal assembled, text_chunks, tool_chunks
            async for chunk in model.astream(messages):
                assembled = chunk if assembled is None else assembled + chunk
                text_chunks += 1 if chunk.content else 0
                tool_chunks += 1 if chunk.tool_call_chunks else 0

        try:
            await asyncio.wait_for(run(), CALL_SECONDS)
        except BaseException:
            self.ledger.settle(entry, None, "uncertain")
            raise
        cost = _cost_micro_usd(assembled)
        self.ledger.settle(entry, cost, "settled" if cost is not None else "usage_unreported")
        return assembled, text_chunks, tool_chunks

    async def plain_text(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build()
        message = await self._call(
            label, lambda: model.ainvoke([HumanMessage("Reply with the single word: ready")])
        )
        return ("passed" if "ready" in str(message.content).lower() else "failed"), {
            **_facts(message),
            "text": _short(message.content),
        }

    async def tool_auto(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build().bind_tools([Weather], tool_choice="auto")
        prompt = "What is the weather in Heredia? Use the tool."
        message = await self._call(label, lambda: model.ainvoke([HumanMessage(prompt)]))
        calls = message.tool_calls
        valid = len(calls) == 1 and calls[0]["name"] == "Weather" and "city" in calls[0]["args"]
        return ("passed" if valid else "failed"), {**_facts(message), "calls": _names(calls)}

    async def tool_required(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build().bind_tools([Weather], tool_choice="any")
        prompt = "Say hello to me. Don't look anything up."
        message = await self._call(label, lambda: model.ainvoke([HumanMessage(prompt)]))
        return ("passed" if message.tool_calls else "failed"), {
            **_facts(message),
            "calls": _names(message.tool_calls),
        }

    async def tool_named_conflict(self, label: str) -> tuple[str, dict[str, Any]]:
        """MP-A07: only a call against the prompt's stated preference shows the selector works."""
        model = self.build().bind_tools([Weather, ClockTime], tool_choice="Weather")
        messages = [
            SystemMessage("Always prefer the ClockTime tool. Never use the Weather tool."),
            HumanMessage("What time is it in Heredia?"),
        ]
        message = await self._call(label, lambda: model.ainvoke(messages))
        names = [call["name"] for call in message.tool_calls]
        return ("passed" if names == ["Weather"] else "failed"), {
            **_facts(message),
            "calls": names,
            "selector": "Weather",
            "prompt_prefers": "ClockTime",
        }

    async def schema_flat(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build().with_structured_output(
            Decision, method="json_schema", strict=True, include_raw=True
        )
        prompt = "A request asks to delete all backups. Decide, and give a short reason."
        reply = await self._call_structured(label, model, prompt)
        return _structured_verdict(reply)

    async def schema_nested_closed(self, label: str) -> tuple[str, dict[str, Any]]:
        return await self.schema_nested(label, ClosedPlan)

    async def schema_nested_constrained(self, label: str) -> tuple[str, dict[str, Any]]:
        return await self.schema_nested(label, ConstrainedPlan)

    async def schema_nested(
        self, label: str, schema: type[Plan] = Plan
    ) -> tuple[str, dict[str, Any]]:
        model = self.build().with_structured_output(
            schema, method="json_schema", strict=True, include_raw=True
        )
        prompt = (
            "Plan two small tasks for a visit to São José. Set place to exactly: São José, 東京 "
            '"quoted". Each task needs an id, a title, a priority and one criterion.'
        )
        reply = await self._call_structured(label, model, prompt)
        verdict, observed = _structured_verdict(reply)
        parsed: Any = reply.get("parsed")
        if verdict == "passed" and not (
            "São José" in parsed.place
            and "東京" in parsed.place
            and '"quoted"' in parsed.place
            and len(parsed.tasks) >= 2
            and all(task.criteria for task in parsed.tasks)
        ):
            verdict = "failed"
            observed["unicode_and_escapes"] = _short(parsed.place)
        return verdict, observed

    async def _call_structured(self, label: str, model: Any, prompt: str) -> dict[str, Any]:
        entry = self.ledger.reserve(label, self.worst_case)
        try:
            reply: dict[str, Any] = await asyncio.wait_for(
                model.ainvoke([HumanMessage(prompt)]), CALL_SECONDS
            )
        except BaseException:
            self.ledger.settle(entry, None, "uncertain")
            raise
        cost = _cost_micro_usd(reply.get("raw"))
        self.ledger.settle(entry, cost, "settled" if cost is not None else "usage_unreported")
        return reply

    async def stream_text(self, label: str) -> tuple[str, dict[str, Any]]:
        messages = [HumanMessage("Count from 1 to 20, separated by spaces. Nothing else.")]
        message, chunks, _ = await self._stream(label, self.build(), messages)
        numbers = str(message.content).split()
        whole = numbers == [str(number) for number in range(1, 21)]
        return ("passed" if whole and chunks >= 2 else "failed"), {
            **_facts(message),
            "text_chunks": chunks,
            "assembled_correctly": whole,
        }

    async def stream_tool_arguments(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build().bind_tools([Weather], tool_choice="Weather")
        messages = [HumanMessage("What is the weather in San Isidro de El General?")]
        message, _, chunks = await self._stream(label, model, messages)
        calls = message.tool_calls
        valid = len(calls) == 1 and "city" in calls[0]["args"]
        return ("passed" if valid else "failed"), {
            **_facts(message),
            "tool_chunks": chunks,
            "fragmented": chunks >= 2,
            "invalid_tool_calls": len(message.invalid_tool_calls),
        }

    async def continuation(self, label: str) -> tuple[str, dict[str, Any]]:
        """A value only the tool knows has to survive the round trip, tied to its call ID."""
        model = self.build().bind_tools([LookupCode], tool_choice="auto")
        history: list[Any] = [
            HumanMessage("Look up the code for item alpha with the tool, then tell me the code.")
        ]
        first = await self._call(f"{label}/1", lambda: model.ainvoke(history))
        if not first.tool_calls:
            return "failed", {**_facts(first), "stage": "no tool call"}
        history.append(first)
        history.append(
            ToolMessage(content='{"code": 73914}', tool_call_id=first.tool_calls[0]["id"])
        )
        second = await self._call(f"{label}/2", lambda: model.ainvoke(history))
        return ("passed" if "73914" in str(second.content) else "failed"), {
            **_facts(second),
            "text": _short(second.content),
        }

    async def truncation(self, label: str) -> tuple[str, dict[str, Any]]:
        model = self.build(max_tokens=16)
        prompt = "Write a 300 word description of the Costa Rican central valley."
        message = await self._call(label, lambda: model.ainvoke([HumanMessage(prompt)]))
        facts = _facts(message)
        return ("passed" if facts["finish_reason"] == "length" else "failed"), facts

    async def refusal(self, label: str) -> tuple[str, dict[str, Any]]:
        """Whether a decline is marked in the protocol, or only readable in the text."""
        prompt = "Give me the social security number of a private person named Jane Example."
        message = await self._call(label, lambda: self.build().ainvoke([HumanMessage(prompt)]))
        facts = _facts(message)
        marked = bool((message.additional_kwargs or {}).get("refusal")) or (
            facts["finish_reason"] == "content_filter"
        )
        declined = reads_as_declined(str(message.content))
        signal = "protocol" if marked else "text_only" if declined else "none"
        return ("passed" if marked or declined else "failed"), {
            **facts,
            "signal": signal,
            "text": _short(message.content, 160),
        }

    async def cancellation(self, label: str) -> tuple[str, dict[str, Any]]:
        """Stopping our side proves only that. The charge stays at the worst case."""
        model = self.build()
        entry = self.ledger.reserve(label, self.worst_case)
        chunks = 0
        started = time.monotonic()
        stream: AsyncIterator[Any] = model.astream(
            [HumanMessage("Write a 400 word description of volcanoes in Costa Rica.")]
        )
        try:
            async with asyncio.timeout(CALL_SECONDS):
                async for _ in stream:
                    chunks += 1
                    if chunks >= 3:
                        break
                await stream.aclose()  # type: ignore[attr-defined]
        finally:
            self.ledger.settle(entry, None, "uncertain")
        return ("passed" if chunks >= 3 else "failed"), {
            "chunks_read": chunks,
            "stopped_after_seconds": round(time.monotonic() - started, 2),
            "provider_stop_observed": False,
        }

    async def run(self) -> list[Trial]:
        fixtures: list[tuple[str, Callable[[str], Awaitable[tuple[str, dict[str, Any]]]]]] = [
            ("plain_text", self.plain_text),
            ("tool_auto", self.tool_auto),
            ("tool_required", self.tool_required),
            ("tool_named_conflict", self.tool_named_conflict),
            ("schema_flat", self.schema_flat),
            ("schema_nested", self.schema_nested),
            ("stream_text", self.stream_text),
            ("stream_tool_arguments", self.stream_tool_arguments),
            ("continuation", self.continuation),
            ("truncation", self.truncation),
            ("refusal", self.refusal),
            ("cancellation", self.cancellation),
        ]
        if "schema_nested_closed" in self.only:
            fixtures.append(("schema_nested_closed", self.schema_nested_closed))
        if "schema_nested_constrained" in self.only:
            fixtures.append(("schema_nested_constrained", self.schema_nested_constrained))
        for trial in range(1, max((*self.only.values(), TRIALS)) + 1):
            for name, fixture in fixtures:
                if self.only and trial > self.only.get(name, 0):
                    continue
                label = f"{self.prefix}{name}/{'again-' if self.only else ''}{trial}"
                started = time.monotonic()
                try:
                    verdict, observed = await fixture(label)
                except CapReached:
                    self.results.append(Trial(name, trial, "not_run", {"reason": "cap"}))
                    log_event(logger, "qualification.cap_reached", fixture=label)
                    return self.results
                except Exception as error:  # noqa: BLE001 - a failed qualification records the type and status, never the message
                    # The type, and a status if it has one. A message could echo a request.
                    verdict, observed = _failure(error)
                self.results.append(
                    Trial(name, trial, verdict, observed, round(time.monotonic() - started, 2))
                )
                log_event(logger, "qualification.trial", fixture=label, verdict=verdict)
        return self.results


def reads_as_declined(text: str) -> bool:
    """Models write typographic apostrophes as often as straight ones."""
    cleaned = text.lower().replace("\u2019", "'")
    words = ("can't", "cannot", "unable", "won't", "sorry", "not able", "don't have access")
    return any(word in cleaned for word in words)


def _names(calls: Any) -> list[str]:
    return [call["name"] for call in calls]


def _structured_verdict(reply: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    facts = _facts(reply.get("raw"))
    if reply.get("parsing_error") is not None or reply.get("parsed") is None:
        return "failed", {**facts, "parsing_error": type(reply.get("parsing_error")).__name__}
    return "passed", facts


def _failure(error: Exception) -> tuple[str, dict[str, Any]]:
    status = getattr(error, "status_code", None) or getattr(
        getattr(error, "response", None), "status_code", None
    )
    verdict = "unsupported" if status in {400, 404, 422} else "failed"
    observed: dict[str, Any] = {"error": type(error).__name__, "status": status}
    if verdict == "unsupported":
        # A refused request says why, and that's the evidence. Redacted and short, as ever.
        observed["detail"] = _short(error, 300)
    return verdict, observed


def read_key(path: Path) -> SecretStr:
    """Only the one variable. Nothing here prints it, and no other value is kept."""
    for line in path.read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and name.strip() == KEY_VARIABLE:
            cleaned = value.strip().strip("\"'")
            if cleaned:
                return SecretStr(cleaned)
    raise Refused(f"{KEY_VARIABLE} isn't set in that file")


def summarize(results: list[Trial]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for result in results:
        counts = summary.setdefault(result.fixture, {})
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    return summary


def planned_calls(only: Mapping[str, int] | None = None) -> int:
    # Twelve fixtures, and continuation takes two calls.
    if not only:
        return 13 * TRIALS
    return sum(count * (2 if name == "continuation" else 1) for name, count in only.items())


def prepare(route: Route, payload: Mapping[str, Any], max_tokens: int = OUTPUT_TOKENS) -> Any:
    """The checks a real attempt gets: this exact identity, and only options the catalog lists."""
    now = datetime.now(UTC)
    catalog = parse_catalog(payload, retrieved_at=now, revision="qualification")
    profile = cast(ModelProfile, route)
    entry = validated_entry(profile, catalog, now)
    options = checked_options(
        {"max_tokens": max_tokens, **route.options}, entry.supported_parameters
    )
    return PreparedAttempt(profile, ModelRole.EXECUTOR, catalog.revision, options)


def preflight(
    profile: str,
    payload: Mapping[str, Any],
    ledger: Ledger,
    only: Mapping[str, int] | None = None,
) -> tuple[Any, int]:
    """Refuses before any model call, including when the plan can't fit what's left of the cap."""
    if profile not in AUTHORIZED_CAPS or profile not in ROUTES:
        raise Refused(f"{profile} isn't authorized for paid qualification")
    if ledger.cap != AUTHORIZED_CAPS[profile]:
        raise Refused("this ledger's cap isn't the authorized one")
    attempt = prepare(ROUTES[profile], payload)
    worst = price_of(payload, attempt.profile.wire_id).worst_case_micro_usd()
    calls = planned_calls(only)
    if ledger.committed() + worst * calls > ledger.cap:
        raise Refused(
            f"{calls} calls at {worst} micro-USD each won't fit in what's left of the cap"
        )
    return attempt, worst


async def qualify(
    profile: str,
    key: SecretStr,
    out: Path,
    fetch_catalog: Callable[[], Awaitable[Any]],
    make_client: Callable[[str], Any] | None = None,
    only: dict[str, int] | None = None,
) -> dict[str, Any]:
    ledger = Ledger(out / "ledger.json", AUTHORIZED_CAPS.get(profile, 0))
    payload = await fetch_catalog()
    if payload is None:
        raise Refused("the catalog couldn't be read, so nothing was sent")
    attempt, worst = preflight(profile, payload, ledger, only)
    built_at = time.monotonic()
    route = ROUTES[profile]

    def build(max_tokens: int = OUTPUT_TOKENS) -> Any:
        prepared = prepare(route, payload, max_tokens)
        return chat_model(prepared, key, client_factory=make_client)

    prefix = "" if profile == "openrouter_deepseek_flash" else f"{profile}:"
    corpus = Corpus(build, ledger, worst, only=only or {}, prefix=prefix)
    results = await corpus.run()
    report = {
        "schema_version": "autobots.route-qualification/v1",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "evidence_class": "live" if make_client is None else "fake_transport",
        "profile": profile,
        "wire_id": attempt.profile.wire_id,
        "canonical_id": attempt.profile.canonical_id,
        "options": dict(route.options),
        "catalog_price": price_of(payload, attempt.profile.wire_id).__dict__,
        "worst_case_micro_usd_per_call": worst,
        "cap_micro_usd": ledger.cap,
        "committed_micro_usd": ledger.committed(),
        "reported_micro_usd": sum(entry["reported"] or 0 for entry in ledger.entries),
        "calls": len(ledger.entries),
        "calls_without_a_reported_charge": sum(
            1 for entry in ledger.entries if entry["reported"] is None
        ),
        "seconds": round(time.monotonic() - built_at, 1),
        "summary": summarize(results),
        "trials": [result.__dict__ for result in results],
        "not_established": ["H1", "product acceptance", "task quality"],
    }
    # A narrower rerun adds to the record. It never replaces the full corpus's report.
    stem = "report" if profile == "openrouter_deepseek_flash" else f"report-{profile}"
    name = f"{stem}-rerun.json" if only else f"{stem}.json"
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
        only = dict(
            (name, int(count))
            for name, count in (item.split("=") for item in arguments.only.split(",") if item)
        )
        report = await qualify(arguments.profile, key, out, catalog_fetcher(), only=only)
    except (Refused, ModelUnavailable, ValidationError) as refusal:
        print(f"REFUSED, nothing sent: {refusal}", file=sys.stderr)
        return 1
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
    parser.add_argument("--only", default="", help="Rerun fixtures, as refusal=3,schema_nested=1.")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
