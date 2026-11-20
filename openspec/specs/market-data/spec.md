# market-data Specification

## Purpose
TBD - created by archiving change us-14-10-market-history-inflation-rates. Update Purpose after archive.

## Requirements

### Requirement: Price history is dated, sourced and bounded

`market_history` SHALL return, for up to 5 valid symbols, dated rows with a close-to-close percent change whose first row is null, the currency, a source named as unofficial and the time it was read. Invalid symbols or values outside the allowed sets SHALL be refused before any request.

#### Scenario: Price history from a fake chart endpoint
- **GIVEN** a granted market_history tool and a fake transport
- **WHEN** it is called with up to 5 symbols matching the pattern, an allowed period and interval
- **THEN** each symbol returns dated rows with close-to-close pct_change whose first row is null, its currency, a source named as unofficial and retrieved_at, and invalid symbols or values outside the allowed sets are refused before any request

### Requirement: Market failures are typed and no crosses are computed

`market_history` SHALL fail as `symbol_not_found`, `provider_unavailable` or `rate_limited`, and SHALL NOT compute a cross rate.

#### Scenario: Typed failures and no crosses
- **GIVEN** a fake transport that reports an unknown symbol, an outage or a rate limit
- **WHEN** market_history is called
- **THEN** it fails as symbol_not_found, provider_unavailable or rate_limited, and computes no cross rate
