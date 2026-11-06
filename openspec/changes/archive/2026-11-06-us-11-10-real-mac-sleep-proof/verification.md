# Verification — us-11-10-real-mac-sleep-proof

Change: us-11-10-real-mac-sleep-proof
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

**Both sleeps were real, and the owner slept this Mac each time.** Nothing used SIGSTOP or slept the Mac by command. Disposable stack, the real `worker.main`, SDK, ledger, leases and checkpoints, with a scripted model over a fake HTTP transport, 30 seconds per call. Raw reports: `.checks/mac-sleep-first-report.json` and `.checks/mac-sleep-second-report.json`, ignored and local.

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Observe one real sleep | PASS | First sleep, below. The wall clock ran 592.7 seconds ahead of the monotonic clock, and macOS's power log shows it |
| Build wake handling only if the test shows it's needed | PASS | The first sleep recorded a failure, so wake handling was built in this story |
| Prove a fix under real sleep | PASS | Second sleep, below. macOS logged `Entering Sleep state` at 07:58:43, 542 seconds, and `Wake` at 08:07:45 by the power button. The failures were gone |

## What each sleep did

| | First sleep, before the fix | Second sleep, with wake handling |
|---|---|---|
| Asleep, by the two clocks | 592.7 seconds | 540.4 seconds |
| Status before, in the database and the API | `running` | `running` |
| Status at the end | **`failed`, `active_time_limit`**, with 9 of 21 calls made | **`succeeded`**, verification passed |
| Steps sent more than once | **Step 3** | None |
| Lease | Lost twice: 3 attempts, generation 3 | Kept: 1 attempt, generation 1 |
| Receipts | 6, none unknown | 20, none unknown |
| Files saved / distinct paths, so effects duplicated | 5 / 5, none | 17 / 17, none |
| Published artifacts | 0 | 1 |
| Reservations at the end | 0 held | 0 held. One call's 34,560 micro-USD was held across the sleep, then settled |
| API and database agree at the end | Yes | Yes |
| The call in flight across the sleep | Replied, and settled | Replied, and settled |

## Findings

**The first sleep found two failures.**

1. **A paid reply was thrown away and sent again.** The lease expired while nothing was running. Docker's VM clock corrected late, so the run carried on, then found its lease gone with step 3 in flight. That call was answered and charged, and the tool that followed was refused, so the reply was lost and step 3 went out again. LC-31 asks for no paid replay on wake.
2. **Time asleep counted as work.** 593 seconds asleep counted toward the 900-second active limit, so the run failed as `active_time_limit` though it hadn't been working that long. That's a false reason.

**The fix.** `WakeClock` sees a real sleep from a process's own two clocks. For 5 minutes after one, the lease keeper beats every second, and takes back a lease that expired only if nobody claimed it, with the same generation, so fencing is unchanged. The time asleep comes off the open active-time segment. `tests/db/wake_check.py` shows that a stall with no clock gap gets none of this, an ordinary heartbeat still refuses an expired lease, and a lease someone took is never revived.

**What's inferred.** The first run deleted its request log with the stack, so that sleep's exact order is inferred from its counts and the code. The report now keeps the log, and the second sleep's is recorded.

Checks on the final code: `harness`, `fast` and `db` exit 0, and `openspec validate` is clean. No code changed between the second sleep and these checks.

## Limits

- **One sleep with the fix,** of 9 minutes, on AC power, with one worker and one run.
- **The model was scripted, and its call came back after waking.** A real provider's connection would likely drop, which pauses the run as `uncertain_acceptance` for a person, and that path wasn't exercised under sleep. No paid call was made here.
- **Two workers waking together weren't tried.** One could claim the expired lease first. That's fenced, so it's safe, but the other's reply would be lost and paid for again.
- **A reply landing within a second of waking,** before the keeper looks, could still hit an expired lease.
- **The active-time discount assumes Docker's clock catches up,** as it did both times. If it didn't, a run would get up to that much extra active time.
- **A workflow's own runs use this keeper,** but only goal runs were slept.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
