## Why

US-14.8, [PRD-Tool-Catalog UG-01](../../../../docs/PRD/PRD-Tool-Catalog.md#url-guard) and Decision 0017 C6: provider and file tools are about to take URLs, and nothing yet stops a URL from reaching this Mac's loopback services (Supabase on `127.0.0.1:55321`, the API), a private network or cloud metadata.

## What Changes

- `adapters/url_guard.py`: `check_url` admits only `https`, no userinfo, at most 2048 characters, and a host whose every DNS answer, or literal address, is globally routable (IPv4-mapped IPv6 unwrapped). `guarded_fetch` checks each hop before requesting it, follows at most three redirects, refuses a fourth, and stops at a size cap (declared or streamed) and a time cap. Refusals are typed: `url_scheme_refused`, `url_userinfo_refused`, `url_too_long`, `url_malformed`, `url_unresolvable`, `url_host_refused`, `url_too_many_redirects`, `url_redirect_malformed`, `url_too_large`, `url_timeout`, `url_unreachable`.
- The resolver and transport are injectable, so tests use fakes and never open a socket.

## Capabilities

### New Capabilities

- `url-guard`: the shared guard for URLs tools fetch or send.

### Modified Capabilities

None.

## Impact

`services/agent/src/autobots/adapters/url_guard.py` and `services/agent/tests/test_url_guard.py`. Nothing calls it yet; US-14.6, US-14.7, US-14.9 and US-14.10 will.
