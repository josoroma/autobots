---
paths:
  - "services/agent/**/*"
---

# Python and durable execution

Use `autobots-python` and, for lifecycle changes, `autobots-durable-worker`. The [Option B contract](../../docs/engineering/option-b-contract.md) owns states and recovery guarantees.

- Keep pure domain/application types separate from framework/persistence/public DTOs. FastAPI schema generation must be offline; resources belong in lifespan.
- Use explicit UTC, exact monetary units, bounded async work and cancellation propagation. Prepared lockfile environments only; checks do not sync/install.
- One LangGraph lifecycle owns execution. Enforce leases/fencing on both product and checkpoint writes; persist outbox events and operation receipts.
- Replay is not exactly-once external execution. Reconcile unknown outcomes before retry; approvals bind the actual normalized effect.
- Use canonical transitions/reducers and sanitized public projections. Do not expose raw graph streams or persist runtime clients/keys.
- Default model tests are fake and reject paid calls. Test stale ownership, cancellation, duplicate delivery and restart where behavior changes.

## Check and review

Check: the `fast` and `full` profiles of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
