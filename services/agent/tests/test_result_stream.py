"""US-15.24: live result text from streamed calls. Offline: notifications are captured, not sent."""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from autobots.adapters import result_stream
from autobots.adapters.loop_middleware import _streamed
from autobots.adapters.result_stream import ResultTap, partial_object, reset_tap, use_tap
from autobots.application.model_attempts import FailureClass, ProviderFailure

CONTENT = 'Line one\nSaid "quoted" \\ and café 😀 — done.\n' * 20
REASONING = "PRIVATE-REASONING-MARKER"


def test_a_growing_object_gives_its_finished_fields_and_the_string_still_arriving() -> None:
    whole = json.dumps({"path": "outputs/r.md", "content": CONTENT, "media_type": "text/markdown"})
    seen: list[str] = []
    for end in range(1, len(whole) + 1):
        fields, growing = partial_object(whole[:end])
        text = fields.get("content") or (growing[1] if growing and growing[0] == "content" else "")
        # The text so far only ever grows, and is always a prefix of the real content.
        assert CONTENT.startswith(text)
        assert not seen or text.startswith(seen[-1])
        seen.append(text)
    fields, growing = partial_object(whole)
    assert fields == {"path": "outputs/r.md", "content": CONTENT, "media_type": "text/markdown"}
    assert growing is None
    assert partial_object('{"path": "outp') == ({}, ("path", "outp"))
    assert partial_object('{"n": [1, {"a": "x"}], "path": "y"}')[0] == {"path": "y"}
    assert partial_object("not json") == ({}, None)


def _fragments(arguments: str, name: str, index: int, size: int = 7) -> list[AIMessageChunk]:
    pieces = [
        AIMessageChunk(
            content="",
            tool_call_chunks=[{"name": name, "args": "", "id": f"call-{index}", "index": index}],
        )
    ]
    for start in range(0, len(arguments), size):
        pieces.append(
            AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "name": None,
                        "args": arguments[start : start + size],
                        "id": None,
                        "index": index,
                    }
                ],
            )
        )
    return pieces


def _chunks() -> list[AIMessageChunk]:
    plan = json.dumps({"tasks": [{"id": "secret-plan-argument"}]})
    note = json.dumps({"path": "notes/private.md", "content": "WORKING-NOTE-NOT-A-RESULT"})
    result = json.dumps({"path": "outputs/report.md", "content": CONTENT})
    chunks = [AIMessageChunk(content="", additional_kwargs={"reasoning_content": REASONING})]
    chunks += _fragments(plan, "propose_plan", 0)
    chunks += _fragments(note, "save_artifact", 1)
    chunks += _fragments(result, "save_artifact", 2)
    chunks.append(AIMessageChunk(content="", response_metadata={"finish_reason": "tool_calls"}))
    chunks.append(AIMessageChunk(content="", response_metadata={"cost": 0.0001}))
    return chunks


class Streams:
    def __init__(self, chunks: list[Any], fail_after: int | None = None, delay: float = 0.0):
        self.chunks = chunks
        self.fail_after = fail_after
        self.delay = delay

    async def astream(self, _messages: Any, **_: Any) -> Any:
        for number, chunk in enumerate(self.chunks):
            if self.fail_after is not None and number == self.fail_after:
                raise ConnectionError("the stream dropped")
            await asyncio.sleep(self.delay)
            yield chunk


def test_only_an_outputs_files_content_is_sent_coalesced_and_nothing_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(result_stream, "FLUSH_SECONDS", 0.05)
    sent: list[dict[str, Any]] = []

    async def notify(payload: dict[str, Any]) -> None:
        sent.append(payload)

    async def run() -> Any:
        tap = ResultTap(uuid4(), notify=notify)
        token = use_tap(tap)
        try:
            return await _streamed(Streams(_chunks(), delay=0.001), [])
        finally:
            reset_tap(token)

    message = asyncio.run(run())
    chunks = _chunks()
    assert sent, "some text was sent"
    assert {tuple(sorted(item)) for item in sent} == {("offset", "run_id", "segment", "text")}
    assert {item["segment"] for item in sent} == {1}
    joined = "".join(item["text"] for item in sorted(sent, key=lambda item: item["offset"]))
    assert joined == CONTENT
    offsets = [item["offset"] for item in sent]
    assert offsets == sorted(offsets) and offsets[0] == 0
    # Coalesced: far fewer notifications than argument fragments.
    assert len(sent) < len([chunk for chunk in chunks if chunk.tool_call_chunks]) / 4
    everything = json.dumps(sent)
    for private in (
        REASONING,
        "secret-plan-argument",
        "WORKING-NOTE-NOT-A-RESULT",
        "outputs/report.md",
        "notes/private.md",
        "tool_call",
    ):
        assert private not in everything
    # The assembled reply is what settles: its tool calls and cost, as a whole call reports them.
    assert [call["name"] for call in message.tool_calls] == [
        "propose_plan",
        "save_artifact",
        "save_artifact",
    ]
    assert message.tool_calls[2]["args"]["content"] == CONTENT
    assert message.response_metadata["cost"] == 0.0001


def test_a_stream_that_fails_after_its_first_chunk_is_a_partial_stream() -> None:
    with pytest.raises(ProviderFailure) as failure:
        asyncio.run(_streamed(Streams(_chunks(), fail_after=3), []))
    assert failure.value.failure is FailureClass.PARTIAL_STREAM
    with pytest.raises(ConnectionError):
        asyncio.run(_streamed(Streams(_chunks(), fail_after=0), []))


def test_a_tap_that_cant_send_never_stops_the_call() -> None:
    async def broken(_: dict[str, Any]) -> None:
        raise OSError("no database")

    async def run() -> Any:
        token = use_tap(ResultTap(uuid4(), notify=broken))
        try:
            return await _streamed(Streams(_chunks()), [])
        finally:
            reset_tap(token)

    assert asyncio.run(run()).tool_calls[2]["args"]["content"] == CONTENT


def test_a_call_cut_off_mid_argument_stays_invalid_as_without_streaming() -> None:
    cut = _fragments('{"path": "outputs/rep', "save_artifact", 0)
    cut.append(AIMessageChunk(content="", response_metadata={"finish_reason": "length"}))
    message = asyncio.run(_streamed(Streams(cut), []))
    assert isinstance(message, AIMessage)
    assert message.tool_calls == []
    assert [call["name"] for call in message.invalid_tool_calls] == ["save_artifact"]
    assert message.invalid_tool_calls[0]["args"] == '{"path": "outputs/rep'
