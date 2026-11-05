# run-workspace Specification

## Purpose
TBD - created by archiving change us-4-6-sanitized-event-replay-run. Update Purpose after archive.

## Requirements

### Requirement: Reconnect from committed events
When a disconnected browser with a run event cursor reconnects, ordered authorized replay and live events SHALL reconstruct status without duplicates, with a snapshot when retained events cannot fill a gap.

#### Scenario: Reconnect from committed events
- **GIVEN** a run event cursor and a disconnected browser
- **WHEN** the user reconnects
- **THEN** ordered authorized replay and live events reconstruct status without duplicates, with a snapshot when retained events cannot fill a gap

### Requirement: Private execution state stays private
When activity from framework state that includes secrets or protected reasoning metadata is projected to the UI, only the sanitized envelope and concise decision and evidence summaries SHALL appear, with explicit paused, error and reconnecting states.

#### Scenario: Keep private execution state private
- **GIVEN** framework state includes secrets or protected reasoning metadata
- **WHEN** activity is projected to the UI
- **THEN** only the sanitized envelope and concise decision/evidence summaries appear, with explicit paused/error/reconnecting states
