# Decision 0038: A local stealth browser for browsing on browser-use

**Date:** 2026-11-25. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The scope:** "the idea is to use browser-use local with stealth capabilities".
- **The request:** "implement docs/plan/stealth-browser.md", which approves [the plan](../../plan/stealth-browser.md) with the answers it recommends. Its W1 amends [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y10.
- **W6:** "Yes, download", on fetching Google Chrome for the stealth image from `dl.google.com` and accepting Google's terms for Chrome by building it.
- **The order:** "Build now, score later", on building before the plan's scoreboard has run on the owner's sites. No site but Decision 0018's qualification hosts is opened by the checks.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0035 to 0037. Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse. The owner can change any of them.

This amends [Decision 0018](0018-browser-executor.md) B1 and B2, [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y10 and Y11, and the PRD rows below. It schedules EPIC-20.

## What was measured

On 2026-11-25, offline, in the box's hardening. Google Chrome 158.0.8127.88 for Linux arm64 started headed under the image's Xvfb as `pwuser`, read-only, with no capabilities, 1 CPU and 1 GiB:
- **What a page read:** no `Headless` in the user agent, the brand `Google Chrome`, a 1440×900 screen, the container's time zone, `en-US,en` and SwiftShader WebGL.
- **Processes:** eight cross-site frames reached 241 and hit the 256-process cap, at 423 MB.
- **A changed user agent:** one set by another CDP client is in the request the worker's guard pauses, before it leaves.
- **Presses:** a script in an isolated world recorded presses and typing by element, and the page saw no trace of it.

## Decision

| # | Choice |
|---|---|
| **Z1. Whose choice** (W1) | An Expert's version names its browser: `box`, the default, or `stealth`. It is set in the Expert editor beside the browse domains, and saved like any other part of a version. No input of `browse_goal` names a browser, so the model never chooses one |
| **Z2. The stealth browser** (W6) | Real Google Chrome, headed, under Xvfb, in an image of its own: `autobots-browser-stealth`, built from the same pinned Playwright image (B1) with Chrome's `.deb`, fetched at build time by exact version and SHA-256, and unpacked without its install scripts. It is the only place Chrome runs. Building it accepts Google's terms for Chrome |
| **Z3. It says what it is** | The stealth browser changes what it is, not what it claims. No user agent, device, GPU, brand or fingerprint is invented. Software WebGL is on rather than absent. Its time zone is the workspace's. Its languages are Chrome's default, since a workspace has no language setting |
| **Z4. The box still holds** | The egress proxy, request guard, caps, hardening, `tmpfs`, ownership and cleanup are the box's own (BX-01 to BX-04). It starts with a fresh profile every call, and holds no key, cookie, card or host file. Two things differ: Z7's challenge hosts, and a cap of 512 processes, because headed Chrome reaches 256 on an ordinary page |
| **Z5. Which engine** | The browser and the engine are separate choices. With YOLO on and browser-use qualified, browser-use drives the Expert's browser. Otherwise Autobots' read-only loop drives it. Z7 to Z10 apply only to browser-use on the stealth browser |
| **Z6. Qualified apart** | The stealth browser has its own fingerprint and live report, like browser-use: every BX-05 refusal, observed on its image, and its own cases. It also needs the executor qualified. While it isn't, a call of an Expert set to `stealth` is refused `stealth_browser_unqualified` before any container starts. No call falls back to another browser |
| **Z7. Challenge hosts** (W2) | A fixed list in code, reachable from a stealth browse on browser-use as frames, scripts and other parts of a page: `challenges.cloudflare.com`, `captcha-delivery.com` and `datadome.co`, each with its subdomains. A top-frame navigation to one is refused and ends the call `refused_action`. The box's browser reaches none |
| **Z8. A check may clear by itself** | On browser-use and stealth, a check that is the page itself gets 20 seconds to clear. The model's next request waits meanwhile, so no model step runs. A page that clears continues. One that doesn't ends the call `bot_check`. The wait counts against the call's own time limit. A check has cleared when the page's top frame commits another page that shows none. Checks that are the page: Google's "sorry" page, a Cloudflare challenge on the site's own host, and a DataDome frame |
| **Z9. A widget that needs nobody** | A Turnstile frame from `challenges.cloudflare.com` on a page isn't a check, since it clears without a person. A reCAPTCHA checkbox or challenge, an hCaptcha or an Arkose frame asks a person, so it still ends the call `bot_check` at first sight |
| **Z10. Nothing solves** | No CAPTCHA solver, service, vision model, proxy service or cloud browser, and nothing presses a check. browser-use is told never to press or answer one, and its model sees no image (Y16). That instruction is not enforced on a Turnstile widget |
| **Z11. Quiet on the page** | On stealth, browser-use's highlights are off, so nothing is drawn on the page. In their place each step's record names the first ten elements it pressed or typed into: the action, the element's kind and its label, never the typed value. The worker reads them from an isolated world the page can't see (amends Y11 for stealth) |
| **Z12. Pace** | On stealth, steps are at least 2 seconds apart, and one browse of a site runs at a time across the install, whichever engine drives it. A call's sites are those of every domain it names, by their registrable part. A second waits within its own time limit, and one that never gets its turn ends `max_seconds` |
| **Z13. The browser's own user agent** | On both browsers, a request whose user agent isn't the browser's own is refused. A top-frame navigation under one ends the call `refused_action`. A page's own request under one is refused without ending it, as Decision 0018 has for a subresource. Y10 said no other user agent, and nothing enforced it on model-written code |
| **Z14. Sites** (W3) | The owner reads a site's terms before listing it on a stealth Expert. The stealth browser is not for YouTube or Google: YouTube's terms bar automated access, and the Transcript reader stays on `box`. Nothing is seeded with `stealth` |
| **Z15. The scoreboard** | `scripts/browser_scoreboard.py` opens each address the owner names once for each browser, with no model, and records `opened`, `check`, `blocked` or `error`, the bytes and the seconds. It is run by the owner, is in no verification profile, and keeps hosts only |
| **Z16. Not in this decision** | Cookies kept between browses (W4), an engine that invents a device, such as Fortress (W5, which needs a key the owner creates), Chrome on the Mac itself, and any cloud browser. Each needs its own decision |

## Requirements revised

Each story amends the rows it changes, in its own change:
- **PRD-Tool-Catalog "Isolated browser executor":** BX-01 gains the stealth image and its process cap (Z2, Z4). BX-03 gains the challenge hosts (Z7). BX-05 gains the stealth browser's own qualification (Z6).
- **"Autonomous browsing":** AB-02 gains the Expert's browser and `stealth_browser_unqualified` (Z1, Z6). AB-03 gains the changed user agent (Z13). AB-04's rule holds for `box`, and for `stealth` as Z8 to Z10. AB-01 gains the element record (Z11).
- **PRD-Studio:** the Expert card and editor show the browser (Z1), and the run's tool row shows what each step pressed or typed into (Z11).
- **Decision 0035:** Y10 holds for `box`. For `stealth` it holds as Z3, Z8, Z9 and Z10. Y11's highlights stay on for `box`.
- **Decision 0018:** B1 gains the stealth image, and B2 its process cap.

## What this gives up

- **No GPU.** A container on a Mac has none, and SwiftShader says so. Strict sites may still refuse it.
- **A second browser to keep patched.** Chrome's download address drops old versions, so a build must move with it and qualify again.
- **Cookies.** Every call is a new visitor.
- **The scoreboard first.** The plan built only what a score showed was needed. This builds first.
- **A bot check on an unused form** still ends the call, unless it is Turnstile's.

## What this doesn't establish

That any site opens. The checks use fixtures, scripted models and Decision 0018's qualification hosts, and no real bot check is met. A site opening is not permission from that site. Nothing here establishes H1 or product acceptance.

## Reversal

Set every Expert back to `box`, or remove the stealth image, which refuses a call of any Expert still set to `stealth`.
