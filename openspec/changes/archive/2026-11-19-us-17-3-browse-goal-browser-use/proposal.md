# Proposal

## Why

US-17.3 in SPECS.md: [Decision 0035](../../../docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md#decision) Y5, Y6, Y8, Y9, Y15, Y16 and Y18. While a call is YOLO, `browse_goal` should run on browser-use 1.0.6 inside the isolated executor, which pages Autobots' read-only loop can't use (a search box, a "Show transcript" button) need. browser-use runs Python its model writes, so it may run only in the box, with nothing of this Mac in reach, and every model call it makes must be an admitted call of the run (US-17.2).

## What Changes

- **Its own environment.** `services/browser-use/` holds `pyproject.toml`, `uv.lock` (browser-use 1.0.6, apart from the worker's lock) and `runner.py`, which runs one browse in the box and prints its outcome as one JSON line.
- **Its image.** `infra/browser/browser-use.Dockerfile` builds from the digest-pinned Playwright image (B1), with uv from its official image by digest, and `uv sync --frozen`. Telemetry and the update check are off in the image's environment.
- **Downloads off by policy.** The browser image gains a Chromium managed policy, `DownloadRestrictions` 3, so a download stays refused even when model-written code changes CDP's download behaviour.
- **One container per call.** For a browser-use browse, the executor starts the usual browser and egress sidecar, with the sidecar's model relay, and then one browser-use container on the session's internal network only, with BX-01's hardening and caps and nothing of the worker's environment. It drives the session's Chromium over CDP, with the call's `allowed_domains`, vision and its judge off, and the relay as its only model.
- **The engine per call (Y15).** browser-use while the call is YOLO and browser-use reports qualified. Otherwise Autobots' loop, with any limit capped to the loop's own.
- **`browse_goal` version 2 (Y9).** Version 2 takes `max_steps` up to 40 and `max_seconds` up to 600, both optional. Unnamed, they resolve to 25 and 300 on browser-use and to the loop's 10 and 120 on the loop, and the loop caps any limit at 20 and 300. Version 1 stays registered, unchanged, for runs and Expert versions that pinned it. New grants take version 2. The browser-use session's box cap is its call's limit plus the grace, so up to 600 seconds for those sessions only.
- **The outcome.** browser-use's status maps onto the same stop reasons. The worker watches its own CDP connection and the requests reaching the endpoint:
  - a refused navigation or download the model chose, or browser-use's own domain refusal, ends the call `refused_action` at the next model request, which is refused before admission;
  - an endpoint refusal from admission ends the call with that code, as the loop's `LoopStopped` does;
  - visited URLs come from the worker's CDP log of top-frame navigations, bare, within the call's domains.
- **Nothing to Browser Use's cloud.** The image's environment turns off telemetry and the update check, and the box has no route out but the egress proxy, which keeps its host rules and filters no methods (Y6).
- **Qualification.** `scripts/qualify_browser_executor.py` also qualifies browser-use, in its own report bound to its own fingerprint and image label, with a scripted model through the real endpoint, reaching only the qualification host. browser-use reports qualified only after every one of its cases is observed. Removing its image leaves `browse_goal` on Autobots' loop.
- **Documents.** PRD-Tool-Catalog BX-01 (the 600-second cap) and the browser-use image, `README-DEV.md`, the operations runbook's browser executor section and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `browser-use-engine`: `browse_goal` on browser-use in the isolated executor under YOLO, its engine choice, limits, outcome, refusals and qualification.

### Modified Capabilities
- None as requirements. `browser-executor` gains a third image and the download policy, which its qualification records, and `goal-driven-browsing`'s loop behaviour is unchanged.

## Impact

- **Python:** `adapters/browser_qualification.py` (the browser-use image, fingerprint, cases and `browser_use_qualified`), `adapters/browser_executor.py` (the browser-use container), `adapters/browser_cdp.py` (the navigation and download log), a new `adapters/browser_use_box.py` (the endpoint guard and the outcome), `application/browsing_tool.py` (the engine, limits and version 2), `contracts/browsing.py` (the version 2 input), `domain/tools.py` and `domain/execution.py` (version 2).
- **Images:** the browser image changes and the browser-use image is new, so `make browser-images` and the executor's qualification run again.
- **Scripts:** `scripts/browser_images.py` builds three images; `scripts/qualify_browser_executor.py` adds the browser-use child check `tests/db/checks/browser_use_check.py`.
- **No paid call.** Every check uses a scripted model. The owner's live run is a separate step.
