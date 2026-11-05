## Why

An owner must be able to configure inference without accidentally starting a paid task, and SP-007, MP-04 and MP-05 require write-only setup, independent statuses, and local work that stays available without a key.

## What Changes

- The exact MP-05 routes through the BFF and Python: provider status, credential PUT and DELETE with a version, validate, model list, and a versioned model policy.
- `application/provider_settings.py`: validation through key metadata and the public catalog only. A rejected key or an outage leaves the prior key alone, and a catalog outage doesn't undo a valid save.
- Settings → Models → OpenRouter: a write-only password form that clears on submit, with `Validate`, `Replace key` and `Disconnect`, and independent source, authentication, catalog and qualification.
- A goal composer whose draft survives setup in `sessionStorage`. `POST /v1/runs/intent` is the credential gate that a user's Run reaches. It creates no run.
- A body size limit in the BFF, and a generator that handles request bodies.

**Limits:** run admission is a later story, so `ready` says nothing was started. No real key or real OpenRouter call: qualification uses a local fake that logs each upstream request.

## Capabilities

### New Capabilities

- `provider-settings`: write-only provider setup, missing-key behavior and explicit run intent.

### Modified Capabilities

None.

## Impact

`apps/web`, `services/agent/src/autobots/api`, `application/`, `adapters/models/`, contracts, a migration, `scripts/generate_contracts.py`, `scripts/qualify_identity.py`, the runbook and `CODEBASE.md`. Adds a direct `httpx` pin, already locked transitively. Disposable Docker only.
