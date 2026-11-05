## ADDED Requirements

### Requirement: Publish a verified object
When an authorized artifact write with stable operation identity uploads and its hash verifies, committed metadata and events SHALL reference the private local object and immutable hash.

#### Scenario: Publish a verified object
- **GIVEN** an authorized artifact write with stable operation identity
- **WHEN** bytes upload and hash verification succeed
- **THEN** committed metadata/events reference the private local object and immutable hash

### Requirement: Reconcile interrupted publication
Recovery SHALL reconcile an orphan upload or missing object after interruption, or report incomplete delivery, and MUST NOT assume the object and database committed atomically.

#### Scenario: Reconcile interrupted publication
- **GIVEN** an orphan upload or missing object after interruption
- **WHEN** recovery inspects staged artifacts
- **THEN** it reconciles or reports incomplete delivery rather than assuming the object and database committed atomically
