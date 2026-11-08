# Tasks

## 1. API (Catalog facts; Where each binding comes from; Discard and Reset all)

- [x] 1.1 Record each role's binding source in `resolve_role_policy`, the effective policy and the frozen run snapshot, and show it in the run's role map
- [x] 1.2 Allow a policy with no workspace default (migration, `default_profile: null`), and report `null` with no saved policy
- [x] 1.3 Add catalog prices per 1M tokens, capabilities and `fetched_at` to `/v1/models`
- [x] 1.4 Add `POST /v1/settings/model-policy/reset` under the expected version, then regenerate the contract and client

## 2. Web and coverage

- [x] 2.1 Render the facts, sources, Built-in default, Discard, Reset all and the summary on Models, and the source in the run's role map
- [x] 2.2 Cover sources in unit tests, and the three scenarios in a browser spec with axe, against a fake catalog with prices and an arranged run on a disposable stack
