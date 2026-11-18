## ADDED Requirements

### Requirement: A published artifact is read by its ID

`read_artifact` version 1 (PRD-Tool-Catalog FI-02, Decision 0034 A1 to A4) SHALL read one published text artifact (markdown, plain text or JSON) of the run's workspace by its ID, in pages of lines as `read_run_file` version 2 does, and SHALL return its ID, name, media type, sha256, size, content, offset, total lines and a cut flag. It SHALL refuse `artifact_not_found` for an unknown ID, another workspace's artifact or one that isn't published, `artifact_missing` when the stored bytes are gone or fail their hash, and `artifact_not_text` for any other media type, with no content. It SHALL be read-only, need no network, key or approval, not be metered, and be granted only by an Expert.

#### Scenario: read_artifact reads a published text artifact of the run's workspace
- **GIVEN** a disposable database with a published markdown artifact in one workspace, a staged one, a published image, a published artifact whose stored bytes are gone, and a second workspace
- **WHEN** a run in the first workspace reads each, and a run in the second workspace reads the published markdown
- **THEN** the first read returns its name, media type, hash, size and content, the staged one and the second workspace's read return artifact_not_found, the image returns artifact_not_text, the lost one artifact_missing, and no refusal carries content

#### Scenario: read_artifact is an Expert-only, read-only tool
- **GIVEN** the tool catalog
- **WHEN** read_artifact's descriptor and the plain goal's tools are read
- **THEN** read_artifact is version 1 in the Files group with a pinned schema digest, read-only, with no network, key, approval or metering, grantable to Experts, and not among a plain goal's tools
