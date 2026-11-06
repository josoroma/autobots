## Why

US-10.2's finding B2: recovery after Mac sleep has only been stood in for by SIGSTOP. Decision 0009 has the owner sleep this Mac during a run, following a written procedure, and has wake handling built only if that test shows it's needed. The owner said "I'm ready now" on 2026-11-06, which settled this story's `External:` dependency.

## What Changes

- A written procedure, `docs/engineering/runbooks/mac-sleep.md`, and a harness that arranges a disposable stack with a scripted model, watches a real sleep, and assesses it.
- The first real sleep found two failures, so wake handling is built: a worker that detects a real sleep from its own clocks takes back a lease that expired with nobody claiming it, and doesn't count that time as active.
- The owner sleeps this Mac a second time under the same procedure, to show the failure is gone.

## Capabilities

### New Capabilities

- `mac-sleep-recovery`: what's observed across a real Mac sleep, how it's assessed, and what a worker does on waking.

### Modified Capabilities

None.

## Impact

`application/worker_leases.py`, `application/goal_loop.py`, `application/run_usage.py`, a new runbook, `scripts/qualify_mac_sleep.py`, `tests/db/sleep_inference_worker.py`, `tests/db/wake_check.py` and tests. No schema change and no paid call. A stall with no sleep, such as SIGSTOP, behaves as before.
