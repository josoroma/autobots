---
name: autobots-durable-worker
description: Implement or review Autobots Python job and LangGraph execution semantics, including leases, checkpoint fencing, receipts, outbox, cancellation, approvals and replay recovery.
---

# Durable execution

Read `.claude/autobots.json`, the mapped contract's state/worker sections, selected story and the mapped product PRD. Use [DH-06 worker standards](../../../PRD-Development-Harness.md#durable-workers-and-model-gateway) for checks.

- Preserve one LangGraph lifecycle; Deep Agents runs bounded stages inside it. HTTP admission commits the run, job and initial outbox event transactionally; no request-local background task owns durable work.
- Use database-time leases, heartbeat and monotonic fencing. Enforce current ownership for both product writes and checkpoint/store writes; checking only before a provider request is insufficient.
- Define typed state/reducers and canonical transition guards. Test concurrent updates, terminal-state rejection and repeated commands. Avoid static edges plus `Command` routing that unintentionally execute both paths.
- Persist stable operation IDs/receipts. Unknown external outcomes require reconciliation; checkpoint replay is not exactly-once remote execution. Approval binds normalized arguments/version/scope/expiry before any effect.
- Bound model/tool budgets and child delegation; stop new admission on pause/cancel/shutdown while preserving in-flight outcome. Release scarce resources before waiting on children. Credential references remain late-bound; model bindings remain immutable.
- Project ordered sanitized events from the outbox. Browser disconnect does not cancel work; raw graph state is not a public stream.

Require meaningful failure fixtures for competing workers, stale product and checkpoint writes, lost responses, lease expiry, process death, pending approvals, cancellation and restart. Use fake inference by default; real paid qualification is separate. Return actual guarantees demonstrated and remaining recovery gaps, linked to the DH-W record.
