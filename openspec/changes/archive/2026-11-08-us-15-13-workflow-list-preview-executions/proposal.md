## Why

US-15.13, [PRD-Studio WF-01 and WF-03 to WF-05](../../../../docs/PRD/PRD-Studio.md#workflows) and [Decision 0022 D11](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). Workflows lists a name, version, node count and hash. It shows nothing of what a workflow does, how it runs, what its executions cost, or how much an execution may spend.

## What Changes

- `WorkflowView` adds facts from the latest published version and the executions:
  - the Experts its agent steps use, in step order;
  - its step count;
  - the last execution, with state and time;
  - its run count.
- `domain.workflows.step_order` sorts nodes so each follows what feeds it, with ties in listed order.
- `GET /v1/workflows/{id}/executions` lists the ten newest executions. Each shows its version, state, ledger spend (charged, outstanding, unreported) and duration.
- `GET /v1/workflows/{id}/preview?version=N|draft` returns the chosen version's steps in order. Each step shows its label, Expert, executor model (resolved as a run started now would) and the Expert's tools, with approval steps marked.
- `ExecutionCreate.budget_micro_usd` follows the D11 rules (US$0.25 to US$5.00 in US$0.25 steps, within today's cap) with the same typed refusals as a goal run, and is frozen as the run's limit.
- Workflows adds:
  - tabs for All, Published and Drafts, with counts;
  - a search by name kept in the URL;
  - rows with the description, the Experts chain, the version and draft badges, steps, last execution and runs;
  - a Preview panel with a version switch, the steps, the approval gate in words, and recent executions labelled estimated or reported.
  
  The editor's run section adds a Budget select.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workflow-screens`: list facts, preview, executions and the execution budget.

## Impact

- New `application/workflow_overview.py`, plus `domain/workflows.py`, `contracts/workflows.py`, `application/workflows.py` and `api/workflow_routes.py`.
- The generated contract and client.
- `workflows-panel.tsx` (rewritten), `app/workflows/page.tsx` (Suspense) and `workflow-editor.tsx`.
- `scripts/qualify_identity.py`, `test_workflows.py` and the new `workflow-list.spec.ts`.
