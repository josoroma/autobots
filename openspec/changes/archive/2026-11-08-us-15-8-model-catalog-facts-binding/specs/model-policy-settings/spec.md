## ADDED Requirements

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
