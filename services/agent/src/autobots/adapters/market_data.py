"""Market history, US-14.10 and Decision 0017 C11, C12 and Q6.

Prices come from Yahoo Finance's chart endpoint, the one yfinance itself reads, called directly
over `httpx` so no `pandas` comes with it (C12). It is unofficial, for a single owner's personal
use, with no SLA, and every output says so (C11). It needs no key, and counts as a metered call
because it leaves this Mac (TU-06). No cross rate is computed: a symbol Yahoo doesn't serve fails
`symbol_not_found` (Q6). Tests use fake transports (C5). Inflation and its World Bank provider are
retired (Decision 0036 R1).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

import httpx

from autobots.adapters.provider_http import ProviderReply, http_client, read_json, refusal_code
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.market_tools import (
    MarketHistoryInput,
    MarketHistoryOutput,
    PriceRow,
    SymbolHistory,
)
from autobots.domain.tool_catalog import CostClass, ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

YAHOO_URL = "https://query1.finance.yahoo.com"
YAHOO_SOURCE = "Yahoo Finance chart endpoint: unofficial, personal use, no SLA"
HEADERS = {"Accept": "application/json", "User-Agent": "autobots-local/1"}
# Each request's bound, inside the tool's 30-second timeout (tests/test_market_data.py).
REQUEST_SECONDS = 20.0
TIMEOUT_SECONDS = 30.0


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class _Quote(ProviderReply):
    open: list[object] | None = None
    high: list[object] | None = None
    low: list[object] | None = None
    close: list[object] | None = None
    volume: list[object] | None = None


class _Indicators(ProviderReply):
    quote: list[_Quote | None] | None = None


class _Meta(ProviderReply):
    currency: str | None = None


class _Series(ProviderReply):
    meta: _Meta | None = None
    timestamp: list[int] | None = None
    indicators: _Indicators | None = None


class _ChartBody(ProviderReply):
    result: list[_Series] | None = None


class _Chart(ProviderReply):
    chart: _ChartBody | None = None


def _number(values: list[object] | None, index: int) -> float | None:
    value = values[index] if values is not None and index < len(values) else None
    return float(value) if isinstance(value, int | float) else None


def _rows(series: _Series) -> list[PriceRow]:
    quotes = series.indicators.quote if series.indicators is not None else None
    quote = (quotes or [None])[0] or _Quote()
    rows: list[PriceRow] = []
    previous: float | None = None
    for index, stamp in enumerate(series.timestamp or []):
        close = _number(quote.close, index)
        change = (
            round((close - previous) / previous * 100, 6)
            if close is not None and previous not in (None, 0.0)
            else None
        )
        rows.append(
            PriceRow(
                date=datetime.fromtimestamp(stamp, UTC).date().isoformat(),
                open=_number(quote.open, index),
                high=_number(quote.high, index),
                low=_number(quote.low, index),
                close=close,
                volume=_number(quote.volume, index),
                pct_change=change,
            )
        )
        if close is not None:
            previous = close
    return rows


def _yahoo_code(status: int) -> str:
    return "symbol_not_found" if status == 404 else refusal_code("yahoo_finance", status)


@dataclass(frozen=True)
class MarketConnector:
    """Its transport, which tests replace, and the clock each output's retrieval time comes from."""

    transport: httpx.AsyncBaseTransport | None
    now: Callable[[], str]

    def client(self, base_url: str) -> httpx.AsyncClient:
        return http_client(
            base_url, timeout=REQUEST_SECONDS, headers=HEADERS, transport=self.transport
        )


async def history(
    market: MarketConnector, arguments: MarketHistoryInput, _: ToolContext
) -> MarketHistoryOutput:
    histories = []
    async with market.client(YAHOO_URL) as client:
        for symbol in arguments.symbols:
            chart = await read_json(
                client,
                "GET",
                f"/v8/finance/chart/{symbol}",
                _Chart,
                code_for=_yahoo_code,
                params={"range": arguments.period, "interval": arguments.interval},
            )
            results = (chart.chart.result if chart.chart is not None else None) or []
            if not results:
                raise ToolFailed("symbol_not_found")
            series = results[0]
            histories.append(
                SymbolHistory(
                    symbol=symbol,
                    currency=series.meta.currency if series.meta is not None else None,
                    rows=_rows(series),
                )
            )
    return MarketHistoryOutput(
        histories=histories,
        source=YAHOO_SOURCE,
        retrieved_at=market.now(),
        symbol_count=len(histories),
    )


def market_tools(
    transport: httpx.AsyncBaseTransport | None = None, now: Callable[[], str] = _now
) -> tuple[ToolDefinition]:
    market = MarketConnector(transport, now)
    return (
        ToolDefinition(
            tool_id="market_history",
            title="Market price history",
            description=(
                "Daily or weekly prices for up to 5 Yahoo Finance symbols, such as BTC-USD, "
                "ETH-USD or CRC=X (US dollar to Costa Rican colón), with each close's percent "
                "change from the one before. Unofficial data, with its source and time."
            ),
            input_model=MarketHistoryInput,
            output_model=MarketHistoryOutput,
            handler=partial(history, market),
            provider=ToolProvider.YAHOO_FINANCE,
            cost_note="No charge, but unofficial and rate limited; counts as a metered call.",
            public_input_fields=("symbols", "period", "interval"),
            public_output_fields=("source", "retrieved_at", "symbol_count"),
            version=1,
            operation_class=OperationClass.READ_ONLY,
            timeout_seconds=TIMEOUT_SECONDS,
            retries=0,
            max_output_bytes=500_000,
            group=ToolGroup.MARKET_DATA,
            network=True,
            cost_class=CostClass.METERED_PROVIDER,
        ),
    )


MARKET_TOOLS = market_tools()
