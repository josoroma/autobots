## ADDED Requirements

### Requirement: Shared budget reservation
With root and workspace spend and outstanding reservations, two shared remote slots and configured limits SHALL apply to concurrent attempts or descendants, cost SHALL be reserved atomically, a warning SHALL occur at 80 percent, and new paid admission SHALL pause at 100 percent.

#### Scenario: Reserve shared budgets
- **GIVEN** root/workspace spend and outstanding reservations
- **WHEN** concurrent attempts or descendants request dispatch
- **THEN** two shared remote slots and configured limits apply, cost is reserved atomically, warning occurs at 80 percent and new paid admission pauses at 100 percent

### Requirement: Explicit uncertain charges
After partial SSE or uncertain provider acceptance, the attempt and reservation SHALL remain recorded, and there MUST be no blind redispatch or incomplete tool execution.

#### Scenario: Keep uncertain charges explicit
- **GIVEN** partial SSE or uncertain provider acceptance
- **WHEN** a request fails or is cancelled
- **THEN** the attempt and reservation remain recorded and no blind redispatch or incomplete tool execution occurs

### Requirement: Bounded safe retries
A safe retryable failure SHALL get at most two permitted retries, respecting Retry-After where supplied, the root deadline and the same model and budget.

#### Scenario: Bound safe retries
- **GIVEN** a safe retryable failure
- **WHEN** retry policy runs
- **THEN** at most two permitted retries respect Retry-After where supplied, the root deadline and the same model/budget
