## ADDED Requirements

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
