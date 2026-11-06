# Verification — us-11-4-run-controls-run-page

Change: us-11-4-run-controls-run-page
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Control a run from its page | PASS | `scripts/qualify_identity.py`, disposable stack, real browser, with the scripted worker. A slowed run reads `Running.`. Pause reads `Paused.`, Resume returns to `Running.`, Cancel run reads `Cancelled.`, after a reload too. At each, the page's state equals `GET /v1/runs/{id}` |
| Offer no control a terminal run can't take | PASS | A succeeded, a failed and a cancelled run show no Pause, Resume or Cancel. On the first two, `resume` through the route also answers 409 |
| Refuse resume until a call is reconciled | PASS (arranged) | The scripted worker kills itself inside a model call, and recovery pauses the run. Pressing Resume shows `A model call's outcome must be reconciled first.`. Three seconds later it's still paused, with the same model-call count |
| Reconcile an uncertain call | PASS (arranged) | Entering 0.00025 records it: uncertain calls go from 1 to 0, spend rises by exactly 250 micro-USD, the form goes away, and Resume runs the goal to `succeeded`. A member gets `403 owner_required` from the route, a non-number is refused on the page, and a fulfilled 403 shows the server's reason |

Checks on the final code: `fast` and `harness` exit 0, the identity qualifier's 339 cases pass, and `openspec validate` is clean.

## Findings

None.

## Limits

- **The model is scripted,** and the uncertain call comes from a killed process, not a real provider failure.
- **A member's screen is arranged.** The refusal on the page uses a fulfilled reply. The member's real refusal was seen at the route. The page shows the form to anyone who can read the run, since it can't tell their role, and says only the owner can record it.
- **The page doesn't confirm a cancel,** and no source asks it to.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
