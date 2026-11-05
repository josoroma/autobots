# Verification — us-4-8-verify-first-durable-goal

Change: us-4-8-verify-first-durable-goal
OpenSpec verify: VERIFIED by the main session, after an independent review found blockers and they were fixed, with the limits below. The review is in `docs/engineering/evidence/US-4.8/`, because this story's tasks ask for one.
Verified: 2026-11-05

Base revision `c91ef48`, working tree with this change and the review's fixes. A disposable Supabase stack, the real API and web app in Chromium, a real fixture worker process and a scripted model. `scripts/qualify_identity.py` exit 0, 133 cases. `scripts/app_db.py types`: 311 cases passed. `--profile full` passed. Details are in `docs/engineering/evidence/US-4.8/summary.md`, and the flow is in `docs/engineering/runbooks/first-slice.md`.

## Scenarios

**Complete the mocked vertical slice: observed.** A goal was admitted through the API with a read-only document holding numbers chosen for this run, and a required `report.md` stating their total. It was planned, then executed through the gateway, each step using what its tool returned. The worker was killed with SIGKILL in a model call and restarted by a loop. Recovery paused on the uncertain call, and the browser showed it. Resume was refused until an owner reported the charge. The worker then continued from its checkpoint and published. The artifact was read back from Storage and checked, the run reached `succeeded` with verification passed, and one artifact holds the total. After a reload the timeline replayed in order, with no gap or duplicate.

**Report unmet criteria honestly: observed, with arranged conditions.**
- Through the browser: a task completed with nothing published gives `failed` with `artifact missing: report.md`. A wrong total gives `failed` with `artifact check failed: report.md`, and stays inspectable. A claim of completion with no plan gives `failed` with `plan missing`.
- On the database and real Storage: a finished plan citing only a saved file fails as `no_published_artifact`. A lost newest copy fails though an older good one exists. An unknown effect fails as `unknown_effect`, and stays visible on the finished run.
- A stale verifier reports `lost` and writes no verdict or reason. A dead verifier's job is claimed and settled by a replacement.

## Findings

- **My first verification was wrong to stop where it did.** The tests passed while a retry could dispatch after a cancel, a run could stick in `cancelling`, a run's own limit was ignored and success could be self-attested. Review found them, with 2 more blockers and 5 majors. Each fix has a case in `tests/db/verification_check.py` or a changed check.
- **A second review round found two majors in those fixes,** and they are changed: a pause abandoned a healthy call, and an unknown internal write could never resolve. No third round ran on those last changes. They have their own cases. See `docs/engineering/evidence/US-4.8/review-r2.md`.
- **A pause now works this way, from reading PRD 10.3:** a live owner finishes its call, saves its step and lets go, and only a cancel interrupts a call. A consequential effect left unknown has no way to be resolved until US-5.4, so its run can only fail.
- **Behavior now decided here that the sources don't fix:** a goal with no stated requirement succeeds once it publishes anything, and the page says its content wasn't judged. A call with no reported charge doesn't block success, and stays visible.
- **The fixture worker isn't a product worker.** There's no worker entry point or supervisor in the product yet, and `tests/web/fixture_worker.py` stands in for both.
- **The workspace policy is reset before the slice,** arranged, because an earlier suite changes it and the fixture's route is fixed. A product worker must take its route from the run's frozen policy.
- **Not established:** a real model doing this task, SP-021's responsiveness targets, H1 or product acceptance. `credential_version` isn't set on attempts, attempts across restarts are uncapped, and whether a real summarization trigger behaves as designed wasn't reached.
