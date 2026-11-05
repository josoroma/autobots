## Why

A consequential effect needs a decision bound to exactly what was proposed. SP-013 and PRD 9.2 require a proposal persisted before the wait, decisions validated against it, and no way for an altered, expired or replayed decision to authorize other work.

## What Changes

- `public.approval_requests`, with the operation ID, tool and version, argument and scope hashes, and expiry.
- `application/approvals.py`: the gateway's gate, decisions and expiry. A proposal and the run's wait commit together.
- The gateway no longer refuses consequential tools outright. It stops at a proposal, and the replayed tool step finds the decision.
- `GET /v1/approvals`, `POST /v1/approvals/{id}/decision` and the inbox at `/approvals`. Decisions are owner-only.

**Limits:** no real consequential tool exists, so a fixture tool stands in, and US-5.4 and US-7.2 follow. Editing arguments in the inbox isn't built, so a changed request is a new proposal from the model. The 24-hour expiry is my default, since the sources set none. This uses its own stop and replay rather than a LangGraph interrupt.

## Capabilities

### New Capabilities

- `approvals`: argument-bound approvals with a durable decision wait.

### Modified Capabilities

None.

## Impact

A migration, new modules and screens, the gateway, `goal_loop.py`, `runs.py`, the event contract, regenerated clients and row types, `scripts/app_db.py`, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or model call.
