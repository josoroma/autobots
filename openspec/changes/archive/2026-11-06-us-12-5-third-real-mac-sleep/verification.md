# Verification — us-12-5-third-real-mac-sleep

Change: us-12-5-third-real-mac-sleep
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Observe a real sleep on the final code | PASS | Attempt 3, on the owner's real sleep at source fingerprint `05916d5e…`, read from `evidence.py` before and after. 988.5 seconds asleep by the two clocks across 20 wakes, and macOS's log shows `Sleep` at 17:36:00 and `Wake` at 17:56:55. Status, receipts, reservations and redispatch are in the [summary](../../../../docs/engineering/evidence/US-12.5/summary.md). No `SIGSTOP`. The harness's own report doesn't hold the fingerprint |
| Report a failure as a failure | PASS | Attempt 2 listed `sleep_counted_as_work`, which this scenario's list doesn't name, and it's recorded as a failure. The story didn't complete on it. The fix voided US-12.3's binding, which was reviewed and bound again, and needed the further real sleep that attempt 3 is |
| Don't count a run that never slept | UNVERIFIED | No run reported `no_sleep_during_the_run`, so this path wasn't exercised here. Attempt 1 is the nearest: it slept for under the runbook's two minutes, nothing is claimed from it, and the owner started again |
| Keep what this doesn't prove | PASS | The summary states a real provider's dropped connection and network loss as limits |

Checks: `harness` exits 0, and `scripts/evidence.py validate US-12.3` passes at the rebound fingerprint. `db` ran on this code in US-12.3's Gate 0.

## Findings

- **A real defect on the code that had shipped,** which every profile passed: a cap on the sleep discount, which I added at a reviewer's request. The cause rests on inference from the lease's timing, and the clock wasn't sampled.
- **The first attempt was too short to count,** and macOS's log, not the answer given, showed it.

## Not exercised

A real provider across a sleep, network loss, and a persistent stack across a sleep.
