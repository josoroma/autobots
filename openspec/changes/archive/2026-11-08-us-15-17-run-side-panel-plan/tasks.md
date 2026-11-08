# Tasks

## 1. Task times (Task times on the fenced path)

- [x] 1.1 Add `app_private.plan_task_times` by migration. Record a task's start in `begin_use`'s leased transaction and its finish in `complete_task`'s, in database time, keeping the first finish

## 2. Read model (The panel)

- [x] 2.1 Add `marker`, task times, `wall_seconds`, per-task `tools`, `current_task_id` and the root tree's metered-call count to `RunWorkspace`, then regenerate OpenAPI and the TypeScript client

## 3. Panel (The panel; Controls with the expected version)

- [x] 3.1 Build the side panel on Runs: a Details link per row, Open run, and Pause, Resume and Cancel with the version the panel loaded, a reload message and a reload button

## 4. Coverage

- [x] 4.1 Cover the fenced times, including the stale worker, on a disposable stack in `tests/db/task_timing_check.py`, and the panel and controls in `run-panel.spec.ts` with axe
