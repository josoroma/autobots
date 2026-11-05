# workflow-execution Specification

## Purpose
TBD - created by archiving change us-6-2-workflow-readiness-emissions-restart. Update Purpose after archive.

## Requirements

### Requirement: Separate node instances and emissions
When inputs and repeated emissions arrive in a bounded foreach, conditional branch and join workflow, readiness SHALL use typed inputs and distinct instance and port identities, and skipped, waiting and failed branches SHALL remain distinguishable.

#### Scenario: Separate node instances and emissions
- **GIVEN** a bounded foreach, conditional branch and join workflow
- **WHEN** inputs and repeated emissions arrive
- **THEN** readiness uses typed inputs and distinct instance/port identities while skipped, waiting and failed branches remain distinguishable

### Requirement: Restart inside iteration
When a worker restarts after a workflow has committed some iteration emissions, it SHALL resume the saved instances without silently replacing prior outputs or duplicating known effects.

#### Scenario: Restart inside iteration
- **GIVEN** a workflow has committed some iteration emissions
- **WHEN** the worker restarts
- **THEN** it resumes the saved instances without silently replacing prior outputs or duplicating known effects
