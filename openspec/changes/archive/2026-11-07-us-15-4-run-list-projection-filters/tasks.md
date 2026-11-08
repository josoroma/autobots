# Tasks

## 1. Projection and API (One row per run with its facts; Status tabs with server counts; Text and profile filters with keyset paging)

- [x] 1.1 Extend `RunListItem` and `RunList` with labels, stop reason, progress, profiles, ledger spend, counts, total and cursor
- [x] 1.2 Rewrite `read_run_list` as one keyset query with group, text and profile filters, and refuse foreign cursors
- [x] 1.3 Add the query parameters to `GET /v1/runs` and regenerate the contract and client
- [x] 1.4 Cover the projection on a disposable stack in `tests/db/run_list_check.py`, run by `scripts/app_db.py`

## 2. Web (Status tabs with server counts; Estimated spend is marked; Text and profile filters with keyset paging)

- [x] 2.1 Render the tabs with counts, text and model filters, row labels, state with stop reason or progress, models, spend with "≈" and a meter, and Load more
- [x] 2.3 Send no query string when every filter is at its default, so the plain list URL stays as the error and loading states expect (found by `slice-visual`)
- [x] 2.4 Mark the selected tab with a border, not a shadow, so its focus ring keeps 3:1 in light (found by `slice-visual`)
- [x] 2.2 Cover the screen in `runs.spec.ts` with axe, against an arranged workspace of 101 runs with held, unreported and reported spend
