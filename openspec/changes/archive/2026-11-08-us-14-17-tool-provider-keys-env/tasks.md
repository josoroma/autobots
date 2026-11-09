# Tasks

## 1. Storage (Owner saves, replaces and removes; The sealed key stays out of durable state)

- [x] 1.1 Migration 51: admit `tavily` and `jina` in `app_private.provider_credentials`, add `app_private.tool_key_settings`, and record it as shipped for schema readiness
- [x] 1.2 Make `ProviderCredentialStore` provider-aware and limit OpenRouter's disconnect to its own provider

## 2. Resolution (Settings, then the environment, then .env; Resolved per attempt; Removing falls back)

- [x] 2.1 Add `application/tool_keys.py`: saved, environment and config-root `.env` resolution, and per-workspace key sources
- [x] 2.2 Resolve the Tavily and Jina keys inside each attempt from the run's workspace in their adapters

## 3. Availability (Availability follows the same order)

- [x] 3.1 Use the workspace's key sources for the Tools page, run admission, Expert save, routine admission and search, and report each key's source in the catalog

## 4. Settings (Owner saves, replaces and removes)

- [x] 4.1 Add the tool-key contract and routes: a member read of source and version, and owner-only versioned save and remove with a shape check only. Regenerate OpenAPI and the TypeScript client
- [x] 4.2 Add Settings → Tool keys in the web app, and the Tools page's repair and source text

## 5. Install (make start passes only the two keys, as data)

- [x] 5.1 Add `scripts/tool_keys_env.py` and use it in the Makefile's API and worker launch

## 6. Coverage and docs

- [x] 6.1 Unit tests, a disposable database check with the secret scan, and the web suite
- [x] 6.2 Update the operations runbook, README-SETUP-RUN, `.env.example` and CODEBASE
