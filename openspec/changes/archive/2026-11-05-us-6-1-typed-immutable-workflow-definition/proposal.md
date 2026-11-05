## Why

A workflow must validate before it can run, and a run must reference the exact graph it was given. PRD 7.3 and SP-016 require typed ports, immutable versions and rejected cycles, and they treat a model's graph as a proposal.

## What Changes

- `domain/workflows.py`: the documented subset of ten blocks, with typed ports, and validation returning typed errors.
- `public.workflows`, immutable `workflow_versions`, and `workflow_executions`, each execution holding its exact version, hash and block versions.
- `POST /v1/workflows/validate`, create, read, publish and create-execution routes. Publishing is owner-only.

**Limits:** nothing runs an execution, which is US-6.2, and the editor is US-6.3. A foreach can't be nested, a choice the sources leave open. Port types are the five needed here. The hundred-item cap is my choice, since the sources ask only for a bound.

## Capabilities

### New Capabilities

- `workflow-definition`: typed validation, immutable versions and exact bindings.

### Modified Capabilities

None.

## Impact

A migration, new modules and routes, regenerated contracts and row types, unit, DB and browser tests, `scripts/app_db.py`, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or model call.
