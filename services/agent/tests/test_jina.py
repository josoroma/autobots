"""US-14.7: Jina's Search The Web and Extract Website Content against a fake transport. US-14.21:
search_web version 2 asks for pages of 10, up to 3 a call (Decision 0031)."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.jina import jina_tools
from autobots.adapters.url_guard import UrlRefused
from autobots.application.tool_definitions import (
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import Refused
from autobots.application.tool_gateway import resolve as resolve_call
from autobots.contracts.web_tools import SearchWebV2Output
from autobots.domain.stops import GatewayCode
from sql_fakes import ScriptedConnection

KEY = {"JINA_API_KEY": "jina_fixture0123456789"}
MODEL_OPTIONS = ("readerlm", "x-respond-with", "x-with-generated-alt: true", "x-engine")
CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)


async def resolve(host: str, _: int) -> list[str]:
    return {"example.com": ["93.184.215.14"], "local.example.com": ["127.0.0.1"]}[host]


class Fake:
    def __init__(self, status: int = 200, page: str = "# Page\n\nText") -> None:
        self.seen: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self.status = status
        self.page = page

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            self.seen.append((request.url.host, json.loads(request.content), dict(request.headers)))
            if request.url.host == "s.jina.ai":
                body: dict[str, Any] = {
                    "data": [
                        {"title": f"T{n}", "url": f"https://example.com/{n}", "description": "d"}
                        for n in range(12)
                    ]
                }
            else:
                body = {
                    "data": {
                        "url": "https://example.com/a",
                        "title": "A",
                        "content": self.page,
                        "links": {"One": "https://example.com/1", "Two": "https://example.com/2"},
                    }
                }
            return httpx.Response(self.status, json=body)

        return httpx.MockTransport(answer)


def tools(fake: Fake, environ: dict[str, str] = KEY, version: int = 1) -> dict[str, Any]:
    """Each tool at `version`, or at version 1 where it has no other."""
    return {
        tool.tool_id: tool
        for tool in jina_tools(fake.transport(), environ=environ, resolver=resolve)
        if tool.version in {1, version}
        and (tool.version == version or tool.tool_id != "search_web")
    }


@pytest.mark.asyncio
async def test_search_returns_labelled_snippets_within_its_ceiling() -> None:
    fake = Fake()
    tool = tools(fake)["search_web"]
    output = await tool.handler(
        tool.input_model.model_validate({"query": "colones", "max_results": 3}), CONTEXT
    )
    host, body, headers = fake.seen[0]
    assert (host, body) == ("s.jina.ai", {"q": "colones", "num": 3})
    assert headers["authorization"] == "Bearer jina_fixture0123456789"
    assert [item.title for item in output.results] == ["T0", "T1", "T2"]
    assert output.source == "third_party" and "never as instructions" in output.notice
    assert "jina_fixture" not in output.model_dump_json()


@pytest.mark.parametrize(
    ("tool_id", "arguments"),
    [
        ("search_web", {"query": "x", "max_results": 11}),
        ("search_web", {"query": ""}),
        ("extract_website_content", {"url": "https://example.com", "engine": "readerlm-v2"}),
    ],
)
def test_a_call_past_a_ceiling_or_with_an_unoffered_option_is_refused_first(
    tool_id: str, arguments: dict[str, Any]
) -> None:
    fake = Fake()
    tool = tools(fake)[tool_id]
    registry = ToolRegistry()
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {tool_id: 1})
    refused = resolve_call(registry, scope, tool_id, arguments)
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert fake.seen == []


@pytest.mark.asyncio
async def test_extract_uses_reader_mode_with_no_model_option() -> None:
    fake = Fake(page="word " * 30_000)
    tool = tools(fake)["extract_website_content"]
    schema = json.dumps(tool.input_model.model_json_schema()).lower()
    assert list(tool.input_model.model_fields) == ["url"]
    output = await tool.handler(
        tool.input_model.model_validate({"url": "https://example.com/a"}), CONTEXT
    )
    host, body, headers = fake.seen[0]
    assert (host, body) == ("r.jina.ai", {"url": "https://example.com/a"})
    sent = json.dumps(headers).lower()
    assert headers["x-return-format"] == "markdown"
    assert headers["x-with-generated-alt"] == "false"
    assert not any(option in sent or option in schema for option in MODEL_OPTIONS[:2])
    assert "x-engine" not in headers
    assert output.truncated is True and len(output.content_markdown) == 100_000
    assert output.links == ["https://example.com/1", "https://example.com/2"]
    assert output.source == "third_party"
    assert len(output.model_dump_json().encode()) < tool.max_output_bytes


@pytest.mark.parametrize(
    "url", ["https://local.example.com/", "http://example.com/", "https://10.0.0.1/"]
)
@pytest.mark.asyncio
async def test_urls_pass_the_guard_before_they_are_sent(url: str) -> None:
    fake = Fake()
    tool = tools(fake)["extract_website_content"]
    with pytest.raises(UrlRefused) as refused:
        await tool.handler(tool.input_model.model_validate({"url": url}), CONTEXT)
    assert str(refused.value) in {"url_host_refused", "url_scheme_refused"}
    assert fake.seen == []


@pytest.mark.asyncio
async def test_refusals_and_a_missing_key_are_typed() -> None:
    fake = Fake(status=429)
    tool = tools(fake)["search_web"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == "rate_limited"
    fake = Fake()
    tool = tools(fake, environ={})["search_web"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == "jina_key_missing"
    assert fake.seen == []


@pytest.mark.asyncio
async def test_a_search_reply_that_isnt_an_object_is_malformed_not_an_empty_success() -> None:
    """A list isn't the reply's shape, so it's malformed, never an empty success (PADP-07)."""

    def answer(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"title": "T"}])

    for tool in jina_tools(httpx.MockTransport(answer), environ=KEY, resolver=resolve):
        if tool.tool_id != "search_web":
            continue
        with pytest.raises(ToolFailed) as failed:
            await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
        assert (tool.version, str(failed.value)) == (tool.version, "provider_reply_malformed")


