"""US-14.22: google_search through SerpApi against a fake transport, Decision 0032 G1 to G7.
Sockets are blocked (conftest), and no SerpApi search is made."""

from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.search_paging import MAX_PAGES
from autobots.adapters.serpapi import REQUEST_SECONDS, google_search_tool
from autobots.adapters.tool_registry import catalog
from autobots.application.tool_definitions import (
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import Refused
from autobots.application.tool_gateway import resolve as resolve_call
from autobots.contracts.web_tools import GoogleSearchOutput
from autobots.domain.execution import TOOL_VERSIONS
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import EXPERT_TOOLS
from sql_fakes import ScriptedConnection

KEY = "serpapi_fixtureKEY0123456789"
ENVIRON = {"SERPAPI_API_KEY": KEY}
CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
NEXT = {"next": "https://serpapi.com/search.json?start=10"}


def organic(start: int, count: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "position": n - start + 1,
            "title": f"T{n}",
            "link": f"https://example.com/{n}",
            "snippet": f"about {n}",
        }
        for n in range(start, start + count)
    ]


def reply(results: list[dict[str, Any]], more: bool = True) -> dict[str, Any]:
    body: dict[str, Any] = {"organic_results": results, "search_metadata": {"status": "Success"}}
    if more:
        body["serpapi_pagination"] = NEXT
    return body


FULLY_EMPTY = {
    "error": "Google hasn't returned any results for this query.",
    "search_information": {"organic_results_state": "Fully empty"},
}


class SerpApi:
    """serpapi.com answering page n (by `start`) with the n-th of `pages`: a JSON body, or a status
    and a body. A page past the list is Fully empty."""

    def __init__(self, *pages: dict[str, Any] | tuple[int, dict[str, Any]]) -> None:
        self.pages = pages
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            number = int(request.url.params.get("start", "0")) // 10 + 1
            served = self.pages[number - 1] if number <= len(self.pages) else FULLY_EMPTY
            if isinstance(served, tuple):
                return httpx.Response(served[0], json=served[1])
            return httpx.Response(200, json=served)

        return httpx.MockTransport(answer)

    def tool(self, environ: dict[str, str] = ENVIRON) -> ToolDefinition:
        return google_search_tool(self.transport(), environ)


async def search(
    fake: SerpApi, max_results: int = 30, environ: dict[str, str] = ENVIRON
) -> GoogleSearchOutput:
    tool = fake.tool(environ)
    arguments = tool.input_model.model_validate({"query": "colones", "max_results": max_results})
    output = await tool.handler(arguments, CONTEXT)
    assert isinstance(output, GoogleSearchOutput)
    return output


def test_google_search_is_a_web_search_tool_from_serpapi() -> None:
    tools = catalog()
    [descriptor] = [item for item in tools.descriptors({}) if item.tool_id == "google_search"]
    assert (descriptor.version, descriptor.group) == (1, "google")
    assert descriptor.provider == "serpapi"
    assert (descriptor.operation_class, descriptor.cost_class) == ("read_only", "metered_provider")
    assert descriptor.key_requirement is not None
    assert descriptor.key_requirement.variables == ["SERPAPI_API_KEY"]
    assert descriptor.key_requirement.credential == "serpapi"
    assert descriptor.availability == "key_missing"
    assert EXPERT_TOOLS["google_search"] == TOOL_VERSIONS["google_search"] == 1
    tool = SerpApi().tool()
    assert tool.retries == 0 and MAX_PAGES * REQUEST_SECONDS < tool.timeout_seconds
    assert tool.public_input_fields == ("query", "max_results")


@pytest.mark.asyncio
async def test_it_asks_serpapi_for_pages_of_ten_by_start() -> None:
    fake = SerpApi(reply(organic(0)), reply(organic(10)), reply(organic(20)))
    output = await search(fake)
    sent = [(request.method, request.url.host, request.url.path) for request in fake.requests]
    assert sent == [("GET", "serpapi.com", "/search.json")] * 3
    params = [dict(request.url.params) for request in fake.requests]
    assert [item["start"] for item in params] == ["0", "10", "20"]
    assert all(
        (item["engine"], item["q"], item["hl"], item["gl"], item["api_key"])
        == ("google", "colones", "en", "us", KEY)
        for item in params
    )
    assert all("num" not in item for item in params)
    assert [item.rank for item in output.results] == list(range(1, 31))
    assert output.results[0].model_dump() == {
        "rank": 1,
        "title": "T0",
        "url": "https://example.com/0",
        "snippet": "about 0",
    }
    assert (output.result_count, output.pages, output.stopped) == (30, 3, "enough")


@pytest.mark.asyncio
async def test_serpapis_next_page_signal_decides_when_there_are_no_more() -> None:
    short_then_last = SerpApi(reply(organic(0, count=8)), reply(organic(10), more=False))
    output = await search(short_then_last)
    assert len(short_then_last.requests) == 2
    assert (output.result_count, output.stopped) == (18, "no_more")
    then_empty = SerpApi(reply(organic(0)), FULLY_EMPTY)
    output = await search(then_empty)
    assert (output.result_count, output.pages, output.stopped, output.page_error) == (
        10,
        2,
        "no_more",
        None,
    )


@pytest.mark.parametrize(
    ("pages", "code"),
    [
        (((401, {"error": f"Invalid API key {KEY}"}),), "serpapi_key_refused"),
        (({"error": f"Something went wrong for {KEY}"},), "serpapi_search_failed"),
        (((503, {"error": "busy"}),), "provider_unavailable"),
    ],
)
@pytest.mark.asyncio
async def test_a_first_page_failure_is_typed(pages: tuple[Any, ...], code: str) -> None:
    fake = SerpApi(*pages)
    with pytest.raises(ToolFailed) as failed:
        await search(fake)
    assert str(failed.value) == code
    assert KEY not in str(failed.value)


@pytest.mark.asyncio
async def test_a_later_page_failure_keeps_the_first_and_shows_no_key_or_provider_text() -> None:
    refusal = (429, {"error": f"Your account {KEY} has run out of searches."})
    fake = SerpApi(reply(organic(0)), refusal)
    output = await search(fake)
    assert len(fake.requests) == 2
    assert [item.title for item in output.results] == [f"T{n}" for n in range(10)]
    assert (output.pages, output.stopped) == (2, "provider_error")
    assert output.page_error == "rate_limited"
    shown = output.model_dump_json()
    assert KEY not in shown and "run out of searches" not in shown


@pytest.mark.asyncio
async def test_without_a_key_nothing_is_sent() -> None:
    fake = SerpApi(reply(organic(0)))
    with pytest.raises(ToolFailed) as failed:
        await search(fake, environ={})
    assert (str(failed.value), fake.requests) == ("serpapi_key_missing", [])


def test_more_than_thirty_is_refused_before_any_request() -> None:
    fake = SerpApi(reply(organic(0)))
    tool = fake.tool()
    registry = ToolRegistry()
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {"google_search": 1})
    refused = resolve_call(registry, scope, "google_search", {"query": "x", "max_results": 31})
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert fake.requests == []


@pytest.mark.asyncio
async def test_long_snippets_share_the_text_budget_and_say_so() -> None:
    long = [dict(item, snippet="word " * 10_000) for item in organic(0)]
    fake = SerpApi(reply(long), reply(organic(10)), reply(organic(20)))
    tool = fake.tool()
    output = await search(fake)
    assert output.truncated is True and output.source == "third_party"
    assert sum(len(item.snippet) for item in output.results) <= 100_000
    assert len(output.model_dump_json().encode()) < tool.max_output_bytes
