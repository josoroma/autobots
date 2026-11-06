## Why

US-10.2's finding B3: required screens are missing, and Decision 0009 keeps the run list and inspector in this release's core subset, so a person can find a run and see what it used, attempted and saved.

## What Changes

- A workspace-scoped `GET /v1/runs` and a Runs screen, newest first, with states and links.
- A sanitized `GET /v1/runs/{id}/inspector` and screen: each model call's role, tokens, provider, canonical and wire identity and upstream provider or unknown, each tool operation attempt, and the run's checkpoints by ID, step and source.
- It's built from typed columns, so checkpoint content, tool arguments, partial output and reasoning metadata can't reach it.

Costs, errors and evidence links in the inspector belong to US-11.9.

## Capabilities

### New Capabilities

- `run-inspector`: the run list and inspector, their isolation and what they leave out.

### Modified Capabilities

None.

## Impact

`contracts/run_workspace.py`, `application/run_projection.py`, `api/event_routes.py`, generated clients, new pages and components, the navigation, `tests/web/fixture_worker.py` and `scripts/qualify_identity.py`. No schema change and no model call.
