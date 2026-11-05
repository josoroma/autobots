## ADDED Requirements

### Requirement: Non-AI work without a key
With no effective OpenRouter credential, local viewing and settings SHALL remain usable, every model call SHALL be credentials_required, and the draft SHALL be preserved.

#### Scenario: Keep non-AI work available
- **GIVEN** no effective OpenRouter credential
- **WHEN** the user signs in, reads files or attempts model-backed work
- **THEN** local viewing/settings remain usable while every model call is credentials_required and the draft is preserved

### Requirement: Validation without a run
A successful Save and validate through key metadata SHALL encrypt the key, keep catalog status separate, and return control to the draft, without paid inference.

#### Scenario: Validate without launching a run
- **GIVEN** an app-managed draft key and preserved composer selection
- **WHEN** Save and validate succeeds through key metadata
- **THEN** the key is encrypted, catalog status remains separate, and control returns to the draft without paid inference

### Requirement: Preserved valid configuration
A bad replacement key or stale mutation version SHALL leave the prior valid key in place or return a conflict, without exposing stored secrets.

#### Scenario: Preserve valid configuration
- **GIVEN** a bad replacement key or stale mutation version
- **WHEN** an owner submits the credential change
- **THEN** the prior valid key remains or conflict is returned without exposing stored secrets
