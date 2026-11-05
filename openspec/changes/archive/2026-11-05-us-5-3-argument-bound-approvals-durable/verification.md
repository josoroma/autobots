# Verification — us-5-3-argument-bound-approvals-durable

Change: us-5-3-argument-bound-approvals-durable
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `e2ff3e6`, working tree with this change. A real Deep Agents graph with a scripted model, a fixture consequential tool, and real Postgres, the API and the web app in Chromium on a disposable stack. `scripts/qualify_identity.py` exit 0, 191 cases, including 3 new browser tests. `scripts/app_db.py types`: 335 cases passed. `--profile full` passed.

## Scenarios

**Bind the review decision: observed.**
- A changed argument hash gives `approval_mismatch`, and another workspace gets `approval_not_found`. The run keeps waiting, with no effect.
- An approval returns the run to the queue, and a repeat with its key is idempotent. The opposite decision is `approval_already_decided`.
- The approved call runs once. The next call with changed arguments stops at a second proposal, and doesn't happen.
- An approval doesn't carry to a changed scope (`approval_scope_changed`).
- A late approval is `approval_expired`, the run pauses, and nothing runs. Expiry is also applied by the worker's own pass. On resume the model is told it expired, and still nothing is sent.
- Cancelling withdraws the request. A paused run takes no decision.
- In the browser: the inbox shows the tool, version, effect and exact arguments, and a tampered hash leaves the run waiting. An owner approves and rejects through the page. A member gets 403, and another workspace gets 404 and an inbox without the request. axe reports no WCAG A or AA violation on the inbox.

**Restart during approval wait: observed, with separate worker passes.**
- The worker stops at the proposal and lets go of its job, with no effect and one model call, and a waiting run isn't claimed. The proposal and the wait commit in one transaction.
- A later pass, after the decision, replays the pending tool step with no new model call before it, and the effect happens then. Repeating the approved call reuses its receipt, so it's delivered once.
- A pause and resume return to the same wait, with no model call or new proposal.
- A rejection reaches the model as `approval_rejected`, and the effect never runs. The run then goes on to fail or replan under the model's normal limits.

## Findings

- **A real bug from US-4.6, now fixed:** the BFF's catch-all route dropped query strings, so the replay cursor and any other query never reached the API. Replay still looked right because it always started from zero. The stream's own route wasn't affected. There's now a browser case for `events?after=3`.
- **A fixture tool stands in.** No real consequential tool exists. A worker killed by a signal during the wait isn't a separate case here, since it holds nothing during the wait. A crash inside the approved effect is US-5.4.
- **Not built:** editing arguments in the inbox, so a change comes as a new proposal from the model. A decision while paused is refused rather than held. A child run's own approval wait under a parent isn't exercised, and its parent would see `assignment_paused` or `assignment_busy` until it's decided.
- **Judgment calls:** owner-only decisions, a 24-hour default expiry, and our own stop and replay instead of a LangGraph interrupt. PRD 9.2 describes an interrupt with a stable thread, and this keeps the same replay behavior without one.
- **The arguments shown are passed through `public_text`,** so a key-like value is masked and long values are cut at 4,000 characters. The hash covers the real arguments.
- **No independent review.**
