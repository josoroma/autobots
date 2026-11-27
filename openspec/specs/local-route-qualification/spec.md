# local-route-qualification Specification

## Purpose
Qualifying a local route with US-3.4's suite at no spend, measuring it on this Mac, and offering a local profile on the Local source only once that suite passes (Decision 0041 A7; US-23.2).

## Requirements

### Requirement: A local route qualifies without spending

The route qualification runner SHALL run US-3.4's suite on a local route in three trials with no paid flag, cap, key or catalog. It SHALL check the served model first and build each call through the factory's local branch. Each fixture's verdict SHALL be recorded with its calls and time. Nothing SHALL be reserved or charged, and nothing SHALL reach OpenRouter.

#### Scenario: A local route qualifies without spending
- **GIVEN** a fake OpenAI-compatible server on 127.0.0.1 that answers US-3.4's fixtures as a local profile's model, and a fake OpenRouter transport that fails if it is touched
- **WHEN** the route qualification runner runs the suite on that local route without --paid
- **THEN** each fixture's verdict in each of three trials is recorded as fake-server evidence with its calls and time to the first token, nothing is reserved or charged, and nothing reaches OpenRouter, its catalog included

### Requirement: Bonsai 2.5's route qualifies on this Mac

On the owner's request, US-3.4's suite SHALL run on Bonsai 2.5's local route against the owner's `llama-server` in three trials. Reading and writing speed, the time to the first token and the server's peak memory SHALL be measured at 8K, 32K and 64K. Each result SHALL be recorded as live local evidence, apart from fake-server results, with the served model ID and the profile's pins. US$0.00 SHALL be spent.

#### Scenario: Bonsai 2.5's route qualifies on this Mac
- **GIVEN** the owner's request, and llama-server started by the owner, serving Bonsai 2.5's pinned Q2_0 on 127.0.0.1
- **WHEN** US-3.4's suite runs on Bonsai 2.5's local route in three trials, and reading and writing speed, time to the first token and the server's peak memory are measured at 8K, 32K and 64K
- **THEN** each result is recorded as live local evidence apart from fake-server results, with the served model ID and the profile's pins, US$0.00 is spent, and nothing is sent to OpenRouter

### Requirement: Offered only once the suite passes

A local profile SHALL be offered on the Local source only when its stored qualification for its own canonical ID is `qualified_with_limits`. That status is recorded only when plain text, automatic and required tool calls, flat structured output and streamed text each passed in all three trials. An offered profile SHALL carry its qualification's date, configuration and limits. Every other local profile SHALL carry a reason naming what hasn't passed.

#### Scenario: Offered only once the suite passes
- **GIVEN** Bonsai 2.5's stored qualification with plain text, automatic and required tool calls, flat structured output and streamed text each passing in all three trials, and no passing qualification for Inkling 2 Mini
- **WHEN** the profiles offered on the Local source are read
- **THEN** Bonsai 2.5's is offered with its qualification's date, configuration and limits, and Inkling 2 Mini's isn't, with a reason that names what hasn't passed

### Requirement: A failed capability keeps a profile from being offered

A fixture that fails or isn't supported in any trial SHALL be recorded against that fixture and listed in the route's limits. If it is one of the five that gate offering, the route SHALL be recorded `not_qualified` and the profile SHALL not be offered. No other model SHALL be tried.

#### Scenario: A failed capability keeps a profile from being offered
- **GIVEN** a fake server whose required tool call fails in one of three trials, as Inkling 2 Mini's did by hand
- **WHEN** the suite runs on that local route
- **THEN** the failure is recorded against its fixture, the profile isn't offered, the capability stays disabled and is listed in its limits, and no other model is tried

### Requirement: Not offered on OpenRouter

A local profile offered on the Local source SHALL still be refused `model_not_offered` wherever new work names it in a workspace on OpenRouter, with nothing substituted and nothing stored changed.

#### Scenario: Not offered on OpenRouter
- **GIVEN** Bonsai 2.5's profile offered on the Local source, in a workspace on OpenRouter
- **WHEN** a new run, the workspace default, a role override or an Expert's role binding names it
- **THEN** it is refused model_not_offered, no run starts, no other model is substituted, and nothing stored changes

### Requirement: The suite qualifies the route as the gateway sends it

The route qualification runner SHALL send `tool_required` and `tool_named_conflict` through the local route's own constraint, so a local route is qualified as runs send it (A7, A18).

#### Scenario: The suite qualifies the route as the gateway sends it
- **GIVEN** a fake suite server that answers each tool call within the JSON schema its request carries, and every other fixture as US-23.2's fake suite server does
- **WHEN** the route qualification runner runs US-3.4's suite on a local route without --paid
- **THEN** tool_required and tool_named_conflict pass in each of three trials through the route's constraint, each verdict is recorded as fake-server evidence, nothing is reserved, and nothing reaches OpenRouter

### Requirement: Bonsai 2.5's route is qualified again on this Mac

On the owner's request, US-3.4's suite SHALL run again on Bonsai 2.5's local route against the owner's `llama-server` in three trials, with the route enforcing required and named tool calls. Each result SHALL be recorded as live local evidence with the served model ID and the profile's pins, and US$0.00 SHALL be spent.

#### Scenario: Bonsai 2.5's route is qualified again on this Mac
- **GIVEN** the owner's request, and llama-server started by the runbook command, serving Bonsai 2.5's pinned Q2_0 on 127.0.0.1 with its weights checked against the download manifest
- **WHEN** US-3.4's suite runs on Bonsai 2.5's local route in three trials
- **THEN** each result is recorded as live local evidence apart from fake-server results, with the served model ID and the profile's pins, US$0.00 is spent, and nothing is sent to OpenRouter

### Requirement: The new result is stored and decides offering

A new forward migration SHALL update Bonsai 2.5's stored qualification, for its own canonical ID, from the live report. Its status SHALL be `qualified_with_limits` only when the five gating capabilities passed in all three trials, and every fixture that didn't pass in every trial SHALL be listed in its limits. Migration 69 SHALL keep its bytes. The Local source SHALL offer Bonsai 2.5 only when its stored status is `qualified_with_limits`.

#### Scenario: The new result is stored and decides offering
- **GIVEN** the live report of Bonsai 2.5's requalification, and Bonsai 2.5's row stored by migration 69 as not_qualified
- **WHEN** a new forward migration is applied on a disposable target after migration 69
- **THEN** Bonsai 2.5's row holds the report's date, configuration and limits, its status is qualified_with_limits only if plain_text, tool_auto, tool_required, schema_flat and stream_text passed in all three trials and not_qualified otherwise, each fixture that didn't pass in every trial is listed in its limits, migration 69 keeps its bytes, and the Local source offers Bonsai 2.5 only when its status is qualified_with_limits
