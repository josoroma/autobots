# Proposal

## Why

US-20.4 in SPECS.md: [Decision 0038](../../../docs/engineering/decisions/0038-local-stealth-browser.md#decision) Z15. The owner has no way to see which of their sites a browser opens before relying on it.

## What Changes

- **`scripts/browser_scoreboard.py`** opens each address the owner names once in each browser, with no model, and records the result, status, bytes and seconds, hosts only.
- **Documents.** The operations runbook, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `browser-scoreboard`: the owner's scoreboard of addresses in each browser.

### Modified Capabilities
- None as requirements.

## Impact

One script and its harness test. No image, database, contract or web change, and no profile runs it.
