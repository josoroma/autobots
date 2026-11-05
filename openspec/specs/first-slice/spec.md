# first-slice Specification

## Purpose
TBD - created by archiving change us-4-8-verify-first-durable-goal. Update Purpose after archive.

## Requirements

### Requirement: Mocked vertical slice
With controlled documents, calculator and read tools, a fake model and a defined artifact criterion, when a goal is admitted, planned, executed, restarted and inspected, the artifact and deterministic criteria SHALL be verified with recoverable state and replayable evidence.

#### Scenario: Complete the mocked vertical slice
- **GIVEN** controlled documents, calculator/read tools, a fake model and a defined artifact criterion
- **WHEN** the goal is admitted, planned, executed, restarted and inspected
- **THEN** the artifact and deterministic criteria are verified with recoverable state and replayable evidence

### Requirement: Honest unmet criteria
With a missing required artifact or failed check, completion verification SHALL give a partial or failed result rather than succeeded.

#### Scenario: Report unmet criteria honestly
- **GIVEN** a missing required artifact or failed check
- **WHEN** completion verification runs
- **THEN** the result is partial or failed rather than succeeded
