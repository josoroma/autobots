# Tasks

## 1. Data and domain (Optional description; Labels bump the IR version)

- [x] 1.1 Add a nullable workflow description by migration
- [x] 1.2 Add an optional node `label` at IR version 2 in the domain, keeping version 1 valid and hashed as before, with shared fixtures for both versions
- [x] 1.3 Expose both in Pydantic and FastAPI (create, view, `PUT …/description`), then regenerate the contract and client

## 2. Editor

- [x] 2.1 Edit the description and the step labels in the workflow editor

## 3. Coverage (all scenarios)

- [x] 3.1 Cover the scenarios in `test_workflows.py`, the shared fixtures, `workflow_run_check.py` (publish, run and an arranged pre-change version) and `workflows.spec.ts` on a disposable stack
