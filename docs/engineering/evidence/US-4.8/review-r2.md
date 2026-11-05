# US-4.8 independent review, round 2

The same reviewer re-read its findings against the fixes, read-only, and ran nothing.

## Findings from round 1

| # | Verdict | What remains |
|---|---|---|
| 1, 2, 3, 6, 8, 9, 10, 11 | Fixed | |
| 7 | Fixed | Artifacts match by file name, so `outputs/a/report.md` and `outputs/b/report.md` collide. Left as a limit |
| 4 | Partly fixed | Any published file still reaches `succeeded` when a goal states no requirement, and evidence can cite any saved file. The page says the content wasn't judged. Left for your decision |
| 5 | Partly fixed | `reconcile_run` wrote without a lease check, so a stale verifier could append events to a finished run. Now fixed, below |
| `credential_version` | Not fixed | No real credential path reaches the loop yet |

## New defects my fixes introduced, now changed

| Severity | Finding | Change |
|---|---|---|
| Major | A pause abandoned a healthy model call, marked it uncertain, and blocked resume until an owner reconciled | Only a cancel interrupts a call. A paused owner finishes the call, saves its step and lets go. A worker that lost its lease still waits for the reply, since it's the only evidence of the charge |
| Major | An unknown tool effect made success impossible, even when it was a checkable internal row, and a refused write was recorded as unknown | A refused write is recorded as failed. `save_artifact` and `complete_task` are safe to finish on replay, and `propose_plan` recognizes a plan that committed |
| Minor | The verification check ran twice | Removed |
| Minor | `Retry-After` accepted `inf` and `nan` | Refused |

A consequential effect left unknown still has no way to be resolved, so its run can only fail. That reconciliation is US-5.4.

No third review round ran on these last changes. They have tests in `tests/db/verification_check.py` and `tests/db/worker_ownership_check.py`.
