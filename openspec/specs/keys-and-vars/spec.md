# keys-and-vars Specification

## Purpose
TBD - created by archiving change us-14-18-settings-keys-vars-github. Update Purpose after archive.

## Requirements

### Requirement: Settings → Keys & vars replaces Tool keys

Settings → Keys & vars SHALL replace Tool keys at /settings/keys-and-vars, listing three secrets and two values; the former page and routes SHALL answer 404.

#### Scenario: Settings → Keys & vars replaces Tool keys
- **GIVEN** a workspace with an owner and a member who isn't an owner, signed in on a disposable stack
- **WHEN** each opens Settings and follows its Keys & vars entry, then requests the former /settings/tool-keys page and /v1/settings/tool-keys routes, and the Tools page is read with no Tavily or Jina key resolved
- **THEN** the entry is labelled Keys & vars and opens /settings/keys-and-vars, which lists the Tavily key, the Jina key and the GitHub token as secrets and the GitHub repository and the browsing switch as values, the former page and routes answer 404, and a Tavily or Jina tool's key_missing repair names Settings → Keys & vars

### Requirement: Settings, then the environment, then .env, for all five

All five items SHALL resolve per workspace in K1's order, and every member SHALL see each item's source and the two values, never a secret.

#### Scenario: Settings, then the environment, then .env, for all five
- **GIVEN** fake values for the Tavily key, the Jina key, the GitHub token, the GitHub repository and the browsing switch set in combinations of a workspace's saved value, the process environment and the .env files under the configuration root, some of them blank or whitespace-only
- **WHEN** each item is resolved for that workspace, and the owner and a member read Settings → Keys & vars
- **THEN** the saved value wins over the process environment, the process environment wins over the .env files, the .env files are read in MP-03's file order, a blank or whitespace-only value is skipped in favor of the next source, both of them see each item's source as settings, environment or none, both see the resolved GitHub repository and browsing switch values, and neither sees a secret's value, prefix, length or hash

### Requirement: Owner-only versioned save and removal, checked without a provider request

Only the owner SHALL save or remove an item, with an expected version and its check, without any provider request.

#### Scenario: Owner-only versioned save and removal, checked without a provider request
- **GIVEN** a workspace with an owner and a member who isn't an owner, and fake transports that record any GitHub, Tavily or Jina request
- **WHEN** the owner saves, replaces and removes the GitHub token, the GitHub repository and the browsing switch with the expected version, the owner submits a stale version, a token that fails the shape check, a repository that isn't owner/name and a switch other than enabled or disabled, and the member tries to save or remove any of the five items
- **THEN** the owner's changes succeed and advance the version, removing falls back to the environment and leaves every .env file byte-for-byte unchanged, the stale version is refused as a conflict, each malformed value is refused by its check, each refusal leaves the saved value unchanged, the member is refused, and no request reaches GitHub, Tavily or Jina

### Requirement: GitHub tools resolve the token and repository per attempt from the run's workspace

GitHub tools SHALL resolve their token and repository inside each attempt from the run's workspace.

#### Scenario: GitHub tools resolve the token and repository per attempt from the run's workspace
- **GIVEN** two workspaces, one with a fake GitHub token and repository saved in Settings and one without, a different fake token and repository in the process environment, and a fake GitHub transport
- **WHEN** a granted GitHub read tool is called in a run of each workspace, the first workspace's saved token and repository are then removed, and its run calls the read tool again without a restart
- **THEN** each request carries its own workspace's token and targets its own workspace's repository, with the environment's for the workspace that has no saved values, the call after removal uses the environment's token and repository, and the token reaches only the adapter's HTTP client

### Requirement: A saved disabled switch turns browsing off for its workspace

A workspace's saved disabled switch SHALL turn browse_goal off for that workspace though the environment enables it.

#### Scenario: A saved disabled switch turns browsing off for its workspace
- **GIVEN** an executor that reports qualified, AUTOBOTS_BROWSER_EXECUTOR set to enabled in the environment, a workspace whose saved browsing switch is disabled, and another workspace with no saved switch
- **WHEN** each workspace's catalog is read, an Expert version granting browse_goal is saved, a run granting it is admitted, and the worker binds tools for a job of each workspace
- **THEN** browse_goal reads disabled_by_policy in the first workspace, its Expert save is refused expert_tool_unavailable and its admission tool_unavailable, the worker doesn't bind browse_goal for its job, and the other workspace sees browse_goal available and its job binds it

### Requirement: A saved enabled switch turns browsing on for its workspace

A workspace's saved enabled switch SHALL turn browse_goal on for that workspace while the executor reports qualified.

