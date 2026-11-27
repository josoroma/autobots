# Spec Delta

## Purpose

A local route enforces a required or named tool call itself, by a JSON-schema constraint on the reply, and turns that reply into the tool call (Decision 0041 A18; US-23.7).

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: One named tool is sent as required
**Reason**: Decision 0041 A18 replaces it. Sending `required` with only the named tool left enforcement to llama.cpp, which didn't enforce a required call for Bonsai 2.5's template (US-23.2).
**Migration**: A named tool is enforced by "A required or named tool call is enforced by the route": every tool stays described, and the JSON schema admits only the named one.
