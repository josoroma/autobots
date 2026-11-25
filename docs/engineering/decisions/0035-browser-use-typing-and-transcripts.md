# Decision 0035: browser-use that presses, types and submits, and a YouTube transcript reader

**Date:** 2026-11-19. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **T1:** "we want this in yolo mode via a checkbox in settings, by default Typing and submitting in yolo mode."
- **T2:** "Yes, skip it", on whether YOLO also skips each browse call's approval.
- **T10:** "Yes, from the Expert", on who sets a browse's domains.
- **The request:** a Transcript reader built on browser-use, run on a YouTube video, then documented in a README and a film.

They delegated the rest, asking to "take senior decisions". Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse.

[The browser typing plan](../../plan/browser-typing-and-flights.md) holds the analysis and the probes behind each choice, and [the local small models plan](../../plan/local-small-models.md#9-browsing-with-browser-use-locally) the engine's shape (its D8 and D9). The owner can change any choice.

This amends:
- [Decision 0018](0018-browser-executor.md) B5 (read only) and B6 (approval on every call), while YOLO is on.
- [Decision 0020](0020-own-browsing-loop.md) L1, so that browser-use runs in the box beside Autobots' loop. L2 to L6 stand for the loop.
- [PRD-Tool-Catalog](../../PRD/PRD-Tool-Catalog.md#autonomous-browsing) "Autonomous browsing", "Isolated browser executor" and "Admitted browser model", as below.

It schedules EPIC-17.

## Decision

| # | Choice |
|---|---|
| **Y1. The setting** (T1, owner) | A workspace setting in Settings, "Let browsing type and submit (YOLO)". It is a checkbox, on by default, including for existing workspaces, with a one-time notice on Home (T3). Only the owner changes it |
| **Y2. No approval under YOLO** (T2, owner) | While YOLO is on, a `browse_goal` call starts without approval. With it off, every call waits for a person, as today (B6) |
| **Y3. Domains from the Expert** (T10, owner) | An Expert that grants `browse_goal` lists the domains it may browse. Under YOLO, a call naming any domain outside that list is refused before a container starts, and an Expert with no list can't browse |
| **Y4. Frozen, and off at once** (T5) | The setting is frozen at a run's admission. Turning it off applies at the next `browse_goal` call of any run, and turning it on applies to newly admitted runs |
| **Y5. Which engine** (T4, D8) | With YOLO off, browsing runs on Autobots' read-only loop (Decision 0020). With it on, it runs on browser-use in the isolated executor, which may press buttons, type and submit within the call's domains |
| **Y6. Model-written code** (D9) | browser-use 1.0 runs Python its model writes. That code runs only inside the isolated executor, which holds no key, cookie, host folder or credential. The egress proxy limits it to the call's domains, and Chromium's policy turns downloads off. The proxy doesn't filter methods, because it can't see inside TLS (T4) |
| **Y7. browser-use's model** (T11) | Every model call browser-use makes goes to an admitted endpoint the worker serves on the box's network only. Each call is admitted on the run's frozen `researcher` route like any other: reservation, invocation ticket, receipt, budget and `model_calls`. It runs on OpenRouter today, and needs no local route |
| **Y8. Its image** (T13) | Built from the pinned Playwright image (B1), with browser-use 1.0.6 in its own uv-locked environment under `services/browser-use/`. A container starts per call. The executor is qualified again for it |
| **Y9. Limits** (T7) | A browser-use call runs up to 600 seconds and 40 steps, by default 300 and 25. The box's cap (B2) rises to 600 seconds for those sessions only. Autobots' loop keeps 20 steps and 300 seconds |
| **Y10. Bot checks** (T12) | A bot check or CAPTCHA ends the call with the stop reason `bot_check`. Nothing solves it, hides from it or retries around it: no stealth settings, no other user agent, and no Browser Use Cloud or its solver |
| **Y11. What a person sees** (T15) | Each browser-use step keeps one screenshot with the run, in its private storage, shown in the run's tool row with each submit's domain and path. Typed values and queries are not recorded |
| **Y12. Typed results** (T6) | A call may name an output schema, and its result is validated against it. Declared link fields keep their query. Visited URLs stay bare |
| **Y13. Editable sites** (T14) | Allowed under YOLO. An Expert that browses a wiki or a forum says in its instructions never to edit or post |
| **Y14. The Transcript reader** (T16) | A seeded Expert and workflow. Given a YouTube watch address, it presses "...more" and "Show transcript", reads every line and publishes `transcript.md` with each line's timestamp. It is seeded with an empty domain list, so it can't browse until the owner adds YouTube's hosts. That is where the owner accepts YouTube's terms on automated access |

The flight-price items of the plan (T8, T9) are not scheduled here.

The backlog's ingestion left five points open. These are decided the same way, by delegation:

| # | Choice |
|---|---|
| **Y15. Approval and engine** | Whether a call waits for approval depends on YOLO alone (Y2, Y4). The engine is browser-use only while the call is YOLO and the browser-use image reports qualified. Otherwise the call runs on Autobots' loop, within the loop's own limits (20 steps, 300 seconds), and any higher limit it names is capped to them |
| **Y16. Text only** | browser-use runs with vision off and its judge off. No route is qualified for image input, so nothing sends a screenshot to a model. The step screenshots of Y11 are kept for people only. Bot checks are recognised in the box from the page itself, such as a CAPTCHA frame, a challenge page or a "sorry" address, not by a model |
| **Y17. A workflow input's pattern** | A workflow's `string` input may declare a pattern. An execution whose value doesn't match is refused before it starts, naming the input. The Transcript workflow's `video` input requires an https YouTube watch or youtu.be address. Inputs that declare no pattern are unchanged |
| **Y18. No real YouTube in checks** | Checks use scripted models and scripted browses, and reach only Decision 0018's qualification host. The owner's live run is the only one that loads YouTube |
| **Y19. Typed results** | An output schema is a JSON Schema object of at most 8 KB. It names its link fields in a top-level `x-link-fields` list |

## Requirements revised

Each story amends the rows it changes, in its own change:
- **PRD-Tool-Catalog "Autonomous browsing":** `browse_goal` may press, type and submit while the workspace's YOLO setting is on (Y1, Y5), so AB-01's read-only rule and AB-02's approval on every call hold only with YOLO off. Its `stopped` reasons gain `bot_check` (Y10), and its call may name an output schema (Y12, Y19). TC-02's approval policy gains "only with YOLO off".
- **"Isolated browser executor":** it gains the browser-use image (Y8) and the 600-second cap for its sessions (Y9). BX-03's refusal of request bodies holds only with YOLO off, since a YOLO browse may submit by `POST` within its domains.
- **"Admitted browser model":** it gains the admitted endpoint (Y7). BM-01 to BM-04 then describe both engines.
- **PRD-Studio:** SE-02 gains Settings → Browsing, Home gains the one-time notice (Y1), and the seed (SD-01, SD-02) gains the Transcript reader and its workflow (Y14).
- **Decision 0018:** B5 and B6 hold only while YOLO is off.

## What this gives up

- **The default asks nothing.** A browse starts, types and submits without a person, within the Expert's domains. A page's text can steer the model within them.
- **Model-written code runs in the box.** The box's isolation and the domain list are the guards, not the model.
- **YouTube's terms forbid automated access** without YouTube's permission. The Transcript reader's empty seed leaves that choice to the owner, per workspace (Y14).
- **Another creator's transcript is their work.** Autobots keeps it as a private artifact of the run, and anything published from it summarises or quotes briefly.

## What this doesn't establish

That browser-use works reliably. Each story's checks use scripted models, and one live run is a separate step the owner starts and caps. Nothing here establishes H1 or product acceptance.

## Reversal

Uncheck the setting, which returns browsing to the read-only loop with approval on every call. Or remove the browser-use image, which leaves `browse_goal` on Autobots' loop.

## Amended

[Decision 0038](0038-local-stealth-browser.md) amends Y10 and Y11 for an Expert set to the `stealth` browser: its Z3 and Z8 to Z11. For `box`, the default, both stand as written. Its Z13 enforces Y10's "no other user agent" on both.
