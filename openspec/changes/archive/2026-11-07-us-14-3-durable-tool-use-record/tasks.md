# Tasks

## 1. Record (Record every dispatch)

- [x] 1.1 Migrate `app_private.tool_uses`, private and cascading with its run
- [x] 1.2 Record every dispatch from the gateway, with the served plan task, fenced by the lease
- [x] 1.3 List a run's or a root's uses by cursor with the task's title, through `GET /v1/runs/{run_id}/tool-uses`

## 2. Project (Public projection and events)

- [x] 2.1 Project public fields after redaction, URLs without query or fragment, digests and sizes otherwise
- [x] 2.2 Add `tool.use.started` and `tool.use.completed` to the union, the generated client and the run workspace, skipping unknown types

## 3. Fence and meter (Fenced and budgeted)

- [x] 3.1 Count metered calls per root tree and deny the 21st before the tool runs
- [x] 3.2 Cover the three scenarios in `tests/db/tool_use_check.py`, run by `scripts/app_db.py` on a disposable stack
