# tool-guide Specification

## Purpose
TBD - created by archiving change us-14-20-tool-guide-shown-modal. Update Purpose after archive.

## Requirements

### Requirement: Every tool carries a guide

The tool guide and its modal SHALL behave so that every descriptor carries a guide with non-empty what, when and why texts, and the Pydantic contract, the generated OpenAPI document and the TypeScript client include guide.

#### Scenario: Every tool carries a guide
- **GIVEN** the registry's tools and the planned descriptors the catalog lists as disabled_by_policy
- **WHEN** GET /v1/tools and each GET /v1/tools/{tool_id}/versions/{version} are read
- **THEN** every descriptor carries a guide with non-empty what, when and why texts, and the Pydantic contract, the generated OpenAPI document and the TypeScript client include guide

### Requirement: A tool without a guide fails a test

The tool guide and its modal SHALL behave so that it fails and names that tool.

#### Scenario: A tool without a guide fails a test
- **GIVEN** a test registry holding a tool definition whose guide is missing or has an empty text
- **WHEN** the catalog's guide test runs
- **THEN** it fails and names that tool

### Requirement: Choosing a tool opens its modal

The tool guide and its modal SHALL behave so that a modal dialog opens with ?tool=<id> in the URL, showing the tool's title and availability, the repair for the unavailable tool, then What, When and Why, then Inputs and Outputs giving each field's name, type, required and whether it is shown in records, and no side panel is rendered.

#### Scenario: Choosing a tool opens its modal
- **GIVEN** a member on the Tools page of a disposable stack, with an available tool and a key_missing tool in the catalog
- **WHEN** the member chooses each tool from the list, and separately opens /tools?tool=<id> directly
- **THEN** a modal dialog opens with ?tool=<id> in the URL, showing the tool's title and availability, the repair for the unavailable tool, then What, When and Why, then Inputs and Outputs giving each field's name, type, required and whether it is shown in records, and no side panel is rendered

### Requirement: Granted to, Copy schema and the full page from the modal

The tool guide and its modal SHALL behave so that Granted to lists that Expert, the clipboard holds exactly the shown version's input JSON Schema, and /tools/{tool_id} opens the full detail as a page.

#### Scenario: Granted to, Copy schema and the full page from the modal
- **GIVEN** the modal open for a tool that an Expert's latest version grants
- **WHEN** the member reads Granted to, presses Copy schema and follows the link to the full detail page
- **THEN** Granted to lists that Expert, the clipboard holds exactly the shown version's input JSON Schema, and /tools/{tool_id} opens the full detail as a page

### Requirement: Closing returns focus to the tool's link

The tool guide and its modal SHALL behave so that the dialog closes each time and focus returns to the link of the tool that opened it.

#### Scenario: Closing returns focus to the tool's link
- **GIVEN** the modal opened from a tool's link in the list
- **WHEN** it is closed with Escape, then reopened and closed with the Close button, then reopened and closed with a click outside the dialog
- **THEN** the dialog closes each time and focus returns to the link of the tool that opened it

### Requirement: Accessible in both themes

The tool guide and its modal SHALL behave so that axe reports no violations in either theme, and the dialog is a native dialog element labelled by the tool's title.

#### Scenario: Accessible in both themes
- **GIVEN** the modal open in the light theme and in the dark theme
- **WHEN** axe scans the page and a keyboard user tabs through the dialog
- **THEN** axe reports no violations in either theme, and the dialog is a native dialog element labelled by the tool's title
