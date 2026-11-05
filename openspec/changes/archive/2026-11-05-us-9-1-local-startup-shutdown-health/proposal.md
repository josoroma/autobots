## Why

US-9.1 needs supported start, drain and stop, visible readiness and logs, and retention that never removes a required receipt. Nothing enforced tracing-off, and no worker process existed outside fixtures.

## What Changes

- `python -m autobots.operations.worker`: heartbeat, SIGTERM drain with a bound, reconnects. It runs maintenance only and claims no job, because no model client is qualified (US-3.4). It says so in its heartbeat.
- `GET /v1/operations/local-status`, usable with the database down. Admission returns 503 `not_ready` when database, schema, Storage or disk isn't ready.
- JSON logs with redaction, and inherited tracing settings turned off at bootstrap of API and worker.
- Per-workspace retention, default keep everything. Purge is a security-definer function, and refuses active trees, unresolved effects, open obligations and other workspaces. Run records, events and tool receipts stay.
- Local Operations page and the operations runbook, exercised by `scripts/qualify_operations.py` on a disposable stack.

## Capabilities

### New Capabilities

- `local-operations`: lifecycle, readiness, safe logs and retention.

### Modified Capabilities

None.

## Impact

Migration `20261105000023_operations.sql`, `services/agent` (operations, retention, routes, admission gate), generated contracts, `apps/web` Operations page, `docs/engineering/runbooks/operations.md`, `scripts/qualify_operations.py`.
