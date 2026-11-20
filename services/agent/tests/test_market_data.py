"""US-14.10: market history against fake transports in Yahoo's reply shape. Inflation and its World
Bank provider are retired (Decision 0036 R1)."""

from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.market_data import market_tools
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolRegistry, ToolScope
from autobots.application.tool_gateway import Refused, resolve
from autobots.domain.stops import GatewayCode
from sql_fakes import ScriptedConnection

CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
DAY = 86_400
START = 1_761_955_200  # 2025-11-01T00:00:00Z


def chart(closes: list[float | None], currency: str = "USD") -> dict[str, Any]:
    return {
        "chart": {
            "result": [
                {
                    "meta": {"currency": currency, "symbol": "X"},
                    "timestamp": [START + DAY * n for n in range(len(closes))],
                    "indicators": {
                        "quote": [
                            {
                                "open": closes,
                                "high": closes,
                                "low": closes,
                                "close": closes,
                                "volume": [100] * len(closes),
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


class Fake:
    def __init__(self, replies: dict[str, httpx.Response]) -> None:
        self.replies = replies
        self.seen: list[str] = []

    def transport(self) -> httpx.MockTransport:
        def answer(request: httpx.Request) -> httpx.Response:
            self.seen.append(str(request.url))
            for marker, reply in self.replies.items():
                if marker in str(request.url):
                    return reply
            return httpx.Response(404, json={"chart": {"result": None, "error": {}}})

        return httpx.MockTransport(answer)


def tools(fake: Fake) -> dict[str, Any]:
    return {
        tool.tool_id: tool
        for tool in market_tools(fake.transport(), now=lambda: "2026-11-07T00:00:00+00:00")
    }


@pytest.mark.asyncio
async def test_history_rows_with_close_to_close_change_source_and_time() -> None:
    fake = Fake(
        {
            "BTC-USD": httpx.Response(200, json=chart([100.0, 110.0, None, 99.0])),
            "CRC%3DX": httpx.Response(200, json=chart([512.0, 506.88], "CRC")),
            "CRC=X": httpx.Response(200, json=chart([512.0, 506.88], "CRC")),
        }
    )
    tool = tools(fake)["market_history"]
    output = await tool.handler(
        tool.input_model.model_validate(
            {"symbols": ["BTC-USD", "CRC=X"], "period": "1mo", "interval": "1d"}
        ),
        CONTEXT,
    )
    btc, crc = output.histories
    assert [row.date for row in btc.rows] == [
        "2025-11-01",
        "2025-11-02",
        "2025-11-03",
        "2025-11-04",
    ]
    assert [row.pct_change for row in btc.rows] == [None, 10.0, None, -10.0]
    assert (btc.currency, crc.currency) == ("USD", "CRC")
    assert crc.rows[1].pct_change == pytest.approx(-1.0)
    assert "unofficial" in output.source and output.retrieved_at == "2026-11-07T00:00:00+00:00"
    assert all("range=1mo" in url and "interval=1d" in url for url in fake.seen)


@pytest.mark.parametrize(
    "arguments",
    [
        {"symbols": ["btc-usd"]},
        {"symbols": ["BTC USD"]},
        {"symbols": ["A", "B", "C", "D", "E", "F"]},
        {"symbols": ["BTC-USD"], "period": "10y"},
        {"symbols": ["BTC-USD"], "interval": "1m"},
        {"symbols": ["../../v7/finance/quote"]},
        {"symbols": ["BTC-USD", "BTC-USD"]},
    ],
)
def test_invalid_symbols_or_values_are_refused_before_any_request(
    arguments: dict[str, Any],
) -> None:
    fake = Fake({})
    tool = tools(fake)["market_history"]
    registry = ToolRegistry()
    registry.register(tool)
    scope = ToolScope(uuid4(), uuid4(), 1, {"market_history": 1})
    refused = resolve(registry, scope, "market_history", arguments)
    assert refused == Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    assert fake.seen == []


@pytest.mark.parametrize(
    ("reply", "code"),
    [
        (
            httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}}),
            "symbol_not_found",
        ),
        (httpx.Response(200, json={"chart": {"result": [], "error": None}}), "symbol_not_found"),
        (httpx.Response(503, text="down"), "provider_unavailable"),
        (httpx.Response(429, text="slow down"), "rate_limited"),
    ],
)
@pytest.mark.asyncio
async def test_typed_failures(reply: httpx.Response, code: str) -> None:
    fake = Fake({"EURCRC": reply})
    tool = tools(fake)["market_history"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"symbols": ["EURCRC=X"]}), CONTEXT)
    assert str(failed.value) == code


@pytest.mark.asyncio
async def test_no_cross_rate_is_computed() -> None:
    fake = Fake({})
    tool = tools(fake)["market_history"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(tool.input_model.model_validate({"symbols": ["EURCRC=X"]}), CONTEXT)
    assert str(failed.value) == "symbol_not_found"
    # Only the symbol asked for was requested; no EURUSD=X or CRC=X was fetched to build a cross.
    assert len(fake.seen) == 1 and "EURCRC" in fake.seen[0]


@pytest.mark.parametrize(
    "body", [{"chart": []}, {"chart": {"result": [{"timestamp": ["x"]}]}}, ["not", "a chart"]]
)
@pytest.mark.asyncio
async def test_a_chart_of_the_wrong_shape_is_malformed(body: object) -> None:
    fake = Fake({"BTC-USD": httpx.Response(200, json=body)})
    tool = tools(fake)["market_history"]
    with pytest.raises(ToolFailed) as failed:
        await tool.handler(
            tool.input_model.model_validate(
                {"symbols": ["BTC-USD"], "period": "1mo", "interval": "1d"}
            ),
            CONTEXT,
        )
    assert str(failed.value) == "provider_reply_malformed"


def test_each_request_fits_inside_its_tools_timeout() -> None:
    from autobots.adapters.market_data import REQUEST_SECONDS

    assert all(REQUEST_SECONDS < tool.timeout_seconds for tool in tools(Fake({})).values())
