# US-4.8 independent review, round 1

An `autobots-reviewer` agent read the working tree without running anything, and repaired nothing. It covered US-4.8 and the US-4.1 to US-4.7 code, which had no independent review when delivered. It was given the code and the requirements, with no conclusions.

It reported 6 blockers, 5 majors and 4 minors, all missed by the tests written alongside the code. It found no cross-workspace path and no leak of secrets or framework state.

| # | Severity | Finding | Change |
|---|---|---|---|
| 1 | Blocker | A retry after backoff dispatched with no fence, and a reservation closed by recovery could still be sent | `dispatch` checks ownership on every attempt, and `mark_dispatched` refuses a closed reservation |
| 2 | Blocker | A pause during a dispatched call, then a cancel, stuck in `cancelling`, since the job was unclaimable | A cancel with open work and no live owner queues the job for recovery |
| 3 | Blocker | A run's own limit was ignored, and spend always showed 0 | `admit` applies the lower of the two limits, and public figures read the ledger |
| 4 | Blocker | Success could be self-attested with no required artifact | A goal with no requirement still needs a published artifact, and the page says its content wasn't judged |
| 5 | Blocker | A stale verifier could write a verdict and a reason, and its recovery could delete a fresh upload | Verdict and reason commit with the fenced transition, the lease is renewed during verification, and recovery lists objects before rows |
| 6 | Blocker | A key didn't cover an input's value, and reconcile ignored its key | Both are fixed |
| 7 | Major | An older copy could satisfy a requirement after the newest was lost, and an input could be published | The newest attempt per name decides, and publishing takes `outputs/` only |
| 8 | Major | Unknown outcomes neither blocked success nor showed publicly | They block success, and `outstanding` shows them. A call with no reported charge is shown and doesn't block |
| 9 | Major | A hung model call was unbounded | Bounded by a timeout, and a cancel or lost lease ends the wait. The outcome stays uncertain |
| 10 | Major | The slice's script ignored tool replies, hard-coded its total, and wrote its own document | Documents come through admission and are read-only, numbers vary per run, and the script computes from what its tools returned |
| 11 | Major | Verification had no database coverage | `tests/db/verification_check.py` covers each finding here |
| - | Minor | `Retry-After` dropped | Passed through from the error's response |
| - | Minor | Stale-write window in saves and plans | `hold_lease` runs in each write's transaction |
| - | Minor | Vacuous checkpoint secret check | A key is now planted on the model client, and all three checkpoint tables are read |
| - | Minor | A retried attempt left a `failed` receipt | It resets to `started` |
| - | Minor | `credential_version` never set | Not fixed. No real credential path reaches the loop yet |

The reviewer also noted that `run_goal` re-raised `UnadmittedModelCall`, with no cap on attempts. It now stops the run with `unadmitted_model_call`. Attempts across restarts are still uncapped, because no source sets a limit.

Round 2 is in [review-r2.md](review-r2.md).

## Judgment calls this leaves for you

- **A goal with no stated requirement** succeeds once it publishes anything, with the page saying the content wasn't judged. The composer states no requirement. The sources don't say whether such a goal should be able to succeed.
- **A call with no reported charge doesn't block success.** It keeps its reservation and stays visible.
