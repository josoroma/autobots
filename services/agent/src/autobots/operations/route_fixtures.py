"""The route qualification's fixtures: what each one sends, and how its reply is judged (US-3.4).

`QualificationRun` sends each fixture through a fresh client, holds every call in the ledger at its
worst case first, and records what the route did. A capability that fails or isn't supported stays
recorded as such. `route_qualification.py` prepares the run and writes its report (POPS-05).
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, ConfigDict, Field

from autobots.application.run_projection import public_text
from autobots.logs import log_event
from autobots.operations.paid.attempts import CALL_SECONDS
from autobots.operations.paid.ledger import CapReached, Ledger
from autobots.operations.paid.pricing import reported_micro_usd

logger = logging.getLogger("autobots.qualification")
TRIALS = 3


class Streams(Protocol):
    """A chat model, or one with tools bound, as far as streaming uses it."""

    def astream(self, messages: Sequence[BaseMessage], /) -> AsyncIterator[AIMessageChunk]: ...


class StructuredModel(Protocol):
    """A chat model with a structured output, whose reply holds `raw`, `parsed` and any error."""

    def ainvoke(self, messages: Sequence[BaseMessage], /) -> Awaitable[dict[str, Any]]: ...


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

    tasks: list[ClosedTask]  # type: ignore[assignment]  # narrows the parent task type for this trial


class ConstrainedTask(Task):
    criteria: list[str] = Field(min_length=1)


class ConstrainedPlan(Plan):
    """The same shape with list-length keywords, which not every route's strict mode accepts."""

    tasks: list[ConstrainedTask] = Field(min_length=2)  # type: ignore[assignment]  # narrows the parent task type for this trial


@dataclass
class Trial:
    fixture: str
    trial: int
    verdict: str  # passed, failed or unsupported
    observed: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0


def _facts(message: object) -> dict[str, Any]:
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


def _short(text: object, limit: int = 200) -> str:
    return public_text(str(text), limit=limit)


@dataclass
class QualificationRun:
    """Each fixture gets a fresh client from `build`, under the shared output limit. `reruns`
    names fixtures to run again, each that many times, instead of the whole corpus."""

    build: Callable[..., Any]
    ledger: Ledger
    worst_case: int
    results: list[Trial] = field(default_factory=list)
    reruns: dict[str, int] = field(default_factory=dict)
    prefix: str = ""
    # How long one call may take. A local route's is its own (Decision 0041's measurements table).
    call_seconds: float = CALL_SECONDS
    first_chunk_seconds: float | None = None

    async def _call(self, label: str, send: Callable[[], Awaitable[AIMessage]]) -> AIMessage:
        async with self.ledger.charge(label, self.worst_case) as charge:
            message = await asyncio.wait_for(send(), self.call_seconds)
            charge.reported = reported_micro_usd(message)
        return message

    async def _stream(
        self, label: str, model: Streams, messages: Sequence[BaseMessage]
    ) -> tuple[AIMessageChunk, int, int]:
        """The assembled message, plus how many chunks carried content and tool arguments. The
        time its first chunk took is kept in `first_chunk_seconds`, for the fixture to record."""
        assembled: AIMessageChunk | None = None
        text_chunks = tool_chunks = 0
        started = time.monotonic()
        self.first_chunk_seconds = None

        async def run() -> None:
            nonlocal assembled, text_chunks, tool_chunks
            async for chunk in model.astream(messages):
                if self.first_chunk_seconds is None:
                    self.first_chunk_seconds = round(time.monotonic() - started, 2)
                assembled = chunk if assembled is None else assembled + chunk
                text_chunks += 1 if chunk.content else 0
                tool_chunks += 1 if chunk.tool_call_chunks else 0

        async with self.ledger.charge(label, self.worst_case) as charge:
            await asyncio.wait_for(run(), self.call_seconds)
            charge.reported = reported_micro_usd(assembled)
        if assembled is None:
            raise ValueError("the stream ended without a chunk")
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

    async def _call_structured(
        self, label: str, model: StructuredModel, prompt: str
    ) -> dict[str, Any]:
        async with self.ledger.charge(label, self.worst_case) as charge:
            reply: dict[str, Any] = await asyncio.wait_for(
                model.ainvoke([HumanMessage(prompt)]), self.call_seconds
            )
            charge.reported = reported_micro_usd(reply.get("raw"))
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
            "first_chunk_seconds": self.first_chunk_seconds,
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
            "first_chunk_seconds": self.first_chunk_seconds,
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
        chunks = 0
        started = time.monotonic()
        async with self.ledger.charge(label, self.worst_case) as charge:
            charge.known = False
            # An async generator, which the SDK types only as an iterator (POPS-16).
            stream: AsyncGenerator[AIMessageChunk] = model.astream(
                [HumanMessage("Write a 400 word description of volcanoes in Costa Rica.")]
            )
            async with asyncio.timeout(self.call_seconds):
                async for _ in stream:
                    chunks += 1
                    if chunks >= 3:
                        break
                await stream.aclose()
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
        if "schema_nested_closed" in self.reruns:
            fixtures.append(("schema_nested_closed", self.schema_nested_closed))
        if "schema_nested_constrained" in self.reruns:
            fixtures.append(("schema_nested_constrained", self.schema_nested_constrained))
        for trial in range(1, max((*self.reruns.values(), TRIALS)) + 1):
            for name, fixture in fixtures:
                if self.reruns and trial > self.reruns.get(name, 0):
                    continue
                label = f"{self.prefix}{name}/{'again-' if self.reruns else ''}{trial}"
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


def _names(calls: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(call["name"]) for call in calls]


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
