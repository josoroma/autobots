# Decision 0032: Google search through SerpApi, and a Google bot Expert

**Date:** 2026-11-18. **Authority:** the owner. They asked for Google search with the key [Deep-Research-Content-Writer](https://github.com/josoroma/Deep-Research-Content-Writer) really uses, as a tool for a Google bot. Its `.env.example` sets both `SERPER_API_KEY` and `SERPAPI_API_KEY`, but only SerpApi is used: `SEARCH_PROVIDER` defaults to `serpapi`, and its ADR 0005 records that Serper answered HTTP 403.

The owner chose two options in this session:
- "Seed a Google bot Expert";
- the SerpApi key from "Keys & vars and .env", like Tavily and Jina.

The other choices below are made under the owner's standing delegation. The owner can change any of them under US-14.22.

This amends [Decision 0017](0017-tool-catalog.md) C1, which named the tool providers, and adds to [PRD-Tool-Catalog](../../../PRD-Tool-Catalog.md#google-search) and [PRD-Studio](../../../PRD-Studio.md) SD-01 and SD-02. It schedules US-14.22.

## SerpApi's Google search (read 2026-11-18)

| Point | What SerpApi documents |
|---|---|
| Request | `GET https://serpapi.com/search.json`, with `engine=google`, `q`, `start` (the result offset: 0, 10, 20), `hl`, `gl` and `api_key` as a query parameter. No header carries the key |
| Results | `organic_results[]`, each with `position`, `title`, `link` and `snippet`, and `serpapi_pagination.next` while another page exists ([Google Search API](https://serpapi.com/search-api)) |
| Errors | An invalid key answers 401, and running out of searches or exceeding the hourly limit answers 429. A search with no results answers 200 with an `error` field and `search_information.organic_results_state` "Fully empty" ([status and error codes](https://serpapi.com/api-status-and-error-codes)) |
| Billing | One search per request. Cached searches, the same query and parameters within an hour, are free |

## Decision

| # | Choice |
|---|---|
| **G1. Provider** | SerpApi is a tool provider (`serpapi`), beside those Decision 0017 C1 names. It is a data service and runs no model for Autobots, so OpenRouter stays the only inference provider. Serper is not added: the reference doesn't use it, and its key didn't work there. Autobots never fetches or parses Google's own result pages |
| **G2. Tool** | `google_search` v1 is in the group `web_search`, with provider `serpapi`. It is `read_only` and `metered_provider`, makes no retry, and needs the `serpapi` key (`SERPAPI_API_KEY`). It takes `query`, 1 to 400 characters, and `max_results`, 1 to 30, default 10. Its output is Decision 0031 S8's, with `results[] {rank, title, url, snippet}`. It is a search tool under Decision 0031 S1, and pages by S2 to S7 |
| **G3. Pages** | Page n is one request with `start = (n - 1) * 10`, `hl=en` and `gl=us`, as the reference sends. `num` isn't sent: SerpApi's Google search doesn't document it. Google often fills a page with fewer than 10 ordinary results while more exist, so SerpApi's own signal decides when there are no more. A page whose reply has no `serpapi_pagination.next` ends paging with `no_more`, and a short page that has one doesn't. A "Fully empty" reply is an empty page, `no_more` and not an error. Any other reply with an `error` field is `serpapi_search_failed` |
| **G4. Errors** | Each status keeps PRD-Tool-Catalog's typed codes:<ul><li>401 or 403 is `serpapi_key_refused`;</li><li>429 is `rate_limited`;</li><li>any other 4xx is `provider_refused_<status>`;</li><li>5xx, a timeout or no answer is `provider_unavailable`.</li></ul>A first page's failure fails the call. A later page's keeps the earlier pages, as Decision 0031 S7 says |
| **G5. The key in a URL** | SerpApi takes the key only as a query parameter, so it is in the request URL. It is added to this attempt's request alone. No error text, URL or provider body reaches the model, a tool-use row, a receipt or a log line, since every failure is a typed code (PADP-07). The URL guard isn't involved: the tool sends no URL of the model's, only to SerpApi's fixed host |
| **G6. Spend** | One metered call per search under TU-06, as Decision 0031 S6 says. Its public output records `pages`, one SerpApi search each, and the cost note says so |
| **G7. The key** | `serpapi` joins Settings → Keys & vars as a secret, by PK-04's order: the key saved for the workspace, then the process environment, then `.env`. Saving it seals it like the other keys. A migration adds `serpapi` to the two database lists of allowed providers, and the owner applies it to the persistent install with `make migrate`. `make start` passes `SERPAPI_API_KEY` from `.env` by PK-06's rules, and `.env.example` names it |
| **G8. Google bot** | The concept seed gains a sixth Expert, **Google bot**: "Searches Google through SerpApi for up to 30 ranked results, reads the most relevant pages and cites each source." Its tools are `google_search`, `extract_website_content`, `save_artifact` and `publish_artifact`. It can read a page through Jina, and it can publish what it saves (Decision 0023 E7). Like every seeded Expert, it is saved without a tool that is unavailable on the install, and its purpose then says so. No workflow is added |

## What this gives up

- **Google only through SerpApi.** Its prices and limits apply, and a call can use 3 searches. A Google result page sometimes has fewer than 10 ordinary results, so 3 pages can return fewer than 30.
- **Fixed language and country.** `hl=en` and `gl=us`, as the reference sends. A search can't ask for another language or country until a later version adds inputs for them.
- **One more Settings item and migration.** The owner applies the migration to the persistent install themselves.

## What this doesn't establish

That `google_search` works against SerpApi live. Every test uses a fake transport (Decision 0017 C5), and no SerpApi search is made. A live check is a separate task with a cap the owner sets. The seed is run only on disposable stacks; the owner runs it on the persistent install. Neither H1 nor product acceptance follows.

## Reversal

Remove `google_search` from new grants and the registry. Runs that pinned it then stop as `incompatible_version`. The migration's wider lists are harmless and can stay. A saved SerpApi key can be removed in Settings → Keys & vars.
