# Tasks

## 1. The rename write (The owner renames a workflow; A name another workflow holds is refused; Two renames race; The name follows creation's rule; Only the owner renames)

- [x] 1.1 `WorkflowRename` in `contracts/workflows.py` with creation's name field. `rename_workflow` in `application/workflows.py`: it updates only the name, turns a unique violation into `workflow_name_taken`, and refuses another workspace's workflow with `workflow_not_found`. `PUT /v1/workflows/{workflow_id}/name` (`renameWorkflow`) is behind `OwnerWorkspace` and takes no key. Checked by pytest under `services/agent/tests`.
- [x] 1.2 Add the route to `WORKFLOW_ROUTES` in `services/agent/tests/test_refusal_responses.py`, so its `workflow_not_found` and `owner_required` replies are covered, with `workflow_name_taken` already mapped to 409. Checked by pytest under `services/agent/tests`.
- [x] 1.3 Regenerate OpenAPI and the TypeScript client with `renameWorkflow` and `WorkflowRename`. Checked by `contract_drift` in the fast profile.

## 2. What a rename leaves alone (The owner renames a workflow and only its name changes; Two renames race; Runs keep the name they ran under; Executions and routines keep binding)

- [x] 2.1 A `workflow_renamed` scenario in `tests/db/checks/workflow_run_check.py`, with a scripted model. It covers:
  - a published workflow with a draft, a description and an agent step whose Expert grants a tool;
  - after the rename: the same id, versions, hashes, draft and description, with the list, the read and Granted to giving the new name;
  - a taken name refused and then its own name accepted;
  - two renames racing, with the first held in an open transaction;
  - an execution before and one after, comparing their goals, the runs list's labels and a search by the old name, with the same version and hash bound and the later one run to its end.

  Checked by the db profile.
- [x] 2.2 In `tests/db/checks/routine_check.py`, rename the workflow a routine targets, then admit an occurrence. Its run binds the same version and hash, and the routine is unchanged. Checked by the db profile.

## 3. The seed (A workflow renamed to a seeded name is kept; A seeded workflow renamed away keeps its new name)

- [x] 3.1 `operations/concept_seed.py` follows a receipt that returned a renamed workflow to a create under a key naming that workflow, and publishes under a key naming the workflow it publishes. Checked by `concept_seed_check` in the db profile.
- [x] 3.2 Give `concept_seed_check` a third workspace from `scripts/qualify_identity.py`, seeded as before US-18.1. Rename its "Monthly FX and inflation note" to "Monthly FX note" and seed again: one "Monthly FX note", unchanged, and nothing added for it. In the fresh workspace, rename "Weekly competitor brief" and "Interview synthesis" away and seed again: both keep their names, versions, hashes and draft, and the seeded ones are added beside them, published and as a draft. Checked by the db profile.

## 4. The editor (The owner renames a workflow in the editor; The editor sends no blank name and shows a taken one's refusal; Only the owner renames)

- [x] 4.1 `use-name.ts` and `name-field.tsx` in `apps/web/components/workflow-editor/`, placed in the editor's card beside the description. The field trims what is typed, sends no blank name and carries no key, updates the heading from the returned view, and words the refusals. Checked by the web unit tests under `apps/web/tests/unit`.
- [x] 4.2 A case in `apps/web/tests/browser/workflow-rename.spec.ts`, its own spec in the `main` project, since `workflows.spec.ts` is at the line limit. It runs through the BFF:
  - the owner renames in the editor with spaces around the name, and the heading, the list and the preview show the trimmed name;
  - a cleared name sends nothing, and a taken name shows its refusal and changes nothing;
  - the API refuses an empty and a 101-character name with `invalid_request`;
  - a member reads the name and is refused a rename with `owner_required`.

  Checked by the db profile.

## 5. Documents

- [x] 5.1 Amend PRD-Studio WF-06 to "Name, labels and description", as Decision 0037's "Requirements revised" lists. Add the rename to `CODEBASE.md`. Checked by reading them against Decision 0037 N2 and N3.
