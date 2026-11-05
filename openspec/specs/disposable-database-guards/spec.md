# disposable-database-guards Specification

## Purpose
TBD - created by archiving change us-1-7-h1-disposable-database-compose. Update Purpose after archive.

## Requirements

### Requirement: Refused persistent target
Test wrappers MUST refuse a reset, cleanup or disposable migration test before mutation when they receive the persistent database identity or volumes.

#### Scenario: Refuse the persistent target
- **GIVEN** test wrappers receive the persistent database identity or volumes
- **WHEN** a reset, cleanup or disposable migration test is requested
- **THEN** the operation is refused before mutation

### Requirement: Disposable fixtures
Synthetic migrations, repeated seeds and authorization fixtures SHALL run on a marked isolated project with distinct ports and volumes, verifying replay and seed repeatability and failing anonymous and cross-workspace access, without touching persistent services.

#### Scenario: Exercise disposable fixtures
- **GIVEN** a marked isolated project with distinct ports and volumes
- **WHEN** synthetic migrations, repeated seeds and authorization fixtures run
- **THEN** replay and seed repeatability are verified and anonymous/cross-workspace access fails without touching persistent services
