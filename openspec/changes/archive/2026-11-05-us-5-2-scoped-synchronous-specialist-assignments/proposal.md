## Why

A parent's delegation must not widen scope, duplicate a child on replay or hold a model slot while it waits. PRD 8.2 and 8.3 and SP-008 require narrowed scope, inherited roles and shared tree budgets.

## What Changes

- `app_private.assignments`, created with the child and before any dispatch, deduplicated by the parent's operation ID.
- `application/assignments.py`: an `assign_specialist` tool for coordinator runs. It intersects tools with the parent, gives the child its own output namespace and the parent's frozen policy, and runs the child synchronously.
- Calls, tools, repairs, revisions, children and time count on the root, and spend reserves on the root.
- A cancel reaches children in the same transaction, a paused or stopped parent stops its child at the next dispatch, and generic claims skip child jobs.
- The run page lists assignments.

**Limits:** a scripted model. Asynchronous specialists aren't built, by the PRD's MVP choice. A child's budget is the root's remainder, since no per-child allocation is stated.

## Capabilities

### New Capabilities

- `specialist-assignments`: scoped, deduplicated synchronous child runs.

### Modified Capabilities

None.

## Impact

A migration, new modules, `runs.py`, `worker_leases.py`, `loop_middleware.py`, `goal_loop.py`, contracts, the run page, DB checks, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or paid call.
