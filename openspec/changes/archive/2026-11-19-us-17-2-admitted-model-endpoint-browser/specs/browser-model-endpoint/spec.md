# Spec Delta

## Purpose
An OpenAI-compatible model endpoint for the browser box, through which every model call browser-use makes is one admitted call of the run on its frozen researcher route (Decision 0035 Y7 and Y16, Decision 0020 L3).

## ADDED Requirements

### Requirement: A request from the box is one admitted call

Each chat completion the endpoint answers SHALL be admitted as one call of the run:
- with a reservation, an invocation ticket and a receipt;
- counted in `model_calls`;
- answered by the run's frozen researcher route only, whatever model the request names.

The client SHALL be given no key.

#### Scenario: A request from the box is one admitted call
- **GIVEN** the endpoint serving a browse's isolated executor network for a run whose researcher route is frozen, and a fake OpenRouter transport
- **WHEN** a client on that network sends a chat completion to the endpoint
- **THEN** it is admitted as one call of the run, with a reservation, an invocation ticket and a receipt, counted in model_calls, answered by that route only whatever model the request names, and the client is given no key

### Requirement: A request past the run's limits is refused

The endpoint SHALL refuse with a typed reason, before anything reaches the transport, a request:
- past the run's budget, model calls or time;
- from a cancelled run;
- carrying content the route isn't qualified for.

#### Scenario: A request past the run's limits is refused
- **GIVEN** the run's budget, model calls or time is exhausted, or the run is cancelled
- **WHEN** a client on the browse's executor network sends another request to the endpoint
- **THEN** the endpoint refuses it with a typed reason, and nothing reaches the transport

### Requirement: Only the box can reach the endpoint

The endpoint SHALL answer only requests that reach it through that browse's executor network. Any other request SHALL be refused.

#### Scenario: Only the box can reach the endpoint
- **GIVEN** the endpoint is serving a browse
- **WHEN** a request reaches it from anywhere but that browse's executor network
- **THEN** it is refused
