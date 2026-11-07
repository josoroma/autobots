# uncertain-call-cause Specification

## Purpose
TBD - created by archiving change us-12-7-record-why-call-outcome-unknown. Update Purpose after archive.

## Requirements

### Requirement: An uncertain call says why in the worker's log

Each path that ends a dispatched model call as `uncertain_acceptance` or `partial_stream` SHALL write one structured worker log event naming the invocation, the run, and the exception's type, its cause's type and its HTTP status where there are any, or which path ended it.

#### Scenario: Name the exception behind an uncertain call
- **GIVEN** a dispatched call on a fake transport raises an exception classed as `uncertain_acceptance`, once with an HTTP status and once without one
- **WHEN** the call ends
- **THEN** one event names the invocation, the run, the exception's type, its cause's type where it has a cause, and the status where there is one

#### Scenario: Say which path had no exception
- **GIVEN** a call is still out at the call time limit, and in a second case when the run's status becomes an interrupting one
- **WHEN** `_bounded` ends the call
- **THEN** one such event says which of those two it was

#### Scenario: Cover a partial stream that is arranged
- **GIVEN** a handler is arranged to raise `partial_stream` with accumulated output
- **WHEN** the call ends
- **THEN** one such event names the exception's type, its output isn't in the event, and the case is reported as arranged

### Requirement: The event holds no text

The event SHALL hold no exception message, no request or reply text and no key.

#### Scenario: Keep a secret out of the log
- **GIVEN** an exception and its cause hold a sentinel that redaction doesn't recognize, and a check that they really carry it
- **WHEN** the call ends as `uncertain_acceptance`
- **THEN** the sentinel, the message, the request and reply text and the key are absent from the log

#### Scenario: Observe it through the product's worker
- **GIVEN** a disposable stack, the product's `worker.main` with no wrapper, a fake HTTP transport, an arranged reply whose text reaches the exception, and no paid call
- **WHEN** a goal's call ends as `uncertain_acceptance`
- **THEN** the log holds one event for that invocation and run, that text and the key are nowhere in it, the run pauses with its reservation held, and any path not run through the worker is reported as not run there

### Requirement: Nothing else changes

The change SHALL add no migration or column, and SHALL change no screen, state, charge or pause, and the runbook SHALL say where to look.

#### Scenario: Change nothing else
- **GIVEN** this change
- **WHEN** it is compared with the code before it
- **THEN** there is no migration or column, and no change to a screen, a state, a charge or what a pause does, and the pause stays a stated limit

#### Scenario: Say where to look
- **GIVEN** an operator reconciling a run paused as `uncertain_acceptance`
- **WHEN** they read the operations runbook
- **THEN** it says which log holds the event and what it names, and still sends them to OpenRouter's records for the charge