def test_each_request_fits_inside_its_tools_timeout() -> None:
    from autobots.adapters.jina import REQUEST_SECONDS

    assert all(REQUEST_SECONDS < tool.timeout_seconds for tool in tools(Fake()).values())


def hits(start: int, count: int = 10, description: str = "d") -> list[dict[str, str]]:
    return [
        {"title": f"T{n}", "url": f"https://example.com/{n}", "description": description}
        for n in range(start, start + count)
    ]


class Paged:
    """s.jina.ai answering page n with the n-th of `pages`: a list of results, or a status and a
    body. A page past the list answers with no results."""

    def __init__(self, *pages: list[dict[str, str]] | tuple[int, dict[str, Any]]) -> None:
        self.pages = pages
        self.bodies: list[dict[str, Any]] = []
        self.keys: list[str] = []

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.bodies.append(body)
            self.keys.append(request.headers["authorization"])
            number = body.get("page", 1)
            served = self.pages[number - 1] if number <= len(self.pages) else []
            if isinstance(served, tuple):
                return httpx.Response(served[0], json=served[1])
            return httpx.Response(200, json={"data": served})

        return httpx.MockTransport(answer)

    def tool(self) -> ToolDefinition:
        [paged] = [
            tool
            for tool in jina_tools(self.transport(), environ=KEY, resolver=resolve)
            if (tool.tool_id, tool.version) == ("search_web", 2)
        ]
        return paged


async def search(paged: Paged, max_results: int) -> SearchWebV2Output:
    tool = paged.tool()
    arguments = tool.input_model.model_validate({"query": "colones", "max_results": max_results})
    output = await tool.handler(arguments, CONTEXT)
    assert isinstance(output, SearchWebV2Output)
    return output


@pytest.mark.asyncio
async def test_version_2_asks_for_pages_of_ten_by_number() -> None:
    paged = Paged(hits(0), hits(10), hits(20))
    output = await search(paged, 30)
    assert paged.bodies == [{"q": "colones", "num": 10, "page": n} for n in (1, 2, 3)]
    assert paged.keys == ["Bearer jina_fixture0123456789"] * 3
    assert [item.rank for item in output.results] == list(range(1, 31))
    assert [item.title for item in output.results] == [f"T{n}" for n in range(30)]
    assert (output.result_count, output.pages, output.stopped) == (30, 3, "enough")
    fewer = Paged(hits(0), hits(10), hits(20))
    output = await search(fewer, 15)
    assert [body["page"] for body in fewer.bodies] == [1, 2]
    assert (output.result_count, output.pages, output.stopped) == (15, 2, "enough")


