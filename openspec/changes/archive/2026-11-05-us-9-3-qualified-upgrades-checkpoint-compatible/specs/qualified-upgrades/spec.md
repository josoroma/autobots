## ADDED Requirements

### Requirement: Preserve execution semantics during upgrade

A reviewed upgrade or forward recovery SHALL migrate compatible state or block it honestly, and SHALL NOT silently replace original model, tool or configuration bindings.

#### Scenario: Preserve execution semantics during upgrade

- **GIVEN** pinned prior application/schema/image fixtures and saved checkpoints
- **WHEN** a reviewed upgrade/forward-recovery procedure runs
- **THEN** compatible state is migrated or blocked honestly and original model/tool/configuration bindings are not silently replaced

### Requirement: Qualify adapter migrations

A changed framework checkpoint or store release SHALL have its actual schema, search-path and grants behavior verified before production continuation.

#### Scenario: Qualify adapter migrations

- **GIVEN** a changed framework checkpoint/store release
- **WHEN** migration and isolated replay tests run
- **THEN** actual schema/search-path/grants behavior is verified before production continuation
