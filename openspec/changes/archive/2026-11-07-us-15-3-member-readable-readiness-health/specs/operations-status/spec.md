## ADDED Requirements

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
