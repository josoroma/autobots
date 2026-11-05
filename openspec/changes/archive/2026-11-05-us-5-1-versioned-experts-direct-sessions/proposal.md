## Why

An Expert is a durable product object (PRD 8.2). Work needs a chosen revision that later edits can't change, and routing that adds no implicit model or broader grant.

## What Changes

- Migration: `experts`, immutable `expert_versions`, `sessions`, and a run's session, Expert and revision.
- `application/experts.py`, `api/expert_routes.py`: Expert and revision APIs, sessions that pin revisions, and routing limited to a coordinator's list.
- Admission freezes the revision's tools, instructions and model bindings into the run. The loop uses them, and the gateway enforces them.
- Screens: `/experts`, the editor at `/experts/[id]`, and `/sessions/[id]`, and the run page shows its Expert.

**Limits:** a coordinator here is routing by the user's choice among its list, with no model making the choice, and specialists are US-5.2. Skills are stored as references, and nothing loads them, which is US-8.2. Connectors don't exist, so none can be granted. The editor offers the executor role only, and the API takes all of them.

## Capabilities

### New Capabilities

- `experts`: versioned Experts, sessions and bounded routing.

### Modified Capabilities

None.

## Impact

A migration, new modules, routes, screens and tests, `RunRequest`, `run_routes.py`, `goal_loop.py`, regenerated contracts and row types, `scripts/app_db.py`, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or model call.
