## Why

US-15.17, [PRD-Studio RN-04 and RN-05](../../../PRD-Studio.md#runs), with [Decision 0017 Q4](../../../docs/engineering/decisions/0017-tool-catalog.md#open-questions), SP-010 and SP-012. To follow and steer a run, a person has to leave Runs today. Plan tasks also have no recorded times, so nothing can say which task is current or how long each took.

## What Changes

- **New table `app_private.plan_task_times`:** keyed by run and task, holding `started_at` and `finished_at` in database time. It is private to the runtime role.
- **The worker records the times on its fenced path:**
  - a task starts with the first tool use that serves it, in `begin_use`'s leased transaction;
  - it finishes when `complete_task` records its evidence, in that write's leased transaction;
  - a stale worker's write is refused with its use, and the first finish stands.
- **`RunWorkspace` additions:**
  - `TaskView` gains `marker` (done, current or to do), `started_at`, `finished_at`, `wall_seconds` and `tools`;
  - `PlanSummary` gains `current_task_id`, the earliest open task that has started;
  - `RunWorkspace` gains `metered_tool_calls` and `metered_tool_call_limit` for the run's root tree.

  OpenAPI and the TypeScript client are regenerated.
- **A side panel on Runs:** each row gets a Details link that sets `?run=<id>`. The panel opens under the list and shows:
  - the state, title, Expert and start time;
  - the plan, with each task's marker in words, tools and wall time;
  - spend, tokens and "N of 20 metered tool calls";
  - Open run, and Pause, Resume and Cancel by state.

  Each command sends the version the panel loaded. A stale one is refused with a reload message and a "Reload the panel" button.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `run-workspace`: plan task timing and the Runs side panel.

## Impact

- A migration, `application/tool_uses.py`, `application/plans.py`, `application/run_projection.py` and `contracts/run_workspace.py`.
- The generated contract and client.
- New `run-panel.tsx`, plus `run-list.tsx` and `app/runs/page.tsx`.
- New `tests/db/task_timing_check.py` and `task_timing_live.py`, registered in `qualify_identity.py`, a new `run-panel.spec.ts`, and `app_db.py` grant cases.
