"""US-16.8, Decision 0034 L6 to L8: every run works in a 64K-token context, so a deep research run
keeps its search results and the pages it reads in view. The first live run re-read three pages of
offloaded search results until it ran out of model calls, with two read-back pages in view."""

import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from autobots.application.compaction import (
    LARGE_TOOL_CHARS,
    READ_BACK_TOOL,
    READ_PAGES_IN_VIEW,
    CompactionPolicy,
    offload_large,
)
from autobots.application.worker_inference import OPTIONS
from autobots.domain.models import CONTEXT_TOKENS, MAX_OUTPUT_TOKENS, RESERVED_PROMPT_TOKENS
from sql_fakes import ScriptedConnection

RUN = uuid4()


def call(name: str, call_id: str, **arguments: object) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": arguments, "id": call_id}])


def result(name: str, call_id: str, content: str) -> ToolMessage:
    return ToolMessage(content=content, name=name, tool_call_id=call_id)


def test_every_run_works_in_a_64k_token_context() -> None:
    policy = CompactionPolicy()
    assert CONTEXT_TOKENS == 64_000
    assert policy.context_chars == 192_000
    assert (LARGE_TOOL_CHARS, policy.large_tool_chars, READ_PAGES_IN_VIEW) == (48_000, 48_000, 16)
    assert (RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS, OPTIONS["max_tokens"]) == (
        64_000,
        4_096,
        4_096,
    )
    # A full view, counted a token a byte as a larger request is, stays below Terra's 272,000-token
    # long-prompt rate.
    assert policy.context_chars + LARGE_TOOL_CHARS < 272_000


@pytest.mark.asyncio
async def test_search_results_stay_in_view() -> None:
    """28 results of about 14,000 characters, as the first live run's google_search returned."""
    rows = [
        {"rank": rank, "title": f"Deep agents result {rank}", "url": f"https://example.com/{rank}"}
        for rank in range(1, 29)
    ]
    found = json.dumps({"results": rows, "result_count": 28, "pages": 3}).ljust(14_000)
    messages: list[BaseMessage] = [
        call("google_search", "s1", query="langchain for deep agents", max_results=30)
    ]
    messages.append(result("google_search", "s1", found))
    connection = ScriptedConnection()
    view = await offload_large(connection, RUN, messages, CompactionPolicy())
    assert view[-1].content == found
    assert connection.statements == []


@pytest.mark.asyncio
async def test_an_offloaded_output_can_be_read_back_whole() -> None:
    """A 60,000-character output is offloaded and read back in 15 pages, all of them in view."""
    offload_id = uuid4()
    messages: list[BaseMessage] = [call("google_extract", "e1", urls=["https://example.com/a"])]
    messages.append(result("google_extract", "e1", "x" * 60_000))
    for page in range(15):
        read = f"r{page}"
        messages.append(call(READ_BACK_TOOL, read, offload_id=str(offload_id), offset=page * 4_000))
        messages.append(result(READ_BACK_TOOL, read, f"page {page}: " + "y" * 3_990))
    connection = ScriptedConnection([(offload_id,)])
    view = await offload_large(connection, RUN, messages, CompactionPolicy())
    pointer = json.loads(str(view[1].content))
    assert (pointer["offloaded"], pointer["characters"]) == (str(offload_id), 60_000)
    pages = [message for message in view if getattr(message, "name", None) == READ_BACK_TOOL]
    assert len(pages) == 15
    assert all(str(page.content).startswith(f"page {index}:") for index, page in enumerate(pages))
