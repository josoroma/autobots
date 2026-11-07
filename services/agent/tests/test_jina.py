"""US-14.7: Jina's Search The Web and Extract Website Content against a fake transport."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.jina import jina_tools
from autobots.adapters.url_guard import UrlRefused
from autobots.application.tool_gateway import (
    ToolContext,
    ToolFailed,
    ToolGateway,
    ToolRegistry,
    ToolScope,
)

KEY = {"JINA_API_KEY": "jina_fixture0123456789"}
MODEL_OPTIONS = ("readerlm", "x-respond-with", "x-with-generated-alt: true", "x-engine")
CONTEXT = ToolContext(None, ToolScope(uuid4(), uuid4(), 1, {}), None)


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


def tools(fake: Fake, environ: dict[str, str] = KEY) -> dict[str, Any]:
    return {
        tool.tool_id: tool
        for tool in jina_tools(fake.transport(), environ=environ, resolver=resolve)
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
@pytest.mark.asyncio
async def test_a_call_past_a_ceiling_or_with_an_unoffered_option_is_refused_first(
    tool_id: str, arguments: dict[str, Any]
) -> None:
    fake = Fake()
    registry = ToolRegistry()
    registry.register(tools(fake)[tool_id])
    scope = ToolScope(uuid4(), uuid4(), 1, {tool_id: 1})
    result = await ToolGateway(registry).execute(None, scope, tool_id, arguments)
    assert (result.outcome.value, result.code) == ("denied", "invalid_arguments")
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
