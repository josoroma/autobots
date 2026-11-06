# github-issue-connector Specification

## Purpose
Let a granted run create an issue in one configured GitHub repository, under the same approval, credential and uncertain-outcome rules as any consequential tool.

## Requirements

### Requirement: Enforce the selected connector contract

An authorized call on the selected connector SHALL follow the registered tool contract for its schema, credentials, permissions, idempotency and uncertain outcomes.

#### Scenario: Enforce the selected connector contract

- **GIVEN** an explicitly selected service and allowed operation with versioned scopes and approval policy
- **WHEN** the connector performs an authorized call
- **THEN** schema, credentials, permissions, idempotency and uncertain-outcome behavior follow the registered tool contract

### Requirement: Reject out-of-scope work

An operation outside the connector's grant SHALL be rejected by the policy gateway before any external effect.

#### Scenario: Reject out-of-scope work

- **GIVEN** the selected connector receives an operation outside its grant
- **WHEN** execution is requested
- **THEN** the policy gateway rejects it before an external effect
