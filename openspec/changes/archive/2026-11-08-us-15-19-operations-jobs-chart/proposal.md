## Why

US-15.19 implements [PRD-Studio OP-03](../../../../docs/PRD/PRD-Studio.md#operations), with [Decision 0022 D5 and D14](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision) and DS-04. Operations doesn't say how much work ran recently or how it ended.

## What Changes

- **`GET /v1/operations/jobs`** (owner only) returns the workspace's timezone and 24 hours, oldest first. Each hour holds its UTC start, its `HH:00` label in that timezone, and four counts:
  - `succeeded`;
  - `waited`: the run entered `waiting_approval` or `waiting_input`;
  - `failed`: failed or cancelled;
  - `in_progress`: a run now running or paused, counted in the hour of its latest change.

  The counts come from the runs' own `run.status_changed` events. There is no identifier and no goal text. OpenAPI and the TypeScript client are regenerated.
- **Operations shows a stacked bar chart:**
  - **Colors:** each outcome wears its status token (success-text, attention, live-text, destructive), stacked in the order that keeps neighbors furthest apart.
  - **Textures:** waited and failed also carry 45° and 135° textures.
  - **Legend:** with totals.
  - **Hover:** a tooltip per hour.
  - **Table:** a disclosed table of the same counts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `operations-status`: the jobs chart.

## Impact

- `application/operations.py`, `api/operation_routes.py` and `contracts/operations.py`.
- The generated contract and client.
- New `jobs-chart.tsx`, and `operations-panel.tsx`.
- `test_operation_values.py`, the path list in `test_app_factory.py`, the `ops-n` timezone in `qualify_identity.py`, a `jobs` action in `tests/db/operations_live.py`, and the new `operations-jobs.spec.ts`.
