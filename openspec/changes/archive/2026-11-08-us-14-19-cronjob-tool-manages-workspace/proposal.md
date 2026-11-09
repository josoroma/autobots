## Why

US-14.19, [Decision 0026](../../../docs/engineering/decisions/0026-cronjob-tool-and-tool-guide.md) C1 to C10, and PRD-Tool-Catalog CJ-01 to CJ-04. The owner asked for an Automation tool, `cronjob`, that manages scheduled tasks with create, list, update, pause, resume, run and remove. Here a scheduled task is an existing routine (US-7.1).

## What Changes

- **The tool.** `cronjob` v1 is in a new group, `automation`, provider `autobots`, class `reversible_internal_write`, `free_local`, Expert-only. Its descriptor's approval is `by_action`.
- **Approval per call.** The gateway gains `approval_when(parsed)`: `list` runs without approval, and every other action waits for a person's approval. The approval's target names the action and the routine. Its arguments carry the schedule.
- **Actions** go through `application/routines.py`, with its validation and codes. Two new service functions:
  - `run_routine_now` admits one occurrence through the scheduled path's checks: overlap, the key and offer check, and `_admit`.
  - `remove_routine` sets `removed_at`.
- **Removed routines.** `list_routines`, `get_routine`, edits and evaluation ignore them, and `run` on a paused routine is `routine_paused`.
- **Migration 53:** `routines.removed_at`, with a name that is unique only among live routines.
- **The catalog contract** gains the group `automation` and the approval value `by_action`, with matching labels on the Tools page. The client is regenerated.

## Capabilities

### New Capabilities

- `cronjob-tool`

### Modified Capabilities

None.

## Impact

- **Domain and contracts:** `domain/tool_catalog.py`, `domain/tools.py` and `contracts/tools.py`, plus a new `contracts/cronjob.py`.
- **Application:** a new `application/cronjob_tool.py`, plus `routines.py`, `tool_gateway.py`, `tool_catalog.py` and `goal_loop.py`.
- **Elsewhere:** migration 53 and the schema record, the web labels, tests, the runbook and CODEBASE.
