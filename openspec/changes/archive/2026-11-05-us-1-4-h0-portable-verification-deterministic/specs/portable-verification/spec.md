## ADDED Requirements

### Requirement: Portable verification profiles
The `harness`, `fast` and `full` verification profiles SHALL run without a coding assistant or model credential, and SHALL return distinct results for pass, failure and prerequisite errors, without paid inference or implicit installation.

#### Scenario: Run independently of Claude
- **GIVEN** the prepared repository and no model credential
- **WHEN** the portable harness, fast or full verification profile runs
- **THEN** required checks return distinct pass, failure or prerequisite errors without paid inference or implicit installation

### Requirement: Deterministic hook dispatcher
The hook dispatcher MUST use bounded validated input, documented event behavior and redacted diagnostics, and MUST NOT treat filenames as shell code.

#### Scenario: Handle unsafe hook input
- **GIVEN** malformed input, shell metacharacters, symlinks, timeout or a missing executable fixture
- **WHEN** the deterministic hook dispatcher processes the fixture
- **THEN** it uses bounded validated input, documented event behavior and redacted diagnostics without treating filenames as shell code