#### Scenario: A saved enabled switch turns browsing on for its workspace
- **GIVEN** AUTOBOTS_BROWSER_EXECUTOR not set in the environment or the .env files, a workspace whose saved browsing switch is enabled, and another workspace with no saved switch
- **WHEN** an executor that reports qualified is in place and each workspace's catalog is read, an Expert version granting browse_goal is saved in the first workspace and the worker binds tools for its job, and then the executor reports not qualified
- **THEN** browse_goal is available in the first workspace, the save succeeds, the worker binds browse_goal for that job, the other workspace sees disabled_by_policy, and once the executor reports not qualified the first workspace also sees disabled_by_policy

### Requirement: An approved GitHub write keeps its repository

An approved GitHub write SHALL run only against the repository its approval recorded; otherwise it SHALL be refused approval_target_changed before any request.

#### Scenario: An approved GitHub write keeps its repository
- **GIVEN** a workspace whose resolved GitHub repository is owner/a, a run granted create_github_issue and github_open_pull_request, and a fake GitHub transport that records every request
- **WHEN** each proposes a call and its approval is requested and granted, the owner then saves owner/b as the workspace's repository before the approved calls run, separately an approved call whose workspace repository is unchanged runs, and an approved call whose recorded target is empty runs
- **THEN** each approval request records owner/a, each changed call and the call with an empty recorded target are refused approval_target_changed before any request, the transport receives no request for them and nothing is written, and the unchanged call runs against owner/a

### Requirement: make start passes only the listed variables, as data

make start SHALL pass only the five listed variables and the exact switch from .env, as data: TAVILY_API_KEY, JINA_API_KEY, SERPAPI_API_KEY (Decision 0032 G7), GITHUB_REPOSITORY and GITHUB_TOKEN.

#### Scenario: make start passes only the listed variables, as data
- **GIVEN** a repository .env holding fake TAVILY_API_KEY, JINA_API_KEY, SERPAPI_API_KEY, GITHUB_REPOSITORY and GITHUB_TOKEN values, AUTOBOTS_BROWSER_EXECUTOR set to enabled, another variable, and a value containing shell syntax, and separately one where those five are blank and the switch holds a value other than enabled
- **WHEN** make start's environment for the API and the worker is built against a disposable target
- **THEN** only those five variables and the switch are passed, the value with shell syntax is passed literally and nothing in it runs, the other variable isn't passed, a blank value passes nothing, and a switch other than exactly enabled passes nothing

### Requirement: The sealed secrets stay out of durable state

Saved secrets SHALL be stored only sealed and appear in no durable state, log or response.

#### Scenario: The sealed secrets stay out of durable state
- **GIVEN** a disposable database, a fake Tavily key, Jina key and GitHub token saved in Settings for a workspace, and runs whose granted Tavily, Jina and GitHub tools, including an approved GitHub write, call fake transports
- **WHEN** the runs finish and a scan reads their scopes, checkpoints, events, tool-use rows, receipts, approval requests and logs
- **THEN** the fake secrets appear in none of them, the provider_credentials rows hold only sealed material, and no API or BFF response contains a secret, including the Keys & vars responses

### Requirement: The SerpApi key in Settings → Keys & vars

The SerpApi key SHALL be a Keys & vars secret named `serpapi`, listed after the Jina key. Saving it SHALL seal it, and it SHALL never be returned. `google_search`'s availability SHALL follow it per workspace, and removing it SHALL fall back to the next source.

#### Scenario: The SerpApi key in Settings → Keys & vars
- **GIVEN** a disposable stack with an owner and a member in one workspace, another workspace, and SERPAPI_API_KEY unset in the API's environment
- **WHEN** the owner saves a fake SerpApi key, the member reads Keys & vars, the catalog is read in both workspaces, and the owner removes the key
- **THEN** serpapi is listed as a secret after jina, the saved key is sealed and never returned, google_search is available from settings in the first workspace and key_missing in the other, and after removal its source falls back to none

### Requirement: Migration 63 allows the serpapi provider

Migration 63 SHALL add `serpapi` to the providers `app_private.provider_credentials` and `app_private.tool_key_settings` allow. It SHALL keep refusing any unknown provider. Readiness SHALL ship 63 migrations.

#### Scenario: Migration 63 allows the serpapi provider
- **GIVEN** a disposable database migrated through migration 62
- **WHEN** migration 63 is applied
- **THEN** app_private.provider_credentials and app_private.tool_key_settings accept serpapi and still refuse an unknown provider, readiness ships 63 migrations, and the schema snapshot matches
