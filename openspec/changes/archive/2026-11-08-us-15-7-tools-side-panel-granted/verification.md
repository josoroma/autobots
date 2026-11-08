# Verification — us-15-7-tools-side-panel-granted

Change: us-15-7-tools-side-panel-granted
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 4 of 4 tasks complete. 1 requirement added to `tool-catalog`.
- **"Group list and side panel":** observed in `python3.12 scripts/verify.py --profile full` (exit 0, 38 browser tests). `tools.spec.ts` "group counts, text filter, side panel and Copy schema" passed:
  - every group's count equals its rows;
  - searching "calculate" puts `q=calculate` in the URL and leaves one row;
  - its title opens `[data-panel="calculate"]` with `tool=calculate` in the URL, keeping `q`, and "Open as a page" links to `/tools/calculate`;
  - axe reports no violations;
  - `/tools/calculate` still opens the page.
  
  "filters live in the URL, so a view can be linked" still passed for provider and availability.
- **"Granted to":** observed in `python3.12 scripts/verify.py --profile db` (exit 0), `experts.spec.ts` "a tool's detail lists who it's granted to now" (passed). Against an arranged workspace, `read_csv`'s panel lists:
  - Expert Market watcher, version 1;
  - Expert Issue triager, version 1;
  - Workflow Nightly triage, version 1, whose published agent step uses Issue triager.
  
  It doesn't list Old granter, which granted `read_csv` only in version 1. The API returns the same. axe reported no violations.
- **"Copy schema":** observed in the same `tools.spec.ts` test. The clipboard holds JSON equal to `/api/v1/tools/calculate/versions/1`'s `input_schema`, and the status reads "Copied the input schema of version 1."
- **Found during verification, fixed before this record:**
  - axe found `scrollable-region-focusable` in the narrower panel, so the field tables and schema `pre` became focusable, named regions.
  - Under heavy machine load (a load average around 10, from the endpoint-security agents), several `db` runs failed on timeouts in unrelated suites. They also exposed a race in `runs.spec.ts`, where a stale row could satisfy a count before the filtered response arrived. The test now waits for each filtered response (task 2.3).
  
  The final `db` run (exit 0, including `slice-visual`) and `fast` (exit 0) passed on the final inputs.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
