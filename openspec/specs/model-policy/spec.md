# model-policy Specification

## Purpose
TBD - created by archiving change us-2-6-two-profile-openrouter-factory. Update Purpose after archive.

## Requirements

### Requirement: Approved role map
A resolved role policy SHALL use DeepSeek for all 14 initial roles in a new workspace, and the documented precedence SHALL select only approved DeepSeek or explicit Astra bindings.

#### Scenario: Resolve the approved role map
- **GIVEN** a new workspace and optional run/workspace overrides
- **WHEN** a role policy is resolved
- **THEN** all 14 initial roles use DeepSeek and the documented precedence selects only approved DeepSeek or explicit Astra bindings

### Requirement: Refused drift and implicit routing
The factory MUST block unsupported dispatch on stale catalog metadata, canonical drift or an unsupported request option, SHALL use the fixed OpenRouter route and fallback settings, and MUST NOT introduce an implicit model or provider.

#### Scenario: Reject drift and implicit routing
- **GIVEN** stale catalog metadata, canonical drift or an unsupported request option
- **WHEN** the factory prepares an attempt
- **THEN** it blocks unsupported dispatch, uses the fixed OpenRouter route and fallback settings, and never introduces an implicit model or provider
