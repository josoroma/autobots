# Verification — us-15-13-workflow-list-preview-executions

Change: us-15-13-workflow-list-preview-executions
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 5 of 5 tasks complete. 1 requirement added to `workflow-screens`.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **Arrangement:** `scripts/qualify_identity.py` gives an owner a US$10.00 daily cap and two Experts. Research analyst grants `calculate` and `read_csv` and binds the executor to Sol. Brief writer grants `save_artifact`.
  - "Weekly brief" has versions 1 and 2: input, research, write, an approval gate and output, with labels. It also has a draft and three executions: one reported, one failed with an unreported charge, and one still running.
  - "Plain totals" has two published versions.
- **"List with tabs and search":** observed in `python3.12 scripts/verify.py --profile db` (exit 0), `workflow-list.spec.ts` (passed).
  - Weekly brief's row shows:
    - its description;
    - "Research analyst → Brief writer";
    - Version 2 and a Draft badge;
    - 5 steps;
    - "Running, N minutes ago";
    - 3 runs.
  - Plain totals shows no description, "None", no draft, "Never run" and 0 runs.
  - The tabs read All 2, Published 2 and Drafts 1, and Drafts lists only Weekly brief.
  - Searching "plain" puts `q=plain` in the URL and leaves one row. axe found no violations.
- **"Preview a version":** observed in `workflow-list.spec.ts` (passed).
  - The version switch offers Version 2, Version 1 and Draft, and starts at 2.
  - Steps are in the order in, research, write, gate, out.
  - Research shows "Find sources", Research analyst, `openai/gpt-6.1-sol-20260929` and "calculate, read_csv".
  - Write shows Brief writer, `openai/gpt-6.1-terra-20261026` and "save_artifact".
  - The gate reads "Approval gate: a person approves before the run continues."
  - Switching to version 1 and to the draft shows their own write labels, and the URL keeps `version`. axe found no violations.
  - `test_workflows.py` covers `step_order`.
- **"Recent executions":** observed in `workflow-list.spec.ts` (passed). Newest first:
  - Version 2, Running, "≈ US$0.05, estimated", still running;
  - Version 2, Failed, "≈ US$0.04, estimated", 2m 00s;
  - Version 1, Succeeded, "US$0.12, reported", 1m 05s, linking to its run.
- **"A budget per execution":** observed in `workflow-list.spec.ts` (passed).
  - The editor's Budget select offered twenty choices up to US$5.00.
  - Running with US$2.50 sent `budget_micro_usd: 2500000`, got 201, and the run froze `limit_micro_usd` 2500000.
  - A request with US$5.25 got 422 `budget_out_of_range`, and the execution count rose only by the first.
- **Found during verification, fixed before this record:**
  - The first `db` run failed for three reasons:
    - The spec's name link also matched "Preview Weekly brief", so it now matches exactly.
    - Workflows overflowed 238px sideways at 400% zoom in `slice-visual`. The Experts, Steps, Last execution and Runs columns now hide below the container's `@xl` width.
    - The next run read a duration of 1m 59s for a two-minute run. Duration was measured from the execution's own timestamp, which differs by milliseconds. It's now measured from the run's admission to its last change, rounded to the nearest second.
  - The final run passed every check, including `slice-visual` for Workflows in both themes and at both zooms.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed (exit 0), with 573 identity cases and all 84 main-suite tests.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
