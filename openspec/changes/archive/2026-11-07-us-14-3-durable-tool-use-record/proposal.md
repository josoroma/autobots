## Why

US-14.3, [PRD-Tool-Catalog TU-01 to TU-07](../../../PRD-Tool-Catalog.md#tool-use-record) and Decision 0017 Q3, Q4 and Q13: only effectful tools leave a receipt, so nothing durable says which reads a run made, when, or for which task, and metered provider calls have no limit.

## What Changes

- Migration 38 adds `app_private.tool_uses`: private, no PostgREST, Realtime or browser role, cascading with its run, insert and update only for the runtime role.
- `ToolGateway.execute` records every dispatch, denials included: a row and a `tool.use.started` event before the dispatch, the outcome and a `tool.use.completed` event after, each in a transaction holding the lease. A worker that lost its lease records nothing, and is refused as before.
- "Why" is the plan task served: `complete_task`'s own task, or else the first open task whose dependencies are done and that lists the tool. No model text is stored.
- Each definition's public input and output fields are projected after its own redaction, URLs without query or fragment. Everything else is a digest and a size.
- A root run tree may make 20 metered calls. The 21st is denied `tool_budget_exceeded` before the tool runs, counted under an advisory lock.
- `RunEvent` gains `tool.use.started` and `tool.use.completed` at schema version 1. `GET /v1/runs/{run_id}/tool-uses` lists a run, or a root's tree, by cursor, with the task's title. The run workspace describes the new events and skips any type it doesn't know.

## Capabilities

### New Capabilities

- `tool-use-record`: the durable tool-use record and its events.

### Modified Capabilities

None.

## Impact

`supabase/migrations/20261107000038_tool_uses.sql`, `application/tool_uses.py`, `application/tool_gateway.py`, `contracts/runs.py`, `api/event_routes.py`, the generated contract and client, `apps/web/components/run-workspace.tsx`, `tests/db/tool_use_check.py` and `scripts/app_db.py`. **The persistent install needs migration 38 applied before it runs this code.** That isn't done here.
