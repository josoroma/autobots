## Why

US-14.10, [PRD-Tool-Catalog "Market data"](../../../../docs/PRD/PRD-Tool-Catalog.md#market-data) and Decision 0017 C11, C12, Q5, Q6 and Q7: the request asked for crypto and colón exchange history with daily percent change, and inflation for Costa Rica, the USA and Europe.

## What Changes

- `market_history`: up to 5 Yahoo Finance symbols (`^[A-Z0-9.^=-]{1,20}$`, e.g. `BTC-USD`, `ETH-USD`, `CRC=X`, `EURCRC=X`), period `5d` to `1y`, interval `1d` or `1wk`, from the chart endpoint yfinance reads, called directly over `httpx`, so no `yfinance` or `pandas`. Each symbol returns dated rows with open, high, low, close, volume and a close-to-close `pct_change` (first row null), its currency, the source named as unofficial with no SLA, and `retrieved_at`. Failures are `symbol_not_found`, `provider_unavailable` or `rate_limited`, and no cross rate is computed.
- `inflation_rates`: `CRI`, `USA` and `EMU` only, over at most 31 years, from the World Bank's `FP.CPI.TOTL.ZG` (annual %), returning rows by country with the indicator and source.
- Both are read-only, need no key, and are metered: they count against the run tree's 20 metered calls. They join the loop, the execution contract and the Expert-grantable set, in the market data group.

## Capabilities

### New Capabilities

- `market-data`: price history and inflation.

### Modified Capabilities

None.

## Impact

`adapters/market_data.py`, `contracts/market_tools.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, `tests/test_market_data.py` and `tests/db/web_tools_check.py`. No package added; no live call made.
