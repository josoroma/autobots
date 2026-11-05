# provider-credentials Specification

## Purpose
TBD - created by archiving change us-3-1-server-credential-precedence-encrypted. Update Purpose after archive.

## Requirements

### Requirement: Source precedence
Native processes resolving a credential from process, dotenv or app-store candidates SHALL agree on whitespace and test-mode rules, and an invalid nonempty higher-priority key MUST block fallback.

#### Scenario: Preserve source precedence
- **GIVEN** shared config roots with process/dotenv/app-store candidates
- **WHEN** the native processes resolve a credential
- **THEN** whitespace and test-mode rules agree and an invalid nonempty higher-priority key blocks fallback

### Requirement: Protected secret material
Only AES-GCM ciphertext and references SHALL be durable when a credential is stored, rotated and resolved, and plaintext and client instances MUST stay out of checkpoints, logs and browser state.

#### Scenario: Persist only protected secret material
- **GIVEN** a valid app credential and the separate protected host master key
- **WHEN** the credential is stored, rotated and later resolved for an attempt
- **THEN** AES-GCM ciphertext and references are durable while plaintext/client instances stay out of checkpoints, logs and browser state

### Requirement: Key loss handling
With encrypted credentials present and the host master key unavailable, credential storage SHALL report unavailable storage, and MUST NOT generate a replacement or use plaintext.

#### Scenario: Handle key loss
- **GIVEN** encrypted credentials already exist but the host master key is unavailable
- **WHEN** credential storage is accessed
- **THEN** it reports unavailable storage without generating a replacement or using plaintext
