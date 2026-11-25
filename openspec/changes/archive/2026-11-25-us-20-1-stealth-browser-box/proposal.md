# Proposal

## Why

US-20.1 in SPECS.md: [Decision 0038](../../../docs/engineering/decisions/0038-local-stealth-browser.md#decision) Z1 to Z6, Z13 and Z14. The box's browser says `HeadlessChrome` in every request, on an 800×600 screen in UTC, so sites that turn away a headless browser never open. The owner asked for browser-use run locally "with stealth capabilities".

## What Changes

- **An Expert's browser.** An Expert version names `box`, the default, or `stealth`. It is set in the editor beside the browse domains, shown on the card, and left out of stored configurations, requests and receipts while `box`. No input of `browse_goal` names it.
- **The stealth image.** `autobots-browser-stealth:local`, from the pinned Playwright image with Google Chrome's `.deb` unpacked, fetched by exact version and SHA-256. The box's entrypoint starts it headed under Xvfb, with software WebGL and the session's time zone.
- **The session.** Same network, proxy, guard, hardening, `tmpfs` and cleanup. Its browser container's process cap is 512.
- **Qualified apart.** Its own fingerprint, label, live check and report: the executor's refusals observed on its image, and its own cases. A call of a stealth Expert is refused `stealth_browser_unqualified` before any container while it isn't qualified.
- **The browser's own user agent.** On both browsers, the guard refuses a request under another user agent.
- **Documents.** PRD-Tool-Catalog BX-01, BX-05, AB-02 and AB-03, PRD-Studio EX-01, the operations runbook, `README.md`, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `stealth-browser`: an Expert's browser, the stealth browser in the box, its own qualification, and the browser's own user agent.

### Modified Capabilities
- None as requirements. `browser-executor`, `browser-use-engine` and `experts` keep theirs.

## Impact

- **Images:** a fourth image, whose first build downloads 142 MB from `dl.google.com`. The entrypoint and guard are in the executor's fingerprint, so every browsing qualification runs again.
- **Python:** `browser_qualification.py`, `browser_executor.py`, `browser_cdp.py`, `browser_use_box.py`, `browsing_tool.py`, `browsing_settings.py`, `contracts/experts.py`, `persistence/records.py`, `application/experts.py`, `domain/browsing.py`.
- **Web:** the Expert editor and card, and the generated client.
- **Database:** none. The browser is in the version's JSON configuration.
- **No paid call, and no real site in checks** beyond Decision 0018's qualification hosts.
