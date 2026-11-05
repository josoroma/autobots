## Why

A passing verifier only means something if it demonstrably fails on real faults, and if an old report cannot speak for changed inputs. SP-002 and H1.1 require this before feature work, and US-1.5's manifest validation has not yet been qualified.

## What Changes

- `tests/faults/`: known-good and known-bad Python, TypeScript, contract, state and model-transport fixtures.
- `scripts/qualify_faults.py` runs the real pinned tools on them. A bad fixture must fail with its case's marker, so a crash does not count as a detected fault. `full` includes it as `fault_qualification`, and a `full` report without it is not current.
- Baseline model tests in `services/agent/tests/`: a fake OpenRouter transport through the real adapter and SDK, checking the two approved profiles, fallback arrays and missing keys. `conftest.py` also removes any inherited `OPENROUTER_API_KEY`, in addition to its existing socket block.

**Limits, by the sources:** the state and contract checkers are fixture checkers, not the product's state machine or contract generation, which later stories build. The fake is not `US-3.x`'s gateway, and proves nothing about real routes.

## Capabilities

### New Capabilities

- `fault-qualification`: known-good and known-bad fixtures, evidence invalidation and refused external inference.

### Modified Capabilities

None.

## Impact

New `tests/faults/`, `scripts/qualify_faults.py`, `tests/harness/test_fault_fixtures.py`, `services/agent/tests/fake_openrouter.py` and `test_model_transport.py`. Updates `scripts/verify.py`, `scripts/harness_lib.py`, `scripts/evidence.py`, `tests/toolchain/test_scaffold_scope.py`, the harness runbook and `CODEBASE.md`. No new dependency, service or real model call.
