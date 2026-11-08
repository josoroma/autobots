# run-disclosure Specification

## Purpose
TBD - created by archiving change us-11-9-run-creation-disclosure-role. Update Purpose after archive.

## Requirements

### Requirement: Every run-creation screen discloses before starting

Each screen that creates a run SHALL state the selected model and roles, the budget and the categories of data sent to OpenRouter, and SHALL send nothing until the person presses Run.

#### Scenario: Disclose before starting
- **GIVEN** a person composing a goal on any screen that creates a run
- **WHEN** the form is shown
- **THEN** it states the selected model and roles, the budget and the categories of data sent to OpenRouter, and nothing is sent until the person presses Run

### Requirement: A person can choose a model for one run

A person SHALL be able to pick an approved model for a single run, which freezes it without changing the workspace default.

#### Scenario: Choose a model for one run
- **GIVEN** the two approved models
- **WHEN** a person picks the other one for a single run
- **THEN** that run freezes the choice, the workspace default is unchanged, and the run workspace shows the complete effective role map and says only the executor's binding dispatches in this release

### Requirement: Budgets, costs and errors can be read

The run workspace SHALL show token and spend budgets, and the inspector SHALL show reported and estimated costs labeled apart, errors and evidence links, with no private reasoning or key.

#### Scenario: Read budgets, costs and errors
- **GIVEN** a finished run with reported charges and a failed call
- **WHEN** a person opens the run workspace and its inspector
- **THEN** the workspace shows token and spend budgets, and the inspector shows reported and estimated costs labeled apart, errors and evidence links, with no private reasoning or key

### Requirement: An unapproved model is refused

A run request naming a model that isn't approved SHALL be refused, with no run started and the draft kept.

#### Scenario: Refuse an unapproved model
- **GIVEN** a run request naming a model that isn't approved
- **WHEN** it is submitted
- **THEN** it is refused, no run starts and the draft is kept

### Requirement: The composer offers Expert, budget and model chips and previews what the run would use

Home's composer SHALL offer an Expert chip, starting a direct session before admission when one is chosen, and a budget chip from US$0.25 to US$5.00 in US$0.25 steps, US$1.00 by default, never above the workspace's remaining daily cap. Admission SHALL freeze the chosen budget as the run's limit and refuse, with a typed code, a budget outside the range, off the step or above the remaining cap. Before Run, chips SHALL show each profile with the roles that resolve to it and the tools the run would be granted, from a preview endpoint that sends nothing to OpenRouter. Attached files SHALL show as chips with name, type and size.

#### Scenario: Budget choices within the daily cap
- **GIVEN** a workspace with US$2.10 left in its daily cap
- **WHEN** the owner opens the budget chip and starts a run with US$1.50
- **THEN** the chip offers US$0.25 to US$2.00 in steps of US$0.25 with US$1.00 selected first, the disclosure shows the chosen budget, and the admitted run freezes a US$1.50 limit

#### Scenario: A budget outside the range is refused
- **GIVEN** run requests with budgets of US$5.25, US$0.10, US$1.10 and one above the remaining daily cap
- **WHEN** each is submitted through the BFF
- **THEN** each is refused with a typed code, no run starts, and the draft is kept

#### Scenario: An Expert chip starts a direct session first
- **GIVEN** the composer once with one Expert chosen and once with no Expert
- **WHEN** the owner presses Run each time
- **THEN** the first starts a direct session with that Expert before admission and the run belongs to it, and the second is admitted as a goal run

#### Scenario: Preview what the run would use
- **GIVEN** a goal, a budget and a model choice in the composer
- **WHEN** the preview loads
- **THEN** chips show each profile with the roles that resolve to it, such as "Terra · 13 roles" and "Sol · researcher", and the tools the run would be granted, all from the preview endpoint, and nothing is sent to OpenRouter until Run

#### Scenario: Attached files as chips
- **GIVEN** two attached text files
- **WHEN** the composer shows them
- **THEN** each chip shows the file's name, type and size
