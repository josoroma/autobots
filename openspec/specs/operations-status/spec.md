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

### Requirement: An Operations verdict and each check's measured value

Operations SHALL show the readiness sentence, "N of M checks pass" counted from the checks shown, the live worker count and the hold state. Each check SHALL show its measured value when one exists:
- the database answer time, as the p95 of the last 20 readiness probes;
- the applied migrations;
- storage bytes;
- disk free and total, as numbers;
- leased and queued jobs;
- the checkpoint adapter;
- the catalog's fetch time;
- a loopback-only bind check.

The status response SHALL hold no path and no secret, and no measured value beyond those Decision 0022 D5 lists. Producing it SHALL send nothing off the Mac beyond the catalog check that already existed. The delayed schedules, backups, restores, tracing, model routes and retention sections SHALL stay.

#### Scenario: Verdict
- **GIVEN** a disposable stack with all checks but one passing, two workers and no installation hold
- **WHEN** an operator opens Operations
- **THEN** it shows the readiness sentence, "N of M checks pass" with N and M matching the checks shown, a worker count of 2 and the hold state

#### Scenario: Values beside checks
- **GIVEN** at least 20 recorded readiness probes, applied migrations, stored objects, leased and queued jobs, a catalog fetch and a loopback-bound service
- **WHEN** the checks render
- **THEN** they show the database answer time as the p95 of the last 20 probes, the applied migrations, storage bytes, disk free and total as numbers, leased and queued jobs, the checkpoint adapter, the catalog's fetch time, and the loopback-only bind check

#### Scenario: Numbers only, and nothing more
- **GIVEN** the Operations status response
- **WHEN** it is inspected
- **THEN** it holds no path and no secret, and no measured value beyond those D5 lists, and producing it sends nothing off the Mac

#### Scenario: Existing sections stay
- **GIVEN** delayed schedules, a backup, a restore, model routes and retention settings
- **WHEN** Operations loads
- **THEN** the delayed schedules, backups, restores, tracing, model routes and retention sections still show

### Requirement: Jobs per hour on Operations

Operations SHALL chart the workspace's jobs per hour over the last 24 hours, in the workspace's timezone. Each hour SHALL be split into:
- succeeded;
- waited for a person, meaning the run entered `waiting_approval` or `waiting_input` in that hour;
- failed, with cancelled included;
- in progress, meaning paused or running.

The chart SHALL mark each series with labels or patterns as well as color, and SHALL have a text table that gives the same counts. Its read SHALL hold hourly counts by outcome only, with no identifier and no goal text.

#### Scenario: Jobs per hour with a text alternative
- **GIVEN** jobs on a disposable stack that succeeded, waited for a person and failed during the last 24 hours
- **WHEN** Operations loads
- **THEN** a chart shows jobs per hour for 24 hours split into those three outcomes, marked with labels or patterns as well as color, and a text table gives the same counts

#### Scenario: Counts only
- **GIVEN** the jobs chart's read
- **WHEN** its response is inspected
- **THEN** it holds hourly counts by outcome only, with no identifier and no goal text

#### Scenario: Buckets and series
- **GIVEN** jobs in the last 24 hours that succeeded, entered waiting_approval or waiting_input, failed, were cancelled, and are paused or running
- **WHEN** the chart is read in the workspace timezone
- **THEN** each hour counts succeeded, waited for a person, failed with cancelled included, and in progress, and the text table gives the same numbers

### Requirement: Schema readiness against shipped migrations

Readiness SHALL compare the database's applied migration count with the count this release ships. Fewer SHALL be `schema_behind` and stop admission. More SHALL be `schema_ahead`, degraded, and SHALL NOT stop admission. Equal SHALL be ready when the required objects exist. The required objects SHALL include what migrations 38 to 49 add. The recorded shipped count and newest name SHALL be checked against `supabase/migrations`. Operations SHALL show the applied count against the shipped count.

#### Scenario: Fewer applied migrations is behind
- **GIVEN** a disposable database that has applied fewer migrations than the release ships
- **WHEN** readiness is read
- **THEN** the schema check is unavailable with schema_behind, admission stops, and Operations shows the applied count against the shipped count

#### Scenario: All applied is ready
- **GIVEN** a disposable database with every shipped migration applied
- **WHEN** readiness is read
- **THEN** the schema check is ok, and Operations shows the two counts equal

#### Scenario: More applied is ahead, not blocking
- **GIVEN** a database that has applied more migrations than the release ships
- **WHEN** readiness is read
- **THEN** the schema check is degraded with schema_ahead, and admission isn't stopped by it

#### Scenario: The shipped count can't drift
- **GIVEN** the release's recorded migration count and newest name
- **WHEN** the harness checks run
- **THEN** they fail unless both match supabase/migrations

#### Scenario: Newer objects are required without a history
- **GIVEN** a database with no readable migration history
- **WHEN** readiness is read
- **THEN** the relations and columns that migrations 38 to 49 add are among those it requires
