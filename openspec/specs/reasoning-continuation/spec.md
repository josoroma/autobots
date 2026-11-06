# reasoning-continuation Specification

## Purpose
TBD - created by archiving change us-11-2-reasoning-continuation-check. Update Purpose after archive.

## Requirements

### Requirement: The continuation request is checked

The system SHALL report whether reasoning metadata returned alongside a tool call is sent back on continuation with its original content and ordering.

#### Scenario: Check the continuation request
- **GIVEN** a fake transport replies with reasoning metadata alongside a tool call
- **WHEN** the application builds the continuation request
- **THEN** the check reports survived only when that metadata is sent back with its original content and ordering, and reports dropped when it is dropped or altered

### Requirement: Each enabled route is tried live

A capped trial SHALL continue a real tool call on each enabled route and record the route, date, configuration, reported cost and outcome, keeping the metadata itself out of records, ordinary logs and activity events.

#### Scenario: Trial each enabled route live
- **GIVEN** a route that returns reasoning metadata with a tool call, under Decision 0009's shared US$1 cap
- **WHEN** the capped trial continues that tool call through the real route
- **THEN** the result records the route, date, configuration, reported cost and whether the metadata survived, with no metadata in ordinary logs or activity events

#### Scenario: Report loss honestly
- **GIVEN** a trial where the metadata did not survive, or the route returned none to preserve
- **WHEN** the result is recorded
- **THEN** it is reported as lost or as not exercised, never as survived, LC-23 stays partial and the owner is told

### Requirement: The trial stops at the shared cap

The trial SHALL send nothing when the spend so far plus its worst-case cost would pass the shared cap.

#### Scenario: Stop at the shared cap
- **GIVEN** the spend so far plus the trial's worst-case cost would pass US$1
- **WHEN** the trial is about to start
- **THEN** no request is sent and the work left undone is reported as not run
