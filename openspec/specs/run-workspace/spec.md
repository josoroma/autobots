# run-workspace Specification

## Purpose
TBD - created by archiving change us-4-6-sanitized-event-replay-run. Update Purpose after archive.

## Requirements

### Requirement: Reconnect from committed events
When a disconnected browser with a run event cursor reconnects, ordered authorized replay and live events SHALL reconstruct status without duplicates, with a snapshot when retained events cannot fill a gap.

#### Scenario: Reconnect from committed events
- **GIVEN** a run event cursor and a disconnected browser
- **WHEN** the user reconnects
- **THEN** ordered authorized replay and live events reconstruct status without duplicates, with a snapshot when retained events cannot fill a gap

### Requirement: Private execution state stays private
When activity from framework state that includes secrets or protected reasoning metadata is projected to the UI, only the sanitized envelope and concise decision and evidence summaries SHALL appear, with explicit paused, error and reconnecting states.

#### Scenario: Keep private execution state private
- **GIVEN** framework state includes secrets or protected reasoning metadata
- **WHEN** activity is projected to the UI
- **THEN** only the sanitized envelope and concise decision/evidence summaries appear, with explicit paused/error/reconnecting states

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

### Requirement: Plan task times on the fenced path

The worker SHALL record each plan task's start, at the first tool use that serves it, and its finish, when `complete_task` records its evidence. Both SHALL be recorded in database time, inside the worker's leased transaction, so a worker that has lost its lease writes neither. The first finish SHALL stand. The current task SHALL be the earliest open task that has started.

#### Scenario: Task times on the fenced path
- **GIVEN** a running run whose current worker starts and finishes plan tasks, and a stale worker that has lost its lease
- **WHEN** each records a task's start or finish
- **THEN** the current worker's times are stored in database time, the stale worker's write is refused, and the current task is the earliest open task that has started

### Requirement: A side panel on Runs

Selecting a run's row on Runs SHALL open a panel. It SHALL show the state badge, title, Expert and start time; the plan, with done, current and to-do markers in words, each task's tools and wall time; the spend, the tokens and "N of 20 metered tool calls" for the root run tree; and Open run with Pause, Resume and Cancel by state. Each command SHALL send the version the panel loaded, so a stale press is refused with a reload message. A terminal run's panel SHALL offer no Pause, Resume or Cancel.

#### Scenario: The panel
- **GIVEN** a running run with one done task, one current task and one to-do task, tool uses, and three metered tool calls in its root tree
- **WHEN** a member selects its row on Runs
- **THEN** a panel shows the state badge, title, Expert and start time, the plan with done, current and to-do markers in words, each task's tools and wall time, the spend, the tokens and "3 of 20 metered tool calls"

#### Scenario: Controls with the expected version
- **GIVEN** the panel of a running run whose version changed after the panel loaded
- **WHEN** the person presses Pause, then reloads and presses Pause again
- **THEN** the first is refused as stale with a reload message, the second pauses the run through its canonical transition, and a terminal run's panel offers no Pause, Resume or Cancel

### Requirement: Streamed result text

While a run's final result is written, the API SHALL emit ephemeral, coalesced `result.text.delta` events with the result text only, at schema version 1, never stored as durable events. Durable events and the stored artifact SHALL stay authoritative, and a reconnect SHALL rebuild from them. No reasoning, tool argument other than the result text, or raw framework value SHALL be streamed. A "Stream text as it's written" preference SHALL turn live display off in the browser.

#### Scenario: Result deltas, ephemeral and coalesced
- **GIVEN** a run writing its final result with a scripted model on a disposable stack
- **WHEN** its owner watches the run
- **THEN** result.text.delta events carry result text only, coalesced, at schema_version 1, none is stored as a durable event, and the text shown when the result completes equals the stored artifact

#### Scenario: Reconnect rebuilds from the artifact
- **GIVEN** a stream cut while the result is being written
- **WHEN** the browser reconnects and the result completes
- **THEN** the view is rebuilt from durable events and the stored artifact, and the final text equals the artifact

#### Scenario: Nothing private is streamed
- **GIVEN** a scripted model that also produces reasoning, tool arguments and framework values while writing
- **WHEN** the deltas are inspected
- **THEN** none carries reasoning, a tool argument or a raw framework value

#### Scenario: The preference turns live text off
- **GIVEN** "Stream text as it's written" turned off in Settings → Appearance
- **WHEN** a result is written
- **THEN** the browser shows no live text, and shows the result once its artifact is stored
