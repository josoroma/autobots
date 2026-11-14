"""US-15.24: a scripted model that streams, as every worker call now does. No provider is involved.

Each reply arrives in pieces: first a chunk carrying reasoning and a raw framework value that must
never be streamed on, then each tool call's arguments in fragments of `piece` characters, then the
finish reason with the cost. `delay` spaces the pieces, so a browser can watch text arrive.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from goal_loop_script import Script
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

REASONING_MARKER = 'PRIVATE-REASONING-MARKER'
FRAMEWORK_MARKER = 'RAW-FRAMEWORK-VALUE-MARKER'


def pieces(message: AIMessage, piece: int) -> list[AIMessageChunk]:
    out = [AIMessageChunk(content='', additional_kwargs={'reasoning_content': f'{REASONING_MARKER} thinking'},
                          response_metadata={'system_fingerprint': FRAMEWORK_MARKER})]
    text = str(message.content or '')
    out += [AIMessageChunk(content=text[start:start + piece]) for start in range(0, len(text), piece)]
    for index, call in enumerate(message.tool_calls):
        arguments = json.dumps(call['args'])
        out.append(AIMessageChunk(content='', tool_call_chunks=[{'name': call['name'], 'args': '', 'id': call['id'], 'index': index}]))
        out += [AIMessageChunk(content='', tool_call_chunks=[{'name': None, 'args': arguments[start:start + piece], 'id': None, 'index': index}])
                for start in range(0, len(arguments), piece)]
    out.append(AIMessageChunk(content='', response_metadata=dict(message.response_metadata)))
    return out


class StreamScript(Script):
    delay: float = 0.0
    piece: int = 9
    # Each reply's chunk count, so a check can show deltas were coalesced.
    chunked: list[int] = []  # noqa: RUF012 - a pydantic field, whose default pydantic copies for each instance

    async def _astream(self, messages: Any, stop: Any = None, run_manager: Any = None, **_: Any) -> Any:
        self.seen.append(list(messages))
        item = self.items.pop(0) if self.items else AIMessage(content='the script ran out', response_metadata={'finish_reason': 'stop', 'cost': 0.0001})
        if callable(item):
            item = item()
        chunks = pieces(item, self.piece)
        self.chunked.append(len(chunks))
        for chunk in chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield ChatGenerationChunk(message=chunk)
