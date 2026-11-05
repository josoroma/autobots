## Why

A successful result must refer to bytes that actually exist. SP-013 and LM-05 require staged private uploads, hash verification and reconciliation, because a database commit and an upload are not atomic.

## What Changes

- `public.artifacts` with RLS and a storage path members can't read, and `runs.event_sequence`, so an event sequence no longer follows the run version.
- `application/artifacts.py`: publish, reconcile, list and read. `publish_artifact` tool reads the run's own saved file.
- `adapters/object_storage.py` over the Storage API, refusing unscoped paths.
- `GET /v1/runs/{id}/artifacts` and a binary download route without a generated client.

**Limits:** no UI, which US-4.6 builds. Retention isn't built. Reconciliation is a function nothing schedules yet, which belongs with US-4.7's recovery. The size cap and allowed types are my choice.

## Capabilities

### New Capabilities

- `private-artifacts`: staged publication, verified downloads and reconciliation.

### Modified Capabilities

None.

## Impact

A migration, new modules and routes, `RunEvent` payload union, regenerated contracts and row types, `scripts/qualify_identity.py`, `scripts/app_db.py`, BFF header pass-through, `CODEBASE.md`. No new dependency or model call.
