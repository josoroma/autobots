## ADDED Requirements

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
