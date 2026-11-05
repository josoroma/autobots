# development-assistant-assets Specification

## Purpose
Gives developers reusable shared instructions and focused project-local assistant definitions whose rules are tied to checks or review, keeps an unavailable or incompatible assistant adapter explicitly inactive, and turns approved sources into a traceable backlog without inventing product behavior.

## Requirements

### Requirement: Portable development policy
Shared instructions and project rules, skills, agents and settings SHALL NOT duplicate common rules inconsistently, and each rule SHALL link to a check or review responsibility.

#### Scenario: Keep development policy portable
- **GIVEN** shared engineering standards and the approved local/OpenRouter boundary
- **WHEN** AGENTS.md, CLAUDE.md and project rules, skills, agents and settings are authored
- **THEN** common rules are not duplicated inconsistently and each rule links to a check or review responsibility

### Requirement: Optional assistant activation stays separate
When the Claude adapter is unavailable or incompatible, validating its configuration SHALL leave it explicitly inactive and MUST NOT introduce a new model provider, a paid review call or an activation claim.

#### Scenario: Separate optional assistant activation
- **GIVEN** an unavailable or incompatible Claude adapter
- **WHEN** its configuration is validated
- **THEN** it remains explicitly inactive and no new model provider, paid review call or activation claim is introduced

### Requirement: Ingestion invents no product behavior
The read-only adapted ingestor SHALL return a proposed backlog for its paired caller to persist. Resulting stories SHALL cite their sources, contain Given/When/Then acceptance, preserve stable identities and honest dependencies and statuses, and generate navigation. Ingestion MUST NOT implement product code or claim delivery complete.

#### Scenario: Ingest without inventing product behavior
- **GIVEN** approved PRDs, preserved SP requirements and descriptive CODEBASE context
- **WHEN** the read-only adapted ingestor returns a proposed backlog and its paired caller persists it
- **THEN** stories cite their sources, contain Given/When/Then acceptance, preserve stable identities and honest dependencies/statuses, and generate navigation without implementing product code or claiming delivery complete
