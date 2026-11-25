## ADDED Requirements

### Requirement: No marks, same record

On the stealth browser nothing SHALL be drawn on the page, and each step's record SHALL name the elements it pressed or typed into, by action, kind and label, read from a world the page can't see.

#### Scenario: No marks, same record
- **GIVEN** a stealth browse on browser-use of the qualification host that presses and types, on a disposable stack with a scripted model
- **WHEN** it finishes
- **THEN** the page's document gained no node from browser-use, the page saw no trace of the worker's reading, and each step's record names the elements it pressed or typed into by action, kind and label

### Requirement: Never the typed value, and at most ten

A step SHALL record at most ten elements, and SHALL NOT record a typed value anywhere.

#### Scenario: Never the typed value, and at most ten
- **GIVEN** a stealth browse whose step types a planted value and presses more than ten elements
- **WHEN** its step is recorded
- **THEN** the record names ten elements, and the planted value is in no row, event or log line

### Requirement: The box keeps its highlights

On the box browser-use's highlights SHALL stay on, and its steps SHALL name no elements.

#### Scenario: The box keeps its highlights
- **GIVEN** a browse on browser-use of an Expert set to box
- **WHEN** it presses and types
- **THEN** browser-use's highlights are on, and its steps' records name no elements

### Requirement: The run's tool row shows them

The run's tool row SHALL show what each stealth step pressed or typed into, and SHALL show a step recorded before as it was.

#### Scenario: The run's tool row shows them
- **GIVEN** a stealth browse's recorded steps, and a step recorded before the change
- **WHEN** a member opens the browse's steps in the run's tool row
- **THEN** each stealth step shows what it pressed or typed into, and the earlier step shows its page, submits and screenshot as before

### Requirement: Steps keep a pace

On the stealth browser, steps SHALL be at least 2 seconds apart on either engine.

#### Scenario: Steps keep a pace
- **GIVEN** a stealth browse of several steps, and a scripted model that answers at once
- **WHEN** it runs on browser-use, and again on Autobots' read-only loop
- **THEN** on both its steps are at least 2 seconds apart

### Requirement: One browse of a site at a time

One stealth browse of a site SHALL run at a time across the install. Another SHALL wait within its own time limit, or end `max_seconds` without running. A box browse SHALL NOT wait.

#### Scenario: One browse of a site at a time
- **GIVEN** a stealth browse of example.com in one workspace, still running
- **WHEN** stealth browses of example.com start in another workspace, one whose time limit outlasts the first and one whose doesn't, and a box browse of example.com starts
- **THEN** the one that outlasts it waits and runs after the first ends, the other ends max_seconds without running, and the box browse doesn't wait
