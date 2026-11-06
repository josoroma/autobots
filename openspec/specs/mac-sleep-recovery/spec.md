# mac-sleep-recovery Specification

## Purpose
TBD - created by archiving change us-11-10-real-mac-sleep-proof. Update Purpose after archive.

## Requirements

### Requirement: One real sleep is observed

The record SHALL state what a real sleep did to run status, receipts and reservations, whether anything was redispatched or duplicated, and that a real sleep was used.

#### Scenario: Observe one real sleep
- **GIVEN** a disposable stack with a scripted model, a run in progress and the written procedure
- **WHEN** the owner sleeps this Mac once and wakes it
- **THEN** the record states what was observed for run status, receipts and reservations, whether any call was redispatched or effect duplicated, and that a real sleep was used, not SIGSTOP

### Requirement: Wake handling follows the result

A blind redispatch, duplicate effect, false status or stranded run SHALL be recorded as a failure with wake handling built, and otherwise none is built and the limit is recorded.

#### Scenario: Build wake handling only if the test shows it's needed
- **GIVEN** the observed sleep's result
- **WHEN** it is assessed against LC-31 and LM-A07
- **THEN** a blind redispatch, duplicate effect, false status or stranded run is recorded as a failure and wake handling is built in this story, and otherwise none is built and the limit is recorded

### Requirement: A fix is proved under real sleep

Wake handling SHALL be shown to remove the failure under a second real sleep, and SIGSTOP alone SHALL NOT complete this story.

#### Scenario: Prove a fix under real sleep
- **GIVEN** wake handling had to be built
- **WHEN** the owner sleeps this Mac a second time under the same procedure
- **THEN** the failure is shown to be gone under real sleep, and SIGSTOP alone doesn't complete this story
