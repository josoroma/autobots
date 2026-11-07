# browsing-loop Specification

## Purpose
TBD - created by archiving change us-14-14-admitted-model-browser-use. Update Purpose after archive.

## Requirements

### Requirement: Every browsing step is an admitted call

The browsing loop SHALL show the model each page's URL, title, a cut of its readable text and its numbered links, and SHALL make each step one admitted call of the run on its frozen `researcher` route, with a reservation, an invocation ticket and receipt, the run's budget and `model_calls`, and the shared transport.

#### Scenario: Each step is an admitted call
- **GIVEN** the browsing loop in the worker with a scripted model and scripted pages, offline
- **WHEN** the loop takes three steps, opening a numbered link, scrolling and finishing with a summary
- **THEN** each step shows the model the page's URL, title, a cut of its readable text and its numbered links, each step's call has a reservation, an invocation ticket and receipt, and the run's frozen researcher route on an approved OpenRouter profile over the shared transport, its spend is settled into the run's model calls and spend, and the loop ends with the model's summary

#### Scenario: An uncertain outcome follows the existing rules
- **GIVEN** a scripted step call through admission whose outcome is uncertain
- **WHEN** the loop records it
- **THEN** its receipt and reservation stay pending reconciliation and it is not redispatched

### Requirement: The loop has no model path of its own

The loop SHALL hold no model client of its own. A call made outside admission SHALL fail as unadmitted, and an exhausted budget SHALL refuse a step before it is sent.

#### Scenario: No other model path
- **GIVEN** the browsing loop in the worker
- **WHEN** a model call is made outside admission, or a step is attempted with the run's budget exhausted
- **THEN** the loop has no model client of its own, the outside call fails as unadmitted, the exhausted budget refuses the call before it is sent, and neither reaches the transport

### Requirement: Actions are required tool calls

Each step SHALL offer exactly four read-only actions as typed tools with a tool call required, SHALL refuse a route lacking tool support with a typed code before sending, and SHALL end the call on an answer that isn't one valid action.

#### Scenario: Actions are required tool calls, refused on a route lacking tool support
- **GIVEN** a route whose catalog entry supports tools and a route whose catalog entry doesn't
- **WHEN** the loop requests a step on each
- **THEN** the first offers exactly the actions open a numbered link, go to a URL, scroll and finish with a summary, as tools with typed arguments and a tool call required, and the second is refused with a typed code before anything is sent

#### Scenario: An answer that isn't one valid action ends the call
- **GIVEN** a scripted model that answers a step with no tool call, more than one tool call, an action outside the fixed set, or arguments that don't fit the action's type
- **WHEN** the loop reads the answer
- **THEN** the call ends with stopped set to invalid_action, keeping the notes so far, and no further step is requested
