# Tasks

## 1. Pager (Duplicates are removed across pages; A short page stops the paging; Never more than 3 pages; A provider error on a later page keeps the earlier pages)

- [x] 1.1 Add `adapters/search_paging.py`: `PAGE_SIZE` 10, `MAX_PAGES` 3, `canonical_url`, and `gather` with the page plan, de-duplication, contiguous ranks, the stops `enough`, `no_more`, `page_limit` and `provider_error`, and a later page's `ToolFailed` kept as `page_error`. Checked by `services/agent/tests/test_search_paging.py` driving `gather` with plain page lists, including a first-page failure that propagates

## 2. Contracts and tools (search_web asks for pages of 10; Tavily asks once for up to 20; What the model sees)

- [x] 2.1 Add the v2 input and output models to `contracts/web_tools.py`, leaving version 1's models unchanged. Checked by the schema-version pin test
- [x] 2.2 Register `search_web` v2 in `adapters/jina.py`, one request per page with `q`, `num` 10 and `page` n through one client per call, with `max_results` 1 to 30, a 70-second timeout and S8's public fields. Checked by `test_jina.py` on a fake transport: the request bodies and page numbers, 30 and 15 results, the 31 refusal, de-dup, the short page, the 429 on page 2 with no third request and no body or key in the output, the 503 on page 1, and the text-budget cut. Version 1's existing tests still pass
- [x] 2.3 Register `tavily_search` v2 in `adapters/tavily.py`, one request for up to 20 with inference options off and `pages` 1. Checked by `test_tavily.py` on a fake transport, including the 21 refusal. Version 1's existing tests still pass

## 3. Versions and guides (Version 2 of each search tool sits beside version 1)

- [x] 3.1 Move `search_web` and `tavily_search` to version 2 in `domain/tools.PROVIDER_TOOLS` and `domain/execution.TOOL_VERSIONS`, add both to `COMPATIBLE_TOOL_CHANGES`, and add their v2 digests to `tests/fixtures/tool_schema_versions.json` beside v1's. Checked by `test_tool_schema_versions.py` and a test that a run recorded with version 1 is still compatible
- [x] 3.2 Update both tools' guides in `domain/tool_guides.py` to describe pages of 10. Checked by the guide test
- [x] 3.3 Fix any test or fixture that assumed one version per search tool, such as the catalog, Expert grant, concept-seed and web suites. Checked by the `fast` profile

## 4. Record and docs (One metered call per search, with its pages recorded)

- [x] 4.1 Add a scenario to `tests/db/checks/web_tools_check.py`: a three-page `search_web` v2 call through the gateway, recorded as one metered tool use whose public output holds `pages` 3 and no result text or key. Checked by the `db` profile on a disposable target
- [x] 4.2 Update `CODEBASE.md` for the pager and the v2 tools. Confirm with `python3.12 scripts/generate_contracts.py check` that no public contract changed

## 5. Record accuracy

- [x] 5.1 Correct `design.md`'s Tavily decision: its plan is one page because `search_once` passes `planned=1` and `page_size=max_results`, not because of `pages_for`. Checked by reading the decision against `adapters/tavily.py`
