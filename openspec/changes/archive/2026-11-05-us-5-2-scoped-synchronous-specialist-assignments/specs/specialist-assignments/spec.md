## ADDED Requirements

### Requirement: Narrowed child execution
When a specialist assignment is created for a parent with fixed policy, deadline and remaining allowance, child scope SHALL intersect parent scope, inherited roles SHALL remain fixed, and depth, headcount, outstanding and spend limits SHALL apply.

#### Scenario: Narrow child execution
- **GIVEN** a parent with fixed policy, deadline and remaining allowance
- **WHEN** a specialist assignment is created
- **THEN** child scope intersects parent scope, inherited roles remain fixed and depth/headcount/outstanding/spend limits apply

### Requirement: Reattachment after replay
When a parent repeats an assignment operation after restart and delegation resumes, the existing assignment or result SHALL be reused rather than creating a duplicate child, and model slots MUST NOT be held while awaiting child work.

#### Scenario: Reattach after replay
- **GIVEN** a parent repeats an assignment operation after restart
- **WHEN** delegation resumes
- **THEN** the existing assignment/result is reused rather than creating a duplicate child and model slots are not held while awaiting child work
