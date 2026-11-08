## ADDED Requirements

### Requirement: The run list shows each run's facts, groups, filters and pages

The run list SHALL return, for this workspace only, each run's goal summary, label, status and stop reason, tasks complete of total, frozen profiles, charged spend, outstanding reservations, an unreported flag, and created and updated times. It SHALL count Active, Needs you and Finished runs on the server, filter by text and profile, and page with a keyset cursor that repeats and skips nothing. An amount with an outstanding reservation or an unreported charge SHALL be shown as an estimate.

#### Scenario: One row per run with its facts
- **GIVEN** runs in this workspace started as a goal, in an Expert session and by a workflow, with plans, frozen profiles and ledger entries, and runs in another workspace
- **WHEN** a member reads the run list through the BFF
- **THEN** each row for this workspace returns the goal summary, the Expert, session or workflow label, the status and stop_reason, tasks complete of total, the frozen profiles, charged spend, outstanding reservations, an unreported flag, and the created and updated times, and no run from the other workspace appears

#### Scenario: Status tabs with server counts
- **GIVEN** runs in every canonical state, including a paused run
- **WHEN** the member switches between All, Active, Needs you and Finished
- **THEN** Active holds queued, running, verifying, paused and cancelling runs, Needs you holds waiting_approval and waiting_input runs, Finished holds succeeded, failed and cancelled runs, and each tab's count comes from the server

#### Scenario: Text and profile filters with keyset paging
- **GIVEN** more matching runs than fit on one page
- **WHEN** the member filters by text that matches a goal or an Expert name, then by a profile, and presses Load more while a new run is admitted
- **THEN** only matching runs appear, the next page continues from the cursor with no row repeated or skipped, and the total reflects the filter

#### Scenario: Estimated spend is marked
- **GIVEN** one run with an outstanding reservation, one with an unreported charge and one that is fully reported
- **WHEN** the list renders
- **THEN** the first two show "≈" before their amounts, the third shows its reported amount without it, and each row's meter shows spent and reserved against the frozen limit in text as well as color
