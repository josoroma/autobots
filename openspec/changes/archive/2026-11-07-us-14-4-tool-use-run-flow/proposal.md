## Why

US-14.4, [PRD-Tool-Catalog TV-01 to TV-03](../../../PRD-Tool-Catalog.md#tool-use-views): US-14.3 records every tool use, but no screen shows them, so a run's outcome can't be traced to the tools behind it.

## What Changes

- The run workspace gains **Tools used**: one row per use, in order, with time and duration, tool and group, the plan task's title, public inputs, public outputs or a size, and outcome with its typed code. It reloads from `GET /v1/runs/{run_id}/tool-uses` whenever a `tool.use.*` event arrives, and announces the newest use in a polite live region.
- The workflow monitor gains **Tool uses by node**, one table per node instance that used a tool.
- Workflow nodes share their execution's run, so migration 39 adds `instance_key` to `app_private.tool_uses`, recorded from the gateway scope, and the listing returns it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tool-use-record`: tool uses on the run and flow screens.

## Impact

`apps/web/components/{tool-uses,run-workspace,workflow-monitor}.tsx`, `supabase/migrations/20261107000039_tool_use_instance.sql`, `application/tool_uses.py`, `contracts/runs.py`, the generated contract and client, `tests/db/tool_use_view_check.py`, `tests/db/tool_use_live.py`, `scripts/qualify_identity.py` and `apps/web/tests/browser/run-workspace.spec.ts`. **The persistent install needs migrations 38 and 39 applied before it runs this code.**
