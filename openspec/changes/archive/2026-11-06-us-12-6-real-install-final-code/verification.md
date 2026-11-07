# Verification — us-12-6-real-install-final-code

Change: us-12-6-real-install-final-code
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Try the migrations on a restored copy first | PASS | Live, the real install at source fingerprint `05916d5e…`: backed up, restored to an isolated held copy, verified, and migrations 33 to 35 applied there through the guarded path before the install. Recorded in `docs/engineering/evidence/US-12.6/report.json`. It stops at any failed step, and none failed, so a failure on the copy leaving the install unchanged is by the order of the steps, not seen |
| Apply and start beside other projects | PASS | Applied through the guarded path, with 32 already applied. Readiness and the schema read `ok`, the listeners are only the recorded loopback bindings, the owner, run and artifact remain by count, and 32 lines of other projects' containers, ports and volumes are identical before and after |
| Run one real goal under the shared cap | PASS | `succeeded`, verified, Terra's route, reported US$0.005848, the ledger at US$0.315650, key usage up US$0.005849, and no live worker claims inference afterward |
| Stop at the shared cap | PASS (arranged) | `qualify_persistent_apply.py`, in US-12.3's `db`: an arranged ledger just below the cap refuses with nothing sent or reserved. The real ledger hasn't come near it. US-12.4's runner shows the same on its own arrangement |
| Stay inside what was authorized | PASS | Only the backup, the isolated copy, these three migrations, a start, one goal and a stop. Nothing was reset, and only the isolated copy was removed. Nothing arose that needed stopping for, so that branch wasn't seen |

Checks: `harness` exits 0, and `scripts/evidence.py validate US-12.3` passes, as nothing here changed its inputs.

## Findings

None. The install is stopped with its data kept, at migration 35 of 35.

## Not exercised

A real browser on the install in this story, a real uncertain call on it, and sleep on it.
