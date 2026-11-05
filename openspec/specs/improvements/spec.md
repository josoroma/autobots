# improvements Specification

## Purpose
TBD - created by archiving change us-8-2-reviewed-memory-skill-promotion. Update Purpose after archive.

## Requirements

### Requirement: Promote only reviewed evidence
When regression checks and review complete for a proposed skill or memory change with supporting run evidence, promotion SHALL create a new scoped version with provenance and rollback rather than replacing instructions silently.

#### Scenario: Promote only reviewed evidence
- **GIVEN** a proposed skill or memory change with supporting run evidence
- **WHEN** regression checks and review complete
- **THEN** a new scoped version may be promoted with provenance and rollback rather than replacing instructions silently

### Requirement: Untrusted material stays subordinate
When the improvement pipeline evaluates retrieved or generated content that asks to expand tools or model access, operating permissions and approved model defaults SHALL remain unchanged.

#### Scenario: Keep untrusted material subordinate
- **GIVEN** retrieved or generated content asks to expand tools or model access
- **WHEN** the improvement pipeline evaluates it
- **THEN** operating permissions and approved model defaults remain unchanged
