# release-qualification Specification

## Purpose
Report measured release outcomes, keeping held-out task results, local responsiveness and unmeasured targets distinct.

## Requirements

### Requirement: Measure the scoped release corpus

The release corpus SHALL be evaluated on the actual qualified configuration with results reported per category, and held-out data SHALL NOT be used for tuning.

#### Scenario: Measure the scoped release corpus

- **GIVEN** 100 protocol cases and 40 held-out tasks with three trials under the shared limits
- **WHEN** the actual qualified configuration is evaluated
- **THEN** results target at least 98 percent first-pass valid calls and 85 percent task success while permission/replay failures remain zero and category failures are reported

### Requirement: Measure local responsiveness separately

Local responsiveness and resource use SHALL be measured apart from model behavior, and a target without a measurement SHALL NOT be claimed as met.

#### Scenario: Measure local responsiveness separately

- **GIVEN** the declared local benchmark workload and configured remote concurrency
- **WHEN** API/event/cancellation/recovery behavior is measured
- **THEN** evidence reports p95 API below 300 ms, committed events below one second, cancellation acknowledgment within one second and eligible recovery within 60 seconds, or records an explicit supported revision rather than claiming unmeasured success
