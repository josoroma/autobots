# US-11.12 independent review, round 3

`autobots-reviewer`, in a fresh read-only context, scoped to what changed for round 2. Saved in substance. Nothing was executed by the reviewer.

**Outcome: changes_required.** 2 blocking, 12 nonblocking.

## Blocking

- **R3-1.** Rows from before migration 35 could still state R2-3's falsehood, as a null source was read as the owner's.
- **R3-2.** The reservation for a large request left out the tier such a request triggers. `_reachable` dropped any rate starting above 32,000 tokens, and the real catalog gives Terra one at 272,000. A prompt past it could spend past the run limit by the difference.

## Nonblocking

- **R3-3.** `tests/db/review_check.py` couldn't run through, for three separate faults: a wrong column, a grant the runtime role lacks, and a run limit below the reservation. It failed loudly, so it couldn't pass falsely.
- **R3-4.** `continue-run.tsx` cleared pending before reading the reply, and a lost reply said it could not be started though it may have, with a new key on retry.
- **R3-5.** The discount ran before the beat, so a discount that kept failing starved the heartbeat, with unbounded logging.
- **R3-6.** The cap limits a double discount but doesn't remove it.
- **R3-7.** `goal` exited 0 when the key-leak check never ran.
- **R3-8.** The failure-path report omitted the failure and what wasn't checked.
- **R3-9.** An empty `started_at` blinded the paid watchdog.
- **R3-10.** Bash secret patterns denied ordinary commands that only name a key.
- **R3-11.** Tests asserting less than they claim: the keeper's forced beat, the capped discount, `refuse_other_work`'s call, `worker.main` and `InferenceSource.bind`'s wiring, the workflow branch, a null objective, the new run's link. `run_not_finished` and the stop-before-read order have no test.
- **R3-12.** `review_check.py` marked every job done, in every workspace.
- **R3-13.** A false refusal message for a child or workflow run. A caller supplying `goal_text` can still link to one.
- **R3-14.** A stale comment, and a case count to check against the final run.

## Round 2, as the reviewer read it

| ID | Verdict |
|---|---|
| R2-4, R2-6, R2-8, R2-11, R2-13, R2-14, R2-15 | Resolved |
| R2-2, R2-10 | Resolved in code |
| R2-5 | Recorded as intended, and understated in the runbook |
| R2-1, R2-3, R2-7, R2-9, R2-12 | Partly |

Outcome line as returned: `outcome: changes_required`.
