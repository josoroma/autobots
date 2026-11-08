## ADDED Requirements

### Requirement: Workspace choice

A member of several workspaces SHALL be able to choose, and change, the workspace member screens act on. The choice SHALL be kept in an HttpOnly, SameSite=Strict cookie that only a same-origin, CSRF-checked request for a workspace the session belongs to can set. The BFF SHALL send it as `X-Autobots-Workspace`, and the API SHALL still check membership on every request. There SHALL be no implicit default for a member of several workspaces. A member of one workspace SHALL see no chooser.

#### Scenario: Choose, then work
- **GIVEN** a member of two workspaces, signed in with no workspace chosen
- **WHEN** they choose one in the sidebar
- **THEN** member screens show that workspace's data, and the choice survives a reload

#### Scenario: Change the workspace
- **GIVEN** that member working in one workspace
- **WHEN** they choose the other
- **THEN** member screens show the other workspace's data

#### Scenario: The browser's choice is still checked
- **GIVEN** a session whose chosen workspace is one the user isn't a member of
- **WHEN** a member screen is requested
- **THEN** the API refuses it, and no data of that workspace is returned

#### Scenario: Only a same-origin, CSRF-checked request sets the choice
- **GIVEN** a request to set the workspace without a valid origin or CSRF token
- **WHEN** it is sent
- **THEN** it is refused and the choice is unchanged

#### Scenario: One workspace needs no choice
- **GIVEN** a member of exactly one workspace
- **WHEN** they sign in
- **THEN** no workspace chooser asks for a choice, and member screens work as before
