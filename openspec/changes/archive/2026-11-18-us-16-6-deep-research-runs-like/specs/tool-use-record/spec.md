## MODIFIED Requirements

### Requirement: Recording is fenced and metered calls are limited

A worker that lost its lease SHALL NOT record a tool use. A root run tree SHALL make at most 40 metered tool calls (Decision 0034 L3), and the next SHALL be denied `tool_budget_exceeded` before any request.

#### Scenario: Fenced and budgeted
- **GIVEN** a worker that has lost its lease, and separately a root run tree that has already made 40 metered tool calls against a fake transport
- **WHEN** each attempts another tool call
- **THEN** the first can't record a tool use, and the second is denied with tool_budget_exceeded before any request
