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
