# tool-use-record Specification

## Purpose
TBD - created by archiving change us-14-3-durable-tool-use-record. Update Purpose after archive.

## Requirements

### Requirement: Every dispatch is recorded

The gateway SHALL record each dispatch exactly once, of every class and including denials, with the tool, version and group as dispatched, the plan task it served, database times, outcome and typed code. An effectful use SHALL carry its receipt's operation ID. The record SHALL be private, and a run's uses SHALL be listed in order with the task's title.

#### Scenario: Record every dispatch
- **GIVEN** a run that calls a pure, a read-only and an effectful tool, and has one call denied
- **WHEN** the calls finish and the run's tool uses are listed
- **THEN** each dispatch has exactly one private tool-use row with tool, version, group, plan task, database times, outcome and typed code, the effectful one carries its receipt's operation ID, and the listing returns them in order with the task's title

### Requirement: Only public fields leave the record

Events SHALL carry identifiers, outcome, code and duration only, at schema version 1. The listing SHALL show only the fields a definition lists as public, URLs without query or fragment, and digests and sizes for content. No configured key value SHALL appear in a row, event, receipt, checkpoint or log line.

#### Scenario: Public projection and events
- **GIVEN** a tool whose definition marks some fields public, and a fake key configured
- **WHEN** its use is streamed as tool.use.started and tool.use.completed and then listed
- **THEN** the events carry identifiers, outcome, code and duration only at schema_version 1, the listing shows only public fields, URLs without query or fragment, and digests and sizes for content, and the fake key appears in no row, event, receipt, checkpoint or log line

### Requirement: Recording is fenced and metered calls are limited

A worker that lost its lease SHALL NOT record a tool use. A root run tree SHALL make at most 20 metered tool calls, and the next SHALL be denied `tool_budget_exceeded` before any request.

#### Scenario: Fenced and budgeted
- **GIVEN** a worker that has lost its lease, and separately a root run tree that has already made 20 metered tool calls against a fake transport
- **WHEN** each attempts another tool call
- **THEN** the first can't record a tool use, and the second is denied with tool_budget_exceeded before any request
