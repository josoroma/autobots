## ADDED Requirements

### Requirement: Workflows have an optional description and nodes an optional label at a new IR version

A workflow SHALL have an optional description. Graph nodes SHALL accept an optional `label`, and a graph carrying labels SHALL be stored at IR version 2. A graph at the previous IR version, with no labels, SHALL still validate, publish and run, stored and hashed exactly as before, and versions published before the change SHALL bind with the same version and hash.

#### Scenario: Optional description
- **GIVEN** one workflow saved with a description and another saved without one
- **WHEN** both are read through the BFF
- **THEN** the first returns its description, the second returns none, and both stay valid

#### Scenario: Labels bump the IR version
- **GIVEN** a graph whose nodes carry optional labels, and a graph at the previous IR version with no labels
- **WHEN** each is validated and published
- **THEN** the first is stored at the new IR version with its labels, and the second still validates, publishes and runs unchanged

#### Scenario: Versions published before the change are untouched
- **GIVEN** a version published before the migration
- **WHEN** a run binds it after the migration
- **THEN** the run references the same version and hash as before
