## ADDED Requirements

### Requirement: The sidebar groups the sections

The sidebar SHALL list its links in three groups, each named in text: the work group (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings). The current page SHALL be marked by more than color. The skip link SHALL stay the first tab stop and move focus to the main content.

#### Scenario: Three named groups
- **GIVEN** a signed-in workspace member on any screen
- **WHEN** the sidebar renders
- **THEN** its links read, in order, Home, Runs and Approvals in the work group, Experts, Workflows and Tools under Build, and Operations, Models and Settings under System, each group is named in text, and the current page is marked by more than color

#### Scenario: The skip link stays first
- **GIVEN** a fresh load of any screen
- **WHEN** the person presses Tab once
- **THEN** the skip link has focus, and activating it moves focus to the main content
