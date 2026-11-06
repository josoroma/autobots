# Verification — us-11-12-final-independent-review-gate

Change: us-11-12-final-independent-review-gate
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Review the final code and repeat Gate 0 | PASS | Five rounds of `autobots-reviewer`, in separate read-only contexts. Round 5 read the tree whose source fingerprint, `3ea96bac…`, the manifest binds, and I compared the two. `harness`, `full`, `db`, `fast` and `operations` exit 0 under `env -i`. The runbook's stale-lock and killed-run recovery and arranged adapter states ran on the same inputs. Everything is under `docs/engineering/evidence/US-11.12/`, `scripts/evidence.py validate` and `complete` pass, and the record says it leaves H1 and product acceptance to US-10.2 |
| Settle what earlier reviews left open | PASS | The summary's dispositions give each of N-1 to N-73, M8, M30, M32, M33 and WORKER-INFERENCE-001 a stated outcome. M30 cites Decision 0009. WORKER-INFERENCE-001 reads complete as built, on mock and disposable evidence only, backed by 45 of 45 cases at this fingerprint |
| Refuse a stale or unresolved result | PASS | Observed on this story: rounds 1 to 3 returned `changes_required`, and the story didn't advance. Each fix was reviewed again, and the fingerprint was bound only after rounds 4 and 5 approved. `evidence.py`'s refusal of a changed fingerprint and of an open blocking finding is held by harness tests, which ran in `harness`. No source changed between the bound fingerprint and `complete` |
| Mark the hook behavior not qualified | PASS | The summary marks Claude's crash, timeout and Stop recursion behavior not qualified, under DH-A03 and its own section. The harness report reads `configured_unqualified`, `delivery_unverified`, with `Claude event delivery` under `not_tested`. No script fixture is reported as event delivery |

Checks on the final code: `full`, `db`, `operations` and `harness` all exit 0 at one input fingerprint, and `openspec validate` is clean. `db` runs `qualify_identity.py`'s 407 cases, and `qualify_worker_inference.py`, in no profile, ran by hand with 45 of 45.

## Findings

Round by round, in the summary's dispositions. What matters most:

- **Round 1 found a false premise of mine.** I told the owner held-out replay stayed with US-10.1, which built no such thing. Corrected in Decision 0011, and the owner chose again.
- **Reviews kept finding real defects in fixes.** Round 2 found the new **Continue in a new run** sending a cut goal and a reservation gap on summaries. Round 3 found that the real catalog's Terra tier at 272,000 tokens made that reservation still wrong for very large requests.
- **Round 3 also found that the new database cases couldn't run,** before any run did.
- **The real-sleep proof predates current code.** US-11.10's sleep ran before the lease keeper's reconnection and fenced discount, which have database cases only.

## Not exercised, and limits

- Nothing here is live, and no model was called. The real install wasn't touched, and stays at migration 32.
- Round 5's seven nonblocking findings are accepted and stated in the summary, without further source changes, to keep the reviewed fingerprint. One corrects the runbook: its `cost_unavailable` row says tokens where the refusal counts bytes.
- This doesn't establish H1 or product acceptance. US-10.2 assesses those.
