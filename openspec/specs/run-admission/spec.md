# run-admission Specification

## Purpose
TBD - created by archiving change us-4-1-atomic-run-admission-canonical. Update Purpose after archive.

## Requirements

### Requirement: Exactly one logical admission
Matching concurrent admissions of an authorized goal with an idempotency key and normalized request hash SHALL commit one Run, job and outbox result, returned with 202, and conflicting content for the key MUST be rejected.

#### Scenario: Admit exactly one logical request
- **GIVEN** an authorized goal with an idempotency key and normalized request hash
- **WHEN** matching concurrent admissions occur
- **THEN** one Run/job/outbox result is committed and returned with 202 while conflicting content for the key is rejected

### Requirement: Lifecycle guards
When an actor requests input, approval, pause, resume or completion on a run with an expected version, the SP-010 transition table and actor guards SHALL apply, and terminal states MUST NOT be reopened.

#### Scenario: Enforce lifecycle guards
- **GIVEN** a run and an expected version
- **WHEN** an actor requests input, approval, pause, resume or completion
- **THEN** the SP-010 transition table and actor guards apply and terminal states cannot be reopened
