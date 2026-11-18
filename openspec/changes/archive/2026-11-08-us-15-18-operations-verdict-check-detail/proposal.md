## Why

US-15.18 implements [PRD-Studio OP-01, OP-02 and OP-04](../../../../docs/PRD/PRD-Studio.md#operations), within [Decision 0022 D5](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision) and [Decision 0013, amended](../../../docs/engineering/decisions/0013-release-closure.md#amended). Operations shows each check's state and message. It doesn't count how many checks pass or how many workers are live, and it shows none of the measured values D5 allows.

## What Changes

- **Probe times:** each readiness probe that reaches the database records its answer time in a 20-probe window, kept in the API process. A probe that finds no database records nothing. There is no tracing or persistence, and nothing is sent anywhere.
- **New values on `LocalStatus`:** an `OperationValues` object holding exactly D5's list:
  - `database_p95_ms` (nearest rank) and `database_probes`;
  - `applied_migrations`;
  - `storage_bytes`, the workspace's published artifact bytes;
  - `disk_free_bytes` and `disk_total_bytes`;
  - `leased_jobs` and `queued_jobs`;
  - `checkpoint_adapter`, the package and its release;
  - `catalog_fetch_ms`, how long this load's catalog check took;
  - `loopback_only`, whether every TCP socket the API listens on is bound to loopback;
  - `workers`, the live heartbeats.

  OpenAPI and the TypeScript client are regenerated.
- **A migration adds `app_private.applied_migration_count()`.** It is security-definer and returns the count of migration files in the install's or the disposable target's history, and nothing of the rows. Only the runtime role may call it.
- **Operations shows:**
  - under the readiness sentence: "N of M checks pass", the worker count and the hold state, all from the checks shown;
  - in each check's card, its value;
  - the catalog time on the OpenRouter line;
  - a new Network line for the loopback check.

  The adapter appears as "LangGraph checkpoint adapter <release>", because the package's name also names the database. The existing sections stay.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `operations-status`: the verdict and the D5 values.

## Impact

- `application/operations.py`, `api/operation_routes.py`, `contracts/operations.py` and a migration.
- The generated contract and client, and `operations-panel.tsx`.
- New `test_operation_values.py`, a stub signature in `test_readiness.py`, and new `app_db.py` cases.
- The `ops-n` arrangement in `qualify_identity.py`, the new `tests/db/operations_live.py`, and the new `operations-values.spec.ts`.
