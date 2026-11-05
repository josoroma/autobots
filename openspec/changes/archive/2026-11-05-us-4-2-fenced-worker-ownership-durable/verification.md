# Verification — us-4-2-fenced-worker-ownership-durable

Change: us-4-2-fenced-worker-ownership-durable
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `2cc419e`, working tree with this change. Real Postgres through the runtime role on a disposable target, the pinned LangGraph and `langgraph-checkpoint-postgres` 3.2.0, a real graph with no model, and a real process killed with SIGKILL. `scripts/app_db.py types`: 159 cases passed. `scripts/qualify_identity.py` exit 0, `--profile full` passed.

## Scenarios

**Fence both product and checkpoint writes: observed.**
- After expiry and reassignment, a stale worker's real graph run gets `AB001` from the database, with 0 new checkpoint rows. Its `apply_command` raises `LeaseLost`, with the run's version unchanged. The new generation succeeds at both.
- An expired lease is refused before anyone reclaims it, and can't be renewed.
- A write racing an uncommitted claim stayed pending, then failed against the new generation, so this is more than a check before the write.
- Bypassing the application: a write with no generation and a thread with no job are refused by the trigger, and the runtime role can't disable it or delete checkpoints.
- Pausing removes ownership at once. A resumed run is claimed by a new generation.

**Recover persisted execution: observed, with a real process death.**
- A worker process was killed by SIGKILL inside the second node, exit -9. Its log shows `first, second`.
- Its 2-second lease held, by database time, against an early claim. After it ran out, the replacement claimed generation 2, attempt 2.
- The saved checkpoint held `['first']` with next node `second`. Resuming finished with `['first', 'second', 'third']`.
- `first` ran once and `second` twice, because the unfinished step runs again. That's why no exactly-once claim is made, and US-4.4's receipts must cover effects inside a step.

Also observed: eight competing workers get one claim, a duplicate delivery gets none, and a job not yet available isn't claimed. The migration records adapter version 9, equal to the pinned adapter's list, so setup has nothing to do, and the runtime role can't run it.

## Findings

- **Fixed from US-4.1:** the API's cancel always went straight to `cancelled`. `apply_command` now derives active work from the lease, so a live owner gives `cancelling`, and a dead one allows `cancelled`. Commands and claims now lock the job and then the run, so they can't deadlock.
- **Measured, SP-012:** `durability="sync"` cost 11.4 ms per three-step run against 3.5 ms for `exit`, with these small states on loopback. One run, not a benchmark.
- **The generation is a session setting.** The trigger stops stale workers, not hostile code running as the runtime role, which could set it.
- **Not covered:** Mac sleep, attempt limits, a thread ID that isn't a UUID fails on the cast rather than with `AB001`, and model slots held by a dead worker, which US-3.3 left to leases and nothing reclaims yet. There's no worker loop, so nothing claims a job in the running product. US-4.7 owns the wider recovery.
