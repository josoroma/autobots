# Proposal: local route qualification and offering, at no spend (US-23.2)

## Why

US-23.1 gave local profiles a route, but Decision 0041 A7 offers one only once US-3.4's suite passes on that route in three trials. The owner asked on 2026-11-27 to start Bonsai 2.5's server and qualify its route ("Start US-23.2"). US-23.3's Model source setting needs an offered local profile before Local can be chosen.

## What Changes

- **The route qualification runner gains local routes.** `--profile local_bonsai_2_5_27b` or `local_inkling_2_mini` runs US-3.4's twelve fixtures in three trials against the owner's `llama-server`:
  - nothing is spent, and there is no `--paid` flag, cap, key or catalog;
  - US-23.1's identity check comes first;
  - each call is built by the factory's local branch and given 1,800 seconds (Decision 0041's measurements table).

  OpenRouter routes keep their flag and caps.
- **A local route's report adds:**
  - reading and writing speed, the time to the first token and the server's peak memory at 8K, 32K and 64K;
  - the served model ID, the profile's pins and US$0.00;
  - whether the five capabilities that gate offering passed in all three trials, with every failed or unsupported fixture listed as a limit;
  - what the report doesn't establish.

  Evidence is `live_local` against the owner's server and `fake_server` in tests.
- **Offering on the Local source.** A local profile is offered once its stored qualification is `qualified_with_limits` for its own canonical ID. A profile without one gets a reason naming what hasn't passed. On OpenRouter, a local profile is still refused `model_not_offered`.
- **Bonsai 2.5's live qualification,** on the owner's request: three trials and the measurements against the owner's `llama-server`. The raw report goes in the ignored `.checks`, and the result is recorded by migration, as Sol's was.
- **Docs:** SP-008's qualification, the runbook's Qualify section, `CODEBASE.md`.

## Capabilities

### New Capabilities
- `local-route-qualification`: qualifying a local route with US-3.4's suite at no spend, measuring it, and offering a local profile on the Local source only once it passes.

### Modified Capabilities
- None. `route-qualification` keeps every OpenRouter requirement.

## Impact

- **Python:**
  - `operations/route_qualification.py` and `operations/route_fixtures.py` (a per-run call time);
  - `operations/local_route_measurements.py` (new);
  - `application/local_offering.py` (new).
- **SQL:** one migration recording Bonsai 2.5's qualification row. No schema change.
- **Docs:** option-b-contract SP-008, `docs/engineering/runbooks/local-app.md` and `CODEBASE.md`.
- **The owner's machine:** `llama-server` serving Bonsai 2.5's Q2_0 on 127.0.0.1:9931 while the live qualification runs, then stopped.
