# Verification — us-7-1-explicit-routines-deduplicated-scheduled

Change: us-7-1-explicit-routines-deduplicated-scheduled
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `09b5686`, working tree with this change. Unit fixtures for time, and real Postgres through the runtime role on a disposable target. Times are injected into `evaluate_routines`, so no real waiting or Mac sleep happens. `pytest`: 276 passed. `scripts/app_db.py types`: 373 cases passed. `--profile full` passed.

## Scenarios

**Deduplicate and recover occurrences: observed, with injected times.**
- Six concurrent evaluations admitted exactly one occurrence, and evaluating the same time again adds nothing.
- With a run still active, the next occurrence is `skipped_overlap` with a reason. Once the run finishes, the next one runs.
- After five due occurrences, 4 are `missed` with `host_away`, and only the latest is admitted.
- A daily 09:00 in `America/Costa_Rica` is stored as 15:00 UTC. Unit fixtures keep the wall-clock time across New York's daylight saving changes, and a skipped or repeated local time runs once.
- A workflow routine binds its exact version.

**Keep scheduling explicit: observed.**
- With no enabled routine, nothing starts and no key is looked at.
- With no usable key, an occurrence is `blocked` with `credentials_required`, and nothing runs.
- An edit leaves an admitted run's goal and tools as they were. The next occurrence uses the new version, with its narrower tools and $0.0005 limit.
- A tool the Expert lacks is `routine_scope_widened`, and so is a shell. An unknown timezone, a missing goal, another workspace's Expert and a stale edit are refused. The runtime role can't rewrite a saved version. A disabled routine is quiet, and doesn't catch up when turned back on.

## Findings

- **No process evaluates routines yet.** `evaluate_routines` is a function. US-9.1 is where a worker process can arrive, and until then nothing is scheduled in a running app, so "the Mac wakes" here means a later injected time.
- **The API routes have no end-to-end test.** They're in the schema and type checked, and each calls a function tested above. There's no screen, since the tasks ask for the logic, and PRD 12.1 lists routines inside the Expert editor, which doesn't show them.
- **Admission holds the routine's row lock in one transaction,** so a slow evaluation of one routine doesn't block another (`skip locked`), and a concurrent worker just skips it.
- **Judgment calls:** interval and daily triggers only, a run's `actor_id` set to the routine's ID, and a scheduled run with no session, so it can't delegate.
- **No independent review.**
