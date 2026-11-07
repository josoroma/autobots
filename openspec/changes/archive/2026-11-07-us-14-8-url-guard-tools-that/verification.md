# Verification — us-14-8-url-guard-tools-that

Change: us-14-8-url-guard-tools-that
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 3/3 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed with a fake resolver and a fake transport, as the scenarios state |
| Coherence | Followed the proposal. No design.md: one module |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Refuse unsafe URLs before any request | PASS | `services/agent/tests/test_url_guard.py`, 23 cases: `http`, `ftp` and `file` schemes give `url_scheme_refused`; `user:pass@` and `user@` give `url_userinfo_refused`; a URL over 2048 characters gives `url_too_long`; literal `127.0.0.1`, `::1`, `10.1.2.3`, `192.168.1.1`, `172.16.0.1`, `169.254.169.254`, `100.64.0.1`, `224.0.0.1`, `240.0.0.1`, `0.0.0.0` and `fd00:ec2::254`, and names resolving to loopback, metadata, IPv4-mapped loopback or a mix of public and private answers, give `url_host_refused`; an unknown name gives `url_unresolvable` and an empty host `url_malformed`. The fake transport recorded no request for any of them. A public name, and an IPv6 one, pass and are fetched once |
| Revalidate every redirect | PASS | A chain of three redirects is followed to its end with four requests; a chain needing a fourth is refused `url_too_many_redirects` and its target never requested. Redirects to `https://127.0.0.1/admin`, a name resolving to loopback, an `http` URL and the metadata address are each refused after the first request only |
| Cap size and time | PASS | A 2048-byte body against a 1024-byte cap is refused `url_too_large` whether its length is declared or streamed in chunks; a response slower than a 0.2-second cap is refused `url_timeout` |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (the 32 guard cases among them), lint, typecheck, contract drift, API client and web unit tests passed |
| `openspec validate us-14-8-url-guard-tools-that` | 0 | valid |

## Limits

- **DNS rebinding:** the guard resolves a host, and the HTTP client resolves it again to connect. A name that answers public then private between the two could slip through. Pinning the connection to the checked address is not done here. Provider adapters send URLs to their provider rather than fetching them, so this matters for tools that fetch themselves (US-14.9's `store_remote_file`).
- `system_resolver` was not exercised against real DNS; sockets are blocked in tests.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
