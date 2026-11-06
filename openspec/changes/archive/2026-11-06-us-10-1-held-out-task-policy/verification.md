# Verification — us-10-1-held-out-task-policy

Change: us-10-1-held-out-task-policy
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Measure the scoped release corpus | PASS | Recomputed from `.checks/release/`: 99 of 100 protocol cases, 104 of 120 goals on 40 tasks and 3 trials, 86.7%, by category: research 27/30, artifact 25/30, workflow 23/24, recovery 12/18, approval 17/18. 0 safety failures and 0 duplicate receipts. The corpus's SHA-256 still matches, and the file is unchanged since the run's commit. Only the connector's readback changed in application code since |
| Measure local responsiveness separately | PASS | `.checks/release-resources/`, this change's live run: API p95 4.7 ms, event visible in a real browser p95 492.1 ms, cancel acknowledged p95 9.5 ms through the API and 20.2 ms through the web app, reclaim 2.3 to 3.2 s after lease expiry across 3 kills, and 59 resource samples with no failed probe. Exit 0 |

Cost of this change's run: US$0.062253 by key usage and US$0.189936 by the ledger, under the user's US$1 cap. The stack was removed, nothing was left behind and other Docker stacks were unchanged.

Checks on the final code: `fast` and `harness` exit 0, and `tests/harness/test_release_qualification.py` covers the resource summaries and the required cap. The spec's only run is the paid one, because no profile runs it.

## Findings

None block. Each of these limits is published in [the evidence](../../../../docs/engineering/evidence/US-10.1/summary.md):

- **The corpus run predates this change's runner edits.** It isn't repeated, because the only application change since is the connector's readback, which its fake destination barely reaches. The resource run is on the current application code.
- **Task success has a narrow margin,** and the corpus was written by the assistant. The user accepted both, as Decision 0008 records.
- **Latency and cancellation were measured on queued runs, one at a time.** Resources weren't measured with both model slots in use, and a running call's stop time isn't measured. The scenario's "configured remote concurrency" was the sequential workload this runner drives, not two concurrent runs.
- **The resource run is short,** at 8 minutes and 12 small goals, on development tasks whose 12 passes say nothing about quality.
- **The web app's stability during goals rests on HTTP probes.** A browser was open only for the latency samples, which followed the goals.
- **Not established:** H1 or product acceptance. No independent review ran for this story, under Decision 0003.
