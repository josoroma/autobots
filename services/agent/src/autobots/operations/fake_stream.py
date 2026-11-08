"""Streamed replies for fake transports: one whole chat completion turned into the server-sent
chunks OpenRouter streams for it (Decision 0022's streaming decision). The fake transports in
tests and qualifiers use it, so a fake can answer a streamed request without a provider.

Text and each tool call's arguments arrive in fragments of `piece` characters, reasoning and its
details in a chunk of their own before them, the finish reason in its own chunk, and usage, with its
cost, last in a chunk with no choices, as OpenRouter sends it with `include_usage`.
"""

import json
from collections.abc import Iterator
from typing import Any


def _chunk(completion: dict[str, Any], delta: dict[str, Any], finish: str | None) -> dict[str, Any]:
    return {
        "id": completion.get("id", "fake"),
        "object": "chat.completion.chunk",
        "created": completion.get("created", 1),
        "model": completion.get("model", "fake"),
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


def stream_chunks(completion: dict[str, Any], piece: int = 16) -> Iterator[dict[str, Any]]:
    choice = completion["choices"][0]
    message = choice.get("message") or {}
    yield _chunk(completion, {"role": "assistant", "content": ""}, None)
    thinking = {key: message[key] for key in ("reasoning", "reasoning_details") if key in message}
    if thinking:
        yield _chunk(completion, thinking, None)
    content = message.get("content") or ""
    for start in range(0, len(content), piece):
        yield _chunk(completion, {"content": content[start : start + piece]}, None)
    for index, call in enumerate(message.get("tool_calls") or []):
        arguments = call["function"].get("arguments") or ""
        yield _chunk(
            completion,
            {
                "tool_calls": [
                    {
                        "index": index,
                        "id": call["id"],
                        "type": "function",
                        "function": {"name": call["function"]["name"], "arguments": ""},
                    }
                ]
            },
            None,
        )
        for start in range(0, len(arguments), piece):
            yield _chunk(
                completion,
                {
                    "tool_calls": [
                        {
                            "index": index,
                            "function": {"arguments": arguments[start : start + piece]},
                        }
                    ]
                },
                None,
            )
    yield _chunk(completion, {}, choice.get("finish_reason") or "stop")
    if completion.get("usage") is not None:
        yield {
            "id": completion.get("id", "fake"),
            "object": "chat.completion.chunk",
            "created": completion.get("created", 1),
            "model": completion.get("model", "fake"),
            "choices": [],
            "usage": completion["usage"],
        }


def completion_to_sse(completion: dict[str, Any], piece: int = 16) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in stream_chunks(completion, piece)]
    return ("".join(lines) + "data: [DONE]\n\n").encode()
