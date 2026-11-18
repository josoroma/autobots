# Design

## Context

- `adapters/jina.py` and `adapters/tavily.py` each make one request per search, through `adapters/provider_http.py`.
- `read_json` turns a non-200 reply into `ToolFailed(<typed code>)`, a transport error into `provider_unavailable`, and an unreadable reply into `provider_reply_malformed`.
- `fit` splits the 100,000-character text budget across results.
- The gateway admits a metered call once, before the handler runs (`tool_gateway.admit_budget`), and records public fields from each definition's `public_output_fields`.
- A version's schema digest is pinned in `tests/fixtures/tool_schema_versions.json`. `domain/execution.TOOL_VERSIONS` and `domain/tools.PROVIDER_TOOLS` name the version new grants take. Tavily's search has no next-page parameter, while Jina's takes `num` and `page` (Decision 0031, Providers).

## Goals / Non-Goals

**Goals:** one pager both v2 tools share, so the page size, cap, de-duplication and stop rules are written once and tested once. Version 1 stays byte-identical.

**Non-Goals:**
- No change to TU-06's counting, the tool-use table or OpenAPI.
- No host denylist, cross-call query plan or retry.
- The GitHub tools, extract, map and crawl are left as they are (Decision 0031 S1).

## Decisions

- **A pure pager over a page-fetch callback.** `adapters/search_paging.py` holds `PAGE_SIZE = 10`, `MAX_PAGES = 3`, `canonical_url`, and `gather(fetch, max_results)`.
  - `fetch(page)` returns that page's items, each a `(url, item)` pair.
  - `gather` plans the pages, calls `fetch` in order, de-duplicates by canonical URL, applies the stop rules and catches a later page's `ToolFailed` into `page_error`. A first-page `ToolFailed` propagates, so the gateway records the typed failure as before.
  - It is an adapter module because it maps provider pages and `ToolFailed` codes. Keeping it free of HTTP lets tests drive it with plain lists.
  - Alternative: paging inside each adapter. That would duplicate the stop and de-dup rules, which the scenarios test as one behavior.
- **One client per call.** Each connector gains a `client(context)` context manager that resolves the key once and yields the configured `httpx` client. Every page of a call goes through it, so the key is read once per attempt (PK-01), and version 1's `post` is built on the same helper, sending exactly the bytes it sent before.
- **Tavily through the pager too.** `tavily_search` v2 (`search_once`) calls `gather` with `planned=1` and `page_size=max_results`. Its fetch answers page 1 with one request for up to `max_results` results and is never asked for page 2. So the "short" test for Tavily compares with what it asked for, not with 10. So both tools share de-dup, ranks, stop reasons and output fields.
- **Versioned contracts.** `contracts/web_tools.py` gains `SearchWebV2Input`, `TavilySearchV2Input`, `RankedSnippet`, `RankedSearchResult`, a `PagedSearch` output base with the paging fields and the `stopped` literal, and the two v2 outputs. Version 1's models are untouched, so their digests hold.
- **Timeouts.** `search_web` v2 keeps the 20-second request bound and gets `timeout_seconds = MAX_PAGES * REQUEST_SECONDS + 10` (70), checked by a test. A per-request timeout is a transport error, so it is `provider_unavailable`, and on a later page it becomes `page_error`. `tavily_search` v2 keeps 45 seconds for its one request.
- **Grants and compatibility.** `PROVIDER_TOOLS` and `TOOL_VERSIONS` move both tools to 2, and `COMPATIBLE_TOOL_CHANGES` gains `(search_web, 1, 2)` and `(tavily_search, 1, 2)`, as `read_run_file` and `create_github_issue` did. The fixture gains the v2 digests and keeps v1's.

## Risks / Trade-offs

- **Jina's `page` is untested live.** Jina's open-source searcher passes `page` to its search engine, but this change proves it only on fakes (Decision 0017 C5). If Jina ignores `page`, the "adds nothing new" rule stops at page 2 with `no_more`, so the extra request is one, not two.
- **Spend per search grows.** A `search_web` call can now cost 3 Jina requests inside one metered call (Decision 0031, What this gives up). It is recorded as `pages` in the tool-use record.
- **Two versions to keep.** Version 1 stays registered until no saved run or Expert version names it. This is the cost every versioned tool already carries.
