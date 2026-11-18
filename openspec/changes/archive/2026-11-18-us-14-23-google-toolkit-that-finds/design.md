# Design

## Context

- `url_guard.guarded_fetch(url, transport=, resolver=, headers=, max_bytes=, seconds=)` follows up to 3 redirects, each re-vetted. It returns `Fetched(url, status, content_type, body)` for any non-redirect status, and raises `UrlRefused(<code>)` on a guard refusal, unreachable host, oversize body or timeout.
- `adapters/serpapi.py` holds one-client-per-call paging for `google_search`, built on `search_paging.gather` and `Page`.
- No HTML extractor is locked. Decision 0017 C12 is amended for `trafilatura` alone (Decision 0033 K5).

## Goals / Non-Goals

**Goals:**
- Three new tools on existing seams: the URL guard, SerpApi paging and the shared text budget.
- One reader that `google_extract` and `google_crawl` share.

**Non-Goals:**
- The switches (US-14.24).
- Readability or Beautiful Soup fallbacks, PDFs and JavaScript rendering.
- Shared robots caches across calls.
- Live requests.

## Decisions

- **`adapters/google_reader.py`.** A `Reader(transport, resolver, sleep, clock)` is built per call, and holds that call's robots cache and per-host last-request times. `read(url, seconds)` works in four steps:
  1. **Robots.** It parses the host and loads the host's robots policy once, through `guarded_fetch` at 256 KiB and 5 seconds. 200 is parsed by `urllib.robotparser.RobotFileParser.parse`. 404 and 410 allow. Anything else, or a `UrlRefused`, denies. A disallowed URL fails `robots_disallowed` with no page request.
  2. **Spacing.** It waits until `last + max(1, min(crawl_delay, 5))` for that host.
  3. **The page.** It fetches the page with the user agent and an `Accept` for HTML and text, at 1 MiB and `seconds`. A redirect's final host is then checked against its own robots policy, and a refusal discards the body.
  4. **The text.** 200 HTML or XHTML goes to `trafilatura.bare_extraction(..., output_format="markdown", include_comments=False, include_tables=True, with_metadata=True, url=final)` for text and title. Plain text and markdown are decoded as they are. Anything else is `unsupported_media_type`, and an empty text is `no_readable_text`.

  `sleep` and `clock` are injected, so tests observe the spacing without waiting.
- **Failures are data.** `google_extract` collects each URL's `ReadResult` or `ReadFailure(code)`. A guard refusal keeps the guard's code (`url_host_refused` and so on). The tool fails as a whole only when no URL was given. Pydantic bounds that to 1 to 5.
- **`google_map`** reuses `serpapi.search`'s paging. The fetch builds `q = f"site:{host}{path}"`, and a URL is kept when its host equals the site's or ends with `.` plus the site's. `GoogleMapInput` is `url` (`GuardedUrl`) plus `max_results` 1 to 30. `GoogleMapOutput(PagedSearchOutput)` adds `base_url` and `urls`.
- **`google_crawl`** calls the map's fetch for one page of `limit`, then `Reader.read` for each URL at 10 seconds a page. Output: `GoogleCrawlOutput(WebOutput)` with `base_url`, `results`, `failed`, `result_count` and `pages`.
- **Contracts.** `GoogleExtractInput` holds `urls`, 1 to 5 `GuardedUrl`s. `ReadPage` holds `url`, `title`, `content_markdown` and `word_count`, and `ReadFailure` holds `url` and `code`. The text budget is `provider_http.fit` over the results' markdown.
- **Catalog vocabulary.** `ToolGroup.GOOGLE` and `ToolProvider.DIRECT` are added to the Literals in `contracts/tool_catalog.py` and to the web label tables. OpenAPI and the client are regenerated.
- **Grants.** `google_map` and `google_crawl` join `PROVIDER_TOOLS`. `google_extract`, which needs no key, joins `EXPERT_TOOLS` directly. All three join `TOOL_VERSIONS` at 1. Their digests are pinned, and `google_search`'s stays.
- **Dependency.** `trafilatura==2.3.1` goes in `pyproject.toml`, and `scripts/toolchain.py lock` and `bootstrap` follow. The toolchain runbook's table names it, and `tests/toolchain/test_manifests.py` checks the table.

## Risks / Trade-offs

- **`trafilatura`'s output varies by page.** Tests use small fixed HTML and assert structure, title and that some text is present, not exact markdown.
- **Robots edge cases.** `robotparser` handles `*` and per-agent groups, but not every wildcard.
- **Redirect robots are checked after the fact.** The request to the final page is made before its robots.txt is known (Decision 0033, What this gives up).
