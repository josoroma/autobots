## Purpose

Record what each enabled OpenRouter route actually does, apart from mocked results, so that an advertised capability is not mistaken for working application behavior.

## ADDED Requirements

### Requirement: Qualify real adapter behavior

An explicitly authorized, bounded paid qualification of a selected model and configuration SHALL record actual route results and reported usage separately from mocks, and unsupported capabilities MUST remain disabled.

#### Scenario: Qualify real adapter behavior

- **GIVEN** an explicitly authorized bounded paid qualification and its selected model/configuration
- **WHEN** tool, strict-schema, fragmented-stream, continuation, refusal and truncation fixtures run
- **THEN** actual route results and reported usage are recorded separately from mocks, and unsupported capabilities remain disabled

### Requirement: Test forced selection honestly

Named tool choice SHALL be tested with competing tools and a conflicting prompt preference, and an automatic matching call MUST NOT count as proof of enforcement.

#### Scenario: Test forced selection honestly

- **GIVEN** two competing tools and a conflicting prompt preference
- **WHEN** named tool choice is exercised
- **THEN** the result demonstrates selector enforcement or records unsupported behavior rather than treating an automatic matching call as proof
