## ADDED Requirements

### Requirement: Streamed result text

While a run's final result is written, the API SHALL emit ephemeral, coalesced `result.text.delta` events with the result text only, at schema version 1, never stored as durable events. Durable events and the stored artifact SHALL stay authoritative, and a reconnect SHALL rebuild from them. No reasoning, tool argument other than the result text, or raw framework value SHALL be streamed. A "Stream text as it's written" preference SHALL turn live display off in the browser.

#### Scenario: Result deltas, ephemeral and coalesced
- **GIVEN** a run writing its final result with a scripted model on a disposable stack
- **WHEN** its owner watches the run
- **THEN** result.text.delta events carry result text only, coalesced, at schema_version 1, none is stored as a durable event, and the text shown when the result completes equals the stored artifact

#### Scenario: Reconnect rebuilds from the artifact
- **GIVEN** a stream cut while the result is being written
- **WHEN** the browser reconnects and the result completes
- **THEN** the view is rebuilt from durable events and the stored artifact, and the final text equals the artifact

#### Scenario: Nothing private is streamed
- **GIVEN** a scripted model that also produces reasoning, tool arguments and framework values while writing
- **WHEN** the deltas are inspected
- **THEN** none carries reasoning, a tool argument or a raw framework value

#### Scenario: The preference turns live text off
- **GIVEN** "Stream text as it's written" turned off in Settings → Appearance
- **WHEN** a result is written
- **THEN** the browser shows no live text, and shows the result once its artifact is stored
