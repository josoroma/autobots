# Verification — us-15-12-workflow-drafts

Change: us-15-12-workflow-drafts
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 5 of 5 tasks complete. 1 requirement added to `workflow-definition`.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **"One saved draft":** observed in `python3.12 scripts/verify.py --profile db` (exit 0).
  - In `workflows.spec.ts` (passed), the owner saved two drafts from the editor. The workflow held one draft, the second graph, at IR version 2 with its label.
  - The member, who isn't the owner, sent a save to workspace A through the BFF and got 403 `owner_required`, and the draft was unchanged.
  - The `app_db` RLS cases passed:
    - A member reads the draft, and another workspace reads none.
    - The owner saves over the draft.
    - A non-owner member and another workspace each change and discard nothing, and their inserts are refused by row-level security.
    - A draft can't name another workspace than its workflow's (composite foreign key), and anonymous access is denied.
- **"Publish from the draft":** observed in `workflows.spec.ts` (passed).
  - With the draft beside version 3, a publish naming expected version 2 got 409 `workflow_version_conflict`. `latest_version` stayed 3 and the draft remained.
  - Publish draft in the editor then created version 4 from the draft's graph and removed the draft.
- **"Discard leaves published versions alone":** observed in `workflows.spec.ts` (passed). Discard draft in the editor removed the draft. Versions 1 to 3 kept their exact version-and-hash list, and version 4 kept its hash.
- **"Runs bind only published versions":** observed in `workflows.spec.ts` (passed).
  - With a draft saved, an execution naming `"draft"` got 409 `draft_not_runnable`, and a routine naming it got 422 `draft_not_runnable`.
  - An execution naming version 4 got 201, bound to version 4 and its hash.
  - Every routine path reads its version through `pinned_version`, which refuses a draft.
- **Found during verification, fixed before this record:**
  - The first `db` run failed `app_db` on generated row type drift, as `workflow_drafts` is a new public table. `scripts/app_db.py types` regenerated the types.
  - The next run failed my spec twice:
    - It read the draft before the second save's response arrived, so it now waits for that `PUT`.
    - The member belongs to two workspaces, so the request got `workspace_required`. It now names workspace A, and then got `owner_required` as intended.
  - Existing `Publish` button locators in `workflows.spec.ts` and `slice-workflows.spec.ts` are now exact, as "Publish draft" also contains the word.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed (exit 0), with 568 identity cases and all 80 main-suite tests.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