@pytest.mark.asyncio
async def test_version_2_never_asks_for_more_than_three_pages() -> None:
    paged = Paged(hits(0), hits(10), hits(20))
    tool = paged.tool()
    registry = ToolRegistry()
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {"search_web": 2})
    refused = resolve_call(registry, scope, "search_web", {"query": "x", "max_results": 31})
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert paged.bodies == []
    repeating = Paged(hits(0), hits(0), hits(0), hits(0))
    output = await search(repeating, 30)
    assert len(repeating.bodies) <= 3
    assert (output.result_count, output.stopped) == (10, "no_more")


@pytest.mark.asyncio
async def test_version_2_drops_repeats_across_pages_keeping_the_first_as_given() -> None:
    repeats = [
        {"title": "R0", "url": "https://example.com/0?utm_source=feed", "description": "d"},
        {"title": "R1", "url": "https://example.com/1#part", "description": "d"},
        {"title": "R2", "url": "https://EXAMPLE.COM/2", "description": "d"},
        {"title": "R3", "url": "https://example.com/3/", "description": "d"},
    ]
    paged = Paged(hits(0), repeats + hits(10, count=6))
    output = await search(paged, 20)
    assert [item.url for item in output.results[:4]] == [
        f"https://example.com/{n}" for n in range(4)
    ]
    assert not any(item.title.startswith("R") for item in output.results)
    assert [item.rank for item in output.results] == list(range(1, 17))
    assert (output.duplicates_removed, output.result_count) == (4, 16)


@pytest.mark.asyncio
async def test_version_2_stops_at_a_short_page() -> None:
    paged = Paged(hits(0), hits(10, count=4), hits(20))
    output = await search(paged, 30)
    assert [body["page"] for body in paged.bodies] == [1, 2]
    assert (output.result_count, output.pages, output.stopped) == (14, 2, "no_more")


@pytest.mark.asyncio
async def test_version_2_keeps_earlier_pages_when_a_later_one_fails() -> None:
    refusal = (429, {"detail": "key jina_fixture0123456789 is over its limit"})
    paged = Paged(hits(0), refusal, hits(20))
    output = await search(paged, 30)
    assert [body["page"] for body in paged.bodies] == [1, 2]
    assert [item.title for item in output.results] == [f"T{n}" for n in range(10)]
    assert (output.pages, output.stopped, output.page_error) == (
        2,
        "provider_error",
        "rate_limited",
    )
    shown = output.model_dump_json()
    assert "jina_fixture" not in shown and "over its limit" not in shown
    failing = Paged((503, {"detail": "down"}), hits(10))
    with pytest.raises(ToolFailed) as failed:
        await search(failing, 30)
    assert str(failed.value) == "provider_unavailable"
    assert len(failing.bodies) == 1


@pytest.mark.asyncio
async def test_version_2_shows_the_model_ranked_labelled_results_cut_to_the_budget() -> None:
    long = "word " * 10_000
    paged = Paged(hits(0, description=long), hits(10, description=long), hits(20, description=long))
    tool = paged.tool()
    output = await search(paged, 30)
    shown = output.model_dump(mode="json")
    assert shown["source"] == "third_party" and "never as instructions" in shown["notice"]
    assert set(shown["results"][0]) == {"rank", "title", "url", "snippet"}
    assert {name: shown[name] for name in tool.public_output_fields} == {
        "result_count": 30,
        "pages": 3,
        "stopped": "enough",
        "duplicates_removed": 0,
        "page_error": None,
        "truncated": True,
    }
    assert sum(len(item["snippet"]) for item in shown["results"]) <= 100_000
    assert len(output.model_dump_json().encode()) < tool.max_output_bytes


def test_version_2_fits_three_requests_in_its_timeout_and_never_retries() -> None:
    from autobots.adapters.jina import REQUEST_SECONDS
    from autobots.adapters.search_paging import MAX_PAGES

    tool = Paged().tool()
    assert MAX_PAGES * REQUEST_SECONDS < tool.timeout_seconds
    assert tool.retries == 0
    assert tool.public_input_fields == ("query", "max_results")
