# tool-catalog Specification

## Purpose
TBD - created by archiving change us-14-1-tool-catalog-api-derived. Update Purpose after archive.

## Requirements

### Requirement: The catalog is derived from the registry

The system SHALL list every registered tool ID and version exactly once, derived from the registry the worker builds, with its title, description, group, provider, operation class, side effects, network use, cost class, key requirement by variable name, approval, input and output schemas, flattened fields, limits, grant sites and availability. Planned tools SHALL appear only as `disabled_by_policy`, and SHALL NOT be registered.

#### Scenario: The catalog matches the registry
- **GIVEN** the tools registered in this build
- **WHEN** a workspace member requests the tool catalog through the BFF
- **THEN** every registered tool ID and version appears exactly once with its descriptor, schemas, group, provider, classes and availability, browse_goal appears only as disabled_by_policy, and no other unregistered tool appears

### Requirement: Discovery doesn't grant

The catalog SHALL NOT change what a run may call. The model SHALL see only its scope's granted tools, and a call naming an ungranted tool SHALL be denied before any effect.

#### Scenario: Discovery doesn't grant
- **GIVEN** a run whose scope doesn't grant a catalogued tool
- **WHEN** the model is shown its tools
- **THEN** the ungranted tool is absent from the agent view, and a call naming it is denied before any effect

### Requirement: No secret in the catalog

Availability SHALL be computed per request from whether each required variable is set, and SHALL NOT be stored. The catalog SHALL name variables only, never a value, prefix, length or hash of one.

#### Scenario: No secret in the catalog
- **GIVEN** a fake value is set for a tool's key requirement
- **WHEN** the catalog and that tool's version are read
- **THEN** the response names only the variable and an availability state, never the value, a prefix, its length or a hash

### Requirement: A Tools screen shows the catalog

The web app SHALL have a Tools entry directly before Settings. Its page SHALL list tools by group with their classes and availability, keep filters in the URL, and show for a tool every registered version and its input and output fields with type, required flag, constraints and whether each is shown on run screens. An unavailable tool SHALL read as unavailable in text, with its typed reason and repair.

#### Scenario: Browse tools by group
- **GIVEN** the catalog holds tools in several groups
- **WHEN** the owner opens Tools from the sidebar entry placed directly before Settings
- **THEN** tools appear by group with their classes and availability, the filters are kept in the URL, and a tool's detail lists every registered version and its input and output fields with type, required flag, constraints and whether they are public

#### Scenario: Show unavailable tools honestly
- **GIVEN** a tool whose key is missing or which is disabled_by_policy
- **WHEN** it is listed or opened
- **THEN** it reads as unavailable in text, not by color alone, with its typed reason and repair

### Requirement: A group grant is saved as explicit tools

An Expert version MAY grant whole groups. Saving it SHALL expand each group into the Expert-grantable tools it holds then, and record both the explicit tools and the groups. A saved version SHALL NOT change when a group changes later. A grant naming a tool unavailable in this install SHALL be refused with a typed code.

#### Scenario: A group grant stays explicit
- **GIVEN** an owner grants a group to an Expert version in the editor
- **WHEN** the expansion is previewed and the version is saved
- **THEN** the version records the expanded tool versions and the groups they came from, a tool added to the group later doesn't change it, and a grant naming an unavailable tool is refused with a typed code

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
