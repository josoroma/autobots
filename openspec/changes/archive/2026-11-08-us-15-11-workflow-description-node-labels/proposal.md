## Why

US-15.11, [PRD-Studio WF-06](../../../../docs/PRD/PRD-Studio.md#workflows). A workflow has only a name, and a graph's nodes have only an ID and a block. Neither lists nor previews can say what a workflow or one of its steps does.

## What Changes

- A migration adds a nullable `public.workflows.description` of 1 to 500 characters.
  - `WorkflowCreate` takes it, and `WorkflowView` returns it.
  - `PUT /v1/workflows/{id}/description` (owner) replaces or removes it without creating a version.
- Workflow IR version 2 adds an optional node `label` of 1 to 80 characters, through `WorkflowNode.label` and `WorkflowGraph.ir_version`.
  - `domain.workflows.ir_normalized` leaves out an absent label or IR version, so a version 1 graph is stored and hashed exactly as before.
  - A graph whose nodes carry labels is stored at IR version 2.
  - `validate_graph` refuses an unknown IR version (`unknown_ir_version`), and a label on a graph that declares version 1 (`label_needs_ir_version_2`).
- Shared fixtures in `contracts/fixtures/boundary-cases.json` cover both IR versions in Python and TypeScript.
- The editor adds a Description field with Save description, and a Step labels list that writes each node's label into the graph and sets or clears IR version 2.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workflow-definition`: descriptions and IR version 2 labels.

## Impact

- `domain/workflows.py`, `contracts/workflows.py`, `application/workflows.py` and `api/workflow_routes.py`.
- The migration, and the generated contract and client.
- `workflow-editor.tsx`.
- The shared fixtures and both contract tests, `test_workflows.py`, `workflow_run_check.py` and `workflows.spec.ts`.
