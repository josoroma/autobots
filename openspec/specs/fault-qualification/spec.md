# fault-qualification Specification

## Purpose
TBD - created by archiving change us-1-6-h1-deliberate-fault-freshness. Update Purpose after archive.

## Requirements

### Requirement: Detected faults and invalidated evidence
Portable checks SHALL fail on known-bad TypeScript, Python, contract, state and model-transport fixtures and pass on corrected inputs, and an older report MUST NOT certify a relevant input changed after it, including an untracked one.

#### Scenario: Detect faults and invalidate old evidence
- **GIVEN** good and faulty TypeScript, Python, contract, state and model-transport fixtures
- **WHEN** the portable checks run and a relevant untracked input later changes
- **THEN** faults fail, corrected inputs pass and the older report cannot certify the changed inputs

### Requirement: Protected paid endpoints during tests
Baseline model tests MUST use fake transports and reject external inference, even when the developer environment contains a provider key.

#### Scenario: Protect paid endpoints during tests
- **GIVEN** a developer environment containing a real provider key
- **WHEN** the baseline model tests execute
- **THEN** fake transports are used and external inference is rejected
