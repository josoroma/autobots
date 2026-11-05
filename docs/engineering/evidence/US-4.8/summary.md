# US-4.8 first durable slice

Base revision `c91ef48`, working tree with this change, 2026-11-05. Reproduce with the [first slice runbook](../../runbooks/first-slice.md):

```sh
python3.12 scripts/qualify_identity.py
```

A disposable Supabase stack with real Postgres, Auth and Storage, the real API and web app in Chromium, and a real worker process. The model is scripted, and a fake upstream answers key validation. No paid call, and no real credential.

## Complete the mocked vertical slice

| Step | Observed |
|---|---|
| Admitted | `POST /v1/runs` returned 202, with a criterion, a read-only document holding two numbers chosen for this run, and a required `report.md` stating their total |
| Planned | Plan version 1 with one task, shown as open |
| Executed | The worker read the document, passed what it read to `calculate`, and saved the report from the result, all through the gateway |
| Restarted | The worker killed itself with SIGKILL inside its sixth model call, and a supervisor loop restarted it |
| Recovered | Its lease expired by database time. The replacement classified the open call as uncertain and paused, shown in the browser, and made no model call |
| Refused | Resume returned 409 `uncertain_model_call` until an owner reported the charge |
| Continued | After reconciling and resuming, the worker continued from its checkpoint, and published `report.md` |
| Verified | The artifact was read back from Storage and checked, the run reached `succeeded`, and verification showed passed |
| Inspected | One artifact, whose download holds the right total, with spend above zero and nothing outstanding. After a reload, the timeline replayed with sequences 1 to n, with no gap or duplicate. axe reported no WCAG A or AA violation |

## Report unmet criteria honestly

| Arranged condition | Observed |
|---|---|
| The model completes its task and claims success, with nothing published | `failed`, verification lists `artifact missing: report.md` |
| The published report states a total one too high | `failed`, `artifact check failed: report.md`, and the artifact stays inspectable |
| The model only says it finished, with no plan | `failed`, `plan missing` |

## Recovery assertions elsewhere

Each is in a real database or process check, and listed in its archived `verification.md`: a stale worker refused at product and checkpoint writes, including a write racing a claim (US-4.2), receipts reused across generations and a lost response reconciled by readback (US-4.4), interrupted publication reconciled against real Storage (US-4.5), reconnect with no duplicates (US-4.6), and a stopped process waking to find it was replaced (US-4.7).

## What this doesn't establish

- **No real model.** The script shows the application's control flow, not that a real model can do this task. Real provider behavior is US-3.4's paid qualification.
- **A fixture worker.** `tests/web/fixture_worker.py` and its restart loop stand in for a product worker and supervisor, which don't exist.
- **Not measured.** SP-021's responsiveness targets and recovery within 60 seconds.
- **Arranged conditions.** The workspace policy was reset before the slice, because an earlier suite changes it and the fixture worker's route is fixed. The key and upstream are fixtures. The death's timing is scripted.
- **Not H1 or product acceptance.** This is one mocked slice on disposable services.

## Review

An independent review found blockers these tests had missed. See [review-r1.md](review-r1.md) and [review-r2.md](review-r2.md).
