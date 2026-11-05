## ADDED Requirements

### Requirement: Restore all required components

A backup SHALL capture database and roles, Storage bytes and configuration with separately protected keys, and its restore to an isolated instance SHALL be verified for Auth, isolation, artifact hashes, credential decryptability and checkpoint history.

#### Scenario: Restore all required components

- **GIVEN** a backup of database/roles, Storage bytes and configuration plus separately protected keys
- **WHEN** it is restored to an isolated instance
- **THEN** Auth, workspace isolation, artifact hashes, credential decryptability and checkpoint history are verified

### Requirement: Avoid accidental resumed charges

Restore verification SHALL NOT replay paid work automatically, and ordinary restore checks SHALL stay bounded to the declared target.

#### Scenario: Avoid accidental resumed charges

- **GIVEN** restored pending runs and model receipts
- **WHEN** restore verification completes
- **THEN** no paid work is automatically replayed and ordinary restore checks remain bounded to the declared target
