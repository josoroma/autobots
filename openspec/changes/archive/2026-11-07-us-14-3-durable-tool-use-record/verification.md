# Verification — us-14-3-durable-tool-use-record

Change: us-14-3-durable-tool-use-record
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 7/7 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed on a disposable stack through the runtime role |
| Coherence | Followed `design.md` |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Record every dispatch | PASS | `tests/db/tool_use_check.py`, run by `scripts/app_db.py` (and again inside the `db` profile): with a two-task plan, `calculate`, `read_run_file` and `save_artifact` succeed and an ungranted `publish_artifact` is denied `tool_not_granted`, unchanged by recording. The listing returns four rows in order: sequence 1 to 4, versions 1, 1, 1 and none, tasks t1 "Add the totals", t1, t2 "Save the note" and none, outcomes and codes as dispatched, groups general, files, files and none, database times with requested before finished and a duration. The save carries its receipt's operation ID and the others none. Authenticated and anon are refused the table, and the runtime role can't delete from it |
| Public projection and events | PASS | Same check: each use appended `tool.use.started` then `tool.use.completed`, 8 events that all parse as the typed `RunEvent` at schema version 1 and hold no field beyond identifiers, tool, version, group, task, outcome, code, duration and operation ID. A fixture metered tool with public `query`, `url` and `title` lists `url` as `https://example.com/a/b` from `...?token=abc#frag`, omits its private `note` and its `page_text`, and the save lists `path` and `media_type` with no body. A fake key the tool sent to its stand-in transport was found in no table of `public`, `app_private` or `agent_runtime` (rows, events, receipts and checkpoint tables included) and in no captured log line, and the page text in no table |
| Fenced and budgeted | PASS | Same check: with its lease expired, a worker's call is refused `lease_lost` and its run's tool-use count stays 0. On a fresh root run, 20 metered calls succeed and the 21st is denied `tool_budget_exceeded` with the transport's request count still 20; an unmetered call then still runs. The root's listing holds all 22 uses, pages by cursor as 5 then 17 with no repeat, and another workspace gets nothing |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/app_db.py qualify` | 0 | every case passed, the US-14.3 cases among them |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification`, `identity_qualification` (whose goal loops, workflows, assignments and run-workspace browser specs now record every dispatch), `persistent_apply_qualification`, `non_mutation_guard` and the rest passed |
| `openspec validate us-14-3-durable-tool-use-record` | 0 | valid |

## Findings

None blocking.

**Suggestion, not blocking:** `GET /v1/runs/{run_id}/tool-uses` is exercised through `list_tool_uses` and the schema test, not by an HTTP call against a stack. US-14.4's screens read it through the BFF.

## Limits

- No checkpoint was written in the key scan's run, so the scan proves checkpoint tables hold no key, not that a loop's checkpoint would leave one out. The gateway never puts a key in a scope, and providers' keys are read inside their adapters (US-14.5).
- A use whose completion lost the lease stays open, with no outcome. Its effect, if any, is in its receipt.
- **The persistent install wasn't migrated.** Migration 38 waits for an owner.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
