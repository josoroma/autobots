# Design

## Context

A browse's session is a Chromium container behind an egress sidecar. browser-use, or Autobots' loop, attaches over CDP, and the worker keeps its own connection with its request guard. The Expert version a run was admitted with already holds its browse domains. Google Chrome 158 for Linux arm64 was run headed in the box's hardening before this was designed (Decision 0038, "What was measured").

## Goals / Non-Goals

**Goals:** US-20.1's scenarios, on fixtures and the qualification hosts.

**Non-Goals:** challenge hosts and clearing checks (US-20.2), highlights, step records and pace (US-20.3), the scoreboard (US-20.4).

## Decisions

**S1. One entrypoint, two modes.** `browser-entrypoint.js` starts headless Chromium, or with `AUTOBOTS_BROWSER=stealth` waits for Xvfb's socket and starts Chrome headed. Every other flag is shared, so the proxy and resolver rules can't drift apart.

**S2. Unpacked, not installed.** `dpkg -x` in a build stage runs no maintainer script, which would add Google's package source. The download is pinned by version and checksum, never the moving `current` address.

**S3. Fingerprint.** The stealth fingerprint is browser-use's files plus its Dockerfile and ignore file, since its live check exercises both engines on it. The executor's own report is required, as for browser-use.

**S4. Which Expert version.** `expert_browser` reads the configuration of the version the run was admitted with, beside the workspace's time zone. An unknown time zone reads as UTC. A run without an Expert has the box.

**S5. The user agent.** The guard reads `Browser.getVersion` once, and compares each paused request's `User-Agent`. A mismatch is refused. A refused top-frame navigation ends the call, and a page's own request is refused and counted without ending it, as Decision 0018 has for a subresource. A request with no such header, such as a data URL, says nothing else.

**S6. Process cap per session.** `BrowserSession` carries its browser container's cap, which the cap watcher compares against. The sidecar and the browser-use container keep 256.

## Risks / Trade-offs

- **SwiftShader** says the browser has no GPU. That is Z3's choice: nothing is invented.
- **A build downloads from Google** when its layer isn't cached, and Google may remove the version. Then the pin moves and the image qualifies again.
