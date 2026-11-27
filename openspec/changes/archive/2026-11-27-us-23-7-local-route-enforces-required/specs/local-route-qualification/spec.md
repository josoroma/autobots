# Spec Delta

## Purpose

US-3.4's suite qualifies a local route as it now sends tool calls, Bonsai 2.5's route is qualified again, and its stored result decides offering on the Local source (Decision 0041 A7, A18; US-23.7).

## ADDED Requirements

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
