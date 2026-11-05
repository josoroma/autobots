# local-identity Specification

## Purpose
TBD - created by archiving change us-2-3-local-identity-workspace-grants. Update Purpose after archive.

## Requirements

### Requirement: Local password ownership
With local Auth and public signup disabled, an owner bootstrapped through supported APIs SHALL sign in, and the BFF and Python service SHALL verify identity and workspace membership without an external identity provider.

#### Scenario: Use local password ownership
- **GIVEN** local Auth with public signup disabled
- **WHEN** the owner is bootstrapped through supported APIs and signs in
- **THEN** the BFF and Python service verify identity and workspace membership without an external identity provider

### Requirement: Rejected cross-boundary access
Anonymous, forged or other-workspace identities MUST be denied domain records, private schemas and private Storage objects, and app_private and agent_runtime MUST be absent from PostgREST and Realtime access.

#### Scenario: Reject cross-boundary access
- **GIVEN** anonymous, forged or other-workspace identities
- **WHEN** they request domain records, private schemas or private Storage objects
- **THEN** access is denied and app_private/agent_runtime are absent from PostgREST and Realtime access
