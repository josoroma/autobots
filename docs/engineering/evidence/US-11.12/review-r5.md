# US-11.12 independent review, round 5

`autobots-reviewer`, in a fresh read-only context, a narrow confirmation over the last edits, on the tree this record's fingerprint binds. Saved in substance. Nothing was executed by the reviewer.

**Outcome: approved.** 0 blocking, 7 nonblocking.

## Round 4's items

R4-1, R4-2, R4-3 and R4-4 done. R4-5 done with inaccuracies (R5-2). R4-6 mostly done (R5-3). R4-7 half done (R5-1). R4-8 is a narrow guard, as intended (R5-7).

## Nonblocking

- **R5-1.** A browser test's name says "new linked run", and it asserts the request carried the ID. The stored link is proved in `tests/db/review_check.py`.
- **R5-2.** The runbook's `cost_unavailable` row says "from 272,000 tokens", where the refusal fires at 272,000 bytes, so it can come before the rate would apply. Its remedy isn't available for a child or workflow run.
- **R5-3.** `calls_without_a_reported_charge` still reads an unread count as 0, and the failure report's `not_checked` misses a blank value.
- **R5-4.** With `ensure_ascii=False`, a lone surrogate would raise before any reservation. The reviewer didn't prove it's reachable, as checkpointing may refuse such a message first. No money is at risk.
- **R5-5.** "As this may already be running" stays on screen after the outcome is known.
- **R5-6.** No test asserts the picker is hidden after a lost reply, or that a refusal clears the key.
- **R5-7.** The Bash guard's stated limit doesn't name `grep . master.key` or piped forms.

Also noted: a page reload loses the kept key, so a press after one can start a second paid run. `run_not_finished` and the failure-path report have no test.

Outcome line as returned: `outcome: approved`
