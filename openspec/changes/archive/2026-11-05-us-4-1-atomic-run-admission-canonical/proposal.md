## Why

Retries and conflicting commands must not corrupt lifecycle state, and SP-010 and SP-014 require typed admission with an idempotency key, atomic run, job and event creation, and version and actor guards on every transition.

## What Changes

- A migration: run `version`, goal text and frozen policy snapshot, `app_private.run_jobs`, and `app_private.idempotency_receipts`.
- `domain/runs.py`: commands, actors and SP-010 sources, with terminal states closed and repeated cancellation idempotent.
- `application/runs.py`: `admit_run` and `apply_command`, each a single transaction with its event. Keys are scoped by workspace, actor, operation and target, and concurrent duplicates serialize.
- `POST /v1/runs` returns 202, plus `GET /v1/runs/{id}` and input, pause, resume and cancel commands. The composer's Run now admits through them, with one key per press.

**Limits:** no worker claims a job yet, so a queued run waits, and no model is called. `run_events` serves as the transactional outbox until US-4.6 builds projection. The approval route belongs to US-5.3; its command exists and is tested. The workspace's credential gate is checked before admission.

## Capabilities

### New Capabilities

- `run-admission`: exactly-once logical admission and guarded lifecycle transitions.

### Modified Capabilities

None.

## Impact

A migration, domain, application, API and contract modules, the composer, regenerated client and row types, fixtures, `scripts/app_db.py`, `scripts/qualify_identity.py` and `CODEBASE.md`. No dependency or model call.
