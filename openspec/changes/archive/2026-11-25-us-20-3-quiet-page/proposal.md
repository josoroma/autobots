# Proposal

## Why

US-20.3 in SPECS.md: [Decision 0038](../../../docs/engineering/decisions/0038-local-stealth-browser.md#decision) Z11 and Z12. browser-use draws its highlights on the page, which the page can see, and steps run as fast as the model answers.

## What Changes

- **Highlights off** on the stealth browser.
- **What a step touched.** The first ten elements by action, kind and label, read from an isolated world, kept in `browse_steps.touched` (migration 67) and shown in the run's tool row.
- **Pace.** Steps at least 2 seconds apart on either engine, and one stealth browse of a site at a time across the install.
- **Documents.** PRD-Tool-Catalog AB-01 and TV-01, PRD-Studio RN-06, the operations runbook, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `stealth-quiet`: what a stealth browse draws and records, its pace, and one browse of a site at a time.

### Modified Capabilities
- None as requirements.

## Impact

**Database:** migration 67 adds `app_private.browse_steps.touched`. **Python:** `browser_cdp.py`, `browser_use_box.py`, `browsing_tool.py`, `browse_steps.py`, a new `application/browse_turns.py`, and the steps' contract. **Web:** the tool row's steps and the generated client. The runner changes, so every browsing qualification runs again.
