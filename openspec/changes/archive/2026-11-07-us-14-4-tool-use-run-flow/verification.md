# Verification — us-14-4-tool-use-run-flow

Change: us-14-4-tool-use-run-flow
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 2 reqs |
| Correctness | 3/3 scenarios observed in browser runs on a disposable stack with real Auth |
| Coherence | Followed the proposal, with one addition recorded below (migration 39) |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Live and reloaded tool use | PASS | `apps/web/tests/browser/run-workspace.spec.ts` "US-14.4: tool uses show live…", run by `scripts/qualify_identity.py` in the `db` profile. `tests/db/tool_use_view_check.py` leaves a claimed, running run with two uses. The page lists them in order: `calculate` with task "Add the totals", inputs "operation: sum", result "result: 3", "Succeeded"; `publish_artifact` with "No plan task" and "Denied: tool not granted". With the stream live, `tests/db/tool_use_live.py` makes a `save_artifact` call through the same gateway, and a third row appears without a reload: task "Save the note", inputs "path: outputs/live.md; media_type: text/markdown", "Succeeded"; the saved text "written live" isn't on the page. After a reload the same three rows show, ids ascending and unique |
| Flow view | PASS | Same spec, "US-14.4: the workflow monitor…": an execution of a read-then-artifact workflow, run by the worker loop in the arranging check, shows `read_run_file` once under "Node read" and `save_artifact` under "Node save" and not under read; the input node has no section. The arranging check also confirms the rows' instance keys: read with `read_run_file`, save with `save_artifact` and `publish_artifact` |
| Accessible list | PASS | Same live test: the polite live region reads "save_artifact: Succeeded. 3 tool uses." after the new use, the list is a captioned table under the "Tools used" heading with column headers, and axe found no WCAG 2.1 AA violation on the run page or the monitor. The visual suite then measured the run and monitor surfaces in both themes with no finding |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `identity_qualification` (main browser suite 55 passed, the slice suite with the visual measurements 33 passed), `app_db_qualification`, `persistent_apply_qualification`, `non_mutation_guard` and the rest |
| `openspec validate us-14-4-tool-use-run-flow` | 0 | valid |

## Findings

**Added:** migration 39 records each use's workflow node instance. A workflow's nodes share their execution's run, so without it the monitor couldn't place a use under its node.

**Found and fixed:**
- The visual suite timed out on the run page after Tools used was added. Bounding its wait for a settled page, and naming what was still open, showed a superseded `tool-uses` read left open: the hook ignored a stale response without aborting it. Both catalog hooks now abort a superseded read. The visual suite keeps the bounded wait, so a page that never settles fails in a minute with the open request named, rather than after ten.
- An earlier qualifier run was started by mistake and overlapped another; it removed its own Docker resources (45 before, 45 after), and only the clean reruns are reported.

## Limits

- The live use comes from a helper calling the gateway on a claimed run, not from a model; that's the same path a model's call takes after the loop.
- **The persistent install wasn't migrated.** Migrations 38 and 39 wait for an owner.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
