# route-qualification-status Specification

## Purpose
TBD - created by archiving change us-11-1-truthful-qualification-status. Update Purpose after archive.

## Requirements

### Requirement: Each route's qualification is stored and shown

The system SHALL keep a durable qualification record for each approved route, holding its status, date, configuration and limits, and Settings SHALL show each route's record apart from authentication and catalog status.

#### Scenario: Show each route's stored qualification
- **GIVEN** a durable qualification record for each approved route, with its date, configuration and limits
- **WHEN** the API restarts and an owner opens Settings
- **THEN** each route shows its own status, date, configuration and limits, apart from authentication and catalog status

### Requirement: Qualification is never inferred

A route with no record, or a record for a different canonical model, SHALL read as not qualified, whatever the key or catalog says.

#### Scenario: Refuse to infer qualification
- **GIVEN** a route with no qualification record and a valid OpenRouter key
- **WHEN** Settings loads
- **THEN** that route reads as not qualified, and neither the key nor an available catalog changes that

### Requirement: The goal composer reports what happened

The goal composer SHALL say an admitted goal is queued and link its run, and SHALL NOT say whether a worker runs it or whether a model has been called.

#### Scenario: Correct the goal message
- **GIVEN** a goal has been admitted
- **WHEN** the composer reports the result
- **THEN** it says the goal is queued and links the run, and no longer says that no worker runs it or that no model has been called

### Requirement: Sol requalified live on the current install

The persistent install SHALL be backed up and then brought to every shipped migration through the guarded apply. Sol's route SHALL be qualified live with the US-3.4 corpus inside its authorized cap, every call reserved at its worst case before it's sent. A passing result SHALL be recorded for Settings → Models with its date and findings.

#### Scenario: Backed up, then current
- **GIVEN** the persistent install behind the shipped migrations
- **WHEN** it is backed up and the guarded apply runs
- **THEN** a completed, encrypted backup exists from before the apply, and readiness reports the schema ready with every shipped migration applied

#### Scenario: A live pass inside the authorized cap
- **GIVEN** Sol's qualification ledger and its US$1.20 cap
- **WHEN** the full corpus runs live on Sol
- **THEN** every call was reserved at its worst case before it was sent, the committed total stays within the cap, and the report records each fixture's outcome

#### Scenario: Today's result on Settings → Models
- **GIVEN** a passing live pass
- **WHEN** the owner opens Settings → Models
- **THEN** Sol shows qualified with limits, dated from today's pass, with its findings
