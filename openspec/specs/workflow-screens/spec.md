# workflow-screens Specification

## Purpose
TBD - created by archiving change us-6-3-workflow-editor-execution-monitor. Update Purpose after archive.

## Requirements

### Requirement: Inspect a validated graph run
When the user validates, publishes and opens an execution of a draft graph and its published immutable version, typed errors or the exact version binding SHALL be visible with node-instance status and output emissions.

#### Scenario: Inspect a validated graph run
- **GIVEN** a draft graph and its published immutable version
- **WHEN** the user validates, publishes and opens an execution
- **THEN** typed errors or the exact version binding are visible with node-instance status and output emissions

### Requirement: UI state as a projection
When the browser reconnects during workflow execution and the monitor refreshes, it SHALL read authorized durable state rather than creating a second scheduler.

#### Scenario: Keep UI state a projection
- **GIVEN** the browser reconnects during workflow execution
- **WHEN** the monitor refreshes
- **THEN** it reads authorized durable state rather than creating a second scheduler
