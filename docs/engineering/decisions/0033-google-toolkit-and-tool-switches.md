# Decision 0033: A Google toolkit that finds with Google and reads directly, and tool switches

**Date:** 2026-11-18. **Authority:** the owner. They asked for:
- Google tools that are "easily turned off or on, with its subtools separate";
- Google to have its own map and crawl, like the other search providers;
- "find with google, read with google equivalent".

They approved this plan in the session ("yes go ahead"):
- a Google group of four tools;
- reading pages directly, as Deep-Research-Content-Writer does (its ADR 0006), with `trafilatura`;
- per-workspace on/off switches on the Tools page, for each tool and each group.

The owner can change any choice under US-14.23 or US-14.24. This amends [Decision 0017](0017-tool-catalog.md) C12 (no new package) for one package, and Decisions 0031 S1 and 0032 G2 (Google Search's group). It adds to [PRD-Tool-Catalog](../../PRD/PRD-Tool-Catalog.md#google-toolkit) and schedules US-14.23 and US-14.24.

## What Google can and can't do here

SerpApi returns Google's search results, and nothing else: it neither reads a page nor walks a site ([Decision 0032](0032-google-search-through-serpapi.md)). So the toolkit finds pages with Google and reads them with Autobots' own fetcher, as the reference does: it searches with SerpApi, then fetches politely and extracts with `trafilatura`. No third-party reader is involved.

## The Google toolkit (US-14.23)

| # | Choice |
|---|---|
| **K1. Group** | A new group, **Google** (`google`): "Find with Google through SerpApi, and read pages directly from their sites." It holds `google_search`, which moves from `web_search` (only its descriptor changes, not its schemas or version), and `google_map`, `google_extract` and `google_crawl`. `search_web` and `tavily_search` stay in `web_search`. Decision 0031's search tools are named by ID |
| **K2. `google_map` v1** | Lists the pages Google has indexed for a site. It searches SerpApi for `site:<host><path>`, taken from `url` (scheme, query and fragment dropped, host lowercased, no trailing slash). It takes `max_results` 1 to 30, default 10, and pages through the shared pager with SerpApi's next-page signal. A result on another host is dropped; a subdomain of the site counts as the site. Output: `base_url`, `urls` in Google's order, and Decision 0031 S8's paging fields. Provider `serpapi`, key `serpapi`, `read_only`, `metered_provider`, one metered call |
| **K3. `google_extract` v1** | Reads up to 5 pages as markdown, fetching each from its own site. Provider `direct` ("Directly from each site"). It needs no key, and like market data it counts as a metered call because it leaves the Mac (TU-06). Its output, labelled third-party, is:<ul><li>`results[] {url, title, content_markdown, word_count}`;</li><li>`failed[] {url, code}`;</li><li>`result_count` and `truncated`.</li></ul>The 100,000-character text budget is shared across the results |
| **K4. Fetching politely** | Every request passes the URL guard (`url_guard.guarded_fetch`, C6), which caps a page at 1 MiB and 15 seconds. Each request sends the user agent `Autobots/1.0 (local research agent)` and no contact of the owner's.<ul><li>**robots.txt** is read once per host per call: 256 KiB and 5 seconds.<ul><li>200 is parsed and obeyed for the `Autobots` agent.</li><li>404 or 410 allows.</li><li>401, 403, a 5xx, no answer or a refusal from the guard denies, failing closed, as the reference does.</li></ul></li><li>**After redirects**, the final host's robots.txt is checked too, and a page whose destination it disallows is discarded, unread.</li><li>**Requests to one host** are at least 1 second apart, or its `Crawl-delay` capped at 5 seconds.</li><li>**No page is retried.**</li></ul>Each failure is a typed code: `robots_disallowed`, `page_http_<status>`, `unsupported_media_type`, `no_readable_text` or the guard's own `url_*` code. Only HTML and XHTML are extracted; `text/plain` and `text/markdown` are returned as they are. The model sees no provider or page error text |
| **K5. Extraction** | `trafilatura` 2.3.1 (Apache-2.0), pinned and locked with its transitive packages. It is the reference's first extractor; its fallbacks are not added. Only `trafilatura.extract` and `bare_extraction` are used, on bytes Autobots fetched. Its own downloader is never called, so it opens no connection. It runs no model. Comments are left out, and tables kept. A page whose extracted text is empty is `no_readable_text` |
| **K6. `google_crawl` v1** | Maps a site with Google, then reads its pages. It runs `google_map` with `max_results` = `limit`, 1 to 10, default 5: one SerpApi search. It then reads each URL as `google_extract` does, in Google's order, at most 10 seconds a page. Output: `base_url`, and `google_extract`'s results, failed, counts and cut flag, plus `pages`. Provider `serpapi` (its find step), key `serpapi`, one metered call. A failed map fails the call, and a failed page is listed in `failed` |
| **K7. Timeouts** | `google_extract` gets 150 seconds, enough for 5 pages with robots.txt and spacing. `google_crawl` gets 180: a 20-second map, then 10 pages |
| **K8. Google bot** | The seeded Google bot is granted `google_search`, `google_map`, `google_extract`, `google_crawl`, `save_artifact` and `publish_artifact`, in place of Jina's reader. The seed never changes an Expert that already exists. On an install that already has Google bot, the owner edits it in the Experts editor, or removes it and seeds again |
| **K9. Versions** | Three new tools, each at version 1, with pinned schema digests, granted to Experts. `google_search` keeps version 1 and its digest |

## Tool switches (US-14.24)

| # | Choice |
|---|---|
| **W1. What** | The owner can turn any tool an Expert can be granted on or off for the workspace, and any group as a whole, on the Tools page. Everything starts on. A tool is on only while both it and its group are on. The plan tools, delegation and workflow approval steps aren't switchable, so a run can't lose the tools it needs to plan and finish |
| **W2. Off means unavailable** | A tool that is off, or in a group that is off, reads `disabled_by_policy` with reason `turned_off` or `group_turned_off`, and its repair says where to turn it back on. Then:<ul><li>a run or routine that grants it is refused `tool_unavailable` at admission;</li><li>saving an Expert that grants it is refused `expert_tool_unavailable`;</li><li>a run already in progress has each call to it refused `tool_turned_off` by the gateway, before any effect.</li></ul>Turning it back on restores all of this for the next call |
| **W3. Storage** | A private table, `app_private.tool_switches`: workspace, kind (`tool` or `group`), target, `enabled`, `version` and `updated_at`. No row means on. Changes take the expected version, like Keys & vars, and a stale one is refused `stale_version`. Direct server SQL only, with no browser role |
| **W4. Who** | Every member sees each tool's and group's switch state. Only the owner changes them, under the same workspace and CSRF checks as Keys & vars |
| **W5. API and screen** | The catalog's descriptors gain `switch {enabled, version, by}` and its groups `switch {enabled, version}`. `PUT /v1/tools/{tool_id}/switch` and `PUT /v1/tools/groups/{group}/switch` take `enabled` and `expected_version`. On the Tools page, each switchable tool and group shows an on/off switch with its state in words. The switches are owner-only, keyboard-operable, and pass axe in both themes |

## What this gives up

- **Google reading is Autobots' own reading.** Pages that need JavaScript, PDFs and paywalled pages come back as failures. `trafilatura` sometimes keeps boilerplate or misses text.
- **Robots.txt by the standard library.** `urllib.robotparser` lacks some wildcard rules that Protego handles.
- **Redirects checked at the end, not at each hop.** A page whose destination robots.txt disallows has already been requested once, though nothing of it is kept or returned.
- **A new dependency** and its transitive packages, to keep current.
- **Switches are per workspace, not per Expert.** Expert grants already narrow a single Expert.

## What this doesn't establish

That any of this works against SerpApi or real websites. Tests use fake transports, fake resolvers and disposable databases, and make no SerpApi search or live page read. A live check is a separate task the owner caps. Neither H1 nor product acceptance follows.

## Reversal

- Turn a tool or the Google group off with its switch.
- Remove a tool from the registry. Runs that pinned it then stop as `incompatible_version`.
- Remove `trafilatura` from the manifest, then lock again.
- The switch table can stay empty.
