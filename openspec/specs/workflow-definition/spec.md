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

### Requirement: A workflow holds one saved draft that only published versions outrank

A workflow SHALL hold at most one saved draft graph, which only an owner can save, publish or discard. Publishing it SHALL validate it and create the next immutable version under the expected version, refusing a stale one and creating nothing. Discarding it SHALL leave every published version and hash unchanged. Runs and routines SHALL bind published versions only, refusing a draft with a typed code.

#### Scenario: One saved draft
- **GIVEN** a published workflow in a workspace
- **WHEN** the owner saves a draft graph twice and a member who isn't the owner tries to save one
- **THEN** the workflow holds one draft with the owner's second graph, and the member's save is refused with a typed code

#### Scenario: Publish from the draft
- **GIVEN** a draft beside published version 3
- **WHEN** the owner publishes it with expected version 3, and another publish names expected version 2
- **THEN** the first validates the draft and creates immutable version 4, and the second is refused as stale and creates nothing

#### Scenario: Discard leaves published versions alone
- **GIVEN** a draft beside published versions
- **WHEN** the owner discards the draft
- **THEN** the draft is gone, and every published version and its hash is unchanged

#### Scenario: Runs bind only published versions
- **GIVEN** a workflow with a draft
- **WHEN** a run or a routine names the draft, and an execution names a published version
- **THEN** the first two are refused with a typed code, and the execution binds the published version's hash
