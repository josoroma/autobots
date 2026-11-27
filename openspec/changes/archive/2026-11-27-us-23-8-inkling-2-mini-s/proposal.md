# Proposal: Inkling 2 Mini's route qualified at its own output cap, and offered on Local beside Bonsai 2.5 (US-23.8)

## Why

The owner asked to requalify Inkling 2 Mini ("Requalify Inkling"), now that the route enforces required tool calls itself (Decision 0041 A18). At the runner's fixed 512-token cap, Inkling's reasoning ran out of room on the named-tool counterexample. At its route's own 8,192-token cap, the cap a run sends, every gating capability and the counterexample passed in all three trials. The owner then asked to "store it and offer it on local as we are offering bonsai as well".

## What Changes

- **The runner gives each local route its own output cap** (`limits_for`): 4,096 tokens for Bonsai 2.5 and 8,192 for Inkling 2 Mini. Only the truncation fixture asks for less. The report records the cap.
- **Inkling 2 Mini's live qualification** at its cap, kept in `.checks` with the 512-token run apart. 39 calls, US$0.00, with only `schema_nested` disabled at 2 of 3.
- **Migration 72** inserts Inkling 2 Mini's `qualified_with_limits` row, with SQLI-12's caveat. Migrations 69 to 71 keep their bytes.
- **The Local source offers both.** Either can be the Local default, and one profile answers every role (A8).
- **Checks** that assumed Inkling wasn't offered now expect it offered. **Docs:** Decision 0041's measurements row, the runbook and `CODEBASE.md`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `local-route-qualification`: the suite sends each local route its own output cap, and Inkling 2 Mini's route is qualified and stored.
- `model-source`: the Local source offers both local profiles, either as the Local default.

## Impact

- **Python:** `operations/route_qualification.py`, `application/schema_release.py`, and tests.
- **SQL:** migration `20261127000072_inkling_local_route_qualified.sql`, data only.
- **Checks:** `tests/db/checks/local_offering_check.py`, `tests/db/checks/model_source_check.py`, `scripts/app_db.py` and `apps/web/tests/browser/models.spec.ts`.
- **Docs:** Decision 0041, `docs/engineering/runbooks/local-app.md` and `CODEBASE.md`.
- **The owner's machine:** `llama-server` served Inkling 2 Mini during the live run, and was then stopped. The owner applies migration 72 to the install.
