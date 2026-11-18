## Why

US-14.22, [Decision 0032](../../../docs/engineering/decisions/0032-google-search-through-serpapi.md) G1 to G8, PRD-Tool-Catalog GS-01 to GS-04 and PRD-Studio SD-01 and SD-02. The owner asked for Google search, using the key Deep-Research-Content-Writer really uses (SerpApi), as a tool for a Google bot. They chose a seeded Google bot Expert and a SerpApi key from Settings → Keys & vars or `.env`, like Tavily and Jina.

## What Changes

- `google_search` v1, provider `serpapi`, group `web_search`:
  - It pages through the shared search pager in pages of 10, at most 3 a call, with `start = (n - 1) * 10`, `hl=en` and `gl=us`.
  - SerpApi's `serpapi_pagination.next` decides when there are no more, and a "Fully empty" reply is an empty page.
  - The output is `search_web` v2's, and its failures are Decision 0032 G4's typed codes.
- The shared pager accepts a provider's own "more pages" signal beside its short-page rule. `search_web` v2 and `tavily_search` v2 behave as before.
- A sixth Keys & vars secret, `serpapi` (`SERPAPI_API_KEY`), resolved by PK-04's order:
  - migration 63 adds `serpapi` to the two database provider lists;
  - the settings contract, OpenAPI and the TypeScript client gain it;
  - `make start` passes it, and `.env.example` and the operations runbook name it.
- The provider `serpapi` joins the catalog contract and the Tools page's labels.
- The concept seed gains Google bot, with `google_search`, `extract_website_content`, `save_artifact` and `publish_artifact`.

## Capabilities

### New Capabilities

- `google-search`: `google_search` through SerpApi, its pages, its next-page signal, its typed failures, the key kept out of outputs, and its spend record.

### Modified Capabilities

- `search-paging`: a short page stops paging unless the provider's reply says whether another page exists.
- `keys-and-vars`:
  - the resolution order covers every item, the SerpApi key included;
  - `make start` passes `SERPAPI_API_KEY`;
  - the SerpApi key is saved, listed and removed like the others.
- `experts`: the concept seed creates six Experts, Google bot among them.

## Impact

- **Backend:**
  - `adapters/serpapi.py` (new), `adapters/search_paging.py` and `adapters/tool_registry.py`;
  - `application/tool_keys.py`, `api/keys_and_vars_routes.py` and `application/schema_release.py`;
  - `contracts/settings.py`, `contracts/tool_catalog.py`, `domain/tool_catalog.py`, `domain/tools.py`, `domain/execution.py` and `domain/tool_guides.py`;
  - `operations/concept_seed.py`.
- **Database:** `supabase/migrations/20261118000063_serpapi_provider.sql`, the schema snapshot and the row types.
- **Web:** `lib/keys-and-vars.ts`, `lib/tools/text.ts`, the generated client and their tests.
- **Scripts and docs:** `scripts/tool_keys_env.py`, `.env.example`, the operations runbook and `CODEBASE.md`.
- **Tests:** unit, harness and disposable database and browser checks. No SerpApi search, live key or model call.
