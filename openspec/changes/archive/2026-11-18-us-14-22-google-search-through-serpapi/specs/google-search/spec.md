# Spec Delta

## Purpose

`google_search` searches Google through SerpApi, the provider the reference really uses, in pages of 10, at most 3 a call (Decisions 0031 and 0032). Autobots never fetches or parses Google's own pages.

## ADDED Requirements

### Requirement: google_search is a web search tool from SerpApi

`google_search` v1 SHALL be registered once in the group `web_search` with provider `serpapi`, operation class `read_only`, cost class `metered_provider`, the key requirement `SERPAPI_API_KEY` and a pinned schema digest. New grants SHALL take version 1. Without a key from any source, it SHALL be `key_missing`, with a repair naming Settings → Keys & vars and `SERPAPI_API_KEY`.

#### Scenario: google_search is a web search tool from SerpApi
- **GIVEN** the registry the catalog and the worker are built from, and a workspace with no SerpApi key in any source
- **WHEN** the catalog lists the group web_search and the schema-version pin test runs
- **THEN** google_search v1 appears once with provider serpapi, operation class read_only, cost class metered_provider and key requirement SERPAPI_API_KEY, its schemas are pinned, new grants take version 1, and it is key_missing with a repair that names Settings → Keys & vars and SERPAPI_API_KEY

### Requirement: google_search asks SerpApi for pages of 10

Each page SHALL be one GET to SerpApi's Google search, sent with:
- `engine=google`, the query, `hl=en` and `gl=us`;
- `start` at 10 times the page index;
- the key, in that request only.

Results SHALL be ranked from 1, with title, url and snippet.

#### Scenario: google_search asks SerpApi for pages of 10
- **GIVEN** google_search over a fake SerpApi transport that serves three pages of 10 organic results, each reply naming a next page
- **WHEN** it is called with max_results 30
- **THEN** it sends three GET requests to serpapi.com/search.json with engine google, the query, start 0, 10 and 20, hl en and gl us, returns 30 results ranked 1 to 30 with title, url and snippet, and reports pages 3 and stopped enough

### Requirement: SerpApi's next-page signal decides when there are no more

A reply that names no next page SHALL end paging with `no_more`. A page with fewer than 10 results that names one SHALL NOT. A "Fully empty" reply SHALL be an empty page, not an error.

#### Scenario: SerpApi's next-page signal decides when there are no more
- **GIVEN** a fake SerpApi transport whose first page holds 8 organic results and names a next page, and whose second holds 10 and names none, and another whose second page is a Fully empty reply
- **WHEN** google_search is called with max_results 30 over each
- **THEN** the first sends two requests, returns 18 results and stops no_more, and the second returns the first page's results, stops no_more and reports no page_error

### Requirement: SerpApi's failures are typed, and the key stays out of every output

Each failure SHALL be a typed code:

| Reply | Code |
|---|---|
| 401 or 403 | `serpapi_key_refused` |
| 429 | `rate_limited` |
| another 4xx | `provider_refused_<status>` |
| 5xx, or no answer | `provider_unavailable` |
| another reply with an `error` field | `serpapi_search_failed` |
| no key in any source | `serpapi_key_missing`, before any request |

A later page's failure SHALL keep the earlier pages. No output SHALL hold the key or provider text.

#### Scenario: SerpApi's failures are typed, and the key stays out of every output
- **GIVEN** fake SerpApi replies of 401 on the first page, 429 on the second page, and 200 with another error on the first page, and a workspace with no SerpApi key
- **WHEN** google_search is called over each, with a distinctive fake key where one is set
- **THEN** the first fails serpapi_key_refused, the second keeps the first page's results with stopped provider_error and page_error rate_limited, the third fails serpapi_search_failed, the last fails serpapi_key_missing before any request, and no output holds the key or provider text

### Requirement: One metered call per Google search, with its pages recorded

A `google_search` call SHALL be one tool use, counted once against the metered limit. Its public output SHALL record:
- `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` and `truncated`;
- no result text, and no key.

#### Scenario: One metered call per Google search, with its pages recorded
- **GIVEN** a disposable database, a run whose scope grants google_search, and a fake SerpApi transport that serves three pages
- **WHEN** the run's gateway executes one google_search call with max_results 30
- **THEN** exactly one tool use is recorded and counted once against the metered limit, its public output holds result_count 30, pages 3, stopped enough, duplicates_removed 0, page_error null and truncated, and neither a result's text nor the key appears in the record
