# model-offer Specification

## Purpose
TBD - created by archiving change us-12-1-stop-offering-deepseek-new. Update Purpose after archive.

## Requirements

### Requirement: Leave it out of every choice

New work SHALL follow Decision 0013 on DeepSeek: leave it out of every choice.

#### Scenario: Leave it out of every choice
- **GIVEN** each screen that creates a run or sets a model for future runs, including the goal composer, a session, Continue in a new run, the workspace default, role overrides and the Expert editor
- **WHEN** its model choices are shown
- **THEN** DeepSeek isn't among them

### Requirement: Refuse it through the API

New work SHALL follow Decision 0013 on DeepSeek: refuse it through the api.

#### Scenario: Refuse it through the API
- **GIVEN** a request naming DeepSeek for a new run, the workspace default, a role override or an Expert's role binding
- **WHEN** it is submitted
- **THEN** it is refused with a reason saying DeepSeek isn't offered for new runs until it's qualified, no run starts and nothing stored changes

### Requirement: Refuse a saved choice without substituting

New work SHALL follow Decision 0013 on DeepSeek: refuse a saved choice without substituting.

#### Scenario: Refuse a saved choice without substituting
- **GIVEN** a workspace default, role override or Expert version saved earlier that names DeepSeek
- **WHEN** a new run, workflow run or routine occurrence would resolve to it
- **THEN** it is refused with the same reason, no run starts, no other model is substituted and the saved choice isn't rewritten

### Requirement: Leave admitted runs as they are

New work SHALL follow Decision 0013 on DeepSeek: leave admitted runs as they are.

#### Scenario: Leave admitted runs as they are
- **GIVEN** a run already admitted on DeepSeek
- **WHEN** it resumes, or a child is admitted under its frozen policy
- **THEN** it keeps its frozen route, and the registry still holds the profile

### Requirement: Keep its record visible

New work SHALL follow Decision 0013 on DeepSeek: keep its record visible.

#### Scenario: Keep its record visible
- **GIVEN** DeepSeek's stored qualification record
- **WHEN** an owner opens Settings and Operations
- **THEN** the record shows with its date, configuration and limits, and Settings lists the model as approved and says it isn't offered for new runs

### Requirement: Keep the qualification runner working

New work SHALL follow Decision 0013 on DeepSeek: keep the qualification runner working.

#### Scenario: Keep the qualification runner working
- **GIVEN** the route qualification runner and a fake transport
- **WHEN** it is run for DeepSeek
- **THEN** it sends on DeepSeek's route, nothing that stops new runs refuses it, and this story makes no paid call
