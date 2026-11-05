## Why

An approved effect may reach its destination while the response is lost. SP-012 and PRD 10.1 require an unknown outcome, reconciled by readback or operator evidence before any retry, with no exactly-once claim.

## What Changes

- A tool's readback can now answer found, not delivered or can't tell. The gateway stops and pauses the run on an unknown outcome.
- `application/reconciliation.py` and `POST /v1/runs/{id}/effects/{operation}/reconcile`: an owner's report, kept with the receipt, resolves what a destination can't.
- Resume is refused while an unknown effect has no way to resolve itself. The run page lists unknown outcomes.
- `tests/db/mock_sink.py`: a controlled file destination, for real killed workers and duplicate delivery.

**Limits:** connector-independent, with only a mock. A real connector is US-7.2, and needs your choice of service. An owner's report is taken as stated.

## Capabilities

### New Capabilities

- `effect-reconciliation`: truthful handling of unknown external outcomes.

### Modified Capabilities

None.

## Impact

A migration, `tool_gateway.py`, `goal_loop.py`, a new route, contracts, the run page, DB and browser tests, `scripts/qualify_identity.py`, `CODEBASE.md`. No dependency or model call.
