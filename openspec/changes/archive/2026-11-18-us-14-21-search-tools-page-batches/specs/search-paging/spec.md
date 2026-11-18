# Spec Delta

## Purpose

How the search tools, `search_web` and `tavily_search`, fetch results in pages of 10, at most 3 a call. It covers de-duplication, early stops, later-page errors, what the model sees and how each search's spend is recorded (Decision 0031).

## ADDED Requirements

### Requirement: Version 2 of each search tool sits beside version 1

`search_web` and `tavily_search` SHALL each be registered at versions 1 and 2. Version 1's input and output schemas SHALL keep their pinned digests. New grants SHALL take version 2, and a run that pinned version 1 SHALL keep calling it without being stopped as incompatible_version.

#### Scenario: Version 2 of each search tool sits beside version 1
- **GIVEN** the registry the catalog and the worker are built from
- **WHEN** the catalog lists the group web_search and the schema-version pin test runs
- **THEN** search_web and tavily_search each list versions 1 and 2, version 1's input and output schemas keep their pinned digests, new grants take version 2, and a run that pinned version 1 keeps calling it and is not stopped as incompatible_version

### Requirement: search_web asks for pages of 10

`search_web` version 2 SHALL request `ceil(max_results / 10)` pages of 10 from Jina, at most 3, each with `num` 10 and its page number. It SHALL return the results ranked from 1 in page order, with the number of pages requested.

#### Scenario: search_web asks for pages of 10
- **GIVEN** search_web version 2 over a fake Jina transport that serves three full pages of distinct results
- **WHEN** it is called with max_results 30, and separately with max_results 15
- **THEN** the first call sends three requests with num 10 and page 1, 2 and 3 and returns 30 results ranked 1 to 30 in page order with pages 3 and stopped enough, and the second sends two requests and returns 15 results with pages 2

### Requirement: Never more than 3 pages

A search call SHALL never request more than 3 pages. A `max_results` above a version's ceiling SHALL be refused before any request.

#### Scenario: Never more than 3 pages
- **GIVEN** the same fake transport, and one whose every page repeats the same 10 results
- **WHEN** search_web version 2 is called with max_results 31, and then with max_results 30 over the repeating transport
- **THEN** the first is refused invalid_arguments before any request, and the second sends no more than 3 requests, returns 10 results and stops no_more

### Requirement: Duplicates are removed across pages

A search call SHALL drop results whose canonical URL was already returned. The canonical URL lowercases the scheme and host, and drops the fragment, `utm_*` and common click-identifier parameters and a trailing slash. The first occurrence SHALL be kept with the URL the provider gave. Ranks SHALL run from 1 without gaps, and the count removed SHALL be reported.

#### Scenario: Duplicates are removed across pages
- **GIVEN** a fake Jina transport whose second page repeats first-page URLs with a utm_source parameter, a fragment, an upper-case host and a trailing slash
- **WHEN** search_web version 2 is called with max_results 20
- **THEN** each repeat is dropped, the first occurrence keeps the URL the provider gave, ranks run from 1 without gaps, and duplicates_removed counts the repeats

### Requirement: A short page stops the paging

Paging SHALL stop at a page with fewer than 10 results, or one that adds nothing new, and SHALL report `no_more`.

#### Scenario: A short page stops the paging
- **GIVEN** a fake Jina transport whose first page is full and whose second page holds 4 results
- **WHEN** search_web version 2 is called with max_results 30
- **THEN** it sends two requests, returns 14 results, and reports pages 2 and stopped no_more

### Requirement: Tavily asks once for up to 20

Tavily offers no next page, so `tavily_search` version 2 SHALL send one request for up to 20 results, with Tavily's inference options off, and report one page.

#### Scenario: Tavily asks once for up to 20
- **GIVEN** tavily_search version 2 over a fake Tavily transport
- **WHEN** it is called with max_results 20, then with max_results 21
- **THEN** the first sends one request with max_results 20 and Tavily's inference options off and reports pages 1, and the second is refused invalid_arguments before any request

### Requirement: A provider error on a later page keeps the earlier pages

A first-page failure SHALL fail the call with its typed code. A later page's failure SHALL end paging without a retry. The call SHALL succeed with the earlier pages' results, `stopped: provider_error` and the failure's typed code as `page_error`. No provider text SHALL reach the output.

#### Scenario: A provider error on a later page keeps the earlier pages
- **GIVEN** a fake Jina transport whose first page is full and whose second page answers 429 with a body naming a fake key, and another whose first page answers 503
- **WHEN** search_web version 2 is called with max_results 30 over each
- **THEN** the first call succeeds with the first page's 10 results, pages 2, stopped provider_error and page_error rate_limited, sends no third request and no retry, and its output holds neither the body nor the key; the second call fails provider_unavailable

### Requirement: What the model sees

A search tool's version 2 output SHALL carry:
- the third-party label and notice;
- results with rank, title and url, and the provider's text: `snippet` for Jina, `content` and `score` for Tavily;
- `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` and `truncated`.

The results SHALL be cut to the shared text budget, within the tool's output cap.

#### Scenario: What the model sees
- **GIVEN** a search_web version 2 call whose results together exceed the shared text budget
- **WHEN** its output is returned to the model
- **THEN** it carries source third_party and the notice, results with rank, title, url and snippet, result_count, pages, stopped, duplicates_removed, page_error and truncated true, within the tool's output cap

### Requirement: One metered call per search, with its pages recorded

A search call SHALL be one tool use, counted once against the metered limit before its first page. Its public output SHALL record `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` and `truncated`, and no result text or key.

#### Scenario: One metered call per search, with its pages recorded
- **GIVEN** a disposable database, a run whose scope grants search_web version 2, and a fake Jina transport that serves three full pages
- **WHEN** the run's gateway executes one search_web call with max_results 30
- **THEN** exactly one tool use is recorded for it and counted once against the metered limit, its public output holds result_count 30, pages 3, stopped enough, duplicates_removed 0, page_error null and truncated, and neither a result's text nor the key appears in the record
