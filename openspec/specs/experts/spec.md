# experts Specification

## Purpose
TBD - created by archiving change us-5-1-versioned-experts-direct-sessions. Update Purpose after archive.

## Requirements

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

### Requirement: Expert cards show usage, effect filters and a way to start

Experts SHALL show each Expert's executor role and profile, its first four tools and a count of the rest, its run count and last run, Start run, and a note in words when a tool needs approval on every call. Experts SHALL filter by All, Can change things outside and Read only, with counts that add up, and by name.

#### Scenario: Card facts
- **GIVEN** an Expert whose latest version binds the executor to a profile and grants six tools, and which has three runs
- **WHEN** a member opens Experts
- **THEN** its card shows the executor role and profile, the first four tools followed by "+2", a run count of 3 with the time of the last run, and Start run

#### Scenario: Start run discloses first
- **GIVEN** an Expert's card
- **WHEN** the member activates Start run
- **THEN** run creation for that Expert shows the MP-07 disclosure, and nothing is sent until Run is pressed

#### Scenario: Can change things outside
- **GIVEN** Experts that grant a consequential tool and Experts that grant none
- **WHEN** the member picks Can change things outside, then types part of a name in the search
- **THEN** each filter shows its count, Can change things outside lists exactly the Experts with a consequential tool, and the search narrows the list by name

#### Scenario: Approval note
- **GIVEN** an Expert granting a tool that needs approval on every call, such as create_github_issue
- **WHEN** its card renders
- **THEN** the card says so in words, such as "Approval on every issue"

#### Scenario: Read only is the complement
- **GIVEN** an Expert whose only writing tool is save_artifact and another granting create_github_issue
- **WHEN** the person picks Read only, then Can change things outside
- **THEN** the first Expert is listed under Read only, the second under Can change things outside, and the two counts add up to All
