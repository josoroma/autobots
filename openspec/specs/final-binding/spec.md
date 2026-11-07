# final-binding Specification

## Purpose
TBD - created by archiving change us-12-8-review-gate-0-last-decisions. Update Purpose after archive.

## Requirements

### Requirement: The last binding is reviewed and repeated

The record SHALL bind a new fingerprint after an independent review of what changed and a repeated Gate 0, and SHALL leave H1 and product acceptance to US-10.2's assessment.

#### Scenario: Review what changed and repeat Gate 0
- **GIVEN** Decision 0014, the LM-07 and LM-A04 revision and US-12.7's code bound to a new fingerprint, and a reviewer who did not author them
- **WHEN** the reviewer inspects everything changed since `05916d5e…`, and Gate 0's checks and the harness runbook are repeated on that revision, including `qualify_worker_inference.py` by hand
- **THEN** findings, dispositions and commands are recorded under docs/engineering/evidence/US-12.8/, scripts/evidence.py validates them and binds the new fingerprint, and the record leaves H1 and product acceptance to US-10.2

#### Scenario: Read the correction left unread
- **GIVEN** review-r3 says the release record's correction wasn't read again
- **WHEN** this review runs
- **THEN** the reader reads that corrected record, and what it finds is recorded with the other findings

#### Scenario: Void a stale binding
- **GIVEN** a blocking finding is open, or a source the fingerprint covers changed after it was bound
- **WHEN** this story, or evidence resting on its fingerprint, is assessed
- **THEN** the binding is void until the finding is resolved, the affected scope is reviewed again and the fingerprint is bound anew

### Requirement: The record states its limits

The record SHALL say what ran earlier, SHALL carry the H1.3 baseline without claiming H1, SHALL mark hook behavior not qualified, and SHALL keep earlier records as history.

#### Scenario: Say plainly what ran earlier
- **GIVEN** the live and real-sleep evidence of US-12.4, US-12.5 and US-12.6 ran before this binding
- **WHEN** the record is published
- **THEN** it says they ran at the earlier fingerprint, lists the inputs that differ, names any other evidence not repeated, and says no paid call or persistent change was made

#### Scenario: Carry the H1.3 baseline
- **GIVEN** H0 and H1 stories with no DH-W record, and US-12.3's record that carried their baseline is void
- **WHEN** the record is published
- **THEN** it says it carries their baseline, as revised H1.3 allows, and doesn't claim H1 is met

#### Scenario: Mark the hook behavior not qualified
- **GIVEN** Claude's crash, timeout and Stop recursion hook behavior has not been qualified
- **WHEN** the Gate 0 report is published
- **THEN** it marks that behavior not qualified, and script fixtures are not reported as actual event delivery

#### Scenario: Keep earlier records as history
- **GIVEN** US-12.3's and US-11.12's records describe their own fingerprints
- **WHEN** this binding replaces US-12.3's
- **THEN** both stay as history, and US-12.3's summary is marked void by this change the way US-11.12's was
