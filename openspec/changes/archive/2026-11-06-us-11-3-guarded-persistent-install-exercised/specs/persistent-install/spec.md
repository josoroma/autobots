## ADDED Requirements

### Requirement: Only the identified install is changed

The guarded apply SHALL change a database only when the requested project, the recorded identity, the container's own labels and port, and the identity row in that database all agree, and SHALL NOT offer a reset.

#### Scenario: Refuse the wrong target
- **GIVEN** a target that is not the identified persistent install, or a request to reset that install
- **WHEN** the guarded apply runs
- **THEN** it refuses before any change, and nothing is migrated, reset or removed

### Requirement: The install stands beside other projects

The install SHALL run on its own recorded loopback ports, and SHALL leave other projects' containers, ports and volumes unchanged.

#### Scenario: Stand up beside other projects
- **GIVEN** other projects' Docker stacks are present on this Mac
- **WHEN** the install starts on its own loopback ports and its migrations apply through the guarded path
- **THEN** readiness is verified, its live listeners are only its recorded loopback bindings, and other projects' containers, ports and volumes are unchanged

### Requirement: The runbooks are exercised on the install

The local Supabase, local app, operations, backup and upgrade runbooks SHALL be followed on the running install, recording what was observed and what was not exercised.

#### Scenario: Exercise the runbooks on the install
- **GIVEN** the running install, with an owner, a finished run and a published artifact
- **WHEN** the local Supabase, local app, operations, backup and upgrade runbooks are followed on it, including stop and start
- **THEN** each observed step is recorded, the owner, run, artifact bytes and volumes survive stop and start, a backup restores into an isolated instance, and any step not exercised is listed as not exercised

### Requirement: Real goals stay under the shared cap

A real goal SHALL NOT start when its worst-case cost would take the shared ledger past US$1, and its outcome and cost SHALL be recorded whether it succeeds or fails.

#### Scenario: Run a real goal under the shared cap
- **GIVEN** inference is on, and the shared US$1 cap's remainder covers the goal's worst-case cost
- **WHEN** the owner's goal runs on OpenRouter through the install's API and worker
- **THEN** its actual outcome, reported cost and the running total are recorded whether it succeeded or failed, and no goal starts whose worst-case cost would take the total past US$1
