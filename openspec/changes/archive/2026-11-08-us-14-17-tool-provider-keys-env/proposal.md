## Why

US-14.17, [Decision 0024](../../../docs/engineering/decisions/0024-tool-keys-from-env-and-settings.md) (K1 to K6) and PRD-Tool-Catalog PK-01, PK-03 to PK-06 and TS-03. The install's Tools page shows every Tavily and Jina tool as "key not set" although the owner's `.env` has both keys: the tools read only their process environment, nothing passes `.env` to the install, and the app has nowhere to enter these keys.

## What Changes

- **Resolution order (K1).** Tavily and Jina keys resolve per workspace, highest first: the key saved in Settings, then the process environment, then the `.env` files under the configuration root in MP-03's order. The first non-blank value wins.
- **Per attempt (K5).** Each call resolves its key inside the attempt from the run's workspace. The key reaches only the adapter's HTTP client, so a change applies to the next call without a restart.
- **Availability.** The Tools page, run admission, Expert save and routine admission follow the same order for the request's workspace. An available key-backed tool reports its key's source, `settings` or `environment`.
- **Settings → Tool keys (K3, K4, K6).**
  - `GET /v1/settings/tool-keys` gives each provider's source and version to any member, never the value.
  - `PUT` and `DELETE /v1/settings/tool-keys/{provider}` are owner-only and take an expected version.
  - Saving checks the key's shape only (printable ASCII, no whitespace, at least 8 characters) and calls no provider.
  - The value is sealed with the master key in `app_private.provider_credentials`.
  - Removing a key falls back to the environment.
- **Migration 51.** Admits the providers `tavily` and `jina`, and adds a per-workspace version for each provider's key.
- **OpenRouter disconnect fix.** It now removes only the OpenRouter row, since the table is now shared.
- **`make start` (K2).** It passes `TAVILY_API_KEY` and `JINA_API_KEY` from the repository's `.env` to the API and the worker. The file is parsed as data by a small script, never sourced, and nothing else is taken from it.
- **Tools page.** The repair text names Settings → Tool keys and `.env`, and an available key-backed tool shows its key's source.

## Capabilities

### New Capabilities

- `tool-provider-keys`: where the Tavily and Jina keys come from, and how they are saved.

### Modified Capabilities

None.

## Impact

Affected code:
- `supabase/migrations`
- `application/credentials/`, a new `application/tool_keys.py`, `application/provider_settings.py`, `application/tool_catalog.py`, `application/experts.py`, `application/routines.py` and `application/search.py`
- `adapters/tavily.py`, `adapters/jina.py` and `adapters/provider_http.py`
- `domain/tool_catalog.py` and `contracts/tools.py`
- `api/tool_routes.py`, `api/run_routes.py`, `api/search_routes.py`, `api/settings_routes.py` and the Expert routes
- the generated contract and client
- Web: `apps/web` Settings → Tool keys, the settings nav and `tool-catalog.tsx`
- `Makefile` and a new `scripts/tool_keys_env.py`
- tests and docs

The persistent install needs the owner's `make migrate`, then `make stop && make start`.
