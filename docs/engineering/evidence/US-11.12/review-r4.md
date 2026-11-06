# US-11.12 independent review, round 4

`autobots-reviewer`, in a fresh read-only context, scoped to the edits for round 3. Saved in substance. Nothing was executed by the reviewer.

**Outcome: approved.** 0 blocking, 8 nonblocking.

## The two blocking findings from round 3

- **R3-1: resolved.** A null source no longer reads as the owner's. The inspector says "Charge reconciled, source not recorded". No browser test renders that text.
- **R3-2: resolved for spend.** Summaries and bound worker routes both carry the tier, and the check runs before any reservation or send, on the one path every call takes. An ordinary Terra request can't reach it. A refusal pauses the run with nothing held.

## Nonblocking

- **R4-1.** Every non-OK reply cleared the kept key, including a 503 that can follow a commit, so a later press could start a second paid run.
- **R4-2.** Changing the model after a lost reply could get a 409 that cleared the key.
- **R4-3.** A replay read "Queued." about a run that may already have finished.
- **R4-4.** `request_bytes` counted escaped characters, so a long non-Latin goal could be refused with no way to resume.
- **R4-5.** The runbook's `cost_unavailable` entry named neither the tier refusal nor its remedy.
- **R4-6.** The failure report claimed more than it held, a found key still exited 0, and an unread spend figure read as zero.
- **R4-7.** The text-only wiring test didn't check the `tier` argument. Also, a browser test's name says "linked" where the link itself is proved in the database case.
- **R4-8.** The narrowed Bash pattern opened other readers of a relative key file.

## Not exercised, as the reviewer noted

A discount that keeps failing while the lease survives, and the failure-path report. `run_not_finished` has no test.

Outcome line as returned: `outcome: approved`
