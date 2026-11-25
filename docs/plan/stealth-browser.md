# Plan: local stealth browsing on browser-use

**Date:** 2026-11-25. **Status:** approved by the owner as [Decision 0038](../engineering/decisions/0038-local-stealth-browser.md), which supersedes it as a source and schedules EPIC-20. Kept as the reasoning behind it. The owner asked for something like [Tilion](https://tilion.com/) "using browser-use", and then made the scope clear: **"the idea is to use browser-use local with stealth capabilities"**. So no cloud browser, proxy service or CAPTCHA solver is in this plan. [Section 8](#8-decisions-the-owner-makes) lists what only the owner could decide, and [section 9](#9-draft-stories-in-specs-style) holds the draft stories.

## Contents

1. [Recommendation](#1-recommendation)
2. [What gives the box away today](#2-what-gives-the-box-away-today)
3. [What a local browser can be](#3-what-a-local-browser-can-be)
4. [The shape](#4-the-shape)
5. [What each change does](#5-what-each-change-does)
6. [What stays, and what changes](#6-what-stays-and-what-changes)
7. [Build order](#7-build-order)
8. [Decisions the owner makes](#8-decisions-the-owner-makes)
9. [Draft stories in SPECS style](#9-draft-stories-in-specs-style)
10. [Risks](#10-risks)
11. [Not verified](#11-not-verified)
12. [Sources consulted](#12-sources-consulted)

## 1. Recommendation

**Run real Google Chrome, headed, in the same isolated box, still driven by browser-use 1.0.6 over CDP, from the owner's own connection.** Fix the things Autobots itself does that give it away. Add a patched Chromium only if a measurement shows it opens sites real Chrome doesn't.

Three reasons:
- **It's what measured best.** An [independent benchmark](https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/) ran 7 tools against 31 sites, headed, from one home connection. The best was real Google Chrome over raw CDP: 28 opened, 0 blocked. The patched Chromium it tested had 26 and 2. browser-use 1.0 is also raw CDP.
- **It's true.** The browser says what it is, so nothing has to stay consistent with a made-up device.
- **It costs nothing,** and pages go only to this Mac. Google ships Chrome for Linux arm64, so it runs natively in the box.

**browser-use itself has no local stealth.** In 1.0.6 the only mention is that its cloud browsers "run with stealth settings" (checked in the box's image). So the stealth has to come from the Chrome it drives.

**Not a separate tool.** It's the same `browse_goal`, with a browser the owner picks on the Expert. The model never picks it, as it never picks the domains (Y3).

## 2. What gives the box away today

Measured on 2026-11-25 in `autobots-browser:local`, with the box's hardening and caps, no network, and a page on `127.0.0.1` inside the container:

| What a site reads | Today, headless | Same Chromium, headed under Xvfb |
|---|---|---|
| User agent, in every request | `HeadlessChrome/156` | `Chrome/156` |
| Screen and window | 800×600, 780×580 | 1440×900, 1439×899 |
| Time zone | `UTC` | `America/Costa_Rica` (set) |
| Languages sent | `en-US,en` | `es-CR,es` (set) |
| WebGL | None | None by default, SwiftShader when turned on |
| Brands (`Sec-CH-UA`) | `Chromium`, without `Google Chrome` | The same |
| Speech voices | 0 | 0 |
| `navigator.webdriver` | `false` | `false` |

So **headed Chromium runs inside the box's present limits**, and clears the loudest marker. Real Google Chrome should add its own brand. No GPU is the marker that stays in any container on a Mac.

**Three more are Autobots' own rules:**
- **The allow list blocks the check itself.** A site's silent check loads from hosts such as `challenges.cloudflare.com`. The egress proxy refuses any host that isn't listed, so the check can't finish.
- **Any embedded challenge frame ends the call.** `bot_check_host` in [`browser_cdp.py`](../../services/agent/src/autobots/adapters/browser_cdp.py) counts every document frame from `challenges.cloudflare.com`, including a widget on a form the task doesn't use, and it stops at first sight.
- **browser-use's highlights are drawn on the page** and kept on for the step screenshots (Y11).

**One suspected cause is weaker than its reputation.** `Runtime.enable`, a well-known sign of CDP, is sent by browser-use's harness, which enables Page, DOM, Runtime and Network on each tab (this plan first said it isn't, from a text search that missed a command built at run time). The worker never sends it. Measured on Chrome 158 on 2026-11-25, the classic check, a getter on an error's `stack`, sees nothing. Two subtler ones differ: a trap on an error's prototype (1 read becomes 3), and the time `console.debug` takes (9 ms becomes about 120 ms for 2,000 calls).

**What sites answered earlier:** the box got Google's "sorry" page on YouTube on 2026-11-20. The day before, outside the box on the same Mac, headless Chromium opened the same kind of page. A US State Department page gave 403, Google Flights a reCAPTCHA and Costa Rica's central bank a 503 ([plan 7.1](browser-typing-and-flights.md#71-what-sites-allow-an-automated-browser)). That suggests the box matters, and doesn't prove which marker.

## 3. What a local browser can be

| | Local evidence | Runs in the box | Keeps BX-01 to BX-05 | Verdict |
|---|---|---|---|---|
| **A. Google Chrome stable, headed** | Best of 7, on a Mac, not in a container | Yes: official arm64 `.deb`, 158.0.8127.88 on 2026-11-25 | Yes | **Build** |
| **B. The box's Chromium, headed** | Bundled Chromium was near the bottom (24 opened, 5 blocked, through Playwright) | Yes, measured above | Yes | **Fallback for A** |
| **C. Fortress** (Tilion's Chromium, local) | Vendor's own: 86.4% of 92 sites, headless from a datacenter | Probably: a `linux-arm64` tarball exists, its Docker images are Intel only | Yes, with a license key in the browser container | **Measure only** |
| **D. CloakBrowser** | 26 opened, 2 blocked, same benchmark | arm64 build exists | **No.** Each launch calls `cloakbrowser.dev`, and the binary downloads at first start | **Rejected** |
| **E. Camoufox** | 25 opened, 3 blocked | Unchecked | Not applicable | **Rejected:** Firefox through Playwright's own protocol, so browser-use can't drive it |
| **F. Patchright, nodriver** | 25 and 28 opened | Not applicable | Not applicable | **Rejected:** they replace the driver, and the driver is browser-use. nodriver's result is A's |
| **G. Chrome on the Mac itself**, throwaway profile | What the benchmark ran: a real GPU and a real Mac | No | **No.** Model-written code would drive a browser outside the container | **Only by its own decision**, if A fails on a site that matters |

On **C**: its default persona claims Windows while the network layer stays Linux's, which its own README notes. It's a closed binary under a license that says it's "not an open-source license", free for an individual. Without a key it falls back to an older engine. Its newest release is 156, see the next point.

**Patched Chromiums lag on security.** CVE-2026-125350, exploited in the wild and in [CISA's catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) since 2026-11-10, is fixed in 157.0.8103.50. Fortress's and CloakBrowser's newest builds are 156.0.8078.47. **The box's own Chromium is 156.0.8078.80, so it's affected too,** and it runs with Chromium's own sandbox off. That needs fixing whatever is decided here, and A fixes it.

## 4. The shape

```text
Expert (owner sets): browse domains + browser = box | stealth
        │
browse_goal v3   same inputs, approval, YOLO, limits, typed result, screenshots
        │
        ▼
browser-use container ──CDP──► browser container ──► egress proxy ──► the Expert's domains
 (unchanged)                    box:     headless Chromium (default, as today)
        │                       stealth: Xvfb + Google Chrome, headed
        └─► model relay ─► admitted endpoint (unchanged)
```

- **Only the browser container changes.** [`runner.py`](../../services/browser-use/runner.py) already attaches by `cdp_url`. The egress proxy, the request guard, the relay, the caps and the cleanup are the same code.
- **A second image**, `autobots-browser-stealth`, from the same pinned base plus Chrome's `.deb`, fetched at build time by exact version and SHA-256. Its policy file goes to `/etc/opt/chrome/policies/managed/`, since real Chrome doesn't read the one for Chrome for Testing.
- **Its own qualification.** The same BX-05 refusals, on its own fingerprint, like browser-use's. Not qualified means not offered, and a call never falls back to another browser.

## 5. What each change does

| # | Change | Removes | Pretends anything? |
|---|---|---|---|
| **1** | Headed Chrome under Xvfb | `HeadlessChrome`, 800×600 | No |
| **2** | Google Chrome, not Chromium | Missing brand | No |
| **3** | The workspace's time zone and languages | `UTC` and `en-US` from a Costa Rican address | No, they are the owner's |
| **4** | Software WebGL on, not absent | "No WebGL at all" | No. It still reads SwiftShader |
| **5** | Fonts with normal coverage, and the emoji font | A bare font list | No |
| **6** | Challenge hosts may load as frames and scripts, never as a page to visit | Checks that can't finish | No |
| **7** | A check gets 20 seconds to clear by itself. Nothing clicks it, and no model step runs | Giving up at first sight | No |
| **8** | A challenge frame ends the call only when it is the page, not a widget on it | False `bot_check` | No |
| **9** | browser-use's highlights off in stealth, with the pressed element recorded instead | Marks drawn on the page | No |
| **10** | A short pause between steps on one site, and one browse of a site at a time | Machine pace | No |
| **11** | A kept profile for each Expert and site, with its cookies and no sign-in | A brand-new visitor every time | No, but see W4 |
| **12** | A patched engine (C) with an invented device | No GPU, other markers | **Yes** |

1 to 10 make the box an ordinary browser. 11 changes a rule about what the box keeps. 12 is the only one that invents a device, so it has its own decision (W5).

## 6. What stays, and what changes

| Rule | With this plan |
|---|---|
| Expert's domains (Y3), YOLO (Y1, Y2), model-written code only in the box (Y6), admitted model calls (Y7), limits (Y9), typed results (Y12), no image to a model (Y16) | Unchanged |
| Egress proxy, private-address refusals, caps, cleanup (BX-01 to BX-04) | Unchanged, except W2's challenge hosts, and the memory cap if Chrome needs more |
| No CAPTCHA solver, no Browser Use Cloud | Unchanged |
| **Y10** and **AB-04**: "no stealth settings, no other user agent", and stop at a check | **Amended**, for Experts set to `stealth` only |
| **B1**: the Playwright image's Chromium | **Amended**: Google Chrome in a second image |
| **Y11**: highlights stay on for the screenshots | **Amended** for `stealth` (change 9) |
| OpenRouter-only inference | Unchanged |

**An existing gap:** Y10 says no other user agent, but browser-use's own help says its agent "can send `Emulation.setUserAgentOverride`", and the guard doesn't refuse it. The stealth story closes that for both browsers, since a user agent the model made up is a new marker.

**Sites whose terms bar automation stay out.** No browser changes what a site allows. YouTube's terms bar it ([README-YouTube-Transcript](../../README-YouTube-Transcript.md)), and Google Flights stays on SerpApi ([browser typing plan](browser-typing-and-flights.md#6-engine-a-a-google_flights-tool-through-serpapi)).

## 7. Build order

1. **Scoreboard.** A disposable script, with no model and no product change. It opens each owner-listed site once in today's box, B, A, and C if W5 says so, and records `opened`, `check` or `blocked`. It adds changes 1 to 8 one at a time on a site that blocks, to see which one matters. **Gate:** a change that opens nothing new isn't built.
2. **Stealth image** (changes 1 to 5), with its qualification: US-20.1.
3. **Checks that clear** (changes 6 to 8): US-20.2.
4. **How it behaves on the page** (changes 9 and 10): US-20.3.
5. Only by their own decisions, if the scoreboard still shows blocked sites the owner wants: 11, 12, then G.

## 8. Decisions the owner makes

| # | Question | Recommended |
|---|---|---|
| **W1** | Amend Y10 so an Expert may use a local stealth browser? Nothing starts without this | Yes, per Expert, off by default |
| **W2** | May challenge hosts load for a listed site, as frames and scripts only? | Yes, a fixed short list in code |
| **W3** | Which sites go on the scoreboard? Each needs the owner's reading of its terms, as Y14 did for YouTube | 5 to 10, named by the owner. No YouTube, no Google |
| **W4** | May the box keep cookies between browses (change 11)? | Not yet. Measure 1 to 10 first |
| **W5** | Put Fortress on the scoreboard? It needs a license key from an account the owner creates, and a 257 MB download | Yes, scoreboard only, in a disposable container |
| **W6** | Download Google Chrome for the image: `google-chrome-stable_158.0.8127.88-1_arm64.deb` from `dl.google.com`, 142 MB? Building the image accepts Google's terms for Chrome | Yes, or the current version when it is built |

## 9. Draft stories in SPECS style

Draft IDs, assigned at ingestion. Each is `BLOCKED` until W1, and the decision that answers it becomes its source. All are checked with local fixture pages and scripted models, reaching only Decision 0018's qualification host. The scoreboard on real sites is the owner's to start.

### US-20.1: A stealth browser in the box

As a workspace owner
I want an Expert to browse with real, headed Google Chrome in the isolated box
So that sites that turn away a headless browser open, and nothing leaves this Mac but the pages I allowed.

```gherkin
Scenario: It looks like the browser it is
  Given an Expert set to the stealth browser, and its image with no outside network
  When a page reads the user agent, brands, window, time zone, languages and WebGL
  Then there is no "Headless" in any, the brands name Google Chrome, the window is a desktop size, the time zone and languages are the workspace's, and WebGL is present

Scenario: The box still holds
  Given the executor's qualification on a disposable stack with the stealth image
  When every refusal BX-05 lists is exercised, and the container is inspected
  Then each is observed, it holds no key, cookie, host folder or credential, and the stealth browser reports qualified only then

Scenario: The owner chooses, not the model
  Given an Expert set to the box browser, and a task that asks for another one
  When it browses
  Then it runs on the box browser, and no input of browse_goal names a browser

Scenario: No quiet fallback
  Given an Expert set to the stealth browser whose image doesn't report qualified
  When a run calls browse_goal
  Then the call is refused with stealth_browser_unqualified before any container starts

Scenario: The model can't change what the browser says
  Given a browse on either browser
  When model-written code sends a user agent override over CDP
  Then the next request still carries the browser's own user agent
```

Dependencies: US-17.4.

### US-20.2: A check that clears by itself

As a workspace owner
I want a check that needs no person to finish
So that a page isn't given up because Autobots blocked or misread the check.

```gherkin
Scenario: A widget the task doesn't use
  Given a page whose content loads and which embeds a challenge frame on an unused form
  When a stealth browse reads the page
  Then the call continues

Scenario: A check that clears
  Given a challenge page that clears by itself within 20 seconds
  When a stealth browse meets it
  Then nothing clicks it, no model call is made meanwhile, and the browse continues

Scenario: A check that stays
  Given a challenge page that doesn't clear within 20 seconds
  When a stealth browse meets it
  Then the call stops with bot_check, and nothing solved or retried it

Scenario: Challenge hosts only as parts of a page
  Given W2's hosts and a stealth browse
  When the page loads a challenge frame, and then the model goes to that host as a page
  Then the frame loads, and the navigation ends the call with refused_action

Scenario: The box browser is unchanged
  Given an Expert set to the box browser
  When it meets the same pages
  Then it stops with bot_check at first sight, and challenge hosts stay refused
```

Dependencies: US-20.1.

### US-20.3: Quiet on the page

As a workspace owner
I want a stealth browse to leave no marks on the page and keep a person's pace
So that the page it reads is the page a visitor gets, and the record still shows what it did.

```gherkin
Scenario: No marks, same record
  Given a stealth browse that presses and types
  When it finishes
  Then the page's document gained no node from browser-use, and each step's record names the element it pressed or typed into, without the typed value

Scenario: One browse of a site at a time
  Given a stealth browse on a domain
  When another run starts one on the same domain
  Then the second waits for the first within its own time limit, or ends with max_seconds
```

Dependencies: US-20.1.

## 10. Risks

- **It may still be blocked.** The benchmark's Chrome had a real GPU on macOS. In a container there is none, and that may decide it on strict sites. G is the only full answer, and it costs the isolation.
- **The home address.** Every browse comes from the owner's connection. Too many, and the address itself gets flagged, also for the owner's own browsing. Change 10 limits that.
- **Upkeep.** Chrome's download address serves the newest version and old ones may disappear, so the build must move with it and qualify again each time. That is also what keeps it patched.
- **Memory.** Headed Chrome ran in 1 GiB on an empty page. Heavy pages may not.
- **YOLO is on by default** (Y1). A browser that opens more sites lets a page steer the model on more sites, so a stealth Expert's domain list matters more.

## 11. Not verified

- No real site was opened, and no stealth browser was downloaded or run.
- That Google Chrome's arm64 build starts under the box's hardening. The box's Chromium does.
- Which marker causes any given block. The scoreboard tests it.
- The benchmark is one person's, on one home address, one night in May 2026, on macOS.
- Fortress's `linux-arm64` build in the box, and what it claims about a GPU there.

## 12. Sources consulted

Read on 2026-11-25.
- [Anti-detect browser benchmark, 7 tools, 651 verdicts](https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/).
- Chrome on arm64 Linux: [Google](https://blog.google/chromium/bringing-chrome-to-arm64-linux-devices/), [Arm's install guide](https://learn.arm.com/install-guides/browsers/chrome/), and Google's own package index for the version.
- browser-use: [browsers in 1.0](https://docs.browser-use.com/open-source/browsers.md), and version 1.0.6's source in the box's image.
- Fortress: [repository](https://github.com/tiliondev/fortress), [license](https://github.com/tiliondev/fortress/blob/main/LICENSE), [releases](https://github.com/tiliondev/fortress/releases).
- CloakBrowser: [repository](https://github.com/CloakHQ/CloakBrowser), [binary license](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md), [issue 653](https://github.com/CloakHQ/CloakBrowser/issues/653).
- [Camoufox](https://camoufox.com/).
- CVE-2026-125350: CISA's catalog, version 2026.11.25.
