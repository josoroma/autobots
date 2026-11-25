# Proposal

## Why

US-20.2 in SPECS.md: [Decision 0038](../../../docs/engineering/decisions/0038-local-stealth-browser.md#decision) Z5 and Z7 to Z10. The egress proxy refuses the hosts a site's silent check loads from, so it can't finish, and any embedded challenge frame ends a call at first sight, a widget on an unused form included.

## What Changes

- **Challenge hosts.** A fixed list, reachable as parts of a page by a session of browser-use on the stealth browser only. Going to one as a page ends the call.
- **A check that is the page** gets 20 seconds to clear, before the next model request is admitted.
- **A Turnstile frame** isn't a check. A reCAPTCHA, hCaptcha or Arkose frame still ends the call at once.
- **Nothing solves.** browser-use is told never to press or answer a check.
- **Documents.** PRD-Tool-Catalog BX-03 and AB-04, the operations runbook, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `stealth-checks`: challenge hosts, and checks that clear, stay or ask a person, on browser-use and the stealth browser.

### Modified Capabilities
- None as requirements.

## Impact

`browser_cdp.py`, `browser_executor.py`, `browser_use_box.py`, `browsing_tool.py` and the runner. Every browsing qualification runs again. No database, contract or web change. No real check is met: each is arranged on the qualification hosts by its address.
