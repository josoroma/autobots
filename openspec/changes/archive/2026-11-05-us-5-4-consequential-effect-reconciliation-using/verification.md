# Verification — us-5-4-consequential-effect-reconciliation-using

Change: us-5-4-consequential-effect-reconciliation-using
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `3767c68`, working tree with this change. A real Deep Agents graph with a scripted model, real Postgres on a disposable stack, the web app in Chromium, a real killed process, and a controlled file sink as the mock destination. `scripts/qualify_identity.py` exit 0, 213 cases, including 1 new browser test. `scripts/app_db.py types`: 335 cases passed. `--profile full` passed.

## Scenarios

**Reconcile a lost response: observed.**
- An approved effect reached the sink, with its acknowledgment lost. The receipt became `unknown`, the run paused with `outcome_unknown`, and there was 1 delivery.
- On resume, the gateway read back from the sink, the receipt became `succeeded`, and there was still 1 delivery, and the model was told it happened.
- A real worker process was killed by SIGKILL right after delivery and before its receipt (`started`). After an arranged lease expiry, the replacement classified it, read back, and didn't send again.
- A readback showing no delivery allowed one real attempt.
- With no readback, a replay doesn't resend and stays paused, and an owner's report resolves it. A report of delivery means no resend. A report of no delivery allows one retry.
- A refusal from the destination is a known failure, not an unknown.

**Keep uncertain results truthful: observed.**
- With no readback, the outcome stays `unknown`, on the run page as well as the receipt. Resume is blocked (`has_unresolvable_effect`), and a tool with a readback isn't blocked, since replay resolves it.
- A resolved outcome can't be changed, and another workspace or run can't reconcile it. In the browser a member gets 403 and another workspace 404.
- Both attempts carry the same operation identity. With an idempotent destination, a mistaken report of no delivery causes 2 attempts and 1 effect. Without one, the same mistake really does duplicate, 2 effects, and this is asserted, so nothing here claims exactly once.

## Findings

- **An owner's report is taken as stated.** The duplicate case above shows what a wrong one costs, and the page tells the owner to check the destination's records.
- **The browser check of resume being blocked is partial.** With no key saved at that point the API answers `credentials_required` first, and the test accepts either. `unknown_effect` itself is shown by the database check of what the route reads, not through the route.
- **Limits:** connector-independent, with only a mock. A real connector is US-7.2 and needs a service chosen. A run that fails with an unknown effect keeps it listed, with nothing further happening.
- **No independent review.**
