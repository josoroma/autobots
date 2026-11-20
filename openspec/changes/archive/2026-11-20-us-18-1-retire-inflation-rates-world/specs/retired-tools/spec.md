## Purpose

A tool Autobots removes is retired, not unknown: saved Expert versions, routines, workflows and runs that name it keep working with their other tools, and nothing stored is rewritten (Decision 0036 R2 to R6).

## ADDED Requirements

### Requirement: The catalog doesn't offer a retired tool

The tool catalog, its API listing, OpenAPI and the TypeScript client SHALL NOT offer `inflation_rates` or the `world_bank` provider. `market_history` SHALL keep its version, provider and pinned schema digest.

#### Scenario: The catalog no longer offers it
- **GIVEN** the tool catalog after the change
- **WHEN** a member lists the tools through the API, and the contracts are generated
- **THEN** neither inflation_rates nor the world_bank provider appears in the listing, OpenAPI or the TypeScript client, and market_history is listed as before, with its version, provider and pinned schema digest

### Requirement: A retired name stays retired

Autobots SHALL keep a list of retired tools, holding `inflation_rates`. No retired name SHALL be registered, granted by a tool map or listed among the tool versions a run records.

#### Scenario: A retired name stays retired
- **GIVEN** inflation_rates is on the list of retired tools
- **WHEN** a tool map or registry that holds that name is checked
- **THEN** the check names it as retired, and the registry and tool maps Autobots ships hold no retired name

### Requirement: A revision drops a retired tool

Saving an Expert revision that names a retired tool SHALL save it without that tool. A revision naming any other tool the catalog doesn't hold SHALL still be refused with `expert_tool_not_available`. Earlier versions SHALL keep what they stored.

#### Scenario: A revision drops it
- **GIVEN** an Expert whose latest version names inflation_rates and market_history
- **WHEN** the owner saves a revision from that version, and then a revision naming a tool that is neither in the catalog nor retired
- **THEN** the first is saved as a new version with market_history and without inflation_rates, the earlier version still lists inflation_rates, and the second is refused with expert_tool_not_available

### Requirement: A saved grant leaves a retired tool out

When a saved Expert version, routine or workflow becomes a run's grant, a retired tool it names SHALL be left out and its other tools granted as before. The stored configuration SHALL NOT change.

#### Scenario: Saved Experts and routines still run
- **GIVEN** an Expert version and a routine saved before the change, each naming inflation_rates and market_history
- **WHEN** a session runs the Expert and the routine's occurrence is admitted
- **THEN** each run is admitted and granted market_history without inflation_rates, and the stored version and routine are unchanged

#### Scenario: A workflow's agent step still runs
- **GIVEN** a published workflow whose agent step names an Expert whose version lists inflation_rates and market_history, and a scripted model
- **WHEN** the workflow is executed
- **THEN** the step's run is granted market_history without inflation_rates, and the execution goes on past the step

### Requirement: A run in flight carries on past a retired tool

A saved run whose recorded execution contract lists a retired tool SHALL continue. Its model SHALL NOT be shown that tool, and a call to it SHALL be refused with `tool_not_registered`, which the model reads before it carries on. A recorded tool that is neither registered nor retired SHALL still refuse a resume with `incompatible_version` and stop a claimed run before any model call.

#### Scenario: A run in flight carries on
- **GIVEN** a paused run admitted before the change, whose recorded execution contract and grant list inflation_rates v1, and a scripted model
- **WHEN** it is resumed and claimed, and its model calls inflation_rates
- **THEN** it continues, its model's tool list leaves inflation_rates out, the call is refused with tool_not_registered, and the run carries on after the model reads the refusal

#### Scenario: A tool removed without being retired still stops a run
- **GIVEN** a saved run whose recorded execution contract lists a tool that is neither registered nor retired
- **WHEN** it is resumed, or a worker claims it
- **THEN** the resume is refused with incompatible_version and the worker stops the run before any model call, each naming the tool as no longer existing, as before

### Requirement: A retired tool's history stays as it was

Tool-use rows, artifacts, receipts and events recorded for a retired tool SHALL read as recorded, and no stored row SHALL be rewritten.

#### Scenario: History stays as it was
- **GIVEN** a run whose inflation_rates call was recorded before the change
- **WHEN** a member lists its tool uses through the API
- **THEN** the inflation_rates row reads with its version, group, provider and outcome as recorded, and its stored row is unchanged
