# Verification — us-15-11-workflow-description-node-labels

Change: us-15-11-workflow-description-node-labels
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 5 of 5 tasks complete. 1 requirement added to `workflow-definition`.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **"Optional description":** observed in `python3.12 scripts/verify.py --profile db` (exit 0).
  - In `workflows.spec.ts`, two workflows were created through the BFF, one with "Shouts the topic back" and one without. Read back through the BFF, the first returned its description and the second `null`.
  - A description saved in the editor persisted across a reload and left `latest_version` at 0.
  - In `workflow_run_check.py`, cases "a workflow keeps its optional description, and one without has none" and "a description can be added later without a new version" passed.
- **"Labels bump the IR version":** observed in the same run.
  - In the editor, labelling step `up` changed the graph to `ir_version: 2` with the label. It validated and published as version 1, with `ir_version` 2 and labels `[null, "Shout it", null]`. Clearing the label returned the draft to IR version 1.
  - Through the BFF, an unlabelled graph validated and published at IR version 1, with the same hash the validate endpoint gave.
  - On the database, the labelled graph was stored at IR version 2 and ran to `succeeded` with output `LOUD`.
  - The unlabelled graph was stored with no `ir_version` or `label` keys, identical to its raw form, with the raw hash. It ran to `succeeded` with output `QUIET`.
  - Unit tests in `test_workflows.py` cover the same hash through the contract, normalization to version 2, and the refusals `label_needs_ir_version_2` and `unknown_ir_version`.
  - Shared fixtures for both IR versions, an unknown version and an empty label pass in Python (`test_contracts.py`) and TypeScript (`contract.test.ts`), under `fast`.
- **"Versions published before the change are untouched":** observed in `workflow_run_check.py`, with the version arranged as published before the migration. Its stored graph and hash were inserted as they were written then.
  - An execution created afterwards bound version 1 with exactly that hash.
  - It ran to `succeeded` with output `KEPT`.
- **Found during verification, fixed before this record:** the first `db` run failed `app_db` on "generated public row types match the schema". `packages/db-types` lacked `workflows.description`, and `python3.12 scripts/app_db.py types` regenerated it. The rerun passed every check.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed (exit 0), with 567 identity cases, including the existing workflow and slice-workflows suites.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
