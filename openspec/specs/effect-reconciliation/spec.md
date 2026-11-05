# effect-reconciliation Specification

## Purpose
TBD - created by archiving change us-5-4-consequential-effect-reconciliation-using. Update Purpose after archive.

## Requirements

### Requirement: Reconcile a lost response
When an approved effect reached a mock destination but its acknowledgment was lost and the worker recovers, it SHALL record an unknown outcome and use the destination idempotency or readback contract or operator evidence before retry.

#### Scenario: Reconcile a lost response
- **GIVEN** an approved effect reached a mock destination but acknowledgment was lost
- **WHEN** the worker recovers
- **THEN** it records unknown outcome and uses the destination idempotency/readback contract or operator evidence before retry

### Requirement: Truthful uncertainty
When a destination cannot establish whether the effect occurred, the uncertainty SHALL remain visible, and no exactly-once guarantee or blind duplicate write MUST be claimed.

#### Scenario: Keep uncertain results truthful
- **GIVEN** the destination cannot establish whether the effect occurred
- **WHEN** recovery is evaluated
- **THEN** the uncertainty remains visible and no exactly-once guarantee or blind duplicate write is claimed
