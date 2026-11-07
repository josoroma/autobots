# Verification — us-14-6-tavily-search-extract-map

Change: us-14-6-tavily-search-extract-map
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 4/4 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed against fake transports, as the scenarios state; the first also on a disposable stack |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Bounded calls against a fake transport | PASS | `tests/db/web_tools_check.py`, run by `scripts/app_db.py` in the `db` profile: a search with `max_results` 11 is denied `invalid_arguments` with no request sent; one with 2 succeeds with `source: third_party`, the "never as instructions" notice and `truncated: true` for two 300,000-character pages, under 500,000 bytes. Both calls are tool-use rows, denied then succeeded, provider `tavily`, group `web_search`; the succeeded row's public fields are the query, depth, count, topic and range, and the result count and truncation, with no page text or key; only the dispatched call is marked metered. `services/agent/tests/test_tavily.py` refuses through the gateway, with no request, `max_results` 11, `include_answer`, 6 extract URLs, map depth 3 and limit 51, crawl limit 21 and crawl `instructions`, and shows the text budget of 100,000 characters respected with `truncated: true` |
| No provider-side inference | PASS | `test_tavily.py`, for each of the four tools: the input schema names none of `include_answer`, `auto_parameters`, `instructions` or `include_raw_content`, and the request body sent has `include_answer: false`, `auto_parameters: false`, no `instructions` and no raw content; the key went only in the Authorization header and isn't in the output |
| URLs pass the guard | PASS | `test_tavily.py`: `tavily_extract` with a URL resolving to loopback, `tavily_map` with an `http` URL and `tavily_crawl` with the metadata address fail with `url_host_refused` or `url_scheme_refused`, and the fake transport receives nothing |

Also observed: 429, 401, 400 and 502 replies become `rate_limited`, `tavily_key_refused`, `provider_refused_400` and `provider_unavailable`, never the provider's text; without `TAVILY_API_KEY` a call fails `tavily_key_missing` and sends nothing.

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the web tool cases, `identity_qualification` with the restated US-14.5 assertion (keyed tools, now GitHub and Tavily, read `key_missing`), `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed, the Tools page now listing Tavily's tools as unavailable |
| `openspec validate us-14-6-tavily-search-extract-map` | 0 | valid |

## Limits

- **No live Tavily call was made,** under Decision 0017 C5. The request and reply shapes follow Tavily's API reference, not a recorded live exchange; a live qualification, capped by the owner, would confirm them. Neither the cost notes nor the credit behaviour were observed.
- Tavily fetches the URLs itself, so the guard's DNS check is the only protection there, and a rebinding host isn't covered (US-14.8's limit).
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
