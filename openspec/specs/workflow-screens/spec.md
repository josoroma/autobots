# workflow-screens Specification

## Purpose
TBD - created by archiving change us-6-3-workflow-editor-execution-monitor. Update Purpose after archive.

## Requirements

### Requirement: Inspect a validated graph run
When the user validates, publishes and opens an execution of a draft graph and its published immutable version, typed errors or the exact version binding SHALL be visible with node-instance status and output emissions.

#### Scenario: Inspect a validated graph run
- **GIVEN** a draft graph and its published immutable version
- **WHEN** the user validates, publishes and opens an execution
- **THEN** typed errors or the exact version binding are visible with node-instance status and output emissions

### Requirement: UI state as a projection
When the browser reconnects during workflow execution and the monitor refreshes, it SHALL read authorized durable state rather than creating a second scheduler.

#### Scenario: Keep UI state a projection
- **GIVEN** the browser reconnects during workflow execution
- **WHEN** the monitor refreshes
- **THEN** it reads authorized durable state rather than creating a second scheduler

### Requirement: Workflows lists each workflow's facts, previews a version and its executions, and budgets an execution

Workflows SHALL list each workflow with its name, description, Experts in step order, published version and any draft, step count, last execution's state and time, and run count, with All, Published and Drafts tabs and a search by name. A preview SHALL show a chosen version's steps in order, each agent step with its label, Expert, model and granted tools, and the approval gate in words, with recent executions showing version, state, spend labelled estimated or reported, and duration. An execution SHALL take a budget from US$0.25 to US$5.00 in US$0.25 steps within the remaining daily cap, frozen on its run, and a budget outside that SHALL be refused with a typed code and start nothing.

#### Scenario: List with tabs and search
- **GIVEN** one workflow with a published version and a draft, and another with published versions only
- **WHEN** a member opens Workflows, switches between All, Published and Drafts, and searches by name
- **THEN** each row shows the name, the description, its Experts in step order such as "Research analyst → Brief writer", the published version and any draft, the number of steps, the last execution's state and time, and a run count, Drafts lists only the first workflow, and the search narrows the list by name

#### Scenario: Preview a version
- **GIVEN** a selected workflow with a published version and a draft
- **WHEN** the member uses the version switch
- **THEN** the panel shows the chosen version's steps in order, each agent step with its label, Expert, model and granted tools, and the approval gate marked in words

#### Scenario: Recent executions
- **GIVEN** executions of several versions, some with reported spend and some with estimated spend
- **WHEN** the panel lists recent executions
- **THEN** each shows its version, state, spend labelled estimated or reported, and duration

#### Scenario: A budget per execution
- **GIVEN** a workspace with more than US$5.00 left in its daily cap
- **WHEN** one execution is started with US$2.50 and another with US$5.25
- **THEN** the first's run freezes a US$2.50 limit, and the second is refused with a typed code and starts nothing
