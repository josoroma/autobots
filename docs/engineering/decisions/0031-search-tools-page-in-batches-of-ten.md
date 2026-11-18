# Decision 0031: Search tools page in batches of 10, at most 3 pages a call

**Date:** 2026-11-18. **Authority:** the owner. They asked that Autobots' search tools fetch results in batches of 10, with at most 3 pages per call, following [Deep-Research-Content-Writer](https://github.com/josoroma/Deep-Research-Content-Writer), planned in SPECS first. The choices below are the ones that request and its sources leave open. They are made under the owner's standing delegation, and the owner can change any of them under US-14.21. This adds the section Search paging to [PRD-Tool-Catalog](../../PRD/PRD-Tool-Catalog.md#search-paging) and schedules US-14.21.

## What the reference does

Deep-Research-Content-Writer searches 3 pages of 10 results, up to 30 URLs (its PRD FR-2, `pages=3`, `per_page=10`).

- **Next page.** It asks the provider for the next page by a parameter: SerpApi's `start=(page-1)*10`, or Serper's `page` with `num`. A result's page-relative position becomes a query-relative rank.
- **Budget.** A per-run plan of query-and-page calls is the budget. A call outside the plan is refused, and a page that failed can't be spent again.
- **Duplicates.** It drops duplicates by canonical URL, keeping the first in page order. The canonical form drops `utm_*` and the common click identifiers, the fragment and a trailing slash. It then re-ranks contiguously.
- **Stopping.** It never stops early: every planned page is requested, an empty page is a valid success, and a provider error never becomes an empty success.

## Providers

| Provider | Paging it offers (read 2026-11-18) |
|---|---|
| Jina `s.jina.ai` | `num` from 0 to 20 (default 10) and a 1-based `page`, passed to its search engine ([`src/api/searcher.ts`](https://github.com/jina-ai/reader/blob/main/src/api/searcher.ts)). It charges at least 10,000 tokens for each 10 results a request returns |
| Tavily `/search` | No next-page request: no `page`, `offset`, `cursor` or `start`. `max_results` runs from 0 to 20, and a request costs 1 credit at basic depth and 2 at advanced, whatever the count ([API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)) |

## Decision

| # | Choice |
|---|---|
| **S1. The search tools** | `search_web` and `tavily_search`, the group `web_search` (TC-03). Each takes free text and returns a provider's ranked list, so a next page means something. Five other tools are left as they are:<ul><li>`github_search_issues` searches one repository. GitHub returns up to 100 items a request, and its search API allows 30 requests a minute, so pages of 10 would cost more requests for fewer results.</li><li>The GitHub list tools already read up to 100 items in one request.</li><li>`tavily_extract`, `tavily_map`, `tavily_crawl` and `extract_website_content` read pages or sites they are given, not a ranked list.</li></ul> |
| **S2. Batch and cap** | A page is 10 results, and a call requests at most 3 pages, so at most 30 results. `max_results` is the call's target, and the call plans `ceil(max_results / 10)` pages, never more than 3. No page past that plan is requested, even when duplicates leave the call short |
| **S3. Next page** | `search_web` v2 sends one request per page to `s.jina.ai`: `q`, `num: 10` and `page: n`. Tavily offers no next page, and asking again for a longer list would pay again for the results already returned. So `tavily_search` v2 asks once, for up to 20 results, Tavily's own ceiling. Its call is one request, and its batches are presented the same way |
| **S4. Duplicates** | Across and within pages, by canonical URL: the scheme and host lowercased, without the fragment, any `utm_*` parameter, `gclid`, `fbclid`, `msclkid`, `mc_cid` or `mc_eid`, and without a trailing slash on the path. The first occurrence is kept in page order, then provider order, with the URL as the provider gave it. Ranks are contiguous from 1 after removal. The count removed is reported. A result without a URL is never treated as a duplicate. No host is filtered: the reference's host denylist served its own corpus, and nothing in Autobots' sources asks for one |
| **S5. Stopping early** | Paging stops at the first of these:<ul><li>`enough`: the call has `max_results` results.</li><li>`no_more`: a page came back with fewer than 10 results, or added nothing new. For Tavily, fewer than asked for.</li><li>`page_limit`: the call's planned pages are spent and it is still short.</li><li>`provider_error`: a later page failed (S7).</li></ul>The reference requests every planned page. Stopping on a short page saves a request that would return nothing |
| **S6. Metering and budget** | A search call stays **one metered tool call** under TU-06, admitted before its first page, as `tavily_crawl` and `browse_goal` already are. The page plan (S2) bounds what one call can spend: 3 Jina requests, or 1 Tavily request. Each tool use records the requests it made as `pages` in its public output, so the run's Tools used list shows what each search spent, page by page. The key is resolved once per call, and every page of the call goes through that attempt's one client. No page is retried |
| **S7. A provider error on a later page** | A failure on the first page fails the call with its typed code, as version 1 does: `rate_limited`, `<credential>_key_refused`, `provider_refused_<status>`, `provider_unavailable`, `provider_reply_malformed`, or `<credential>_key_missing` before any request. A failure on a later page ends paging. The call succeeds with the earlier pages' results, `stopped: provider_error`, and the failure's typed code as `page_error`. The provider's body never reaches the model. The timeout fits three requests: `search_web` v2 bounds each request at 20 seconds, within a 70-second call |
| **S8. What the model sees** | The output keeps version 1's third-party label, notice and `truncated` flag, plus these fields:<ul><li>`results`, in rank order, each with `rank`, `title` and `url`, then `snippet` from Jina, or `content` and `score` from Tavily.</li><li>`result_count`, `pages`, `stopped`, `duplicates_removed` and `page_error`.</li></ul>The 100,000-character text budget is shared across all results, as before. Public output fields are `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` and `truncated`. Public input fields are unchanged |
| **S9. Versions** | A changed schema is a new version (Decision 0029 F13):<ul><li>`search_web` v2 takes `max_results` from 1 to 30, default 10.</li><li>`tavily_search` v2 takes `max_results` from 1 to 20, default 10, with version 1's other inputs.</li><li>Both have S8's output.</li></ul>Version 1 of each stays registered, unchanged, with the schema digest it was published with. A run or an Expert version that pinned version 1 keeps calling it, and its old checkpoints keep their meaning. New grants take version 2. Each tool keeps one guide, which describes version 2 |

## What this gives up

- **Tavily can't page.** A Tavily call returns at most 20 results, not 30.
- **More provider spend inside the same count.** A root run tree may still make 20 metered calls, but a Jina search can now be 3 requests. Up to 60 Jina search requests fit where 20 did. Decision 0017 already accepted this for crawl: the page plan bounds it, and the tool-use record shows it.
- **No cross-call plan.** Unlike the reference, nothing stops a run from asking for the same query again. Each call stands alone.

## Alternatives not taken

- **Counting each page against TU-06.** A search would take up to 3 of the 20. That needs a count column on `tool_uses` and changes what the run screen's "metered tool calls" means. It would also differ from crawl and browsing, which count once.
- **Paging Tavily by asking for 10, then 20.** The second request returns the first 10 again, at a second credit.
- **Failing the whole call on a later page's error.** Results already paid for would be lost.

## What this doesn't establish

That paging works against the live providers. Every test uses a fake transport, as Decision 0017 C5 requires. A live check of Jina's `page` is a separate task with a cap the owner sets. Neither H1 nor product acceptance follows.

## Reversal

Version 2 of either tool can be withdrawn from new grants by pointing `PROVIDER_TOOLS` back to version 1. Runs that pinned version 2 would stop as `incompatible_version` once it is unregistered, with a linked new run as the way forward.
