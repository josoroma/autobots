# Tasks

## 1. API (Budget choices; A budget outside the range is refused; Preview)

- [x] 1.1 Add the D11 budget rules, the remaining daily cap, `RunIntentCheck.budget` and `GET /v1/run-preview` (profiles by role and granted tools), then regenerate the contract and client
- [x] 1.2 Validate and freeze `budget_micro_usd` at admission with typed refusals, and raise the ledger's per-run ceiling to US$5.00 so a chosen budget isn't cut
- [x] 1.3 Forward intent, preview and budget through the BFF (the existing `/api/v1/[...path]` and `/api/settings/[...path]` routes carry them)

## 2. Web and coverage (all scenarios)

- [x] 2.1 Add the Model, Expert and Budget chips, the preview chips and the file chips to Home's composer, with Run starting a direct session first for an Expert
- [x] 2.2 Cover the budget rules in unit tests and the five scenarios in `composer.spec.ts` with axe, on a disposable stack with a fake transport
