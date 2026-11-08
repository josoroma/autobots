## ADDED Requirements

### Requirement: Schema readiness against shipped migrations

Readiness SHALL compare the database's applied migration count with the count this release ships. Fewer SHALL be `schema_behind` and stop admission. More SHALL be `schema_ahead`, degraded, and SHALL NOT stop admission. Equal SHALL be ready when the required objects exist. The required objects SHALL include what migrations 38 to 49 add. The recorded shipped count and newest name SHALL be checked against `supabase/migrations`. Operations SHALL show the applied count against the shipped count.

#### Scenario: Fewer applied migrations is behind
- **GIVEN** a disposable database that has applied fewer migrations than the release ships
- **WHEN** readiness is read
- **THEN** the schema check is unavailable with schema_behind, admission stops, and Operations shows the applied count against the shipped count

#### Scenario: All applied is ready
- **GIVEN** a disposable database with every shipped migration applied
- **WHEN** readiness is read
- **THEN** the schema check is ok, and Operations shows the two counts equal

#### Scenario: More applied is ahead, not blocking
- **GIVEN** a database that has applied more migrations than the release ships
- **WHEN** readiness is read
- **THEN** the schema check is degraded with schema_ahead, and admission isn't stopped by it

#### Scenario: The shipped count can't drift
- **GIVEN** the release's recorded migration count and newest name
- **WHEN** the harness checks run
- **THEN** they fail unless both match supabase/migrations

#### Scenario: Newer objects are required without a history
- **GIVEN** a database with no readable migration history
- **WHEN** readiness is read
- **THEN** the relations and columns that migrations 38 to 49 add are among those it requires
