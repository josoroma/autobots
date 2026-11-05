## Why

All model-backed roles must follow one auditable policy, and SP-006, MP-01 and MP-02 require exactly two profiles, a fixed resolution order, and blocked dispatch on stale catalogs, drift or unsupported options, with no implicit model or provider.

## What Changes

- `domain/models.py`: the two profiles, 14 roles and MP-01's exact precedence, giving a frozen role policy. Unknown profiles and roles are refused.
- `adapters/models/catalog.py`: a five-minute freshness limit and an exact canonical association. Missing, drifted or ambiguous entries raise `model_unavailable`.
- `adapters/models/factory.py`: `prepare_attempt` runs each check before dispatch, and `chat_model` fixes the route, `require_parameters=true`, `allow_fallbacks=false` and no retries. It's the only place in the application that builds an inference client.
- `contracts/models.py`: the effective role map as a public contract, generated into TypeScript from one definition.

**Limits:** mocked catalogs and fake transports only, with no model call. No live catalog fetch, credential resolution, snapshot persistence or spend control yet: credentials are in EPIC-3, and persistence comes with run admission. US-3.4 owns live qualification.

## Capabilities

### New Capabilities

- `model-policy`: approved role resolution and refused drift or implicit routing.

### Modified Capabilities

None.

## Impact

New `domain/models.py`, `adapters/models/`, `contracts/models.py` and tests, regenerated contracts, and `CODEBASE.md`. No dependency, service or paid call.
