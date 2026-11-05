## ADDED Requirements

### Requirement: Honest work-record templates
Work-record and evidence templates SHALL contain traceable IDs, fingerprints, findings, expected and observed results and runbook links for the plan, implementation, independent review, verification and runbook stages, and their examples MUST remain visibly unexecuted.

#### Scenario: Prepare honest templates
- **GIVEN** the required plan, implementation, independent review, verification and runbook stages
- **WHEN** work-record and evidence templates are created
- **THEN** they contain traceable IDs, fingerprints, findings, expected/observed results and runbook links while examples remain visibly unexecuted

### Requirement: Rejected unsupported completion
Completion evidence validation MUST refuse a template, a stale fingerprint, a skipped check or an unresolved blocking review finding, and SHALL keep the missing evidence visible.

#### Scenario: Reject unsupported completion
- **GIVEN** a template, stale fingerprint, skipped check or unresolved blocking review finding
- **WHEN** completion evidence is validated
- **THEN** the work item cannot be marked complete and the missing evidence remains visible
