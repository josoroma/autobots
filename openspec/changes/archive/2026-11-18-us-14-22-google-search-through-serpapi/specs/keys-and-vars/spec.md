# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: make start passes only the listed variables, as data

make start SHALL pass only the five listed variables and the exact switch from .env, as data: TAVILY_API_KEY, JINA_API_KEY, SERPAPI_API_KEY (Decision 0032 G7), GITHUB_REPOSITORY and GITHUB_TOKEN.

#### Scenario: make start passes only the listed variables, as data
- **GIVEN** a repository .env holding fake TAVILY_API_KEY, JINA_API_KEY, SERPAPI_API_KEY, GITHUB_REPOSITORY and GITHUB_TOKEN values, AUTOBOTS_BROWSER_EXECUTOR set to enabled, another variable, and a value containing shell syntax, and separately one where those five are blank and the switch holds a value other than enabled
- **WHEN** make start's environment for the API and the worker is built against a disposable target
- **THEN** only those five variables and the switch are passed, the value with shell syntax is passed literally and nothing in it runs, the other variable isn't passed, a blank value passes nothing, and a switch other than exactly enabled passes nothing
