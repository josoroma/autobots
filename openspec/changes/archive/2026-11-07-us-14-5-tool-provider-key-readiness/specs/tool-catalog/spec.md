## ADDED Requirements

### Requirement: A missing key disables only its provider's tools

A run or Expert version that grants a tool whose key is missing SHALL be refused with a typed code before any run or dispatch exists. Runs and versions that grant none of that provider's tools SHALL be unaffected, and only that provider's tools SHALL read `key_missing`.

#### Scenario: A missing key disables only its provider's tools
- **GIVEN** one tool provider's key is not set in the worker's environment
- **WHEN** a run or Expert version that grants none of its tools is admitted or saved, and another that grants one is requested
- **THEN** the first is unaffected, the second is refused with a typed code before any dispatch, and only that provider's tools read key_missing

### Requirement: A key reaches only its adapter's HTTP client

A tool-provider key SHALL be read in the worker for each attempt and passed only to that attempt's HTTP client. No tool input SHALL have a credential field. The key SHALL NOT appear in a scope, checkpoint, graph state, prompt, schema, event, tool-use row, receipt, log line or evidence.

#### Scenario: A key stays out of durable state
- **GIVEN** a fake key set for a tool provider
- **WHEN** its tools run against a fake transport
- **THEN** the key reaches only the adapter's HTTP client, and a scan finds it in no scope, checkpoint, graph state, prompt, schema, event, tool-use row, receipt, log line or evidence

### Requirement: No automatic live key check

Availability SHALL report only whether a key is set. Nothing SHALL send a request to a provider to check a key, and tests SHALL use fake transports even when a real key is present.

#### Scenario: No automatic live key check
- **GIVEN** a real key may be present in the environment
- **WHEN** availability is computed and the tests run
- **THEN** no request leaves for the provider, and availability reports only whether the key is set
