# Verification — us-14-10-market-history-inflation-rates

Change: us-14-10-market-history-inflation-rates
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 4/4 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed against fake transports, as stated; the metering also on a disposable stack |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Price history from a fake chart endpoint | PASS | `services/agent/tests/test_market_data.py`: `BTC-USD` and `CRC=X` over `1mo` and `1d` return rows dated 2025-11-01 onward; closes 100, 110, none, 99 give changes none, 10.0, none, −10.0 (a missing close is skipped, not zeroed), and 512 to 506.88 colones gives −1.0%; currencies USD and CRC; the source says "unofficial" and `retrieved_at` is set; both requests carry `range=1mo` and `interval=1d`. Lowercase, spaced, six, duplicate and path-like symbols, `10y` and `1m` are refused `invalid_arguments` through the gateway with no request |
| Typed failures and no crosses | PASS | Same tests: a 404, an empty result, a 503 and a 429 for `EURCRC=X` fail `symbol_not_found`, `symbol_not_found`, `provider_unavailable` and `rate_limited`; when `EURCRC=X` isn't served, only that symbol was requested, so no `EURUSD=X` or `CRC=X` was fetched to build a cross |
| Annual inflation from a fake World Bank transport | PASS | `test_market_data.py`: CRI and USA for 2023 to 2024 return rows sorted by year (CRI 0.53, 0.84; USA none, 2.95) with `FP.CPI.TOTL.ZG` and the World Bank source, from `/v2/country/CRI;USA/indicator/FP.CPI.TOTL.ZG`; `MEX`, a reversed range, a 65-year range and a repeated country are refused first. `tests/db/web_tools_check.py` in the `db` profile: after 19 `market_history` calls, `inflation_rates` for EMU succeeds as the 20th metered call (2024, 2.36, Euro area); the next is denied `tool_budget_exceeded` and `MEX` `invalid_arguments`, with exactly 20 requests sent; its record lists countries and years, the indicator and source, and not the value |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the market cases, `identity_qualification`, `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed |
| `openspec validate us-14-10-market-history-inflation-rates` | 0 | valid |

## Limits

- **No live call to Yahoo or the World Bank was made.** The fixtures follow each provider's documented reply shape. Yahoo's endpoint is unofficial and can change or require a cookie without notice; whether `EURCRC=X` is served is unconfirmed (Decision 0017 Q6).
- Inflation is annual, and the World Bank publishes with a lag, so the latest year may be missing.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
