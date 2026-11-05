# Verification — us-4-1-atomic-run-admission-canonical

Change: us-4-1-atomic-run-admission-canonical
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `bae00ed`, working tree with this change. Real Postgres through the runtime role on a disposable target, and the real API and browser against a disposable stack with a fake OpenRouter upstream and an arranged key. No model call. `scripts/app_db.py types`: 122 cases passed. `scripts/qualify_identity.py`: exit 0, including 5 new browser tests. `--profile full`: passed.

## Scenarios

**Admit exactly one logical request: observed.**
- Twelve simultaneous connections with one key: 1 run, 11 replays, and exactly one run, one job and one event committed.
- The same key with different content is refused with `idempotency_conflict`. Whitespace around the goal normalizes to a match. A different actor or workspace gets its own run, and different keys admit separately.
- Through the API: 202, a replay with the same run ID, 409 for different content, 422 for an empty key.
- Through the form: one Run press sends one POST and shows `queued`, and a reload sends none.
- A workspace with no key is refused with `credentials_required`.
- The role policy is frozen on the run at admission, 14 bindings, and `authenticated` is denied it and the job table.

**Enforce lifecycle guards: observed.**
- Every worker and user path tested moves by SP-010, with version 2 and one event. Worker commands here ran with an arranged lease, since no worker exists.
- Refused, with the version unchanged: wrong state, a user completing, claiming or failing, and a worker resuming or pausing.
- Each terminal state refuses resume, claim and pause, including through the API.
- Cancel goes straight to `cancelled` with no active work, enters `cancelling` with it, repeats harmlessly, and leaves no claimable job.
- A stale expected version is refused with `version_conflict`. Six simultaneous commands on one version apply once.
- A repeated command key returns the original result. A run in another workspace is not found, in the DB check and for a real second account through the API.

## Findings

- **Fixed during this story:** a cancelled run kept a claimable job, the job status now follows the transition. The first browser run failed because admission correctly refused a workspace with no key, so the spec now saves one.
- **`run_events` is the outbox for now.** Each event commits with its change. Projection and delivery are US-4.6.
- **Nothing runs a queued run yet,** so the composer says so. No model is called.
- **`has_active_work` is a parameter here,** and the user routes leave it false, so through the API a cancel always goes straight to `cancelled`. That's correct while no worker exists, and US-4.2 must derive it from the lease.
- **Guards SP-010 asks for that have no data yet:** resume's readiness checks and keeping outstanding input or approval requirements across a pause need US-5.3's records. The approval decision route belongs to US-5.3, and its command is tested.
- **Judgment calls the sources don't fix:** the $1 default limit in `RunRequest`, matching MP-07's run cap, and using the new `/v1/runs` for the composer instead of `/v1/runs/intent`, which stays as an API route with an unused BFF route.
