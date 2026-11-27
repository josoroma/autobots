# Spec Delta

## Purpose

A model call answered by a model served on this Mac, through the shared gateway: identity checked before each call, at no spend, with thinking kept out of the reply (Decision 0041 A2, A3, A9; US-23.1).

## ADDED Requirements

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

### Requirement: One named tool is sent as required

On a local route, a call that names one tool in `tool_choice` SHALL be sent with `tool_choice` `required` and only that tool.

#### Scenario: One named tool is sent as required
- **GIVEN** a local route, and a model call among several tools that names one in tool_choice
- **WHEN** the request is sent
- **THEN** its tool_choice is required and it carries only that tool

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
