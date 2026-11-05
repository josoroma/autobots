## ADDED Requirements

### Requirement: Offline generation with drift detection
Generating OpenAPI/JSON Schema and the TypeScript client from Pydantic public contracts MUST require no service connection or provider credential, and drift SHALL be detected against versioned artifacts.

#### Scenario: Generate without credentials or services
- **GIVEN** Pydantic public contracts and explicit domain/persistence/state boundaries
- **WHEN** OpenAPI/JSON Schema and the TypeScript client are generated
- **THEN** generation requires no service connection or provider credential and drift is detected against versioned artifacts

### Requirement: Validation at trust boundaries
Runtime validation SHALL reject invalid identifiers, money, timestamps or enum values when a public request or response crosses a boundary, and MUST NOT rely on a TypeScript cast.

#### Scenario: Validate at trust boundaries
- **GIVEN** invalid identifiers, money, timestamps or enum values
- **WHEN** a public request or response crosses a boundary
- **THEN** runtime validation rejects invalid values rather than relying on a TypeScript cast
