# Tasks

## 1. US-20.3

- [x] 1.1 Turn browser-use's highlights off on stealth only (Z11). Checked by pytest under `services/agent/tests` and by `scripts/qualify_browser_executor.py` on a disposable stack.
- [x] 1.2 Read each step's presses and typing from an isolated world the page can't see: up to ten elements by action, kind and label, never the typed value (Z11). Checked by pytest under `services/agent/tests` with a planted value, and by `scripts/qualify_browser_executor.py` on a disposable stack.
- [x] 1.3 Add what each step pressed or typed into to `app_private.browse_steps` in a migration with its traceability header and its Locks, Data and Recovery lines. Earlier rows read as none, and writes stay fenced (TU-02). Checked by `tests/harness/test_migration_headers.py` and the db profile's disposable fixtures (`browse_steps_check`).
- [x] 1.4 Add it to the steps' contract, regenerate OpenAPI and the TypeScript client, and show it in the run's tool row. Checked by `contract_drift` in the fast profile, the web unit tests under `apps/web/tests/unit` and the run workspace browser suite under `apps/web/tests/browser`, with axe.
- [x] 1.5 On stealth, keep steps at least 2 seconds apart on both engines, and run one browse of a site at a time across the install. A second waits within its own time limit or ends `max_seconds`, and a site is free again when its browse ends, is cancelled or loses its lease (Z12, BX-04). Checked by pytest under `services/agent/tests` and the db profile's disposable fixtures with scripted browses.
- [x] 1.6 Add these to the stealth browser's required cases, and qualify again what the changed files bind. Checked by `scripts/qualify_browser_executor.py` on disposable stacks, reaching only the qualification hosts.
- [x] 1.7 Amend PRD-Tool-Catalog AB-01, and PRD-Studio for the run's tool row, as Decision 0038's "Requirements revised" lists. Update the operations runbook, `README-DEV.md` and `CODEBASE.md`. Checked by reading each against Z11 and Z12.
