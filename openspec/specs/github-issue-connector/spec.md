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

### Requirement: Read-only GitHub tools and issue labels on the one configured repository

The four GitHub read tools SHALL work only on the configured repository, with bounded inputs and no repository input, recorded as read-only tool uses. `github_read_file` content SHALL never appear on run screens. `create_github_issue` version 2 SHALL accept up to 10 labels while version 1 is unchanged. Every GitHub tool SHALL read `key_missing` until both variables are set, with a repair naming them, the token's scopes and a restart.

#### Scenario: Read tools against a fake transport
- **GIVEN** GITHUB_REPOSITORY and a fake GITHUB_TOKEN set, a fake GitHub transport, and an Expert granting the four read tools
- **WHEN** the model calls github_list_pull_requests, github_list_workflow_runs, github_search_issues and github_read_file with allowed inputs
- **THEN** each returns validated output with the fields its requirement lists, every request targets only the configured repository, the search is restricted to it, and each call is recorded as a read-only tool use

#### Scenario: Bounded inputs, and no repository argument
- **GIVEN** the same tools on a fake transport
- **WHEN** a call names a repository, a state outside its allowed set or a limit above 100, and when github_read_file meets a file over 1 MiB
- **THEN** the first three are refused before any request, the oversized file fails with a typed code, and no tool schema offers a repository input

#### Scenario: File content stays private
- **GIVEN** a github_read_file call that returns text
- **WHEN** its tool use is listed and the run's screens render it
- **THEN** the content appears only as a digest and size, with its SHA and size, and never as text

#### Scenario: Labels on new issues, version 1 kept
- **GIVEN** create_github_issue version 2, an Expert version that pinned version 1, and a fake transport
- **WHEN** version 2 is approved and called with 10 labels, version 2 is proposed with 11 labels, and version 1 is approved and called with a title and body
- **THEN** the first creates the issue with those labels, the second is refused before any approval request or request to GitHub, and version 1 behaves as before

#### Scenario: Key missing until both are set
- **GIVEN** only one of GITHUB_REPOSITORY and GITHUB_TOKEN set
- **WHEN** the catalog is read
- **THEN** every GitHub tool reads key_missing, and the repair names both variables, the token's scopes and a restart, and never a value
