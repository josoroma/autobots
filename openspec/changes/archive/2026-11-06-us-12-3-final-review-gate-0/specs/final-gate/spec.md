## ADDED Requirements

### Requirement: Review what changed and repeat Gate 0

The final review SHALL do this: review what changed and repeat gate 0.

#### Scenario: Review what changed and repeat Gate 0
- **GIVEN** the final code of US-12.1 and US-12.2 bound to a fingerprint, and a reviewer who did not author it
- **WHEN** the reviewer inspects everything changed since US-11.12's bound fingerprint, and Gate 0's checks and the harness runbook are repeated on that revision
- **THEN** findings, dispositions and commands are recorded under docs/engineering/evidence/US-12.3/, scripts/evidence.py validates them, and the record leaves H1 and product acceptance to US-10.2's assessment

### Requirement: Carry the H1.3 baseline

The final review SHALL do this: carry the h1.3 baseline.

#### Scenario: Carry the H1.3 baseline
- **GIVEN** H0 and H1 stories delivered under Decision 0003 with no DH-W record
- **WHEN** the record is published
- **THEN** it says it carries their baseline, as revised H1.3 allows, and doesn't claim H1 is met

### Requirement: Void a stale binding

The final review SHALL do this: void a stale binding.

#### Scenario: Void a stale binding
- **GIVEN** a blocking finding is open, or a source the fingerprint covers changed after it was bound, which `scripts/evidence.py` decides and which leaves out `SPECS.md`, `CODEBASE.md` and evidence as records
- **WHEN** this story, or evidence resting on its fingerprint, is assessed
- **THEN** the binding is void until the finding is resolved, the affected scope is reviewed again and the fingerprint is bound anew

### Requirement: Mark the hook behavior not qualified

The final review SHALL do this: mark the hook behavior not qualified.

#### Scenario: Mark the hook behavior not qualified
- **GIVEN** Claude's crash, timeout and Stop recursion hook behavior has not been qualified
- **WHEN** the Gate 0 report is published
- **THEN** it marks that behavior not qualified, and script fixtures are not reported as actual event delivery
