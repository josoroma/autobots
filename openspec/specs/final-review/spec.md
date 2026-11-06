# final-review Specification

## Purpose
TBD - created by archiving change us-11-12-final-independent-review-gate. Update Purpose after archive.

## Requirements

### Requirement: The final code is reviewed and Gate 0 repeated

An independent reviewer SHALL inspect the final code bound to a fingerprint, and Gate 0's checks and the harness runbook SHALL be repeated on that revision, with validated evidence.

#### Scenario: Review the final code and repeat Gate 0
- **GIVEN** the final code of every EPIC-11 story, bound to a fingerprint, and a reviewer who did not author it
- **WHEN** the reviewer inspects it, and Gate 0's checks and the harness runbook are repeated on that revision
- **THEN** findings, dispositions and commands are recorded under docs/engineering/evidence/US-11.12/, scripts/evidence.py validates them, and the record leaves H1 and product acceptance to be assessed afterward

### Requirement: Earlier reviews are settled

The 41 minors, majors M8, M30, M32 and M33, and WORKER-INFERENCE-001 SHALL each have a stated outcome.

#### Scenario: Settle what earlier reviews left open
- **GIVEN** the 41 minors, majors M8, M30, M32 and M33, and WORKER-INFERENCE-001
- **WHEN** the review's dispositions are recorded
- **THEN** each has a stated outcome, M30 cites Decision 0009, and WORKER-INFERENCE-001 has a status backed by its evidence

### Requirement: A stale or unresolved result is refused

The story SHALL NOT complete while a blocking finding is open or a source changed after the reviewed fingerprint.

#### Scenario: Refuse a stale or unresolved result
- **GIVEN** a blocking finding is open, or a source changed after the reviewed fingerprint
- **WHEN** the story is assessed
- **THEN** it does not complete until the finding is resolved, the affected scope is reviewed again and the fingerprint is bound anew

### Requirement: Hook behavior is marked not qualified

The Gate 0 report SHALL mark Claude's crash and timeout hook behavior not qualified, and SHALL NOT report script fixtures as actual event delivery.

#### Scenario: Mark the hook behavior not qualified
- **GIVEN** Claude's crash and timeout hook behavior has not been qualified
- **WHEN** the Gate 0 report is published
- **THEN** it marks that behavior not qualified, and script fixtures are not reported as actual event delivery
