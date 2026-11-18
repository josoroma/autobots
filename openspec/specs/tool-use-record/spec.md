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

A worker that lost its lease SHALL NOT record a tool use. A root run tree SHALL make at most 40 metered tool calls (Decision 0034 L3), and the next SHALL be denied `tool_budget_exceeded` before any request.

#### Scenario: Fenced and budgeted
- **GIVEN** a worker that has lost its lease, and separately a root run tree that has already made 40 metered tool calls against a fake transport
- **WHEN** each attempts another tool call
- **THEN** the first can't record a tool use, and the second is denied with tool_budget_exceeded before any request

### Requirement: The run workspace shows tools used

The run workspace SHALL list a run's tool uses once each, in order, with time and duration, tool and group, the plan task's title, public inputs, public outputs or a size, and outcome. New uses SHALL appear live and SHALL be announced politely, and a reload SHALL show the same list. The list SHALL keep heading and table semantics.

#### Scenario: Live and reloaded tool use
- **GIVEN** a running run that calls tools
- **WHEN** the owner watches its workspace, then reloads it
- **THEN** Tools used shows each use once, in order, with time and duration, tool and group, the plan task's title, public inputs, outputs or digests, and outcome

#### Scenario: Accessible list
- **GIVEN** the Tools used list is open
- **WHEN** a new use arrives
- **THEN** it is announced politely, the list keeps heading and table semantics, and axe reports no violations

### Requirement: The workflow monitor shows tool uses by node

The workflow monitor SHALL show each tool use under the node instance that made it.

#### Scenario: Flow view
- **GIVEN** a workflow execution whose nodes call tools
- **WHEN** the workflow monitor is opened
- **THEN** each tool use appears under the run of the node that made it
