# application-migrations Specification

## Purpose
TBD - created by archiving change us-2-4-application-migrations-deterministic-seeds. Update Purpose after archive.

## Requirements

### Requirement: Replayable application schema
Ordered migrations and reference seeds on a marked disposable direct database with a supported prior fixture SHALL give correct schema constraints and relationships, stable reference rows, and MUST NOT overwrite user edits when seeds run again.

#### Scenario: Replay and upgrade application schema
- **GIVEN** a marked disposable direct database and a supported prior fixture
- **WHEN** ordered migrations and reference seeds run, then seeds run again
- **THEN** schema constraints and relationships are correct, reference rows are stable and user edits are not overwritten

### Requirement: Separate migration authority
Only the explicit guarded migration path SHALL change schema, with no competing ORM history or worker-startup DDL.

#### Scenario: Separate migration authority
- **GIVEN** restricted runtime roles and a migration identity
- **WHEN** schema setup or a framework table upgrade is requested
- **THEN** only the explicit guarded migration path changes schema and no competing ORM history or worker-startup DDL is introduced
