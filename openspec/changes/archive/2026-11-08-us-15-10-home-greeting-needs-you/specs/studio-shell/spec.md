## ADDED Requirements

### Requirement: Home greets the member and shows what needs them and recent runs

Home SHALL greet the member by the workspace's timezone, with "Good morning" from 05:00 to 11:59, "Good afternoon" from 12:00 to 17:59 and "Good evening" from 18:00 to 04:59, followed by the display name and the heading "What should we work on?". Needs you SHALL list pending approvals, linking to their Review, and runs waiting for input, linking to Reply on the run, and SHALL NOT list paused runs. Recent runs SHALL list the five newest runs with state, progress or spend, and relative time.

#### Scenario: Greeting by the workspace's timezone
- **GIVEN** a workspace whose timezone is America/Costa_Rica and a member whose display name is Ada
- **WHEN** Home loads at 09:00, 14:00 and 20:00 local time
- **THEN** it reads "Good morning", "Good afternoon" and "Good evening" in turn, each followed by "Ada", and then the heading "What should we work on?"

#### Scenario: Needs you
- **GIVEN** a pending approval, a run in waiting_input and a paused run
- **WHEN** Home loads
- **THEN** Needs you lists the approval with a link to its Review and the waiting run with a link to Reply on the run, and doesn't list the paused run

#### Scenario: Recent runs
- **GIVEN** seven runs in the workspace
- **WHEN** Home loads
- **THEN** Recent runs lists the five newest, each with its state, its progress or spend, and a relative time

#### Scenario: Greeting boundaries
- **GIVEN** the workspace timezone and local times 04:59, 05:00, 11:59, 12:00, 17:59 and 18:00
- **WHEN** Home renders at each time
- **THEN** it reads evening, morning, morning, afternoon, afternoon and evening
