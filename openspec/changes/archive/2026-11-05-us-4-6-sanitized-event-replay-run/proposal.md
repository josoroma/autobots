## Why

A user needs an inspectable timeline that survives reconnects and tells activity, waiting, errors and evidence apart. SP-011 and SP-014 require cursor replay then live SSE, a snapshot for gaps, and only sanitized events.

## What Changes

- `application/run_projection.py`: events pass the public contract or stay out, and model-written text is redacted.
- `GET /v1/runs/{id}/events`, `/workspace` and a live `/events/stream`, with a BFF route that passes the stream through.
- `/runs/[id]`: status, goal, plan, artifacts, usage and timeline, with explicit connection and error states. Run links to the new run.

**Limits:** no list of runs, chat, role map or approvals on this screen, which belong to later stories. The stream polls the database, which is simple and fine for one local user. Retention isn't built, so gaps are arranged.

## Capabilities

### New Capabilities

- `run-workspace`: sanitized replay, live events and a run inspector.

### Modified Capabilities

None.

## Impact

New API and web routes, generated contracts, a new screen and browser tests, `apps/web/lib/bff.ts`, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or model call.
