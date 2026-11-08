# Verification — us-15-17-run-side-panel-plan

Change: us-15-17-run-side-panel-plan
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 2 requirements |
| Correctness  | 2/2 requirements, 3/3 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0. Ruff, mypy, pytest (803 passed), contract drift, web lint, format, types and unit tests.
- **`python3.12 scripts/verify.py --profile full`:** exit 0. The production build and its browser suite.
- **`python3.12 scripts/verify.py --profile db`:** run twice.
  - **First run:** it exposed a bug in the new check. The default registry has no planning tools, so `complete_task` was `tool_not_registered`. It also showed that the visual walk's 200-stop bound was too small for Runs, now that each row has two controls. Both were fixed.
  - **Second run (2026-11-08T15:51Z):** `identity_qualification` passed with every case below. `app_db_qualification` failed once in `tests/db/recovery_check.py`'s Mac-sleep scenario: the timed sleeping worker was taken over before its slow call. `python3.12 scripts/app_db.py qualify` then passed alone, with 508 cases and exit 0, including the new grant cases. Nothing in this change touches that scenario's path, but the full `db` profile wasn't rerun green in one pass.

## Scenario: Task times on the fenced path — PASS (disposable stack)

`tests/db/task_timing_check.py` ran in `identity_qualification`. Its run is bound to the Expert "Figures analyst", with tasks gather, write (after gather) and review (after write).
- **Start:** the first worker's `calculate` served gather and started it, between two database-clock readings taken around the call.
- **Stale worker:** after its lease ran out and a second worker claimed the run, the first worker's `save_artifact` and `complete_task` were both denied with `lease_lost`. There were 0 new uses, no finish and no evidence.
- **Current worker:** its gather finish and the start of write (served by `save_artifact`) are both between the database-clock readings, with start ≤ finish.
- **Repeat:** a repeated finish kept the first.
- **Read model:** gather is done, write is current (`current_task_id` write) and review is to do.
  - Tools: gather has `calculate, save_artifact`, write has `save_artifact`, review has none.
  - Wall times: gather and write have one, review has none.
- **Metered calls:** `admit_metered` admitted three uses, counted as 3 of 20 for the root tree.
- **Grants:** the `app_db` cases confirmed that `authenticated` can't read `plan_task_times` and the runtime role can't delete from it.

## Scenario: The panel — PASS (browser, disposable stack)

`run-panel.spec.ts`, first test. The run is found with the list's filter, and its row's Details is selected. The panel shows:
- the state "Running", the title as a heading, the Expert "Figures analyst" and the start time;
- the task markers Done, Current and To do;
- each task's tools and wall time, with "—" for the to-do task;
- the spend "US$0.00 of US$1.00", the tokens "0 in, 0 out" and "3 of 20 metered tool calls";
- an "Open run" link to `/runs/<id>`.

Details has `aria-expanded="true"`, and axe found no violations at WCAG 2.2 AA. The visual walk also passed the Runs surface in both themes, at 200% and 400% zoom.

## Scenario: Controls with the expected version — PASS (browser, disposable stack)

`run-panel.spec.ts`, second test.
- **Stale press:** with the panel open, `tests/db/task_timing_live.py` moved the run's version through the current worker's VERIFY and then REPAIR, leaving it running. Pause was then refused with "This run changed after the panel loaded, so nothing was done.", and the API still read `running`.
- **After reload:** "Reload the panel" showed the new version. Pause then paused the run (the API read `paused` at version +1), the panel offered Resume, and the row read Paused.
- **Terminal run:** a run cancelled through its canonical transition shows Cancelled and Open run, and no Pause, Resume or Cancel button.

## Findings

- **WARNING:** the `db` profile didn't pass in a single run. Its one failure is the timing-sensitive Mac-sleep recovery scenario, which passed on the standalone `app_db` rerun. Everything this change covers passed.
- **SUGGESTION:** the visual walk's keyboard bound rose from 200 to 400 stops, because a full Runs page now has 207 controls in its main area. Every control must still be reached, but there are now two Tab stops per run row.
- **Interpretation (design.md):** a task starts at the first tool use that serves it. A task served by no use before its `complete_task` gets a wall time of zero.
- **Not established:** H1 and product acceptance. No live model call was made: every model call was scripted or a fake.
