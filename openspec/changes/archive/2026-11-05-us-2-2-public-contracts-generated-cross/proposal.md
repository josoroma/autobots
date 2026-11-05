## Why

Python, TypeScript and persisted state must not drift silently, and SP-009 and DH-06 require Pydantic to own the public API with generated consumers and runtime validation at trust boundaries.

## What Changes

- `services/agent/src/autobots/contracts/`: strict public DTOs for the initial slice: `RunSummary`, `BudgetCounters`, `RunEvent`, `RunStatusChanged` and `ErrorResponse`, with exact integer microdollars, UUIDs and UTC timestamps.
- `domain/runs.py` holds the canonical SP-010 state machine. `persistence/rows.py` holds row shapes. `contracts/adapters.py` converts explicitly, so lease and checkpoint fields never reach a response.
- `scripts/generate_contracts.py` generates `contracts/generated/openapi.json` and `packages/api-client/src/generated.ts`, offline, and detects drift. `fast` and `full` run it.
- `packages/api-client/src/runtime.ts` validates at runtime. `contracts/fixtures/boundary-cases.json` is read by both Python and TypeScript tests.

**Decision the sources leave open:** the generator is project code with no new dependency, not a registry tool. It covers the JSON Schema subset these contracts use. The sources name no TypeScript generator or validator for Option B; `zod` is named only for the other option. **Compatibility:** unknown enum values are refused at the boundary.

**Limits:** no route exists yet, so no real client operation is generated; US-2.5 adds routes. Graph state belongs to the worker stories. The US-1.3 scaffold allow-list is retired, because it existed to keep the tree free of product code.

## Capabilities

### New Capabilities

- `public-contracts`: Pydantic-owned contracts, offline generation with drift detection, and runtime validation in both languages.

### Modified Capabilities

None.

## Impact

New contracts, domain and persistence modules, generator, client package content and fixtures. Updates `scripts/verify.py`, `scripts/harness_lib.py`, `tests/toolchain/test_scaffold_scope.py`, the harness runbook and `CODEBASE.md`. No dependency install, service or model call.
