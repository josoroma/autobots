# Tasks

## 1. Pager signal (SerpApi's next-page signal decides when there are no more)

- [x] 1.1 Let `gather` accept a `Page(items, more)` from a fetch, keeping the short-page rule when `more` is None. Checked by new `test_search_paging.py` cases, with the existing `search_web` and Tavily tests unchanged

## 2. Keys & vars and the database (The SerpApi key in Settings → Keys & vars; Migration 63 allows the serpapi provider; make start passes SERPAPI_API_KEY)

- [x] 2.1 Add migration 63 with the two widened CHECK lists, ship 63 in `schema_release`, and regenerate the schema snapshot and row types with `scripts/app_db.py types` on a disposable stack. Checked by the harness migration-header test and the `db` profile's app_db qualification
- [x] 2.2 Add the `serpapi` item to `tool_keys.ITEMS`, `KeyOrVarName`, `REFUSED_VALUE` and the web tables, and add `serpapi` to the catalog provider enum and label. Regenerate OpenAPI and the client. Checked by `generate_contracts.py check`, the web unit tests and the Keys & vars browser suite's item list
- [x] 2.3 Add `SERPAPI_API_KEY` to `scripts/tool_keys_env.NAMES`, `.env.example` and the operations runbook. Checked by `tests/harness/test_tool_keys_env.py`
- [x] 2.4 Add a SerpApi save, read, availability and removal case to the database checks. Checked by the `db` profile

## 3. The tool (google_search is a web search tool from SerpApi; google_search asks SerpApi for pages of 10; SerpApi's failures are typed; One metered call per Google search)

- [x] 3.1 Add `adapters/serpapi.py` with `google_search` v1 and register it. Give new grants version 1, pin its digest, and add its guide. Checked by `services/agent/tests/test_serpapi.py` on a fake transport (pages, `start`, `hl` and `gl`, the next-page signal, Fully empty, 401, 429 on page 2, a 200 error, a missing key, no key in outputs), the pin and guide tests, and the catalog repair text
- [x] 3.2 Add a three-page `google_search` scenario to `tests/db/checks/web_tools_check.py`, and add `serpapi` to `browse_goal_check`'s provider set. Checked by the `db` profile

## 4. Seed and docs (The concept seed adds Google bot)

- [x] 4.1 Add Google bot to `concept_seed.EXPERTS`, `test_concept_seed.py` and `concept_seed_check.py`. Checked by unit tests and the `db` profile
- [x] 4.2 Update `CODEBASE.md`
