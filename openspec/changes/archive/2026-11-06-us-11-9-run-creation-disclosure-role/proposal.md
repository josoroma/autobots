## Why

US-10.2's finding B3, and Decision 0009's added run-screens story: a person can start a cloud run without seeing what it will use, send or spend, can't pick a model for one run, and can't read a finished run's costs, errors or evidence.

## What Changes

- MP-07's disclosure on every run-creation screen: the selected model and roles, the budget and the categories of data sent, with nothing sent before Run.
- A per-run model choice on the goal and session screens, refused by the server when it isn't approved, with the draft kept.
- The run workspace shows the complete frozen role map, what dispatches, and token and spend budgets.
- The inspector shows reported and estimated costs labeled apart, errors and evidence links.

## Capabilities

### New Capabilities

- `run-disclosure`: what a run discloses before starting, how one run's model is chosen, and how its budgets, costs and errors read afterward.

### Modified Capabilities

None.

## Impact

`contracts/run_commands.py`, `contracts/run_workspace.py`, `application/run_projection.py`, `api/run_routes.py`, `domain/models.py`, generated clients, a new disclosure component, the composer, session and workflow screens, the run workspace, the inspector, `tests/web/fixture_worker.py` and a new browser suite. No schema change, and no model call.
