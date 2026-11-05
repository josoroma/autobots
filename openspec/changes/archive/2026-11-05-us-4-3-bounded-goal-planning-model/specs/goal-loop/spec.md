## ADDED Requirements

### Requirement: Goal and evidence preserved through planning
When the loop proposes and revises a validated plan for an admitted goal, versioned tasks SHALL retain criteria, completed evidence and revision reasons without expanding scope.

#### Scenario: Preserve goal and evidence through planning
- **GIVEN** an admitted original goal, scope and criteria
- **WHEN** the loop proposes and revises a validated plan
- **THEN** versioned tasks retain criteria, completed evidence and revision reasons without expanding scope

### Requirement: Root limits
When the loop reaches a limit of the root call, tool, repair, child or time envelope, or receives invalid structured output, it SHALL stop new work or perform only the allowed repair, and return honest partial or failure information instead of retrying without bound.

#### Scenario: Stop within root limits
- **GIVEN** the configured root call/tool/repair/child/time envelope
- **WHEN** the loop reaches a limit or receives invalid structured output
- **THEN** new work stops or performs only the allowed repair and returns honest partial/failure information instead of unbounded retries
