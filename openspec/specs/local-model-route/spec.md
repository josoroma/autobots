# local-model-route Specification

## Purpose
A model call answered by a model served on this Mac, through the shared gateway: identity checked before each call, at no spend, with thinking kept out of the reply (Decision 0041 A2, A3, A9; US-23.1).

## Requirements

### Requirement: A local route answers through the shared gateway

A model call on a local profile SHALL go to the owner's server on 127.0.0.1 at the configured port, through the one model factory, with the profile's model ID, no SDK retries and no key. It SHALL be admitted like any call, with an invocation ticket and a receipt, reserve and settle US$0, and be counted in `model_calls` with its tokens. Nothing SHALL reach OpenRouter, its catalog included.

#### Scenario: A local route answers through the shared gateway
- **GIVEN** Bonsai 2.5's local profile, whose route names an OpenAI-compatible server on 127.0.0.1 at the configured port, a fake server on that port reporting the profile's model ID, a run whose frozen executor route is on that profile, and a fake OpenRouter transport that fails if it is touched
- **WHEN** the run makes a model call
- **THEN** the call is sent to the loopback server with the profile's model ID through the one model factory, with no SDK retries and no key, it is admitted with an invocation ticket and a receipt, reserves US$0, is counted in model_calls with its tokens, and nothing reaches OpenRouter, its catalog included

### Requirement: The served model is checked before each call

Before each call on a local profile, the gateway SHALL read the server's `/v1/models`. A model ID other than the profile's SHALL be refused `model_unavailable` before any chat completion is sent, and no other model or source SHALL be tried.

#### Scenario: The served model is checked before each call
- **GIVEN** a fake server on the local route's port whose /v1/models reports a model ID other than the profile's
- **WHEN** a run on that profile makes a model call
- **THEN** the call is refused model_unavailable, no chat completion is sent to the server, and no other model or source is tried

### Requirement: A stopped server blocks inference only

When nothing answers on the local route's port, the call SHALL be blocked with the typed reason `local_model_server_unavailable`, which says the local model server isn't running. Nothing SHALL be sent, no other model or source SHALL be tried, and settings and files SHALL read as before.

#### Scenario: A stopped server blocks inference only
- **GIVEN** nothing listening on the local route's port
- **WHEN** a run on a local profile makes a model call, and a member then reads the workspace's settings and the run's files
- **THEN** the call is blocked with a typed reason saying the local model server isn't running, nothing is sent and no other model or source is tried, and the settings and files read as before

### Requirement: The run's limits still count

A run on a local profile SHALL stop on its model calls, tool dispatches or active time with the same code as a run on an OpenRouter route, before anything is sent.

#### Scenario: The run's limits still count
- **GIVEN** a run on a local profile whose model calls, tool dispatches or active time is used up
- **WHEN** it makes another model call
- **THEN** it stops with the same code a run on an OpenRouter route stops with, and nothing is sent to the server

### Requirement: Thinking stays out of the reply

A local profile's request SHALL carry the profile's thinking switch. Reasoning a server returns in its own field SHALL appear in neither the reply's text nor its tool arguments, nor in any activity log.

#### Scenario: Thinking stays out of the reply
- **GIVEN** Bonsai 2.5's local profile, which turns thinking off with enable_thinking false, Inkling 2 Mini's, whose reasoning can't be turned off, and a fake server for each, Inkling 2 Mini's answering with reasoning in its own field
- **WHEN** a run on each makes a model call
- **THEN** Bonsai 2.5's request turns thinking off, and Inkling 2 Mini's reasoning is in neither the reply's text nor its tool arguments, nor in any activity log

### Requirement: OpenRouter routes are unchanged

A call on an OpenRouter profile SHALL keep its catalog check, MP-02's routing flags and its reservation, and SHALL send nothing to the loopback.

#### Scenario: OpenRouter routes are unchanged
- **GIVEN** a run whose frozen route is on Terra, and a fake OpenRouter transport
- **WHEN** it makes a model call
- **THEN** the call passes the catalog check and goes to OpenRouter with MP-02's routing flags and the reservation it had before, and nothing is sent to the loopback

