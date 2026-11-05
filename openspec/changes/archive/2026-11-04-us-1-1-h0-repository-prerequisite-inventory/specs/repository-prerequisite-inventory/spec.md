# Spec Delta

## Purpose

Makes existing repository work and missing local prerequisites visible to a developer before changes begin, without exposing secret values or overwriting unrelated settings, and establishes version control and required ignores only where they are absent.

## ADDED Requirements

### Requirement: Repository and prerequisite inventory
The repository SHALL provide an inventory of the documentation and project-local development assets already present and of the installed tools, recording actual paths, versions and missing prerequisites. The inventory MUST NOT contain secret values, and producing it MUST NOT overwrite unrelated settings.

#### Scenario: Preserve existing work
- **GIVEN** the documentation and project-local development assets already present
- **WHEN** the repository and installed tool versions are inspected
- **THEN** the inventory records actual paths, versions and missing prerequisites without secret values or overwritten unrelated settings

### Requirement: Repository hygiene
When version control or required ignores are absent, preparing the H0 foundation SHALL establish them, preparing only what is missing. Doing so MUST NOT commit credentials, local transcripts or disposable data.

#### Scenario: Establish repository hygiene
- **GIVEN** version control or required ignores are absent
- **WHEN** the H0 foundation is prepared
- **THEN** version control and ignores are established without committing credentials, local transcripts or disposable data
