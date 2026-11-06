## ADDED Requirements

### Requirement: A workspace's runs can be listed

The system SHALL list only the current workspace's runs, with their states and links, and listing SHALL start nothing and need no key.

#### Scenario: List this workspace's runs
- **GIVEN** this workspace and another each have runs, and no OpenRouter key is configured
- **WHEN** a person opens the run list
- **THEN** it shows only this workspace's runs with their states and links, and no run starts

### Requirement: A run can be inspected without private data

The inspector SHALL show each call's role, token counts and provider, canonical and wire identity, the upstream provider or unknown, each tool operation attempt and the run's checkpoints, with no raw checkpoint state, reasoning metadata or key.

#### Scenario: Inspect a run
- **GIVEN** a finished run with model calls, tool operations and checkpoints
- **WHEN** a person opens its inspector
- **THEN** it shows each call's role, token counts and provider, canonical and wire identity, the upstream provider or unknown, each tool operation attempt and the run's checkpoints, with no raw checkpoint state, reasoning metadata or key

### Requirement: Another workspace's run is refused

The inspector SHALL refuse a run in another workspace and show none of its data.

#### Scenario: Refuse another workspace's run
- **GIVEN** a run in another workspace
- **WHEN** a person requests its inspector
- **THEN** the request is refused and none of that run's data appears
