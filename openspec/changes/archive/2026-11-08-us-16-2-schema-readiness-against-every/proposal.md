## Why

US-16.2 implements [Decision 0023 E2](../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#decision). Readiness checks a hand-kept list of relations and columns that stops at migration 37, and Operations shows the applied-migration count without comparing it to anything. The persistent install was at 35 of 49 and read ready.

## What Changes

- **`autobots.application.schema_release`** records the count and newest name of the migrations this release ships. A harness test fails unless both match `supabase/migrations`.
- **Readiness** reads the applied count through `app_private.applied_migration_count()`, when that function exists:
  - fewer than shipped is `schema_behind` (unavailable, blocking, as before);
  - more than shipped is `schema_ahead` (degraded), which doesn't stop admission;
  - equal, or no readable history, falls back to the required objects.
- **The required relations and columns** gain what migrations 38 to 49 add, for a database without a readable history.
- **Operations** shows "N of M migrations applied", and words for `schema_ahead`. `OperationValues` gains `shipped_migrations`, and the TypeScript client is regenerated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `operations-status`: schema readiness against shipped migrations.

## Impact

- `services/agent/src/autobots/application/{operations,schema_release}.py`, `contracts/operations.py`, `api/operation_routes.py`; the generated contract and client.
- `apps/web/components/operations-panel.tsx`.
- Tests: `services/agent/tests/test_schema_release.py`, `tests/harness/test_app_db.py`, and a disposable-stack check, `tests/db/schema_release_check.py`, registered in `qualify_identity.py`.
