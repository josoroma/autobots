## ADDED Requirements

### Requirement: Only supported claims close

The release record SHALL map every applicable requirement to current redacted evidence, and unresolved mandatory work SHALL prevent completion.

#### Scenario: Close only supported claims
- **GIVEN** final implementation, independent review, required suites and exercised runbooks
- **WHEN** release readiness is assessed
- **THEN** every applicable LC/MP/LM/DH requirement maps to current redacted evidence and unresolved mandatory work prevents completion

### Requirement: Evidence limits are preserved

The release record SHALL identify exact revisions and limitations, and SHALL NOT promote templates, skips or mocked provider behavior into live qualification.

#### Scenario: Preserve evidence limits
- **GIVEN** static, mock, disposable and live results coexist
- **WHEN** the release record is published
- **THEN** it identifies exact revisions and limitations without promoting templates, skips or mocked provider behavior into live qualification
