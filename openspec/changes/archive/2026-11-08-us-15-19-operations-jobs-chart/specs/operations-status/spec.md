## ADDED Requirements

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
