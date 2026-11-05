## ADDED Requirements

### Requirement: Configuration versions
When a revision of an Expert with instructions, tools, skills and model-role binding is saved and new or existing sessions dispatch work, new work SHALL use the chosen revision and in-flight work SHALL preserve its frozen revision and permissions.

#### Scenario: Preserve configuration versions
- **GIVEN** an Expert with instructions, tools, skills and model-role binding
- **WHEN** a revision is saved and new or existing sessions dispatch work
- **THEN** new work uses the chosen revision and in-flight work preserves its frozen revision and permissions

### Requirement: Routing within granted scope
When an assignment is selected in a coordinator or direct Expert session, the configured Expert and allowed tools SHALL be visible, and no implicit model or broader connector grant MUST be added.

#### Scenario: Route within granted scope
- **GIVEN** a coordinator or direct Expert session
- **WHEN** an assignment is selected
- **THEN** the configured Expert and allowed tools are visible and no implicit model or broader connector grant is added
