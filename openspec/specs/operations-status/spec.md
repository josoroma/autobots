# operations-status Specification

## Purpose
TBD - created by archiving change us-11-8-operations-completeness. Update Purpose after archive.

## Requirements

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

### Requirement: Members can read service readiness

Any member of the workspace SHALL be able to read the readiness of the API, worker, database and OpenRouter authentication, each in words, without counts, paths or secrets, and without a model call. The shell SHALL show "All local services ready", or name the first service that isn't ready. Home SHALL show each service's readiness in text.

#### Scenario: All ready
- **GIVEN** a disposable stack whose API, worker and database are ready and whose OpenRouter authentication is valid
- **WHEN** a member who isn't the owner opens any screen and then Home
- **THEN** the shell's line reads "All local services ready", and Home shows the API, worker and database as ready and OpenRouter as authenticated, each in words

#### Scenario: Name the service that isn't ready
- **GIVEN** a disposable stack whose worker has no current heartbeat and whose other services are ready
- **WHEN** the member opens any screen and then Home
- **THEN** the shell's line names the worker as not ready, Home's worker chip says so in text, and the screens stay usable

#### Scenario: Nothing private in the member read
- **GIVEN** the member readiness read
- **WHEN** its response is inspected
- **THEN** it holds readiness states only, with no counts, no paths and no secret, and reading it makes no model call
