## Why

US-10.1 needs measured end-to-end outcomes. A live corpus run already met the protocol, task and safety targets, but [its evidence](../../../../docs/engineering/evidence/US-10.1/summary.md) names what it left open: an event's time to appear in the UI, CPU, disk and connection use during the workload, and recovery timed only by inference from the heartbeat.

## What Changes

- Keep the held-out result as measured: 99 of 100 protocol cases and 104 of 120 goals. No re-run, rescoring or tuning, and the corpus's hash stays the same.
- Extend `scripts/qualify_release.py` to sample CPU, memory, disk and connections while goals run, to probe the UI and API for stability, to read the lease expiry of a killed worker so recovery is measured from it, and to take its spending cap as an explicit argument, since the US$5 go-ahead belonged to the earlier run.
- A browser spec that times a committed event until the real UI shows it, through the real API and Next.js.
- One paid run under the user's US$1 cap, on the development tasks in `tests/qualification/dev_tasks.json`, so no held-out task is touched.
- Publish the results, and record the user's decisions: the plan-rejection margin and an assistant-written corpus are both accepted as published limitations.

## Capabilities

### New Capabilities

- `release-qualification`: measuring and publishing the scoped release corpus and local responsiveness.

### Modified Capabilities

None.

## Impact

`scripts/qualify_release.py`, `scripts/release_scoring.py`, `tests/harness/test_release_qualification.py`, `apps/web/tests/browser/release-latency.spec.ts`, `docs/engineering/evidence/US-10.1/summary.md`, a new decision record and `CODEBASE.md`. No product behavior changes. Billed OpenRouter calls happen only in the one authorized run.
