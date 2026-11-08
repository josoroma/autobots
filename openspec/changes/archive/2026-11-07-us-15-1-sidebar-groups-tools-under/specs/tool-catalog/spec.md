## MODIFIED Requirements

### Requirement: A Tools screen shows the catalog

The web app SHALL have a Tools entry under **Build**, directly after Workflows. Its page SHALL list tools by group with their classes and availability, keep filters in the URL, and show for a tool every registered version and its input and output fields with type, required flag, constraints and whether each is shown on run screens. An unavailable tool SHALL read as unavailable in text, with its typed reason and repair.

#### Scenario: Browse tools by group
- **GIVEN** the catalog holds tools in several groups
- **WHEN** the owner opens Tools from the sidebar entry placed under Build, directly after Workflows
- **THEN** tools appear by group with their classes and availability, the filters are kept in the URL, and a tool's detail lists every registered version and its input and output fields with type, required flag, constraints and whether they are public

#### Scenario: Show unavailable tools honestly
- **GIVEN** a tool whose key is missing or which is disabled_by_policy
- **WHEN** it is listed or opened
- **THEN** it reads as unavailable in text, not by color alone, with its typed reason and repair

#### Scenario: The browser specs follow the decision
- **GIVEN** tools.spec.ts and appearance.spec.ts
- **WHEN** they run against the regrouped sidebar
- **THEN** tools.spec.ts asserts Tools directly after Workflows under Build, no spec asserts Tools directly before Settings, and axe reports no violations
