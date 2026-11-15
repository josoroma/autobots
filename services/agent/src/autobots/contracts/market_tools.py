"""Inputs and outputs of the market data tools, PRD-Tool-Catalog "Market data" and Decision 0017
C11, Q5 and Q6. Every output names its source and when it was read."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from autobots.contracts.primitives import TOOL_CONTRACT
from autobots.contracts.tool_fields import Symbol


class MarketHistoryInput(BaseModel):
    model_config = TOOL_CONTRACT

    symbols: list[Symbol] = Field(min_length=1, max_length=5)
    period: Literal["5d", "1mo", "3mo", "6mo", "1y"] = "1mo"
    interval: Literal["1d", "1wk"] = "1d"

    @model_validator(mode="after")
    def _symbols(self) -> "MarketHistoryInput":
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("each symbol once")
        return self


class PriceRow(BaseModel):
    model_config = TOOL_CONTRACT

    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    pct_change: float | None


class SymbolHistory(BaseModel):
    model_config = TOOL_CONTRACT

    symbol: str
    currency: str | None
    rows: list[PriceRow]


class MarketHistoryOutput(BaseModel):
    model_config = TOOL_CONTRACT

    histories: list[SymbolHistory]
    source: str
    # Text, as v1's output schema states it (Decision 0029 F13).
    retrieved_at: str
    symbol_count: int


Country = Literal["CRI", "USA", "EMU"]


class InflationInput(BaseModel):
    model_config = TOOL_CONTRACT

    countries: list[Country] = Field(min_length=1, max_length=3)
    start_year: int = Field(ge=1960, le=2100)
    end_year: int = Field(ge=1960, le=2100)

    @model_validator(mode="after")
    def _range(self) -> "InflationInput":
        if self.end_year < self.start_year:
            raise ValueError("end_year comes after start_year")
        if self.end_year - self.start_year > 30:
            raise ValueError("at most 31 years")
        if len(set(self.countries)) != len(self.countries):
            raise ValueError("each country once")
        return self


class InflationRow(BaseModel):
    model_config = TOOL_CONTRACT

    year: int
    inflation_pct: float | None


class CountryInflation(BaseModel):
    model_config = TOOL_CONTRACT

    country: Country
    name: str
    rows: list[InflationRow]


class InflationOutput(BaseModel):
    model_config = TOOL_CONTRACT

    countries: list[CountryInflation]
    indicator: Literal["FP.CPI.TOTL.ZG"] = "FP.CPI.TOTL.ZG"
    source: str
    # Text, as v1's output schema states it (Decision 0029 F13).
    retrieved_at: str
