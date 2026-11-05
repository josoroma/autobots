# approvals Specification

## Purpose
TBD - created by archiving change us-5-3-argument-bound-approvals-durable. Update Purpose after archive.

## Requirements

### Requirement: Decisions bound to the proposal
When a reviewer approves or rejects a persisted tool, version, normalized arguments hash, scope and expiry, only the matching authorized current proposal SHALL be released, and changed, expired or replayed decisions MUST NOT authorize other work.

#### Scenario: Bind the review decision
- **GIVEN** a persisted tool/version, normalized arguments hash, scope and expiry
- **WHEN** the reviewer approves or rejects
- **THEN** only the matching authorized current proposal is released and changed/expired/replayed decisions cannot authorize other work

### Requirement: Restart during an approval wait
When a worker that persisted a proposal and stopped restarts and receives a decision, proposal persistence SHALL remain idempotent, no pre-approval effect SHALL occur, and rejection SHALL permit only replanning or failure handling.

#### Scenario: Restart during approval wait
- **GIVEN** a worker has persisted the proposal and interrupted
- **WHEN** the worker restarts and receives a decision
- **THEN** proposal persistence remains idempotent, no pre-approval effect occurs and rejection permits only replanning or failure handling
