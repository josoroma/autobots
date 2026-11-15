"""Market history and inflation, US-14.10 and Decision 0017 C11, C12, Q5 and Q6.

Prices come from Yahoo Finance's chart endpoint, the one yfinance itself reads, called directly
over `httpx` so no `pandas` comes with it (C12). It is unofficial, for a single owner's personal
use, with no SLA, and every output says so (C11). Inflation comes from the World Bank Indicators
API, `FP.CPI.TOTL.ZG`, annual, for Costa Rica, the USA and the euro area (Q5). Neither needs a key,
and both count as metered calls because they leave this Mac (TU-06). No cross rate is computed: a
symbol Yahoo doesn't serve fails `symbol_not_found` (Q6). Tests use fake transports (C5).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import TypedDict

import httpx
from pydantic import RootModel, ValidationError

from autobots.adapters.provider_http import (
    MALFORMED,
    Number,
    ProviderReply,
    Text,
    http_client,
    read,
    read_json,
    refusal_code,
)
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.market_tools import (
    CountryInflation,
    InflationInput,
    InflationOutput,
    InflationRow,
    MarketHistoryInput,
    MarketHistoryOutput,
    PriceRow,
    SymbolHistory,
)
from autobots.domain.tool_catalog import CostClass, ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

YAHOO_URL = "https://query1.finance.yahoo.com"
WORLD_BANK_URL = "https://api.worldbank.org"
YAHOO_SOURCE = "Yahoo Finance chart endpoint: unofficial, personal use, no SLA"
WORLD_BANK_SOURCE = "World Bank Indicators API, FP.CPI.TOTL.ZG (consumer prices, annual %)"
NAMES = {"CRI": "Costa Rica", "USA": "United States", "EMU": "Euro area"}
HEADERS = {"Accept": "application/json", "User-Agent": "autobots-local/1"}
# Each request's bound, inside each tool's 30-second timeout (tests/test_market_data.py).
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


class _Observation(ProviderReply):
    countryiso3code: Text = ""
    date: Text = ""
    value: Number = None


class _Indicator(RootModel[list[object]]):
    """The World Bank answers a list: paging, then the rows. An error is a list of one message."""


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


def _observations(body: list[object]) -> list[_Observation]:
    """The rows of a World Bank answer. A list without them is the API refusing the request."""
    if len(body) < 2 or not isinstance(body[1], list):
        raise ToolFailed("provider_refused_400")
    try:
        return [_Observation.model_validate(item) for item in body[1] if isinstance(item, dict)]
    except ValidationError:
        raise ToolFailed(MALFORMED) from None


async def inflation(
    market: MarketConnector, arguments: InflationInput, _: ToolContext
) -> InflationOutput:
    path = f"/v2/country/{';'.join(arguments.countries)}/indicator/FP.CPI.TOTL.ZG"
    async with market.client(WORLD_BANK_URL) as client:
        reply = await read(
            client,
            "GET",
            path,
            code_for=partial(refusal_code, "world_bank"),
            params={
                "format": "json",
                "date": f"{arguments.start_year}:{arguments.end_year}",
                "per_page": 200,
            },
        )
    try:
        body = _Indicator.model_validate_json(reply.content).root
    except ValueError:
        raise ToolFailed(MALFORMED) from None
    found: dict[str, list[InflationRow]] = {country: [] for country in arguments.countries}
    for row in _observations(body):
        if row.countryiso3code in found and row.date.isdigit():
            found[row.countryiso3code].append(
                InflationRow(year=int(row.date), inflation_pct=row.value)
            )
    return InflationOutput(
        countries=[
            CountryInflation(
                country=country,
                name=NAMES[country],
                rows=sorted(found[country], key=lambda row: row.year),
            )
            for country in arguments.countries
        ],
        source=WORLD_BANK_SOURCE,
        retrieved_at=market.now(),
    )


class _MarketTraits(TypedDict):
    """What the two market tools share. Typed, so each definition is checked field by field."""

    version: int
    operation_class: OperationClass
    timeout_seconds: float
    retries: int
    max_output_bytes: int
    group: ToolGroup
    network: bool
    cost_class: CostClass


_MARKET = _MarketTraits(
    version=1,
    operation_class=OperationClass.READ_ONLY,
    timeout_seconds=TIMEOUT_SECONDS,
    retries=0,
    max_output_bytes=500_000,
    group=ToolGroup.MARKET_DATA,
    network=True,
    cost_class=CostClass.METERED_PROVIDER,
)


def market_tools(
    transport: httpx.AsyncBaseTransport | None = None, now: Callable[[], str] = _now
) -> tuple[ToolDefinition, ToolDefinition]:
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
            **_MARKET,
        ),
        ToolDefinition(
            tool_id="inflation_rates",
            title="Inflation rates",
            description=(
                "Annual consumer price inflation, in percent, for Costa Rica (CRI), the USA (USA) "
                "and the euro area (EMU), from the World Bank, over at most 31 years."
            ),
            input_model=InflationInput,
            output_model=InflationOutput,
            handler=partial(inflation, market),
            provider=ToolProvider.WORLD_BANK,
            cost_note="No charge; counts as a metered call.",
            public_input_fields=("countries", "start_year", "end_year"),
            public_output_fields=("indicator", "source", "retrieved_at"),
            **_MARKET,
        ),
    )


MARKET_TOOLS = market_tools()
