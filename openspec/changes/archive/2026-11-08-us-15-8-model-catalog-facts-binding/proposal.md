## Why

US-15.8, [PRD-Studio MD-01 to MD-03](../../../../docs/PRD/PRD-Studio.md#models). Models lists each approved model's identity only. It shows no catalog price or capability, and doesn't say where a role's binding comes from. It can't discard edits or clear every override at once.

With no saved policy, it also claims Terra as the workspace default, so `researcher` reads Terra even though admission gives it Sol, MP-01's built-in default.

## What Changes

- `/v1/models` adds each profile's catalog input and output price per 1M tokens (micro-USD) and its supported parameters as `capabilities`. The catalog's `fetched_at` sits beside `qualification`, which stays separate.
- Resolving a role policy records each role's `source`: `run_override`, `workspace_override`, `workspace_default` or `builtin_default`.
  - The effective policy on `/v1/settings/model-policy` carries it.
  - A run's frozen snapshot carries it, so the run's role map shows it. A run admitted earlier shows no source.
- A workspace policy may have no default (`default_profile: null`), so each role without an override takes its built-in default. With no saved policy, `default_profile` is `null`, not Terra. A migration makes the column nullable.
- `POST /v1/settings/model-policy/reset`, owner only, with `expected_version`. It clears every role override and keeps the default. A stale version is refused with `stale_version`.
- On Models, each profile shows its prices, its capabilities labelled "from the catalog", and the fetch time. Each role shows its source.
  - The form adds Discard, which returns it to the saved state, and Reset all.
  - A summary reads "N of 14 roles follow the workspace default", counted from the saved policy.
  - The workspace default offers "Built-in default".

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-policy-settings`: catalog facts, binding sources, Discard and Reset all.

## Impact

- `domain/models.py` (sources), `contracts/models.py`, `contracts/settings.py` and `contracts/run_workspace.py`.
- `adapters/models/catalog.py`, `application/provider_settings.py`, `application/runs.py` (the snapshot), `application/run_projection.py` and `api/settings_routes.py`.
- A migration making `model_policies.default_profile` nullable.
- The generated contract and client.
- `model-policy-panel.tsx` and `run-workspace.tsx`.
- The fixture catalog gains prices and parameters.
- `scripts/qualify_identity.py` and a `tests/db` arrangement for the run override.
- Specs.
