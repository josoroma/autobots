## Context

The OpenRouter key already has sealed storage in `app_private.provider_credentials` (AES-256-GCM, with the workspace, provider, credential id and version as associated data), a master key file, and an owner-only Settings panel. Tool adapters read `TAVILY_API_KEY` and `JINA_API_KEY` from a mapping fixed when they are built. The catalog decides availability from the same mapping, with no workspace.

## Decisions

- **One resolver, `application/tool_keys.py`.**
  - `saved_key(connection, workspace, provider, key_file)` unseals the active row.
  - `environment_key(variable, environ)` reads the process environment, then `<AUTOBOTS_CONFIG_ROOT>/.env*` in MP-03's order, through the existing `parse_dotenv`.
  - `resolve_tool_key(context, requirement, environ)` is what an adapter calls inside the attempt. A saved key that exists but can't be unsealed fails the call with `<provider>_key_unavailable` and never falls through, as with OpenRouter.
- **Availability without unsealing.** `key_sources(connection, workspace, environ)` returns a `KeySources` mapping: each variable's source, `settings` or `environment`. The catalog functions keep taking a `Mapping`. A `KeySources` holds markers, never values, and adapters never receive it. Callers without a database, such as the concept seed and offline tests, keep passing the environment.
- **Store.** `ProviderCredentialStore` takes a `provider` (default `openrouter`), so the OpenRouter code keeps its behavior. OpenRouter's disconnect now filters by provider.
- **Versions.** A new `app_private.tool_key_settings (workspace_id, provider, version)` gives each workspace and provider an optimistic version. Saving and removing advance it under `for update`, so a stale write is refused with `stale_version`.
- **Contract.** `KeyRequirementView.source` becomes `"settings" | "environment" | null`, the effective source for the request's workspace. Tool keys get their own contract, `ToolKeyStatus` with `provider`, `variable`, `source` and `version`, under `/v1/settings/tool-keys`.
- **`make start`.** `scripts/tool_keys_env.py` reads the repository's `.env` with the same parser and prints `export NAME='value'` lines for the two names only, shell-quoted with `shlex.quote`. A blank value prints nothing. `launch` evaluates that output only for the API and the worker. Its tests run the script on fixture files.

## Risks

- **A busier catalog request.** Each Tools page read now does one indexed query for the workspace's saved providers.
- **An owner change.** A persistent install needs migration 51 before Settings → Tool keys can save. Until then, saving returns `credential_storage_unavailable`, and the environment still works.
