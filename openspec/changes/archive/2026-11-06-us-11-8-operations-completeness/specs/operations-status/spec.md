## ADDED Requirements

### Requirement: Operations shows the four facts

Operations SHALL show delayed schedules, OpenRouter availability, each restore's date and result, and each route's qualification date and limits, with no address, path, identifier or secret.

#### Scenario: Show the four missing facts
- **GIVEN** a delayed routine occurrence, a known OpenRouter status, a verified restore and a stored qualification record
- **WHEN** an operator opens Operations
- **THEN** it shows the delayed schedule, OpenRouter availability, the restore's date and result, and each route's qualification date and limits, with no address, path, identifier or secret

### Requirement: Operations says what is unknown or unavailable

Operations SHALL say when no restore is recorded and when OpenRouter can't be reached, stay usable, and make no model call.

#### Scenario: Say what is unknown or unavailable
- **GIVEN** no restore has been recorded and OpenRouter can't be reached
- **WHEN** Operations loads
- **THEN** it says none is recorded and OpenRouter is unavailable, the page stays usable, and no model call is made
