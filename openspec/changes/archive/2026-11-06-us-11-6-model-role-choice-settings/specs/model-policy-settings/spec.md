## ADDED Requirements

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
