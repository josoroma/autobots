## ADDED Requirements

### Requirement: Fenced writes
When a worker lease expires and a new generation claims the job, a stale worker's domain and checkpoint writes SHALL be rejected by the qualified ownership mechanism.

#### Scenario: Fence both product and checkpoint writes
- **GIVEN** a worker lease expires and a new generation claims the job
- **WHEN** the stale worker tries to update domain records or checkpoint state
- **THEN** both writes are rejected by the qualified ownership mechanism

### Requirement: Recovery from a saved checkpoint
A replacement claiming an eligible job after its worker died SHALL use database-time ownership and the saved checkpoint without redoing known effects or claiming exactly-once remote execution.

#### Scenario: Recover persisted execution
- **GIVEN** the current worker dies after a persisted boundary
- **WHEN** a replacement claims the eligible job
- **THEN** it uses database-time ownership and the saved checkpoint without redoing known effects or claiming exactly-once remote execution
