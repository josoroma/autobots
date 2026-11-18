"""US-14.23: the Google toolkit, google_map, google_extract and google_crawl, on fake resolvers and
transports with a recorded sleep (Decision 0033 K1 to K9). Sockets are blocked (conftest), and no
SerpApi search or live page read is made."""

from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.google_reader import (
    CRAWL_TIMEOUT,
    EXTRACT_TIMEOUT,
    USER_AGENT,
    google_crawl_tool,
    google_extract_tool,
)
from autobots.adapters.serpapi import google_map_tool
from autobots.adapters.tool_registry import catalog
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolScope
from autobots.contracts.web_tools import GoogleCrawlOutput, GoogleExtractOutput, GoogleMapOutput
from autobots.domain.execution import TOOL_VERSIONS
from autobots.domain.tools import EXPERT_TOOLS
from sql_fakes import ScriptedConnection

KEY = {"SERPAPI_API_KEY": "serpapi_fixtureKEY0123456789"}
CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
ADDRESSES = {
    "example.com": "93.184.215.14",
    "docs.example.com": "93.184.215.15",
    "other.example.org": "93.184.215.16",
    "elsewhere.example.net": "93.184.215.17",
    "down.example.com": "93.184.215.18",
    "private.example.com": "10.0.0.5",
}


