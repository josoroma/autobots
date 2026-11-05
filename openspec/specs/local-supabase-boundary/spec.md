# local-supabase-boundary Specification

## Purpose
TBD - created by archiving change us-2-1-pinned-local-supabase-service. Update Purpose after archive.

## Requirements

### Requirement: Approved local publications
The pinned self-hosted release and local overlay SHALL bind required ports only to loopback, direct database access MUST reach db:5432, and Studio MUST remain behind authenticated gateway access.

#### Scenario: Publish only approved local services
- **GIVEN** the pinned self-hosted Compose release and local overlay
- **WHEN** the rendered configuration and actual listeners are qualified
- **THEN** required ports bind only to loopback, direct database access reaches db:5432 and Studio remains behind authenticated gateway access

### Requirement: Protected unrelated services
Startup preflight SHALL report a host port conflict, and MUST NOT kill the other process or retain a wildcard publication.

#### Scenario: Protect unrelated services
- **GIVEN** a proposed host port conflicts with another process
- **WHEN** startup preflight runs
- **THEN** it reports the conflict instead of killing that process or retaining a wildcard publication
