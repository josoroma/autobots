# run-limits Specification

## Purpose
TBD - created by archiving change us-16-6-deep-research-runs-like. Update Purpose after archive.

## Requirements

### Requirement: Every run gets the raised limits

By Decision 0034 L1 to L4, every model call SHALL ask for at most 4,096 output tokens, SHALL reserve its worst case at that size before it is sent, and MAY take up to 300 seconds before it is interrupted. A root run tree SHALL allow 64 model calls, 96 tool dispatches, 8 child runs and 45 active minutes, with one repair, two plan revisions, two child levels and two outstanding assignments, and SHALL refuse the next of each with its existing code. Budgets and the daily cap SHALL still bound spend.

#### Scenario: Every run gets the raised limits
- **GIVEN** the worker's defaults and a fake OpenRouter transport
- **WHEN** a run's model call is sent and its run tree's counters are consumed
- **THEN** the request asks for at most 4,096 output tokens and reserves its worst case at that size, a call may take 300 seconds, and the run tree allows 64 model calls, 96 tool dispatches, 8 child runs, 40 metered tool calls and 45 active minutes, refusing the next of each with its existing code
