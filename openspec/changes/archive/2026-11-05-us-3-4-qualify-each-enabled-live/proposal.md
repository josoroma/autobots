## Why

US-3.4 needs real protocol evidence for each enabled OpenRouter route, so advertised capabilities aren't mistaken for working application behavior. The paid rounds have run. What's left is settling the outcome: [Decision 0005](../../../docs/engineering/decisions/0005-deepseek-strict-nested-unsupported.md) records a capability that failed as unsupported, and "remain disabled" should be something a check can catch.

## What Changes

- No new paid calls. Scenarios are scored from the recorded live reports of the three rounds.
- A test fails if application code starts asking for strict output, so the unsupported capability stays disabled.
- A test fails if an approved profile has no matching qualification route, so "each enabled route" can't drift.
- The evidence and `CODEBASE.md` state the final outcome and what stays open.

## Capabilities

### New Capabilities

- `route-qualification`: recording live route behavior apart from mocks, keeping unsupported capabilities disabled, and testing named tool selection honestly.

### Modified Capabilities

None.

## Impact

`services/agent/tests/test_route_qualification.py`, `docs/engineering/evidence/US-3.4/summary.md`, `docs/engineering/decisions/0005-deepseek-strict-nested-unsupported.md`, `CODEBASE.md`. No application behavior changes.
