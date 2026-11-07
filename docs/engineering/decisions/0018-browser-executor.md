# Decision 0018: Isolated browser executor, admitted browser model and browse_goal

**Date:** 2026-11-07. **Authority:** the owner, who read [the browser-executor plan](../../plan/browser-executor.md) and answered "Approve and ingest" to its recommendations. That approves decisions B1 to B8 below, the PRD-Tool-Catalog sections they add, and the stories US-14.13 and US-14.14, and it answers [US-14.12's open questions](../../../SPECS.md#us-1412-goal-driven-browsing). [Decision 0017](0017-tool-catalog.md) C3 and C4 stand: `browse_goal` stays disabled until both new stories are delivered.

## Decision

| # | Choice |
|---|---|
| **B1. Browser image** | The official Playwright image for the pinned Playwright version, pinned by digest. Chromium lives only in that image, never on the host |
| **B2. Resource caps** | Per call: 1 CPU, 1 GiB memory, 256 processes, a 256 MiB `tmpfs`, and 300 seconds |
| **B3. Egress proxy** | A sidecar container on the browser's internal network and the default network. It applies the URL guard to every request and connects to the address it checked |
| **B4. Model role** | `researcher`, on the run's frozen policy (Terra by default). No other model path exists for browsing |
| **B5. Allowed actions** | Read only: navigate, click links, scroll, read and extract. No typing, form submission, sign-in, upload or download. Typing and submitting need their own decision, with approval per action |
| **B6. Approval** | Every `browse_goal` call waits for a person, who sees the task, start URL, allowed domains and limits |
| **B7. Dependency** | `browser-use` is added, pinned in `uv.lock`, by US-14.14, with its dependency tree reviewed. The adapter is tested against that version's own model protocol |
| **B8. Live checks** | Only the executor's isolation is checked live, on a disposable stack, with a scripted model. A run with a real model is a separate task the owner authorizes and caps |

**The shape:** browser-use's agent loop runs in the worker, so every model call is an admitted call of the run. The browser runs in a disposable container driven over CDP, published on loopback only behind a per-session token. The container has no key, no host path and no inherited environment.

## Requirements revised

- PRD-Tool-Catalog gains [Isolated browser executor](../../../PRD-Tool-Catalog.md#isolated-browser-executor) and [Admitted browser model](../../../PRD-Tool-Catalog.md#admitted-browser-model). [Autonomous browsing](../../../PRD-Tool-Catalog.md#autonomous-browsing) gains `browse_goal`'s contract.
- PRD 9.1's rule stands: arbitrary execution stays disabled except for a tool whose executor reports qualified. `browse_goal` is the only such tool, and only through an Expert grant with approval on every call.

## What this gives up

- **Read-only browsing** can't use sites that need typing, a search form or a sign-in.
- **One container per call** costs a few seconds to start.
- **A Chromium exploit** from a hostile page lands in the container; the caps and the proxy bound what it reaches. Keeping the image current is the main defence.
- **The sidecar is an image built locally,** which adds a build step to the install.

## What this doesn't establish

That browsing works against real sites with a real model. The live checks prove isolation only, and a scripted model drives them.

## Reversal

Remove `browse_goal`'s registration and its executor. The descriptor returns to `disabled_by_policy`. Saved runs that pinned it stop as `incompatible_version`.
