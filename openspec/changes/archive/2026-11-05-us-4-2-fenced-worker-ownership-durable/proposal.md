## Why

A restarted or stale worker must not write conflicting progress. SP-012 requires leases by database time, a rising generation, and enforced ownership of both product and checkpoint writes, shown by a stale worker that tries both.

## What Changes

- A migration owns the pinned adapter's checkpoint tables, so a worker never runs setup, and triggers refuse a checkpoint write unless its connection carries the current generation of a live lease.
- `application/worker_leases.py`: `claim_next` and `heartbeat`, all by database time.
- `adapters/checkpoints.py`: a fenced checkpointer on a direct connection with `agent_runtime` on its search path, and `durability="sync"`.
- `apply_command` now requires the current generation for worker commands, under the job's row lock, and derives active work from the lease.

**Limits:** no worker loop yet, so nothing claims a job in the running product. Exactly-once remote effects are not claimed. The connection's generation is a setting the runtime role can change, so this stops stale workers, not hostile code running as that role. Mac sleep, attempt limits, the reconciliation of model slots held by a dead worker, and operation receipts (US-4.4, US-4.7) are not covered.

## Capabilities

### New Capabilities

- `worker-ownership`: fenced product and checkpoint writes, and recovery from a saved checkpoint.

### Modified Capabilities

None.

## Impact

A migration, `application/runs.py`, new modules and DB checks, `scripts/app_db.py`, `CODEBASE.md`. No dependency or model call.
