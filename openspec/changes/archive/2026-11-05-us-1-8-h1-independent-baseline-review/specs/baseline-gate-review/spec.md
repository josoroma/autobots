## ADDED Requirements

### Requirement: Honest Gate 0 closure
Required findings from an independent review of the baseline SHALL be resolved, its runbook SHALL be exercised, and the redacted report SHALL record real commands, outcomes, failures and recovery.

#### Scenario: Close Gate 0 honestly
- **GIVEN** positive/negative portable and disposable checks have current evidence
- **WHEN** an independent reviewer inspects the baseline and its runbook is exercised
- **THEN** required findings are resolved and the redacted report records real commands, outcomes, failures and recovery

### Requirement: Reported optional adapter status
When the portable baseline passes and Claude is incompatible, Gate 0 results SHALL keep the adapter explicitly inactive, and MUST NOT claim script fixtures as actual assistant event delivery.

#### Scenario: Report optional adapter status
- **GIVEN** the portable baseline passes but Claude is incompatible
- **WHEN** Gate 0 results are published
- **THEN** the adapter remains explicitly inactive and script fixtures are not claimed as actual assistant event delivery
