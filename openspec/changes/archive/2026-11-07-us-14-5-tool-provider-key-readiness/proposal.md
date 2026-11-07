## Why

US-14.5, [PRD-Tool-Catalog PK-01 to PK-03](../../../PRD-Tool-Catalog.md#provider-keys) and Decision 0017 C1, C5, C8 and Q1: provider tools are about to arrive, and nothing yet reads a tool-provider key safely, refuses a run that grants a tool whose key is missing, or recognizes those keys in logs and evidence.

## What Changes

- `adapters/provider_http.py`: `provider_key` reads a credential's variables from the worker's environment inside each attempt and fails `<credential>_key_missing` naming nothing else; `provider_client` builds that attempt's `httpx` client with an injectable transport, no redirects and no inherited proxy settings. Every provider adapter will use them.
- Run creation through a session, and a routine's occurrence, are refused `tool_unavailable` when the Expert grants a tool unavailable in this install, before a run exists. US-14.2 already refuses such an Expert save.
- Log redaction and the evidence secret scan recognize Tavily (`tvly-`), Jina (`jina_`) and GitHub (`ghp_`, `github_pat_` and the like) key shapes.
- The operations runbook documents `TAVILY_API_KEY` and `JINA_API_KEY`, and warns that a broader developer token under `GITHUB_TOKEN` would be picked up. `.env.example` says which tools read each key.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `tool-catalog`: tool-provider key readiness.

## Impact

`adapters/provider_http.py`, `application/tool_catalog.py`, `application/routines.py`, `api/run_routes.py`, `operations/logs.py`, `scripts/evidence.py`, `docs/engineering/runbooks/operations.md`, `.env.example`, `tests/db/provider_key_check.py`, `scripts/qualify_identity.py`, `apps/web/tests/browser/experts.spec.ts` and unit tests. No migration.
