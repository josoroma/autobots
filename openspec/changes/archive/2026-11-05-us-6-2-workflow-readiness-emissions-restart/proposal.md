## Why

Iteration and joins must not overwrite or lose outputs. PRD 7.3 and LC-14 require readiness over typed inputs, distinct instance and port identities, and skipped, waiting and failed branches that stay distinguishable through a restart.

## What Changes

- `domain/workflow_execution.py`: pure readiness, with one instance per iteration.
- `workflow_node_instances` and insert-only `workflow_emissions`.
- `application/workflow_runner.py`: runs an execution under a lease, committing each instance as it finishes. Reads and artifacts use the gateway, an approval step uses the approval gate, and an agent step is an assignment.
- `create_execution` now admits a run, so executions share jobs, leases, cancellation and budgets.

**Limits:** no product worker process, as before. No foreach inside a foreach. Monitoring screens are US-6.3. The HTTP/read connector in the PRD's subset is only a run-file read, since no connector exists.

## Capabilities

### New Capabilities

- `workflow-execution`: readiness, emissions and restart semantics.

### Modified Capabilities

None.

## Impact

A migration, new modules, `workflows.py`, `goal_loop.py`, contracts, tests, `scripts/app_db.py`, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or paid call.