### Requirement: A local profile isn't offered before it qualifies

A local profile with no stored qualification SHALL be refused `model_not_offered`, with a reason naming the model, wherever new work names it, and SHALL be left out of every choice. Nothing SHALL be substituted and nothing stored SHALL change.

#### Scenario: A local profile isn't offered before it qualifies
- **GIVEN** Bonsai 2.5's and Inkling 2 Mini's local profiles with no qualification stored
- **WHEN** a new run, the workspace default, a role override or an Expert's role binding names either
- **THEN** it is refused model_not_offered with a reason naming the model, no run starts, no other model is substituted, nothing stored changes, and no picker lists it

### Requirement: A required or named tool call is enforced by the route

On a local route, a call whose `tool_choice` is `required` or names a tool SHALL keep its tools described and ask the server for a reply constrained by a JSON schema to one call of a tool the request offers, or of the named tool only, with arguments matching that tool's parameters. The route SHALL turn that reply into the one tool call and leave none of it as text. A reply cut off by its output cap SHALL read as cut off, with no tool call. A reply that otherwise doesn't parse or doesn't match SHALL fail the call, and the route SHALL NOT repair it, retry it or pass it on as text. A call that leaves the choice to the model, and structured output, SHALL be sent as before. A streamed call SHALL be asked for whole, since only a complete call can be checked.

#### Scenario: A required tool call becomes one tool call
- **GIVEN** a local route, a model call offering Weather and LookupCode with tool_choice required, and a fake server on loopback that answers with one call matching the JSON schema it is sent
- **WHEN** the call is sent
- **THEN** the request asks for a reply constrained by a JSON schema to one call of Weather or LookupCode with arguments matching that tool's parameters, the reply becomes that one tool call, and none of the constrained reply is in the reply's text

#### Scenario: A named tool call is constrained to that tool
- **GIVEN** a local route, a model call offering Weather and ClockTime that names Weather under a system prompt preferring ClockTime and never Weather, and a fake server that answers with a ClockTime call whenever the schema it is sent admits one
- **WHEN** the call is sent
- **THEN** the schema sent admits only a Weather call with Weather's parameters, and the reply becomes one Weather call

#### Scenario: A constrained reply cut off by its output cap
- **GIVEN** a local route, a model call that requires a tool call, and a fake server whose constrained reply stops at the output cap with finish reason length, once whole and once streamed
- **WHEN** each call is sent
- **THEN** each reply is reported as cut off, as a cut-off reply on any route is, with no tool call, none of its text passed on and nothing run

#### Scenario: A constrained reply that doesn't parse or doesn't match fails the call
- **GIVEN** a local route, model calls that require a tool call or name Weather, and a fake server whose constrained reply is, in turn, JSON that doesn't parse, a call of a tool the request doesn't offer, a call of a tool other than the named one, and arguments that don't match the tool's parameters
- **WHEN** each call is sent
- **THEN** each call fails with no tool run and nothing from the reply passed on as text, the route doesn't repair it, and the server receives one chat completion for each call

#### Scenario: A call that leaves the choice to the model is sent as before
- **GIVEN** a local route, a model call with tool_choice auto, one with tools and no tool_choice, and one asking for structured output with a nested schema
- **WHEN** each request is sent
- **THEN** each body is what the route sent before A18, with its tools, tool choice and response format unchanged, and no JSON-schema constraint added for a tool call

#### Scenario: A streamed required tool call
- **GIVEN** a local route, a streamed model call that requires a tool call, and a fake server that answers the constrained request
- **WHEN** the stream is read to its end
- **THEN** the server was asked for the reply whole, since only a complete call can be checked, the assembled message holds the one tool call the reply gave with its arguments whole and its usage, and no chunk carries any of the constrained reply as text

#### Scenario: Nothing reaches OpenRouter
- **GIVEN** a run whose frozen route is on Bonsai 2.5's local profile, a fake local server, and a fake OpenRouter client that fails if it is built
- **WHEN** the run makes a model call that requires a tool call and one that names a tool
- **THEN** each goes to the loopback server only and reserves US$0, no other model or source is tried, and nothing reaches OpenRouter, its catalog included
