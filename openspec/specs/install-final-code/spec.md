# install-final-code Specification

## Purpose
TBD - created by archiving change us-12-6-real-install-final-code. Update Purpose after archive.

## Requirements

### Requirement: Try the migrations on a restored copy first

The install SHALL do this: try the migrations on a restored copy first.

#### Scenario: Try the migrations on a restored copy first
- **GIVEN** the real install on US-12.3's bound code, with its pending migrations
- **WHEN** it is backed up, the backup is restored to an isolated held copy and the pending migrations are applied there through the guarded path
- **THEN** each step is recorded, and a failure there leaves the install's database unchanged and stops the story with a report

### Requirement: Apply and start beside other projects

The install SHALL do this: apply and start beside other projects.

#### Scenario: Apply and start beside other projects
- **GIVEN** the restored copy took the migrations
- **WHEN** the same migrations are applied to the install through the guarded path and it starts on its own loopback ports
- **THEN** readiness is verified, its schema is current, its live listeners are only its recorded loopback bindings, its owner, runs and artifacts remain, and other projects' containers, ports and volumes are unchanged

### Requirement: Run one real goal under the shared cap

The install SHALL do this: run one real goal under the shared cap.

#### Scenario: Run one real goal under the shared cap
- **GIVEN** inference is on for this goal, and the shared cap's remainder covers its worst-case cost
- **WHEN** one goal runs on Terra through the install's API and worker
- **THEN** its frozen route, actual outcome, reported cost, the ledger's total and actual key usage are recorded whether it succeeded or failed, and the worker's inference switch is off afterward

### Requirement: Stop at the shared cap

The install SHALL do this: stop at the shared cap.

#### Scenario: Stop at the shared cap
- **GIVEN** the shared ledger plus the goal's worst-case cost would pass US$1
- **WHEN** the goal is about to start
- **THEN** no request is sent and the goal is reported as not run

### Requirement: Stay inside what was authorized

The install SHALL do this: stay inside what was authorized.

#### Scenario: Stay inside what was authorized
- **GIVEN** a step beyond this backup, these migrations, this start and one goal would be needed
- **WHEN** it comes up
- **THEN** the story stops and reports it, and nothing is reset, removed or spent beyond the decision
