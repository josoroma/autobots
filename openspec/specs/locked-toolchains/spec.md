# locked-toolchains Specification

## Purpose
Gives developers pinned, locked and reproducible Node and Python environments with minimal non-feature packages, so that verification can run against prepared environments without changing dependencies.

## Requirements

### Requirement: Resolved combined environment
Pinned Node/pnpm and Python 3.12/uv manifests and locks SHALL be resolved from the researched package candidates and Python/OpenRouter compatibility constraints, and SHALL yield a reproducible prepared environment and minimal non-feature packages with recorded versions.

#### Scenario: Resolve the combined environment
- **GIVEN** the researched package candidates and Python/OpenRouter compatibility constraints
- **WHEN** pinned Node/pnpm and Python 3.12/uv manifests and locks are resolved
- **THEN** a reproducible prepared environment and minimal non-feature packages exist with recorded versions

### Requirement: Non-mutating verification
A verification command run against a prepared locked environment MUST NOT silently install dependencies or rewrite the lock.

#### Scenario: Keep verification non-mutating
- **GIVEN** a prepared locked environment
- **WHEN** a verification command runs
- **THEN** it does not silently install dependencies or rewrite the lock
