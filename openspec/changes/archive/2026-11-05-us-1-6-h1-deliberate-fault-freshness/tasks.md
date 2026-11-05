## 1. Deliberate failure and correction fixtures

- [x] 1.1 Add good and bad Python, TypeScript, contract, state and model-transport fixtures (Detect faults and invalidate old evidence)
- [x] 1.2 Add `scripts/qualify_faults.py` and include it in `full` (Detect faults and invalidate old evidence)
- [x] 1.3 Add the fake OpenRouter transport and baseline model tests, and remove inherited provider keys in `conftest.py` (Protect paid endpoints during tests)

## 2. Qualify manifest validation and fingerprint invalidation

- [x] 2.1 Exercise real faults, correction and report staleness in a disposable copy (Detect faults and invalidate old evidence)
- [x] 2.2 Exercise manifest validation against that copy's real fingerprints (Detect faults and invalidate old evidence)
- [x] 2.3 Document the procedure in the harness runbook (Detect faults and invalidate old evidence)
