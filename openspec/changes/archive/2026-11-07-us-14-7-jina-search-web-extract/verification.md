# Verification — us-14-7-jina-search-web-extract

Change: us-14-7-jina-search-web-extract
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 4/4 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed against fake transports, as stated; the first also on a disposable stack |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Search against a fake transport | PASS | `tests/db/web_tools_check.py` in the `db` profile: `max_results` 11 is denied `invalid_arguments` with no request; a search for 2 returns 2 results labelled third-party; the run's tool uses are the denial and the success, provider `jina`, group `web_search`. `services/agent/tests/test_jina.py`: the request to `s.jina.ai` carries `{"q": "colones", "num": 3}` and the key only in its Authorization header; 3 of the fake's 12 results come back with title, URL and snippet, with the third-party notice and no key in the output; an empty query is also refused first |
| Extract in reader mode without provider inference | PASS | `test_jina.py`: the input has only `url` (an `engine` option is refused before any request); the request to `r.jina.ai` carries `{"url": ...}`, `X-Return-Format: markdown`, `X-With-Generated-Alt: false` and no `X-Respond-With`, ReaderLM or `X-Engine`; a 150,000-character page comes back as 100,000 characters with `truncated: true`, the third-party label and both links, under the byte cap. On the stack, the extract's record lists its URL without `?token=abc`, the title and link count, and no page text or key |
| URLs pass the guard | PASS | `test_jina.py`: a name resolving to loopback, an `http` URL and `10.0.0.1` fail `url_host_refused` or `url_scheme_refused` with nothing sent |

Also observed: a 429 is `rate_limited`, and without `JINA_API_KEY` a call fails `jina_key_missing` and sends nothing.

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the Jina cases, `identity_qualification`, `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed |
| `openspec validate us-14-7-jina-search-web-extract` | 0 | valid |

## Limits

- **No live Jina call was made,** under Decision 0017 C5. The POST bodies and headers follow Jina's documented reader and search interfaces, not a recorded live exchange.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
