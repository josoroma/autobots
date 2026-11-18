## Why

US-15.12, [PRD-Studio WF-02](../../../../docs/PRD/PRD-Studio.md#workflows) and [Decision 0022 D8](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). The editor can only publish what's in its text area. There's no way to keep a next version in progress without publishing it.

## What Changes

- A migration adds `public.workflow_drafts`, one per workflow, whose workspace is tied to its workflow by a composite foreign key.
  - Its RLS lets members read the draft and only an owner insert, update or delete it.
  - It adds the `public.is_workspace_owner(uuid)` helper.
  - `app_db` gains negative tests.
- `save_draft` replaces the one draft. `publish_draft` validates it and publishes it under the expected version as the next immutable version, then removes it. A stale publish creates nothing and keeps the draft. `discard_draft` removes only the draft.
- `WorkflowView` carries `draft`. The owner-only routes are `PUT` and `DELETE /v1/workflows/{id}/draft`, and `POST …/draft/publish`, refusing a member with `owner_required`.
- `ExecutionCreate.version` and `RoutineTarget.version` accept `"draft"` only to refuse it with `draft_not_runnable`: 409 for an execution, 422 for a routine. Every routine path reads its version through `pinned_version`.
- The editor opens a saved draft and adds Save draft, Publish draft and Discard draft, with a "Draft saved" badge.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workflow-definition`: one saved draft per workflow.

## Impact

- The migration, and the `app_db.py` reset and draft cases.
- `contracts/workflows.py` and `contracts/routines.py`.
- `application/workflows.py` and `application/routines.py`.
- `api/workflow_routes.py` and `api/routine_routes.py`.
- The generated contract and client.
- `workflow-editor.tsx`, and `workflows.spec.ts`, whose `Publish` locators are now exact, as is `slice-workflows.spec.ts`'s.
