# local-operations Specification

## Purpose
TBD - created by archiving change us-9-1-local-startup-shutdown-health. Update Purpose after archive.

## Requirements

### Requirement: Start and stop without data loss

The supported lifecycle SHALL verify readiness before admission, and ordinary shutdown SHALL preserve volumes, records and bounded in-flight state.

#### Scenario: Start and stop without data loss

- **GIVEN** the configured persistent local stack
- **WHEN** the supported lifecycle procedure starts or drains/stops services
- **THEN** readiness is verified before admission and ordinary shutdown preserves volumes, records and bounded in-flight state

### Requirement: Expose safe operational evidence

Local Operations and logs SHALL report degraded readiness with redacted identifiers, no remote trace collector and no exposed secret configuration.

#### Scenario: Expose safe operational evidence

- **GIVEN** database/storage/disk or queue readiness degrades
- **WHEN** local Operations and logs report status
- **THEN** the condition is visible with redacted identifiers and no remote trace collector or exposed secret configuration

### Requirement: Apply declared retention without erasing recovery evidence

Retention SHALL enforce only its configured scope, and SHALL NOT remove required operation receipts early or expose another workspace's records.

#### Scenario: Apply declared retention without erasing recovery evidence

- **GIVEN** configured local retention and the supported retry, replay and run-retention windows
- **WHEN** scoped retention or deletion runs
- **THEN** the configured scope is enforced without prematurely removing required operation receipts or exposing another workspace's records
