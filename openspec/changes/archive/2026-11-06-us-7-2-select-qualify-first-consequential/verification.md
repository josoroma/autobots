# Verification — us-7-2-select-qualify-first-consequential

Change: us-7-2-select-qualify-first-consequential
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Enforce the selected connector contract | PASS | Live against `josoroma/bot-test`, a private repository: 8 of 8 cases, issue 2, exit 0. On a disposable database through the real gateway, with a fake destination: approval first, one issue, repeats from the receipt, a lost reply is unknown, a readback settles it, a refusal's code is on the receipt, no token in any record |
| Reject out-of-scope work | PASS | On a disposable database through the real gateway: no grant, another grant version and a repository argument are all refused with no request sent and no receipt |

Checks on the final code: `fast`, `db` and `harness` all exit 0, the unit suite covers the connector and qualifier, and `openspec validate` is clean. The adapter and qualifier didn't change after the live run. The raw report is `.checks/github-connector/qualification.json`, which is ignored and local.

## Findings

**Found by the live run, and fixed.** The first live run created issue 1, then a readback at once didn't find it, because GitHub's issue list lagged the create. The gateway treats "not delivered" as safe to send again, so a lost reply could have become a second issue. Fake transports had never shown this. The readback now reads for about 15 seconds before saying not delivered, and the second live run found issue 2 after 8.9 seconds. The qualifier also crashed with no report on that failure. It now reports a failed case, saves the report and still closes the issue, covered by a test.

**The repository was public at first.** The qualifier refused it with nothing written. The user approved making it private, and it was private for both writes.

## Limits

- **The 15-second wait rests on one measurement of 8.9 seconds.** An issue slower than the wait could still be duplicated after a lost reply. This narrows the risk Decision 0007 accepted, and doesn't remove it.
- **A real lost acknowledgment wasn't exercised.** Only the fake transport arranges one. The live run checks the readback the recovery depends on.
- **The live run and the gateway were tested separately.** The live run has no database or approval, and the gateway runs have a fake destination. No model has called this connector against GitHub.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
