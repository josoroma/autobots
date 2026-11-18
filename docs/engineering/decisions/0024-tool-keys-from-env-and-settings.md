# Decision 0024: Tool-provider keys from `.env`, overridden in Settings

**Date:** 2026-11-08. **Authority:** the owner. They asked: "Read them from .env, if they dont exist in .env capture its values in settings, so values in settings override values in .env". The keys are `TAVILY_API_KEY` and `JINA_API_KEY`. Earlier in this work they delegated the design choices ("take in auto the best decisions"), so the choices below are made under that delegation. This amends [PRD-Tool-Catalog PK-01 and TS-03](../../PRD/PRD-Tool-Catalog.md#provider-keys) and schedules US-14.17.

## What was found

The Tools page on the persistent install showed every Tavily and Jina tool as "Unavailable: key not set", although the owner's `.env` has both keys. The tools read only their own process environment. The install's API and worker get theirs from the install's `app.env`, and nothing passes the repository's `.env` to them. There was also no place in the app to enter these keys, unlike the OpenRouter key (MP-05).

## Decision

| # | Choice |
|---|---|
| **K1. Order** | For each tool-provider key, highest first: the workspace's key saved in Settings, then the process environment, then the `.env` files under the configuration root, in [MP-03](../../PRD/PRD-Model-Providers.md#mp-03-configuration-precedence)'s file order. The first non-blank value wins. This is the reverse of the OpenRouter key, where the environment wins, because the owner asked for it |
| **K2. `.env` on the install** | `make start` passes `TAVILY_API_KEY` and `JINA_API_KEY` from the repository's `.env` to the API and the worker. It parses the file as data and never sources it, and takes nothing else from it. A blank value passes nothing |
| **K3. Settings** | Settings → Tool keys lets the workspace owner save, replace or remove a Tavily or Jina key. The value is sealed with the existing master key in `app_private.provider_credentials`, with the provider `tavily` or `jina`, versioned like the OpenRouter key. Members see each key's source (Settings, environment or none), never its value, prefix, length or hash |
| **K4. No live check** | Saving checks the key's shape only, by the rule the OpenRouter key already uses: printable ASCII, no whitespace, at least 8 characters. By PK-03, nothing calls Tavily or Jina to test it, since that costs a request |
| **K5. Per attempt and per workspace** | Each tool call resolves its key inside the attempt, from the run's workspace, so a change applies to the next call without a restart. Availability on the Tools page, at run admission and at Expert, routine and workflow save follows the same order for that workspace |
| **K6. Removing** | Removing a saved key falls back to the environment. It never edits `.env` |
| **K7. Browsing switch** | Added 2026-11-08 at the owner's request ("Yes, add it"), so `browse_goal` can be turned on from `.env` too. `make start` also passes `AUTOBOTS_BROWSER_EXECUTOR` to the API and the worker, and only when the repository's `.env` sets it to exactly `enabled`. Any other value passes nothing. Browsing still needs a passing executor qualification at the current code (AB-02), and every call still waits for approval |

PK-01's other guarantees stay: a key reaches only the adapter's HTTP client, and never a scope, checkpoint, graph state, prompt, tool schema, event, tool-use row, receipt, log line or evidence.

## Owner steps after delivery

Applying the migration that admits the two providers changes the persistent database, so the owner runs `make migrate`, then `make stop && make start`. The project's hook keeps the install's records out of the assistant's commands.

## What this doesn't establish

No live Tavily or Jina call is made. Tests use fake transports even when a real key is present.
