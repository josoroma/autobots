# workflow-definition Specification

## Purpose
TBD - created by archiving change us-6-1-typed-immutable-workflow-definition. Update Purpose after archive.

## Requirements

### Requirement: Validation before publication
When publication is requested for a proposal using the documented input, output, transform, condition, foreach, join, read, artifact, approval and agent subset, types, links, iteration bounds and versions SHALL validate, or typed errors SHALL be returned, before an immutable version is published.

#### Scenario: Validate before publication
- **GIVEN** a proposal using the documented input/output/transform/condition/foreach/join/read/artifact/approval/agent subset
- **WHEN** publication is requested
- **THEN** types, links, iteration bounds and versions validate or typed errors are returned before an immutable version is published

### Requirement: Exact execution bindings
When a run is created from a published workflow or model-generated proposal, it SHALL reference the exact validated graph and block versions, and unsupported arbitrary cycles MUST be rejected.

#### Scenario: Preserve exact execution bindings
- **GIVEN** a published workflow or model-generated proposal
- **WHEN** a run is created
- **THEN** it references the exact validated graph/block versions and unsupported arbitrary cycles are rejected

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
