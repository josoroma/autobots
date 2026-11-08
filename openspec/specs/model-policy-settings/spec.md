# model-policy-settings Specification

## Purpose
TBD - created by archiving change us-11-6-model-role-choice-settings. Update Purpose after archive.

## Requirements

### Requirement: An owner chooses the workspace default

Settings SHALL list each approved model's canonical and wire identity and save the workspace default, and only a run admitted afterward SHALL freeze the new choice.

#### Scenario: Choose the workspace default
- **GIVEN** an owner on Settings, which lists each approved model's canonical and wire identity
- **WHEN** the owner saves a different workspace default
- **THEN** a new run freezes that choice, and a run already admitted keeps its bindings

### Requirement: The screen says what role overrides do

The screen SHALL say that only the executor's binding dispatches in this release, that other differing roles don't take effect, and that a differing summarizer pauses the run with route_not_bound.

#### Scenario: Say what a role override does
- **GIVEN** an effective policy whose executor and another role differ, including when only the executor was overridden
- **WHEN** the screen shows that policy
- **THEN** it says only the executor's binding dispatches in this release, other differing roles don't take effect, and a summarizer that differs pauses the run with route_not_bound

### Requirement: A stale save is refused

A save made from an outdated screen SHALL be refused with a reload message, leaving the stored policy unchanged.

#### Scenario: Refuse a stale save
- **GIVEN** the policy changed after the screen loaded
- **WHEN** the owner saves
- **THEN** the save is refused with a reload message, and the stored policy is unchanged

### Requirement: Models shows catalog facts, binding sources and form actions

Models SHALL show each approved profile's catalog input and output price per 1M tokens, its supported parameters as capabilities labelled "from the catalog" and kept apart from qualification, and the catalog's fetch time. Each role's binding SHALL say whether it comes from a run override, a workspace override, the workspace default or the built-in default, on Models and in a run's role map. Discard SHALL return the form to its saved state. Reset all SHALL clear every role override under the expected version, refusing a stale one. The summary SHALL count the saved policy's roles that follow the workspace default.

#### Scenario: Catalog facts apart from qualification
- **GIVEN** a fresh catalog fetch with prices and supported parameters for each approved profile
- **WHEN** the owner opens Models
- **THEN** each profile shows its input and output price per 1M tokens, its supported parameters as capabilities labelled "from the catalog" and kept separate from its qualification, and the catalog's fetch time

#### Scenario: Where each binding comes from
- **GIVEN** a workspace with no saved default and one workspace role override, and a run admitted with a run role override
- **WHEN** Models and that run's role map are shown
- **THEN** each role says whether its binding comes from a run override, a workspace override, the workspace default or the built-in default, and researcher reads Sol from the built-in default where nothing else names it

#### Scenario: Discard and Reset all
- **GIVEN** unsaved edits on the form and two saved role overrides
- **WHEN** the owner presses Discard, then Reset all, and then Reset all again from a screen loaded before that reset
- **THEN** Discard returns the form to its saved state, the first Reset all clears both overrides with the expected version, the stale one is refused with a reload message, and the summary's count of roles that follow the workspace default matches the saved policy
