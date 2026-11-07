## ADDED Requirements

### Requirement: Observe a real sleep on the final code

The proof SHALL do this: observe a real sleep on the final code.

#### Scenario: Observe a real sleep on the final code
- **GIVEN** a disposable stack with a scripted model on US-12.3's bound code, a run in progress and the written runbook
- **WHEN** the owner sleeps this Mac for at least two minutes and wakes it
- **THEN** the record states what was observed for run status, receipts and reservations, whether any call was redispatched or effect duplicated, macOS's own Sleep and Wake, and the fingerprint it ran on, and SIGSTOP isn't used

### Requirement: Report a failure as a failure

The proof SHALL do this: report a failure as a failure.

#### Scenario: Report a failure as a failure
- **GIVEN** the report lists blind_redispatch, duplicate_effect, false_status or stranded_run
- **WHEN** it is assessed against LC-31 and LM-A07
- **THEN** it is recorded as a failure, this story doesn't complete, and any fix voids US-12.3's binding and needs another real sleep

### Requirement: Don't count a run that never slept

The proof SHALL do this: don't count a run that never slept.

#### Scenario: Don't count a run that never slept
- **GIVEN** the report says no_sleep_during_the_run
- **WHEN** it is assessed
- **THEN** nothing is claimed from it, and the owner starts again

### Requirement: Keep what this doesn't prove

The proof SHALL do this: keep what this doesn't prove.

#### Scenario: Keep what this doesn't prove
- **GIVEN** the model is scripted
- **WHEN** the record is published
- **THEN** a real provider's connection dropped across a sleep, and network loss, stay stated limits
