## Why

Late responses must not undo a cancellation or bypass a wait. SP-010, SP-012 and MP-08 require cancellation from every nonterminal state, resume that keeps obligations and bindings, and reconciliation before another paid dispatch.

## What Changes

- `apply_command` enters `cancelling` while work is unsettled, even with no live owner, and records obligations that outlive a pause.
- `application/recovery.py`: classifies a dead owner's calls and effects. `run_goal` checks obligations, uncertain calls and the frozen policy before any dispatch, renews its lease, and settles a cancellation.
- `POST /runs/{id}/input` carries a value, resume checks readiness, `continues_run_id` links a new run to a finished one, and an owner can record a charge with `POST /runs/{id}/model-calls/reconcile`.

**Limits:** no process runs `process_next` yet, and there's no UI for reconciliation. Children don't exist, so cancellation doesn't propagate to any. Real wake detection isn't built, so a stopped process stands in for sleep.

## Capabilities

### New Capabilities

- `run-recovery`: monotonic cancellation, obligation-preserving resume and reconciled recovery.

### Modified Capabilities

None.

## Impact

A migration, `application/runs.py`, `goal_loop.py`, `loop_middleware.py`, new routes and contracts, DB and browser tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or paid call.
