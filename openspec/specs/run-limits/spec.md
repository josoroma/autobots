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

### Requirement: Every run works in a 64K-token context

By Decision 0034 L6 to L8, a run's view SHALL be compacted toward 192,000 characters, tool output of up to 48,000 characters SHALL stay in view and longer output SHALL be offloaded and read back 4,000 characters a page, the latest 16 read-back pages SHALL stay in view, and each model call SHALL reserve 64,000 prompt tokens with its reply.

#### Scenario: Every run works in a 64K-token context
- **GIVEN** the worker's defaults
- **WHEN** a run's view is compacted and a model call is reserved
- **THEN** the view is compacted toward 192,000 characters, tool output of up to 48,000 characters stays in view, the latest 16 read-back pages stay in view, and the call reserves 64,000 prompt tokens with its 4,096-token reply

#### Scenario: Search results stay in view
- **GIVEN** a run whose google_search returned 28 results of about 14,000 characters, as the first live run's did
- **WHEN** its next model call is prepared
- **THEN** the results are in the model's view whole, not offloaded

#### Scenario: An offloaded output can be read back whole
- **GIVEN** a tool output of 60,000 characters, offloaded
- **WHEN** the model reads it back in 15 pages of 4,000 characters
- **THEN** all 15 pages are in its view on the next call
