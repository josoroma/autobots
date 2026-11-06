# Verification — us-12-4-measure-two-call-workload

Change: us-12-4-measure-two-call-workload
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Measure two goals at once | PASS | Live, on disposable stacks at US-12.3's bound code. Four rounds of two Terra goals through the real API and two workers. CPU, memory, disk and connections for the UI, API, workers and Docker, each goal's outcome and the fingerprint, are in `docs/engineering/evidence/US-12.4/`. The story asked for one run, and three more went looking for a cause. Rounds 2 to 4 used a worker with a logging wrapper |
| Don't count goals that never overlapped | PASS | The runner reads each call's start and end from the ledger, and reports `not_measured` when no two runs' calls overlap. Live rounds overlapped for 1.3 to 14.9 seconds. No round hit that branch, so it's by reading |
| Report a failed result as failed | PASS | Round 1: a run paused as `uncertain_acceptance` on its first call, and the runner reports `failed`. LM-A09 stays partial, and this story's report tells the owner. The cause isn't known |
| Stop at the shared cap | PASS (arranged) | A ledger arranged 10 micro-USD below the cap: refused before any stack or request, nothing reserved. The real ledger hasn't come near it |
| Record what was spent | PASS | Reported charges US$0.040265, key usage up US$0.040263, the shared ledger at US$0.298439, which still holds round 1's US$0.25. No key in the record, by the runner's scan and a check of the retained files |

Checks: `harness` exits 0, `scripts/evidence.py validate US-12.3` still passes, as nothing here changed its inputs, and `openspec validate` is clean.

## Findings

- **An intermittent pause with no recorded cause.** One of 40 live calls in these rounds paused a run, as `uncertain_acceptance`, apparently at no charge. The product records only the class. Finding the cause needs that recorded, which is a source change, and that's the owner's call as it would void US-12.3's binding.
- **Stability isn't established.** Three of four rounds were stable, on short goals.

## Not exercised

Long runs at two calls, responsiveness under load, and a persistent stack.
