## Why

US-14.6, [PRD-Tool-Catalog "Web tools"](../../../../docs/PRD/PRD-Tool-Catalog.md#web-tools) and Decision 0017 C1, C2, C5 and C12: runs can't search, read or crawl the web. Tavily is the first tool provider.

## What Changes

- `adapters/tavily.py`: `tavily_search`, `tavily_extract`, `tavily_map` and `tavily_crawl`, read-only and metered, as plain `httpx` adapters with an injectable transport. The key is read per attempt through `provider_key`. `include_answer` and `auto_parameters` are always sent false, natural-language `instructions` and raw-content options are never offered or sent, and the schemas carry the PRD's ceilings: 10 results, 5 URLs, depth 2, breadth 20, 50 mapped and 20 crawled pages.
- Every URL passes `check_url` before it is sent. Output is labelled third-party with a notice, page text shares a 100,000-character budget and says when it was cut, and a provider refusal is a typed code (`rate_limited`, `tavily_key_refused`, `provider_refused_<status>`, `provider_unavailable`). No retries, since each call spends credits.
- The tools join the loop's registry, the execution contract's version table and the Expert-grantable set, in the web search, extraction and crawling groups.

## Capabilities

### New Capabilities

- `web-tools`: provider-backed web tools.

### Modified Capabilities

None.

## Impact

`adapters/tavily.py`, `adapters/provider_http.py` (`failure_for`, `fit`), `contracts/web_tools.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, the generated contract, `tests/test_tavily.py`, `tests/db/web_tools_check.py`, `scripts/app_db.py` and the US-14.5 browser assertion. No package was added. No live Tavily call was made.
