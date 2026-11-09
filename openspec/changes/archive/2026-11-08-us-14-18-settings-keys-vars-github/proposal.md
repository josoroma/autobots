## Why

US-14.18, [Decision 0025](../../../docs/engineering/decisions/0025-keys-and-vars.md) (V1 to V9) and PRD-Tool-Catalog PK-07 and PK-08. The owner asked to bring `GITHUB_REPOSITORY`, `GITHUB_TOKEN` and `AUTOBOTS_BROWSER_EXECUTOR` into Settings, beside the Tavily and Jina keys, under the name "Keys & vars".

## What Changes

- **Settings → Keys & vars** replaces Tool keys, at `/settings/keys-and-vars` with `/v1/settings/keys-and-vars[/{item}]`. It has five items:
  - Secrets: `tavily`, `jina` and `github_token`, sealed in `app_private.provider_credentials` with the providers `tavily`, `jina` and `github`.
  - Values: `github_repository` (`owner/name`) and `browser_executor` (`enabled` or `disabled`), kept in `app_private.tool_key_settings.value`.
  - Members read each item's source and version, plus the values' current values. The owner saves and removes with an expected version.
- **One resolution order** for every item, per workspace: saved, then the process environment, then the config-root `.env`.
- **GitHub tools** resolve the repository and token inside each attempt from the run's workspace.
- **GitHub writes:** the gateway records the repository the approval was requested for, and refuses an approved call `approval_target_changed` when the repository now resolves differently or the recorded target is empty.
- **The browsing switch** resolves per workspace for the catalog, admission and Expert save. The worker binds `browse_goal` for a job only when the run's workspace resolves it to `enabled` and the executor reports qualified.
- **`make start`** also passes `GITHUB_REPOSITORY` and `GITHUB_TOKEN` from `.env`.
- **Migration 52.**

## Capabilities

### New Capabilities

- `keys-and-vars`

### Modified Capabilities

None. The `tool-provider-keys` behaviour is kept and extended.

## Impact

- Migration 52 and the schema record.
- **Application:** `application/tool_keys.py`, `tool_key_settings.py`, `tool_gateway.py`, `tool_catalog.py`, `worker_inference.py` and `browsing_tool.py`.
- **Adapters:** the three GitHub adapters.
- **API:** `settings_routes.py` and the contracts, with a regenerated client.
- **Web:** the settings page, nav and Tools repair text.
- **Install:** the Makefile and `scripts/tool_keys_env.py`.
- Tests and docs. The persistent install needs the owner's `make migrate`.
