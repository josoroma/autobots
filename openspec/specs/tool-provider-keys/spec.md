# tool-provider-keys Specification

## Purpose
TBD - created by archiving change us-14-17-tool-provider-keys-env. Update Purpose after archive.

## Requirements

### Requirement: Settings, then the environment, then .env

The Tavily and Jina keys SHALL resolve for a workspace in this order, highest first: that workspace's key saved in Settings, the process environment, then the `.env` files under the configuration root in MP-03's file order. A blank or whitespace-only value SHALL be skipped in favor of the next source.

#### Scenario: Settings, then the environment, then .env
- **GIVEN** fake Tavily and Jina keys set in combinations of a workspace's saved key, the process environment and the .env files under the configuration root, some of them blank or whitespace-only
- **WHEN** each provider's key is resolved for that workspace
- **THEN** the saved key wins over the process environment, the process environment wins over the .env files, the .env files are read in MP-03's file order, and a blank or whitespace-only value is skipped in favor of the next source

### Requirement: Resolved per attempt from the run's workspace

Each Tavily or Jina call SHALL resolve its key inside the attempt from the run's workspace and pass it only to the adapter's HTTP client, so a changed key applies to the next call without a restart.

#### Scenario: Resolved per attempt from the run's workspace
- **GIVEN** two workspaces, one with a fake Tavily key saved in Settings and one without, a different fake key in the process environment, and a fake transport for each adapter
- **WHEN** a granted Tavily tool is called in a run of each workspace, the saved key is then replaced, and the first workspace's run calls the tool again without a restart
- **THEN** each request carries its own workspace's key, with the environment key for the workspace that has no saved key, and the second call in the first workspace carries the replacement, with each key reaching only the adapter's HTTP client

### Requirement: Owner saves, replaces and removes, and members see only the source

Only the workspace owner SHALL save, replace or remove a Tavily or Jina key, each with the expected version. Saving SHALL check the key's shape only and make no provider request. Every member SHALL see each key's source as settings, environment or none and its version, never its value, prefix, length or hash.

#### Scenario: Owner saves, replaces and removes, and members see only the source
- **GIVEN** a workspace with an owner and a member who isn't an owner, and a fake transport that records any provider request
- **WHEN** the owner saves, replaces and removes a Tavily or Jina key with the expected version, the owner submits a stale version or a malformed value, the member tries to save or remove a key, and each of them reads Settings → Tool keys
- **THEN** the owner's changes succeed and advance the version, the stale version is refused as a conflict and the malformed value is refused by the shape check, each leaving the saved key unchanged, the member is refused, both of them see each key's source as settings, environment or none and never its value, prefix, length or hash, and no request reaches Tavily or Jina

### Requirement: Removing falls back to the environment

Removing a saved key SHALL make the next resolution use the environment, and SHALL never edit a `.env` file.

#### Scenario: Removing falls back to the environment
- **GIVEN** a workspace with a saved Jina key and a different fake key in the configuration root's .env
- **WHEN** the owner removes the saved key
- **THEN** the next resolution for that workspace uses the environment's key, the source reads environment, and every .env file is byte-for-byte unchanged

### Requirement: Availability follows the same order

The Tools page, run admission, and Expert, routine and workflow save SHALL decide a Tavily or Jina tool's availability for the request's workspace by the same order. A tool with no key SHALL read `key_missing` with a repair naming Settings → Tool keys and the provider's variable in `.env`. An available key-backed tool SHALL report its key's source.

#### Scenario: Availability follows the same order
- **GIVEN** a workspace with a key saved for one provider, an environment key only for the other, and a third arrangement with neither
- **WHEN** the Tools page is read, a run granting each provider's tools is admitted, and an Expert, routine and workflow granting them are saved, all for that workspace
- **THEN** availability, admission and save agree with the resolution order, a tool with no key reads key_missing with a repair naming Settings → Tool keys and the provider's variable in .env, and an available key-backed tool shows its key's source as Settings or environment

### Requirement: make start passes only the two keys, as data

`make start` SHALL pass `TAVILY_API_KEY` and `JINA_API_KEY` from the repository's `.env` to the API and the worker, parsing the file as data and never sourcing it, taking no other variable, and passing nothing for a blank value.

#### Scenario: make start passes only the two keys, as data
- **GIVEN** a repository .env holding fake TAVILY_API_KEY and JINA_API_KEY values, another variable, and a value containing shell syntax, and separately one where both keys are blank
- **WHEN** make start's environment for the API and the worker is built against a disposable target
- **THEN** only the two keys are passed, the value with shell syntax is passed literally and nothing in it runs, the other variable isn't passed, and a blank key passes nothing

### Requirement: The sealed key stays out of durable state

A key saved in Settings SHALL be stored only sealed, and SHALL appear in no scope, checkpoint, graph state, event, tool-use row, receipt, log, evidence or API or BFF response.

#### Scenario: The sealed key stays out of durable state
- **GIVEN** a disposable database, a fake key saved in Settings for each provider, and runs whose granted Tavily and Jina tools call fake transports
- **WHEN** the runs finish and a scan reads their scopes, checkpoints, graph state, events, tool-use rows, receipts, logs and evidence
- **THEN** the fake keys appear in none of them, the provider_credentials rows hold only sealed material, and no API or BFF response contains a key
