## Why

A plausible answer alone must not mark work successful. US-4.8 asks for the mocked vertical slice, with evidence-backed completion, recovery assertions, an exercised user-flow runbook and an independent review.

## What Changes

- `GoalSpec.required_artifacts` and `application/verification.py`: completion comes from required artifacts read back from storage and their checks, recorded in `run_verifications`.
- `process_next` settles a candidate, and picks up one whose worker died. The run workspace shows verification.
- `tests/web/fixture_worker.py`, `slice.spec.ts` and `docs/engineering/runbooks/first-slice.md`: the flow in a real browser with a real killed process.
- `inputs` joins the default path grants, for controlled documents.

**Limits:** a scripted model and a fixture worker. There is no product worker process or supervisor, no real provider, and no measured responsiveness targets. This doesn't establish H1 or product acceptance.

## Capabilities

### New Capabilities

- `first-slice`: evidence-based completion through a durable goal-to-artifact flow.

### Modified Capabilities

None.

## Impact

A migration, a new application module, contracts, the run workspace, `scripts/qualify_identity.py`, a runbook, `docs/engineering/evidence/US-4.8/`, `CODEBASE.md`. No dependency or paid call.
