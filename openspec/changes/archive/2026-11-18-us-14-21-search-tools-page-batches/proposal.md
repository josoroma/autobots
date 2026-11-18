## Why

US-14.21, [Decision 0031](../../../docs/engineering/decisions/0031-search-tools-page-in-batches-of-ten.md) S1 to S9, and PRD-Tool-Catalog WS-01 to WS-06. The owner asked that Autobots' search tools fetch results in batches of 10, with at most 3 pages a call, following Deep-Research-Content-Writer. Today `search_web` and `tavily_search` make one request each and return at most 10 results.

## What Changes

- A shared pager for the search tools:
  - a page size of 10 and a cap of 3 pages, planned as `ceil(max_results / 10)`;
  - canonical-URL de-duplication across and within pages, with contiguous ranks;
  - early stops `enough`, `no_more`, `page_limit` and `provider_error`;
  - a later page's typed failure kept as `page_error`, with the earlier pages' results.
- `search_web` v2: one Jina request per page (`q`, `num: 10`, `page: n`), `max_results` 1 to 30, a 70-second timeout for three 20-second requests.
- `tavily_search` v2: Tavily has no next-page request, so it asks once for up to 20 results, `max_results` 1 to 20, with version 1's other inputs.
- Both v2 outputs give the model ranked results with `result_count`, `pages`, `stopped`, `duplicates_removed` and `page_error`, keep the third-party label and the shared text budget, and make those counts public in the tool-use record.
- Version 1 of each tool stays registered and unchanged, with its pinned schema digest. New grants take version 2, and runs that pinned version 1 keep it.
- A search call stays one metered call under TU-06. Its pages are recorded in its public output.

## Capabilities

### New Capabilities

- `search-paging`: the search tools' page size, page cap, de-duplication, early stops, later-page errors, output to the model and spend record.

### Modified Capabilities

- `web-tools`: "Jina search is bounded and recorded" now applies to `search_web` version 1. Version 2 follows `search-paging`.

## Impact

- **Backend:**
  - `adapters/search_paging.py` (new), `adapters/jina.py`, `adapters/tavily.py`, `contracts/web_tools.py`;
  - `domain/tools.py`, `domain/execution.py` and `domain/tool_guides.py`.
- **Tests:**
  - `services/agent/tests/test_search_paging.py` (new), `test_jina.py` and `test_tavily.py`;
  - the schema-version fixture and `tests/db/checks/web_tools_check.py`.
- **Docs:** `CODEBASE.md`.
- No migration, no new dependency and no OpenAPI change: tool schemas reach the catalog at runtime.
