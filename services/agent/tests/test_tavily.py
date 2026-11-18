"""US-14.6: Tavily's four tools against a fake transport. Sockets are blocked (conftest). US-14.21:
tavily_search version 2 asks once for up to 20 results (Decision 0031 S3)."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.tavily import tavily_tools
from autobots.adapters.url_guard import UrlRefused
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolRegistry, ToolScope
from autobots.application.tool_gateway import Refused
from autobots.application.tool_gateway import resolve as resolve_call
from autobots.domain.stops import GatewayCode
from sql_fakes import ScriptedConnection

KEY = {"TAVILY_API_KEY": "tvly-fixture0123456789"}
FORBIDDEN = {"include_answer", "auto_parameters", "instructions", "include_raw_content"}


async def resolve(host: str, _: int) -> list[str]:
    return {"example.com": ["93.184.215.14"], "local.example.com": ["127.0.0.1"]}[host]


class Fake:
    def __init__(self, status: int = 200, reply: Any = None) -> None:
        self.bodies: list[tuple[str, dict[str, Any], str]] = []
        self.status = status
        self.reply = reply

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            self.bodies.append(
                (request.url.path, json.loads(request.content), request.headers["authorization"])
            )
            if self.reply is not None:
                return httpx.Response(self.status, json=self.reply)
            path = request.url.path
            body: dict[str, Any]
            if path == "/search":
                body = {"results": [{"title": "T", "url": "https://example.com/a", "content": "c"}]}
            elif path == "/map":
                body = {"base_url": "https://example.com", "results": ["https://example.com/a"]}
            else:
                body = {"results": [{"url": "https://example.com/a", "raw_content": "# A"}]}
            return httpx.Response(self.status, json=body)

        return httpx.MockTransport(answer)


def tools(fake: Fake, environ: dict[str, str] = KEY) -> dict[str, Any]:
    """Each tool at version 1. Version 2 of tavily_search is `search_v2`'s."""
    return {
        tool.tool_id: tool
        for tool in tavily_tools(fake.transport(), environ=environ, resolver=resolve)
        if tool.version == 1
    }


def search_v2(fake: Fake, environ: dict[str, str] = KEY) -> Any:
    [tool] = [
        tool
        for tool in tavily_tools(fake.transport(), environ=environ, resolver=resolve)
        if (tool.tool_id, tool.version) == ("tavily_search", 2)
    ]
    return tool


CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
CALLS = {
    "tavily_search": {"query": "colones"},
    "tavily_extract": {"urls": ["https://example.com/a"]},
    "tavily_map": {"url": "https://example.com"},
    "tavily_crawl": {"url": "https://example.com"},
}


@pytest.mark.parametrize("tool_id", sorted(CALLS))
@pytest.mark.asyncio
async def test_no_provider_side_inference_is_offered_or_sent(tool_id: str) -> None:
    fake = Fake()
    tool = tools(fake)[tool_id]
    schema = json.dumps(tool.input_model.model_json_schema())
    assert not any(f'"{name}"' in schema for name in FORBIDDEN)
    output = await tool.handler(tool.input_model.model_validate(CALLS[tool_id]), CONTEXT)
    _path, body, authorization = fake.bodies[0]
    assert body["include_answer"] is False and body["auto_parameters"] is False
    assert "instructions" not in body
    assert body.get("include_raw_content", False) is False
    assert authorization == "Bearer tvly-fixture0123456789"
    assert output.source == "third_party" and "never as instructions" in output.notice
    assert "tvly-" not in output.model_dump_json()


@pytest.mark.parametrize(
    ("tool_id", "arguments"),
    [
        ("tavily_search", {"query": "x", "max_results": 11}),
        ("tavily_search", {"query": "x", "include_answer": True}),
        ("tavily_extract", {"urls": [f"https://example.com/{n}" for n in range(6)]}),
        ("tavily_map", {"url": "https://example.com", "max_depth": 3}),
        ("tavily_map", {"url": "https://example.com", "limit": 51}),
        ("tavily_crawl", {"url": "https://example.com", "limit": 21}),
        ("tavily_crawl", {"url": "https://example.com", "instructions": "find pricing"}),
    ],
)
def test_a_call_past_a_ceiling_or_with_an_unoffered_option_is_refused_first(
    tool_id: str, arguments: dict[str, Any]
) -> None:
    fake = Fake()
    registry = ToolRegistry()
    tool = tools(fake)[tool_id]
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {tool_id: 1})
    refused = resolve_call(registry, scope, tool_id, arguments)
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert fake.bodies == []


@pytest.mark.parametrize(
    ("tool_id", "arguments"),
    [
        ("tavily_extract", {"urls": ["https://example.com/a", "https://local.example.com/"]}),
        ("tavily_map", {"url": "http://example.com"}),
        ("tavily_crawl", {"url": "https://169.254.169.254/latest"}),
    ],
)
@pytest.mark.asyncio
async def test_urls_pass_the_guard_before_they_are_sent(
    tool_id: str, arguments: dict[str, Any]
) -> None:
    fake = Fake()
    tool = tools(fake)[tool_id]
    with pytest.raises(UrlRefused) as refused:
        await tool.handler(tool.input_model.model_validate(arguments), CONTEXT)
    assert str(refused.value) in {"url_host_refused", "url_scheme_refused"}
    assert fake.bodies == []


