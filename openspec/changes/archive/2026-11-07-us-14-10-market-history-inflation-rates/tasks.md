# Tasks

## 1. Adapters (all three scenarios)

- [x] 1.1 Add `market_history` over Yahoo's chart endpoint and `inflation_rates` over the World Bank API, plain `httpx`, read-only, metered, keyless
- [x] 1.2 Register them in the loop, the execution contract and the Expert-grantable set

## 2. Observe

- [x] 2.1 Cover rows, percent change, refusals, typed failures and no crosses with fake transports in the providers' reply shapes
- [x] 2.2 Cover inflation as the 20th metered call and the 21st denied on a disposable stack
