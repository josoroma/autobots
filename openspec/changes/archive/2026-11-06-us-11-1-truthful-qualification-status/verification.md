# Verification — us-11-1-truthful-qualification-status

Change: us-11-1-truthful-qualification-status
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Show each route's stored qualification | PASS | `scripts/qualify_identity.py`, disposable stack: the driver stops and restarts the real API process, then the browser opens Settings. DeepSeek and Terra each show their own status, `2026-11-05`, configuration and limits, with authentication and catalog in their own fields |
| Refuse to infer qualification | PASS (arranged) | Same run: the Terra record is deleted from the database, and with a valid key and an available catalog Settings shows Terra as `Not qualified` with no date or limits, and DeepSeek unchanged. A unit test covers a record for another canonical model |
| Correct the goal message | PASS | The Run form's outcome reads exactly `Your goal is queued. Open this run`, and the link goes to `/runs/<id>` |

Checks on the final code: `fast`, `db` and `harness` all exit 0, the identity qualifier's 336 cases pass, and `openspec validate` is clean.

## Findings

None.

## Limits

- **The stored results are what US-3.4 observed:** three trials per fixture on one day. The records repeat its limits and add no new evidence. No model was called here.
- **Results are added by migration,** so a later qualification round needs one. No screen or route can change a record.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
