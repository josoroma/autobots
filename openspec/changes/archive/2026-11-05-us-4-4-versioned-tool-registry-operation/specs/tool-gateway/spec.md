## ADDED Requirements

### Requirement: Validation before execution
When the loop requests a registered versioned tool with completed arguments, schema, scope, run status, timeout and operation policy SHALL be checked before effects, and streamed prefixes MUST NOT execute.

#### Scenario: Validate before execution
- **GIVEN** a registered versioned tool and completed arguments
- **WHEN** the loop requests the tool
- **THEN** schema, scope, run status, timeout and operation policy are checked before effects and streamed prefixes never execute

### Requirement: No inherited capabilities
A tool request outside granted resources, or an unqualified shell capability, MUST be denied at the executor regardless of SDK discovery or middleware defaults.

#### Scenario: Reject inherited capabilities
- **GIVEN** a tool request outside granted resources or an unqualified shell capability
- **WHEN** the request reaches the executor
- **THEN** it is denied regardless of SDK discovery or middleware defaults

### Requirement: Durable effect identity
On replay of a repeated logical tool operation the executor SHALL reuse the operation identity and receipt rather than blindly repeating a known effect.

#### Scenario: Keep effect identity durable
- **GIVEN** a repeated logical tool operation
- **WHEN** the executor handles replay
- **THEN** it reuses the operation identity and receipt rather than blindly repeating a known effect
