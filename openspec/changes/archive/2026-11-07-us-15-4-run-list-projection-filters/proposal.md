## Why

US-15.4, [PRD-Studio RN-01 to RN-03](../../../../docs/PRD/PRD-Studio.md#runs) and [Decision 0022 D9](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). The run list returns only ID, parent, status, goal and created time, capped at 100 rows with no filters, counts or paging. Studio's Runs needs each run's facts, status groups with server counts, filters and keyset paging.

## What Changes

- `RunListItem` gains: updated time, a label (goal, Expert, coordinator session, or workflow with version), `stop_reason`, tasks complete of total from the latest plan, the frozen profiles, ledger spend (charged, outstanding reservations, an unreported flag) and the frozen limit.
- `GET /v1/runs` takes `group` (`all`, `active`, `needs_you`, `finished`), `q` (goal or Expert or workflow name, case-insensitive, with wildcards escaped), `profile`, `cursor` and `limit`. It returns counts per group under the same filters, the selected group's total, and a keyset `next_cursor`. A cursor the API didn't issue is refused with `422 invalid_cursor`.
- Groups follow D9. Active is queued, running, verifying, paused and cancelling. Needs you is `waiting_approval` and `waiting_input`. Finished is succeeded, failed and cancelled.
- Runs renders the tabs with counts, a text filter, a model filter, row labels, state with stop reason or progress, models, spend with "≈" while estimated and a meter with its words, and Load more.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `run-workspace`: the run list projection, filters and paging.

## Impact

- `contracts/run_workspace.py`, `application/run_projection.py` and `api/event_routes.py`.
- The generated contract and client.
- `apps/web/components/run-list.tsx`.
- Tests: `tests/db/run_list_check.py`, run from `scripts/app_db.py`; an arranged user in `scripts/qualify_identity.py`; and `runs.spec.ts`.
