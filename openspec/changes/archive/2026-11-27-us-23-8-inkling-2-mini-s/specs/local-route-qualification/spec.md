# Spec Delta

## Purpose

The suite sends each local route its own output cap, and Inkling 2 Mini's route is qualified at that cap and stored (Decision 0041 A7, A11, A18; US-23.8).

## ADDED Requirements

### Requirement: The suite sends each local route its own output cap
The route qualification runner SHALL build each call on a local route with that route's own output cap, as a run on it sends, except the truncation fixture's, and SHALL record the cap in the report.

#### Scenario: The suite sends each local route its own output cap
- **GIVEN** Bonsai 2.5's and Inkling 2 Mini's local profiles, a fake suite server on loopback for each that records the requests it receives, and a fake OpenRouter client that fails if it is built
- **WHEN** the route qualification runner runs US-3.4's suite on each local route without --paid
- **THEN** every chat completion asks for the route's own output cap, 4,096 tokens for Bonsai 2.5 and 8,192 for Inkling 2 Mini, except the truncation fixture's, which asks for the small cap it truncates at, each report records the route's cap, nothing is reserved, and nothing reaches OpenRouter

### Requirement: Inkling 2 Mini's route is qualified on this Mac at its own output cap
On the owner's request, US-3.4's suite SHALL run on Inkling 2 Mini's local route against the owner's `llama-server` in three trials at its 8,192-token cap, recorded as live local evidence at US$0.00.

#### Scenario: Inkling 2 Mini's route is qualified on this Mac at its own output cap
- **GIVEN** the owner's request to requalify Inkling 2 Mini, and llama-server started by the runbook command, serving Inkling 2 Mini's pinned UD-Q3_K_XL on 127.0.0.1 with its weights checked against the profile's pin and the download manifest
- **WHEN** US-3.4's suite runs on Inkling 2 Mini's local route in three trials, each call at the route's 8,192-token output cap
- **THEN** each result is recorded as live local evidence apart from fake-server results, with the served model ID, the profile's pins and the output cap, US$0.00 is spent, and nothing is sent to OpenRouter

### Requirement: Inkling 2 Mini's qualification is stored
A forward migration SHALL store Inkling 2 Mini's qualification for its own canonical ID from the live report, with every fixture that didn't pass in every trial and SQLI-12's caveat in its limits.

#### Scenario: Inkling 2 Mini's qualification is stored
- **GIVEN** the live report of Inkling 2 Mini's qualification at its 8,192-token cap, in which plain_text, tool_auto, tool_required, schema_flat and stream_text passed in all three trials and schema_nested passed 2 of 3, and no stored qualification for Inkling 2 Mini
- **WHEN** a new forward migration is applied on a disposable target after migration 71
- **THEN** Inkling 2 Mini's row holds the report's date, configuration and limits for its own canonical ID with status qualified_with_limits, schema_nested is listed in its limits and stays disabled, its limits state that concurrent admission on a live route wasn't tested, Bonsai 2.5's row is unchanged, and migrations 69 to 71 keep their bytes
