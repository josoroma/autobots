# routines Specification

## Purpose
TBD - created by archiving change us-7-1-explicit-routines-deduplicated-scheduled. Update Purpose after archive.

## Requirements

### Requirement: Deduplicated occurrences
When duplicate triggers arrive or the Mac wakes after missed work for a routine with frozen configuration, timezone, scope and budgets, unique occurrence keys SHALL prevent duplicates and the default no-overlap and one-catch-up policy SHALL be applied visibly.

#### Scenario: Deduplicate and recover occurrences
- **GIVEN** a routine with frozen configuration, timezone, scope and budgets
- **WHEN** duplicate triggers arrive or the Mac wakes after missed work
- **THEN** unique occurrence keys prevent duplicates and the default no-overlap/one-catch-up policy is applied visibly

### Requirement: Explicit scheduling
When future scheduling is evaluated with a saved provider key or an edited routine, the key alone SHALL start no job, and edits MUST NOT mutate admitted runs or widen their inference or tool permissions.

#### Scenario: Keep scheduling explicit
- **GIVEN** a saved provider key or an edited routine
- **WHEN** future scheduling is evaluated
- **THEN** the key alone starts no job and edits do not mutate admitted runs or widen their inference/tool permissions