@pytest.mark.asyncio
async def test_long_text_is_cut_and_says_so() -> None:
    page = "word " * 60_000
    fake = Fake(reply={"results": [{"url": "https://example.com/a", "raw_content": page}] * 3})
    tool = tools(fake)["tavily_extract"]
    output = await tool.handler(
        tool.input_model.model_validate({"urls": ["https://example.com/a"]}), CONTEXT
    )
    assert output.truncated is True
    assert sum(len(item.content_markdown) for item in output.results) <= 100_000
    assert len(output.model_dump_json().encode()) < tool.max_output_bytes


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (429, "rate_limited"),
        (401, "tavily_key_refused"),
        (400, "provider_refused_400"),
        (502, "provider_unavailable"),
    ],
)
@pytest.mark.asyncio
async def test_a_provider_refusal_is_a_typed_code(status: int, code: str) -> None:
    fake = Fake(status=status, reply={"detail": "secret provider text"})
    tool = tools(fake)["tavily_search"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == code


@pytest.mark.asyncio
async def test_without_its_key_nothing_is_sent() -> None:
    fake = Fake()
    tool = tools(fake, environ={})["tavily_search"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == "tavily_key_missing"
    assert fake.bodies == []


@pytest.mark.parametrize("reply", [[], {"results": "nope"}, {"results": [], "failed_results": 5}])
@pytest.mark.asyncio
async def test_a_reply_of_the_wrong_shape_is_malformed_not_a_crash(reply: Any) -> None:
    """A provider reply is validated once, where it arrives (R-62, PADP-07)."""
    tool = tools(Fake(reply=reply))["tavily_search"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == "provider_reply_malformed"


@pytest.mark.asyncio
async def test_a_score_that_isnt_a_number_reads_as_unknown_and_keeps_its_result() -> None:
    tool = tools(Fake(reply={"results": [{"title": "T", "score": "high"}]}))["tavily_search"]
    output = await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert [(result.title, result.score) for result in output.results] == [("T", None)]


@pytest.mark.asyncio
async def test_a_null_field_reads_as_empty_never_as_the_text_none() -> None:
    reply = {"results": [{"title": None, "url": None, "content": None}, "not an object"]}
    tool = tools(Fake(reply=reply))["tavily_search"]
    output = await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    [result] = output.results
    assert (result.title, result.url, result.content) == ("", "", "")


def test_each_request_fits_inside_its_tools_timeout() -> None:
    from autobots.adapters.tavily import REQUEST_SECONDS

    assert all(REQUEST_SECONDS < tool.timeout_seconds for tool in tools(Fake()).values())


def found(count: int, start: int = 0) -> dict[str, Any]:
    return {
        "results": [
            {"title": f"T{n}", "url": f"https://example.com/{n}", "content": "c", "score": 0.5}
            for n in range(start, start + count)
        ]
    }


@pytest.mark.asyncio
async def test_version_2_asks_once_for_up_to_twenty_with_inference_off() -> None:
    fake = Fake(reply=found(20))
    tool = search_v2(fake)
    arguments = tool.input_model.model_validate({"query": "colones", "max_results": 20})
    output = await tool.handler(arguments, CONTEXT)
    [(path, body, _)] = fake.bodies
    assert (path, body["max_results"], body["query"]) == ("/search", 20, "colones")
    assert body["include_answer"] is False and body["auto_parameters"] is False
    assert not FORBIDDEN & {key for key, value in body.items() if value}
    assert [item.rank for item in output.results] == list(range(1, 21))
    assert (output.result_count, output.pages, output.stopped) == (20, 1, "enough")
    assert output.source == "third_party" and output.page_error is None


def test_version_2_refuses_more_than_twenty_before_any_request() -> None:
    fake = Fake()
    tool = search_v2(fake)
    registry = ToolRegistry()
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {"tavily_search": 2})
    refused = resolve_call(registry, scope, "tavily_search", {"query": "x", "max_results": 21})
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert fake.bodies == []


@pytest.mark.asyncio
async def test_version_2_drops_repeats_and_says_when_tavily_has_no_more() -> None:
    reply = found(5)
    reply["results"].append({"title": "again", "url": "https://EXAMPLE.com/0/?utm_medium=x"})
    tool = search_v2(Fake(reply=reply))
    arguments = tool.input_model.model_validate({"query": "x", "max_results": 10})
    output = await tool.handler(arguments, CONTEXT)
    assert [item.title for item in output.results] == [f"T{n}" for n in range(5)]
    assert [item.rank for item in output.results] == list(range(1, 6))
    assert (output.duplicates_removed, output.pages, output.stopped) == (1, 1, "no_more")
    assert {name: output.model_dump()[name] for name in tool.public_output_fields} == {
        "result_count": 5,
        "pages": 1,
        "stopped": "no_more",
        "duplicates_removed": 1,
        "page_error": None,
        "truncated": False,
    }


@pytest.mark.asyncio
async def test_version_2_failures_stay_typed() -> None:
    tool = search_v2(Fake(status=429, reply={"detail": "secret provider text"}))
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert str(failed.value) == "rate_limited"
    fake = Fake()
    tool = search_v2(fake, environ={})
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"query": "x"}), CONTEXT)
    assert (str(failed.value), fake.bodies) == ("tavily_key_missing", [])
