# Verification — us-15-4-run-list-projection-filters

Change: us-15-4-run-list-projection-filters
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

- **Completeness:** 8 of 8 tasks complete. 1 requirement added to `run-workspace`.
- **"One row per run with its facts":** observed on a disposable stack in `python3.12 scripts/verify.py --profile db` (exit 0), through `tests/db/run_list_check.py`. Ten runs were arranged in a fresh workspace, plus one in another workspace. These cases passed:
  - only this workspace's 10 runs are listed;
  - a goal run returns `goal`, 2 of 5 tasks, frozen `openrouter_sol`/`openrouter_terra` and 50,000 reserved;
  - an Expert run is labelled `Writer …` with 70,000 charged and nothing held;
  - a coordinator session run is labelled "Coordinator session";
  - a workflow run is labelled "Weekly …, version 1";
  - a failed run returns `tool_budget_exceeded` and `unreported`;
  - the updated time follows the created time.
- **"Status tabs with server counts":** observed in the same check, with counts all 10, active 5, needs_you 2, finished 3.
  - Active is cancelling, paused, queued, running and verifying.
  - Needs you is `waiting_approval` and `waiting_input`.
  - Finished is cancelled, failed and succeeded.
  
  In the browser (`runs.spec.ts` "status tabs, filters, paging and estimated spend on Runs", passed), against an arranged workspace of 101 runs, the tabs read "All 101", "Active 50", "Needs you 24" and "Finished 27". Needs you lists 24 `waiting_input` rows.
- **"Text and profile filters with keyset paging":** observed in the same check:
  - case-insensitive goal text matches one run;
  - an Expert's name matches its two runs;
  - the Sol profile filter returns 9;
  - `%` is a literal;
  - pages of 3 return all 10 rows in order, once each, while a run is admitted mid-paging;
  - a filtered page reports its group total;
  - a foreign cursor raises `invalid_cursor`.
  
  In the browser, "Showing 100 of 101", then Load more gives 101 unique rows. The text filter narrows to one run, and the Model filter to the Sol run.
- **"Estimated spend is marked":** observed in the browser.
  - The held run shows "≈", "US$0.18" and "estimated, of US$1.00".
  - The unreported run shows "≈" and "estimated".
  - The reported run shows "US$0.07" and "of US$1.00", with neither "≈" nor "estimated".
  - The meter's share is drawn and its words state the limit. axe reported no violations.
- **Found during verification, fixed before this record:**
  - Task 2.3: `slice-visual`'s error and loading states intercept `**/api/v1/runs`, so default filters now send no query string.
  - Task 2.4: the selected tab's shadow replaced the focus ring, at 2.45:1 in light on runs, state-loading and state-error, so it now uses a border.
  - The tab labels and counts now have a space between them, so they read "All 101".
  
  Then `full` (exit 0), `db` (exit 0, including `slice-visual` on every screen in both themes) and `fast` (exit 0) passed on the final inputs.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
- **Process note:** the planning artifacts were written after implementation began. They describe the change as built, and verification checked the code against them.
