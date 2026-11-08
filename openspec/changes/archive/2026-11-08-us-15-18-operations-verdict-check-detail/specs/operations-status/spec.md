## ADDED Requirements

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
