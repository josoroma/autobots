# US-12.5: a third real sleep

**Class: a real sleep of this Mac by its owner, on a disposable stack, with a scripted model.** No spending. This doesn't establish H1 or product acceptance. It says nothing about a real provider's connection dropped across a sleep, about network loss, or about a persistent stack.

**Result: a real failure, fixed, and the fix proven by another real sleep.** It ran on US-12.3's binding as bound again, source fingerprint `05916d5e…`.

| Attempt | Asleep, by the two clocks | macOS's log | Result |
|---|---|---|---|
| 1 | 49.7 s | Sleep 16:35:06, Wake 16:36:21 | **Doesn't count.** Under the runbook's two minutes and the 60-second lease. No failure, and nothing claimed |
| 2 | 900.2 s, in two sleeps of 359 s and 541 s | Sleep 16:41:22, Wake 16:47:52. Sleep 16:48:20, Wake 16:57:23 | **Failed: `sleep_counted_as_work`.** The run ended `failed`, `active_time_limit`, at step 19 of 21 |
| 3, on the fix | **988.5 s, across 20 wakes** | Sleep 17:36:00, Wake 17:56:55, with dark wakes between | **`no_failure_observed`.** `succeeded`, verification passed, 1 artifact published |

## What attempt 2 found

A defect on the code that shipped in US-11.12, which **I introduced**. A reviewer asked for the discount on time asleep to be capped at elapsed time, and I added `least(..., clock_timestamp())` to `discount_sleep`.

Docker's clock lags a wake by about half a minute and then jumps. `worker.lease_revived` came 26 seconds after `worker.woke` both times, though the lease had long expired in true time, which fits only that. The clock was never sampled directly, so the lag is inferred. During the lag the cap reset the segment's start to the lagging now, and the jump then counted the sleep as work.

No database test could have shown this, and every profile passed with it in place. US-11.10's passing sleep predated the cap.

**The fix:** the cap is gone, and reads floor at zero until the clock catches up. A new case in `tests/db/wake_check.py` fails with the cap restored. It voided US-12.3's binding, as the story's scenario says, so a fresh review and Gate 0 bound it again, and attempt 3 ran on that.

## Attempt 3, against the runbook

| | Before the sleep | After |
|---|---|---|
| Run status | `running` | `succeeded`, in the database and from the API |
| Receipts | 1, none unknown | 20, none unknown |
| Files saved / distinct paths, so effects duplicated | 0 / 0 | 17 / 17, none |
| Reservations | 34,560 held | 0 held |
| Redispatch | | `steps_sent_more_than_once` is empty, 1 attempt, generation 1 |
| Lease | | Revived 4 times, by the wake handling, with no step failed |

**Why this one proves it:** a short sleep could pass with the bug present, as it trips only when the run reaches the limit. Here the time asleep alone passes the 900-second limit, so the old cap would have failed it.

## Limits

- **The model is scripted,** so a real provider's connection dropped across a sleep isn't observed, and neither is network loss.
- **One passing sleep.** It's what was seen once, with many short dark wakes and one of 450 seconds.
- **The report has no active-time reading,** so the proof is the run reaching the end under its limit.
- **Accepted, from the fix's review:** with no cap, a clock that never catches up, a forward wall-clock step over 20 seconds, or a discount applied twice can leave a segment's active time uncounted, and a segment that begins during the lag could add a jump to active time. Model-call, tool and money limits don't depend on it.
- **The runbook's failure list** doesn't name `sleep_counted_as_work`, and US-12.3's review records that. Editing it would void the binding again.
