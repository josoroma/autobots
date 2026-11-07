"""Market history and inflation, US-14.10 and Decision 0017 C11, C12, Q5 and Q6.

Prices come from Yahoo Finance's chart endpoint, the one yfinance itself reads, called directly
over `httpx` so no `pandas` comes with it (C12). It is unofficial, for a single owner's personal
use, with no SLA, and every output says so (C11). Inflation comes from the World Bank Indicators
API, `FP.CPI.TOTL.ZG`, annual, for Costa Rica, the USA and the euro area (Q5). Neither needs a key,
and both count as metered calls because they leave this Mac (TU-06). No cross rate is computed: a
symbol Yahoo doesn't serve fails `symbol_not_found` (Q6). Tests use fake transports (C5).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from autobots.adapters.provider_http import failure_for, provider_client
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


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _number(values: list[Any], index: int) -> float | None:
    value = values[index] if index < len(values) else None
    return float(value) if isinstance(value, int | float) else None


def _rows(result: dict[str, Any]) -> list[PriceRow]:
    stamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
    series = {name: quote.get(name) or [] for name in ("open", "high", "low", "close", "volume")}
    rows: list[PriceRow] = []
    previous: float | None = None
    for index, stamp in enumerate(stamps):
        close = _number(series["close"], index)
        change = (
            round((close - previous) / previous * 100, 6)
            if close is not None and previous not in (None, 0.0)
            else None
        )
        rows.append(
            PriceRow(
                date=datetime.fromtimestamp(int(stamp), UTC).date().isoformat(),
                open=_number(series["open"], index),
                high=_number(series["high"], index),
                low=_number(series["low"], index),
                close=close,
                volume=_number(series["volume"], index),
                pct_change=change,
            )
        )
        if close is not None:
            previous = close
    return rows


def market_tools(
    transport: httpx.AsyncBaseTransport | None = None, now: Callable[[], str] = _now
) -> tuple[ToolDefinition, ToolDefinition]:
    async def history(arguments: MarketHistoryInput, _: ToolContext) -> MarketHistoryOutput:
        histories = []
        async with provider_client(YAHOO_URL, HEADERS, transport) as client:
            for symbol in arguments.symbols:
                try:
                    reply = await client.get(
                        f"/v8/finance/chart/{symbol}",
                        params={"range": arguments.period, "interval": arguments.interval},
                    )
                except httpx.HTTPError:
                    raise ToolFailed("provider_unavailable") from None
                if reply.status_code == 404:
                    raise ToolFailed("symbol_not_found")
                if reply.status_code != 200:
                    raise failure_for("yahoo_finance", reply.status_code)
                try:
                    chart = reply.json().get("chart") or {}
                except (ValueError, AttributeError):
                    raise ToolFailed("provider_reply_malformed") from None
                results = chart.get("result") or []
                if not results:
                    raise ToolFailed("symbol_not_found")
                result = results[0]
                meta = result.get("meta") or {}
                histories.append(
                    SymbolHistory(
                        symbol=symbol,
                        currency=meta.get("currency"),
                        rows=_rows(result),
                    )
                )
        return MarketHistoryOutput(
            histories=histories,
            source=YAHOO_SOURCE,
            retrieved_at=now(),
            symbol_count=len(histories),
        )

    async def inflation(arguments: InflationInput, _: ToolContext) -> InflationOutput:
        path = f"/v2/country/{';'.join(arguments.countries)}/indicator/FP.CPI.TOTL.ZG"
        async with provider_client(WORLD_BANK_URL, HEADERS, transport) as client:
            try:
                reply = await client.get(
                    path,
                    params={
                        "format": "json",
                        "date": f"{arguments.start_year}:{arguments.end_year}",
                        "per_page": 200,
                    },
                )
            except httpx.HTTPError:
                raise ToolFailed("provider_unavailable") from None
        if reply.status_code != 200:
            raise failure_for("world_bank", reply.status_code)
        try:
            body = reply.json()
        except ValueError:
            raise ToolFailed("provider_reply_malformed") from None
        if not isinstance(body, list) or len(body) < 2 or not isinstance(body[1], list):
            raise ToolFailed(
                "provider_refused_400" if isinstance(body, list) else "provider_reply_malformed"
            )
        found: dict[str, list[InflationRow]] = {country: [] for country in arguments.countries}
        for item in body[1]:
            code = item.get("countryiso3code") if isinstance(item, dict) else None
            if code in found and str(item.get("date", "")).isdigit():
                value = item.get("value")
                found[code].append(
                    InflationRow(
                        year=int(item["date"]),
                        inflation_pct=float(value) if isinstance(value, int | float) else None,
                    )
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
            retrieved_at=now(),
        )

    common: dict[str, Any] = {
        "version": 1,
        "operation_class": OperationClass.READ_ONLY,
        "timeout_seconds": 30.0,
        "retries": 0,
        "max_output_bytes": 500_000,
        "group": ToolGroup.MARKET_DATA,
        "network": True,
        "cost_class": CostClass.METERED_PROVIDER,
    }
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
            handler=history,
            provider=ToolProvider.YAHOO_FINANCE,
            cost_note="No charge, but unofficial and rate limited; counts as a metered call.",
            public_input_fields=("symbols", "period", "interval"),
            public_output_fields=("source", "retrieved_at", "symbol_count"),
            **common,
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
            handler=inflation,
            provider=ToolProvider.WORLD_BANK,
            cost_note="No charge; counts as a metered call.",
            public_input_fields=("countries", "start_year", "end_year"),
            public_output_fields=("indicator", "source", "retrieved_at"),
            **common,
        ),
    )


MARKET_TOOLS = market_tools()
