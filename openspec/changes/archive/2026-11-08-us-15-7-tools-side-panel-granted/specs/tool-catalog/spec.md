## ADDED Requirements

### Requirement: A tool's detail opens beside the list and says who holds it

Tools SHALL show each group's count, keep its text, provider and availability filters and the selected tool in the URL, and open a tool's detail in a side panel while `/tools/{tool_id}` still opens it as a page. The detail SHALL list the Experts whose latest version grants the tool and the published workflows that reach it through an agent step, and SHALL copy exactly the shown version's input schema.

#### Scenario: Group list and side panel
- **GIVEN** a catalog with tools in several groups
- **WHEN** a member opens Tools, filters by text and by provider and availability, and selects a row
- **THEN** each group shows its count, the filters stay in the URL, the row's detail opens in a side panel, and /tools/{tool_id} still opens the same detail as a page

#### Scenario: Granted to
- **GIVEN** an Expert whose latest version grants the tool, another Expert whose only grant of it is in an older version, and a published workflow whose agent step uses the first Expert
- **WHEN** the tool's detail opens
- **THEN** it lists the first Expert and the published workflow, and not the Expert whose grant is only in an older version

#### Scenario: Copy schema
- **GIVEN** a tool's detail showing one of its versions
- **WHEN** the member presses Copy schema
- **THEN** the clipboard holds exactly that version's input JSON Schema
