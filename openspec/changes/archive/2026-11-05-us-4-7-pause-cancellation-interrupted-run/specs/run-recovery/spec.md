## ADDED Requirements

### Requirement: Cancellation from any nonterminal state
When an authorized cancellation arrives for a queued, running, waiting, paused, verifying or cancelling run, new dispatch SHALL be fenced, and the run SHALL move directly to cancelled only without unsettled work, otherwise through cancelling with truthful reconciliation.

#### Scenario: Cancel any nonterminal run
- **GIVEN** a queued, running, waiting, paused, verifying or cancelling run
- **WHEN** an authorized cancellation arrives
- **THEN** new dispatch is fenced and the run moves directly to cancelled only without unsettled work, otherwise through cancelling with truthful reconciliation

### Requirement: Resume only paused work
When authorized resume of a paused run with immutable bindings and outstanding obligations passes readiness checks, the same policy SHALL continue without bypassing obligations, and terminal states SHALL require a linked new run.

#### Scenario: Resume only paused work
- **GIVEN** a paused run with immutable bindings and outstanding input/approval obligations
- **WHEN** authorized resume passes readiness checks
- **THEN** the same policy continues without bypassing obligations while terminal states require a linked new run

### Requirement: Recovery after sleep or loss
When execution becomes available after a worker or Mac interruption during a model or tool attempt, saved receipts and unknown outcomes SHALL be reconciled before another paid or consequential dispatch.

#### Scenario: Recover after sleep or loss
- **GIVEN** a worker or Mac interruption during a model/tool attempt
- **WHEN** execution becomes available again
- **THEN** saved receipts and unknown outcomes are reconciled before another paid or consequential dispatch
