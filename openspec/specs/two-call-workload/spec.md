# two-call-workload Specification

## Purpose
TBD - created by archiving change us-12-4-measure-two-call-workload. Update Purpose after archive.

## Requirements

### Requirement: Measure two goals at once

The measurement SHALL do this: measure two goals at once.

#### Scenario: Measure two goals at once
- **GIVEN** a disposable stack on US-12.3's bound code, and the shared cap's remainder covers both goals' worst cases
- **WHEN** two goals run at once on Terra in one workspace, through the real API and workers
- **THEN** CPU, memory, disk and connections are recorded through the workload for the UI, API, workers and Docker, with each goal's outcome and the fingerprint it ran on

### Requirement: Don't count goals that never overlapped

The measurement SHALL do this: don't count goals that never overlapped.

#### Scenario: Don't count goals that never overlapped
- **GIVEN** the two goals' model calls never ran at the same time
- **WHEN** the result is assessed
- **THEN** the two-call workload is reported as not measured, never as stable

### Requirement: Report a failed result as failed

The measurement SHALL do this: report a failed result as failed.

#### Scenario: Report a failed result as failed
- **GIVEN** a service crashed, restarted or went unhealthy during the workload, or a run was stranded or reported a false status
- **WHEN** the result is recorded
- **THEN** it is reported as a failed stability result, LM-A09 stays partial and the owner is told

### Requirement: Stop at the shared cap

The measurement SHALL do this: stop at the shared cap.

#### Scenario: Stop at the shared cap
- **GIVEN** the shared ledger plus a goal's worst-case cost would pass US$1
- **WHEN** the goal is about to start
- **THEN** no request is sent, and the work left undone is reported as not run

### Requirement: Record what was spent

The measurement SHALL do this: record what was spent.

#### Scenario: Record what was spent
- **GIVEN** the goals have settled
- **WHEN** the result is recorded
- **THEN** each reported charge and the ledger's total stand beside actual key usage before and after, with no key in the record
