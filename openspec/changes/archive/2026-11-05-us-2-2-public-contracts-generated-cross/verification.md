# Verification — us-2-2-public-contracts-generated-cross

Change: us-2-2-public-contracts-generated-cross
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `165d29e`, working tree with this change. Local static and fixture evidence; no service, database or model call.

## Scenarios

**Generate without credentials or services: observed.**
- `sandbox-exec` denying outbound network with `env -i`: `generate_contracts.py check` exit 0. Inside pytest, the socket block is in force and `openapi_document()` still returns all schemas.
- Drift, arranged in a disposable copy: a clean copy exits 0. A changed Pydantic field exits 1, naming `openapi.json` and `generated.ts`. `write` then `check` exits 0, and the client gained `title: string`. A hand-edited client exits 1. A missing prepared environment exits 2.
- `full` exit 0 under `env -i`, including `contract_drift`, `api_client_typecheck` and `api_client_tests`. `fast` and `harness` exit 0.
- Boundaries: `domain/`, `persistence/` and `contracts/` are separate, and adapters convert explicitly. A response built from a row holds neither the lease nor the checkpoint value. An unknown stored status raises.

**Validate at trust boundaries: observed in both languages.** `contracts/fixtures/boundary-cases.json` has 25 cases, read by both pytest and `node --test`, with both exit 0 (59 Python tests, 29 TypeScript tests). Refused in both: a non-UUID, numeric or empty identifier; fractional, negative, string, boolean and above-range money; non-date, offset-less, non-UTC and numeric timestamps; unknown and wrong-case statuses, and an unknown event type; a wrong schema version; a missing field; and private fields on a run and in an event payload. Four valid cases pass in both. A TypeScript test shows a value cast to `unknown` is still refused, and a response failing its contract is refused after `requestJson`.

## Findings

- **Decision the sources leave open:** the generator and validator are project code, not a registry tool, covering only the JSON Schema subset in use. It adds no dependency and can be replaced without changing the contracts. An unsupported schema keyword is silently ignored by `runtime.ts`, so a new keyword in a contract needs a matching validator and fixture. If you'd rather use `openapi-typescript` and `zod`, this is the moment.
- **No real client operation yet.** No route exists, so `generated.ts` has parsers and no request function. Operation generation is checked on a fixture document only. `requestJson` was exercised with a fake `fetch`.
- **Requests are not sent with bodies yet**, since `requestJson` has no body parameter. US-2.5 or the first mutation route must add one.
- **Boundary validation is exercised by parsing,** not by real HTTP. The app has no routes.
- **Graph state is absent** from the explicit boundaries, because it belongs to the worker stories.
- **The state table is now in two places:** `domain/runs.py` and the fixture checker in `tests/faults/state/check.py`, which is deliberately independent.
- **US-1.3's scaffold allow-list, web dependency and placeholder tests were removed.** They guarded "no product code yet", which ended here, and US-1.3's archive keeps its record. The unused-SDK import rule stays and runs in `full`. `test_manifests.py` still passes, offline.
- **Runbook:** the added section's commands were run.
- This is not H1 or product acceptance.
