## ADDED Requirements

### Requirement: A Tools screen shows the catalog

The web app SHALL have a Tools entry directly before Settings. Its page SHALL list tools by group with their classes and availability, keep filters in the URL, and show for a tool every registered version and its input and output fields with type, required flag, constraints and whether each is shown on run screens. An unavailable tool SHALL read as unavailable in text, with its typed reason and repair.

#### Scenario: Browse tools by group
- **GIVEN** the catalog holds tools in several groups
- **WHEN** the owner opens Tools from the sidebar entry placed directly before Settings
- **THEN** tools appear by group with their classes and availability, the filters are kept in the URL, and a tool's detail lists every registered version and its input and output fields with type, required flag, constraints and whether they are public

#### Scenario: Show unavailable tools honestly
- **GIVEN** a tool whose key is missing or which is disabled_by_policy
- **WHEN** it is listed or opened
- **THEN** it reads as unavailable in text, not by color alone, with its typed reason and repair

### Requirement: A group grant is saved as explicit tools

An Expert version MAY grant whole groups. Saving it SHALL expand each group into the Expert-grantable tools it holds then, and record both the explicit tools and the groups. A saved version SHALL NOT change when a group changes later. A grant naming a tool unavailable in this install SHALL be refused with a typed code.

#### Scenario: A group grant stays explicit
- **GIVEN** an owner grants a group to an Expert version in the editor
- **WHEN** the expansion is previewed and the version is saved
- **THEN** the version records the expanded tool versions and the groups they came from, a tool added to the group later doesn't change it, and a grant naming an unavailable tool is refused with a typed code
