## ADDED Requirements

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
