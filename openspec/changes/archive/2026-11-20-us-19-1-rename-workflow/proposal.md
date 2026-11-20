# Proposal

## Why

US-19.1 in SPECS.md: [Decision 0037](../../../docs/engineering/decisions/0037-workflow-rename.md#decision) N1 to N6. The owner asked to rename the workflow their install was seeded with as "Monthly FX and inflation note" to "Monthly FX note", and chose to add rename to the app over updating their database. Autobots has no way to change a workflow's name once it is created. Two existing paths would also misbehave around a rename:
- `create_workflow` checks a name with a select, so a lost race reaches a generic 500;
- the concept seed creates and publishes under keys built from the seeded name, so after a seeded workflow is renamed away, seeding again replays the old receipt onto the renamed workflow, and for a draft replaces its draft.

## What Changes

- **A rename write (N1, N2, N5).**
  - `PUT /v1/workflows/{workflow_id}/name` with `{name}`, behind `OwnerWorkspace`, returns the workflow's view and carries no idempotency key.
  - The name follows creation's rule: 1 to 100 characters, unique within the workspace.
  - A name another workflow holds is refused with `workflow_name_taken`, including when the unique constraint decides a race. Renaming to the workflow's own name succeeds and changes nothing.
  - OpenAPI and the TypeScript client gain `renameWorkflow`.
- **Nothing else changes (N3, N4).** No version, graph, hash, draft, description or execution changes. Lists, the read, Granted to and the runs list show the new name. A run's goal keeps the name its execution started under.
- **The editor.** A Name field beside the description. It trims what is typed, sends no blank name, updates the heading from the returned view, and words `workflow_name_taken` and `owner_required`.
- **The seed (N6).** A workflow renamed to a seeded name is kept. When a seeded workflow was renamed away, the seed notices that its earlier receipt returns a workflow under another name. It then adds the seeded one beside it under a key of its own, and leaves the renamed workflow, its versions and its draft as they were.
- **Documents.** PRD-Studio WF-06 becomes "Name, labels and description", and `CODEBASE.md` gains the rename.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `workflow-definition`: a requirement for renaming a workflow, with its rule, its refusals and what it leaves unchanged.
- `experts`: a requirement for what the concept seed does with a workflow renamed to, or away from, a seeded name.

## Impact

- **Python:**
  - `contracts/workflows.py` (`WorkflowRename`);
  - `api/workflow_routes.py`;
  - `application/workflows.py` (`rename_workflow`);
  - `operations/concept_seed.py`;
  - tests under `services/agent/tests`;
  - checks under `tests/db/checks`, and the third seed workspace in `scripts/qualify_identity.py`.
- **Contracts:** `contracts/generated/openapi.json` and `packages/api-client/src/generated.ts` gain `renameWorkflow` and `WorkflowRename`.
- **Web:** `apps/web/components/workflow-editor/` gains the name field and its hook, with a unit test and a workflows browser-suite case.
- **No migration and no paid call.** The name check, the unique constraint and the runtime role's update grant already exist.