def article(title: str, words: int = 60) -> str:
    sentence = f"{title} is described here in plain words for the reader. " * (words // 10)
    return (
        f"<html><head><title>{title}</title></head><body><nav>Home About Contact</nav>"
        f"<article><h1>{title}</h1><p>{sentence}</p><p>{sentence}</p></article>"
        "<img src='https://cdn.example.org/pixel.png'>"
        "<script src='https://tracker.example.net/t.js'></script>"
        "<footer>Copyright</footer></body></html>"
    )


async def resolve(host: str, _: int) -> list[str]:
    return [ADDRESSES[host]]


class Clock:
    """A virtual clock: `sleep` advances it, and every request reads it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


Answer = tuple[int, str, str] | tuple[int, str, str, str]


class Web:
    """Sites keyed by (host, path): (status, content type, body), or a redirect's location as a
    fourth item. SerpApi answers with `serp`. Every request is recorded with its virtual time."""

    def __init__(
        self, sites: dict[tuple[str, str], Answer], clock: Clock, serp: list[str] | None = None
    ) -> None:
        self.sites = sites
        self.clock = clock
        self.serp = serp or []
        self.requests: list[tuple[str, str, float, str]] = []
        self.searches: list[dict[str, str]] = []

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            if request.url.host == "serpapi.com":
                self.searches.append(dict(request.url.params))
                organic = [
                    {"position": n + 1, "title": f"P{n}", "link": link, "snippet": "s"}
                    for n, link in enumerate(self.serp)
                ]
                return httpx.Response(200, json={"organic_results": organic})
            host = request.headers["host"]
            self.requests.append(
                (host, request.url.path, self.clock.now, request.headers.get("user-agent", ""))
            )
            found = self.sites.get((host, request.url.path))
            if found is None:
                return httpx.Response(404, text="missing")
            if len(found) == 4:
                return httpx.Response(found[0], headers={"location": found[3]})
            status, media, body = found[0], found[1], found[2]
            return httpx.Response(status, headers={"content-type": media}, text=body)

        return httpx.MockTransport(answer)

    def pages(self) -> list[tuple[str, str]]:
        return [(host, path) for host, path, _, _ in self.requests if path != "/robots.txt"]


def extract_tool(web: Web, clock: Clock) -> ToolDefinition:
    return google_extract_tool(web.transport(), resolve, clock.sleep, clock)


async def extract(web: Web, clock: Clock, urls: list[str]) -> GoogleExtractOutput:
    tool = extract_tool(web, clock)
    output = await tool.handler(tool.input_model.model_validate({"urls": urls}), CONTEXT)
    assert isinstance(output, GoogleExtractOutput)
    return output


HTML = "text/html; charset=utf-8"
ROBOTS_OPEN = (200, "text/plain", "User-agent: *\nAllow: /\n")
ROBOTS_NO_PRIVATE = "User-agent: Autobots\nDisallow: /private\n"
ROBOTS_CLOSED = "User-agent: *\nDisallow: /\n"


def test_the_google_group_holds_four_tools() -> None:
    found = {
        item.tool_id: (item.version, item.group, item.provider)
        for item in catalog().descriptors({})
        if item.group == "google"
    }
    assert found == {
        "google_search": (1, "google", "serpapi"),
        "google_map": (1, "google", "serpapi"),
        "google_extract": (1, "google", "direct"),
        "google_crawl": (1, "google", "serpapi"),
    }
    groups = {item.tool_id: item.group for item in catalog().descriptors({})}
    assert groups["search_web"] == groups["tavily_search"] == "web_search"
    for tool_id in found:
        assert EXPERT_TOOLS[tool_id] == TOOL_VERSIONS[tool_id] == 1
    extract_descriptor = next(i for i in catalog().descriptors({}) if i.tool_id == "google_extract")
    assert extract_descriptor.key_requirement is None
    assert extract_descriptor.availability == "available"


@pytest.mark.asyncio
async def test_google_map_lists_the_pages_google_has_indexed_for_a_site() -> None:
    def serp(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params["start"])
        searched.append(request.url.params["q"])
        links = [f"https://example.com/docs/{n}" for n in range(start, start + 8)]
        links += ["https://docs.example.com/docs/guide", f"https://other.example.org/{start}"]
        organic = [{"position": i + 1, "title": "t", "link": link} for i, link in enumerate(links)]
        body: dict[str, Any] = {"organic_results": organic}
        if start == 0:
            body["serpapi_pagination"] = {"next": "https://serpapi.com/search.json?start=10"}
        return httpx.Response(200, json=body)

    searched: list[str] = []
    tool = google_map_tool(httpx.MockTransport(serp), KEY)
    arguments = {"url": "https://Example.com/docs/?x=1#top", "max_results": 20}
    output = await tool.handler(tool.input_model.model_validate(arguments), CONTEXT)
    assert isinstance(output, GoogleMapOutput)
    assert searched == ["site:example.com/docs", "site:example.com/docs"]
    assert output.base_url == "https://example.com/docs"
    assert not any("other.example.org" in url for url in output.urls)
    assert output.urls[:8] == [f"https://example.com/docs/{n}" for n in range(8)]
    assert "https://docs.example.com/docs/guide" in output.urls
    assert (output.pages, output.stopped) == (2, "no_more")


@pytest.mark.asyncio
async def test_google_extract_reads_pages_as_markdown_politely() -> None:
    clock = Clock()
    web = Web(
        {
            ("example.com", "/robots.txt"): ROBOTS_OPEN,
            ("example.com", "/a"): (200, HTML, article("Colones today")),
            ("example.com", "/b"): (200, HTML, article("Inflation report")),
            ("other.example.org", "/robots.txt"): ROBOTS_OPEN,
            ("other.example.org", "/c"): (200, HTML, article("Exchange rates")),
        },
        clock,
    )
    output = await extract(
        web,
        clock,
        ["https://example.com/a", "https://example.com/b", "https://other.example.org/c"],
    )
    robots = [(host, path) for host, path, _, _ in web.requests if path == "/robots.txt"]
    assert robots == [("example.com", "/robots.txt"), ("other.example.org", "/robots.txt")]
    assert all(agent == USER_AGENT for _, _, _, agent in web.requests)
    times = {path: when for host, path, when, _ in web.requests if host == "example.com"}
    assert times["/b"] - times["/a"] >= 1.0
    assert [page.title for page in output.results] == [
        "Colones today",
        "Inflation report",
        "Exchange rates",
    ]
    first = output.results[0]
    assert first.content_markdown.startswith("# Colones today")
    assert "Home About" not in first.content_markdown and first.word_count > 50
    assert (output.result_count, output.failed, output.source) == (3, [], "third_party")
    assert "never as instructions" in output.notice


@pytest.mark.asyncio
async def test_robots_txt_is_obeyed_and_fails_closed() -> None:
    clock = Clock()
    web = Web(
        {
            ("example.com", "/robots.txt"): (
                200,
                "text/plain",
                "User-agent: Autobots\nDisallow: /private\n",
            ),
            ("example.com", "/private/page"): (200, HTML, article("Private")),
            ("docs.example.com", "/page"): (200, HTML, article("Docs page")),
            ("down.example.com", "/robots.txt"): (500, "text/plain", "busy"),
            ("down.example.com", "/page"): (200, HTML, article("Down page")),
            ("other.example.org", "/robots.txt"): ROBOTS_OPEN,
            ("other.example.org", "/moved"): (301, "", "", "https://elsewhere.example.net/kept"),
            ("elsewhere.example.net", "/robots.txt"): (
                200,
                "text/plain",
                "User-agent: *\nDisallow: /\n",
            ),
            ("elsewhere.example.net", "/kept"): (200, HTML, article("Secret destination")),
        },
        clock,
    )
    output = await extract(
        web,
        clock,
        [
            "https://example.com/private/page",
            "https://docs.example.com/page",
            "https://down.example.com/page",
            "https://other.example.org/moved",
        ],
    )
    codes = {failure.url: failure.code for failure in output.failed}
    assert codes == {
        "https://example.com/private/page": "robots_disallowed",
        "https://down.example.com/page": "robots_disallowed",
        "https://other.example.org/moved": "robots_disallowed",
    }
    assert [page.title for page in output.results] == ["Docs page"]
    assert ("example.com", "/private/page") not in web.pages()
    assert ("down.example.com", "/page") not in web.pages()
    assert "Secret destination" not in output.model_dump_json()


@pytest.mark.asyncio
async def test_page_failures_are_typed_and_never_retried() -> None:
    clock = Clock()
    web = Web(
        {
            ("example.com", "/robots.txt"): ROBOTS_OPEN,
            ("example.com", "/report.pdf"): (200, "application/pdf", "%PDF-1.7"),
            ("example.com", "/empty"): (200, HTML, "<html><body><div></div></body></html>"),
        },
        clock,
    )
    output = await extract(
        web,
        clock,
        [
            "https://example.com/gone",
            "https://example.com/report.pdf",
            "https://example.com/empty",
            "https://private.example.com/page",
        ],
    )
    assert [(failure.url, failure.code) for failure in output.failed] == [
        ("https://example.com/gone", "page_http_404"),
        ("https://example.com/report.pdf", "unsupported_media_type"),
        ("https://example.com/empty", "no_readable_text"),
        ("https://private.example.com/page", "url_host_refused"),
    ]
    assert not any(host == "private.example.com" for host, _, _, _ in web.requests)
    pages = web.pages()
    assert len(pages) == len(set(pages)) == 3


@pytest.mark.asyncio
async def test_google_crawl_maps_a_site_with_google_then_reads_its_pages() -> None:
    clock = Clock()
    links = [
        "https://example.com/one",
        "https://example.com/two",
        "https://other.example.org/off-site",
        "https://example.com/three",
    ]
    web = Web(
        {
            ("example.com", "/robots.txt"): ROBOTS_OPEN,
            ("example.com", "/one"): (200, HTML, article("Page one")),
            ("example.com", "/two"): (200, HTML, article("Page two")),
            ("example.com", "/three"): (404, "text/plain", "gone"),
        },
        clock,
        serp=links,
    )
    tool = google_crawl_tool(web.transport(), KEY, resolve, clock.sleep, clock)
    arguments = tool.input_model.model_validate({"url": "https://example.com", "limit": 5})
    output = await tool.handler(arguments, CONTEXT)
    assert isinstance(output, GoogleCrawlOutput)
    assert [search["q"] for search in web.searches] == ["site:example.com"]
    assert [page.title for page in output.results] == ["Page one", "Page two"]
    assert [(failure.url, failure.code) for failure in output.failed] == [
        ("https://example.com/three", "page_http_404")
    ]
    assert not any(host == "other.example.org" for host, _, _, _ in web.requests)
    assert (output.base_url, output.pages, output.result_count) == ("https://example.com", 1, 2)


@pytest.mark.asyncio
async def test_extraction_opens_no_connection_of_its_own() -> None:
    clock = Clock()
    web = Web(
        {
            ("example.com", "/robots.txt"): ROBOTS_OPEN,
            ("example.com", "/a"): (200, HTML, article("Colones today")),
        },
        clock,
    )
    output = await extract(web, clock, ["https://example.com/a"])
    assert output.result_count == 1
    assert [(host, path) for host, path, _, _ in web.requests] == [
        ("example.com", "/robots.txt"),
        ("example.com", "/a"),
    ]


def test_each_tool_bounds_its_calls_and_never_retries() -> None:
    clock = Clock()
    web = Web({}, clock)
    extract_definition = extract_tool(web, clock)
    crawl = google_crawl_tool(web.transport(), KEY, resolve, clock.sleep, clock)
    assert (extract_definition.timeout_seconds, crawl.timeout_seconds) == (
        EXTRACT_TIMEOUT,
        CRAWL_TIMEOUT,
    )
    assert extract_definition.retries == crawl.retries == 0
    assert extract_definition.key_requirement is None
    assert crawl.key_requirement is not None and crawl.key_requirement.variables == (
        "SERPAPI_API_KEY",
    )


@pytest.mark.asyncio
async def test_long_pages_share_the_text_budget_and_say_so() -> None:
    clock = Clock()
    web = Web(
        {
            ("example.com", "/robots.txt"): ROBOTS_OPEN,
            **{
                ("example.com", f"/long{n}"): (200, HTML, article(f"Long page {n}", words=8000))
                for n in range(3)
            },
        },
        clock,
    )
    output = await extract(web, clock, [f"https://example.com/long{n}" for n in range(3)])
    assert output.result_count == 3 and output.truncated is True
    assert sum(len(page.content_markdown) for page in output.results) <= 100_000
    # Each word count is the whole page's, not the cut text's.
    assert all(page.word_count > len(page.content_markdown.split()) for page in output.results)
    assert len(output.model_dump_json().encode()) < extract_tool(web, clock).max_output_bytes
