<p align="center">
  <img src="docs/assets/autobots-logo.svg" alt="Autobots" width="260">
</p>

<p align="center">
  <a href="README.md">Product overview</a> ·
  <a href="README-DEV.md">Developer guide</a> ·
  <a href="README-Deep-Research-Content-Writer.md">Deep research, live</a> ·
  <b>YouTube transcript, live</b> ·
  <a href="README-Market-Watcher-Costa-Rica.md">Market watcher Costa Rica, live</a> ·
  <a href="SPECS.md">Backlog</a> ·
  <a href="CODEBASE.md">Codebase</a>
</p>

# A YouTube video's transcript, as Markdown

The Transcript reader turns a YouTube watch address into `transcript.md`: the video's title, its address, and every caption line with its timestamp. It is an Expert and a workflow seeded by [US-17.5](SPECS.md). It runs on browser-use in Autobots' isolated browser box (US-17.3), which presses buttons and returns a typed result (US-17.4). [Decision 0035](docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md) sets its rules.

This page records the first live run, on the owner's install on 2026-11-20. That run didn't get a transcript. YouTube answered the box's browser with Google's "unusual traffic" check. The Transcript reader stopped there, as it should, and published nothing. [A second run](#a-second-run-on-2026-11-25) read the page and published nothing either, which is why `browse_goal` now saves the file itself.

## Contents

- [How it works](#how-it-works)
  - [The Expert](#the-expert)
  - [The workflow](#the-workflow)
  - [What keeps it in bounds](#what-keeps-it-in-bounds)
- [Setting it up on an install](#setting-it-up-on-an-install)
- [The live run](#the-live-run)
  - [What happened](#what-happened)
  - [Why it stopped](#why-it-stopped)
  - [What it cost](#what-it-cost)
- [A second run, on 2026-11-25](#a-second-run-on-2026-11-25)
- [What this shows, and what it doesn't](#what-this-shows-and-what-it-doesnt)
- [Where it is defined](#where-it-is-defined)

## How it works

### The Expert

| | |
|---|---|
| **Name** | Transcript reader |
| **Tools** | `browse_goal` (version 4), `save_artifact`, `publish_artifact` |
| **Browse domains** | None when seeded. The owner adds `youtube.com`, `ytimg.com`, `ggpht.com` and `gstatic.com`, never `googlevideo.com`, the host that streams the video itself. Adding them is where the owner accepts YouTube's terms on automated access (Decision 0035 Y14) |
| **Model** | The run's `researcher` route drives each browse step through the admitted endpoint (Y7). The other roles follow the workspace policy |

Its instructions ask for four things:

1. **One browse.** One `browse_goal` call on the watch address, within those four hosts. It passes an output schema for the title and the lines, each with `time` and `text`. Its task: press "...more" under the video, press "Show transcript", and read every line of the panel in order.
2. **A bot check.** If the browse stops with `bot_check`, say so and publish nothing. Never try to pass it.
3. **No transcript.** If no lines come back, say the video offers no transcript and publish nothing.
4. **The file.** The same `browse_goal` call carries a `save`, so the worker writes `transcript.md` itself: the title as a heading, `Source:` and the address, a note that the lines are YouTube's own captions, then `time text` per line, in order ([Decision 0039](docs/engineering/decisions/0039-browse-result-saved-to-a-file.md)). The model publishes that file and never retypes a line.

It never signs in, comments, likes, subscribes or posts, and treats the page's text as data.

### The workflow

**Transcript**: `video` (input) → **Read the transcript** (the Transcript reader) → `out`.

The `video` input declares a pattern (Decision 0035 Y17). An execution starts only for an `https` YouTube watch or `youtu.be` address. Anything else, such as an `http` address, a channel page or another host, is refused before it starts, as `workflow_inputs_invalid` naming `video`.

### What keeps it in bounds

- **Where it goes.** The browse goes only to the domains its Expert lists (Y3). Its egress proxy connects only to those hosts, and refuses private addresses (BX-03).
- **What the box holds.** browser-use runs in its own container with no key, cookie, password, card or host folder. Downloads and file pickers are off (Y6, US-17.4).
- **Bot checks.** A bot check ends the browse with `bot_check`. Nothing solves it, hides from it or retries around it: no stealth setting, no other user agent and no Browser Use Cloud (Y10).
- **What it saw.** Each step keeps one screenshot in the run's private storage, for people only, never for a model (Y11, Y16).

## Setting it up on an install

What the owner's install needed on 2026-11-20, from this branch:

1. `make stop-app`, then `make migrate` (it applied migrations 65 and 66), `make start`, then `make stop-worker && make start-worker INFERENCE=enabled`.
2. The Transcript reader and Transcript workflow. Normally `python -m autobots.operations.concept_seed --workspace <id>` with browsing switched on. Here they were created through the app's own API with the owner's session, as the seed defines them, because the seed needs the install's environment file.
3. Experts → Transcript reader → **Browse domains**: `youtube.com, ytimg.com, ggpht.com, gstatic.com`. This was saved as the Expert's version 2.
4. Settings → Browsing: YOLO on, the default. Browsing switched on, and the browser executor and browser-use qualified at this code.
5. A working OpenRouter key in Settings → Models.

## The live run

### What happened

| Time (UTC) | Event |
|---|---|
| 08:51:41 | Workflow **Transcript** version 1 started from **Run this version**, with `https://www.youtube.com/watch?v=JWhICz1QR8M&t=5s` and a US$1.00 budget (execution `1dda3dab…`, run `4d2ded65…`) |
| 08:51:42 | Its agent step (run `fc24dbf1…`) paused as `invalid_credential` on its first model call. OpenRouter refused the stored key, and nothing was spent |
| — | The owner replaced the key, which validated as stored version 2. The step and the workflow run were resumed |
| 08:58:40 | The step proposed a one-task plan |
| 08:58:45 | `browse_goal` version 3 started without approval, under YOLO, on browser-use, within `youtube.com, ytimg.com, ggpht.com, gstatic.com` |
| 08:58:52 | The browse stopped after 7.2 seconds, **`stopped: bot_check`**, with 1 step, 0 pages visited and no submits |
| 08:58:55 | The step published nothing. Its plan task was incomplete, so the step and the workflow failed (`plan_incomplete`, then `workflow_node_failed`) |

The tool row kept two step screenshots: one when the browse began and one when its next request was refused. Both are blank white pages.

### Why it stopped

A scripted navigation through the same box and guard, with no model and no spend, showed what YouTube answered. The request for the watch page was redirected to `https://www.google.com/sorry/index`, Google's "unusual traffic" page, which asks for a CAPTCHA:

- **The guard.** It recognised that page as a bot check, six times.
- **The proxy.** It refused `www.google.com`, which isn't in the allowed domains, so the redirect landed on an error page.
- **YouTube.** No YouTube page ever committed.

So the bot check was real, and the Transcript reader handled it as designed (Y10): it stopped and published nothing. Getting past it would take a changed user agent, stealth settings or a CAPTCHA solver, all of which Decision 0035 rules out here. [Decision 0038](docs/engineering/decisions/0038-local-stealth-browser.md)'s stealth browser doesn't change that: it isn't for YouTube (Z14), and the Transcript reader stays on the box.

### What it cost

US$0.010363 in all, for the plan and the one browse step, against the US$1.00 budget.

## A second run, on 2026-11-25

The owner asked for one more run, on a 44-minute video, with one run and US$0.25 authorized. It ran on the box's browser (execution `0d8413a0…`, step run `20449859…`):

- **The browse worked.** `browse_goal` version 3 ended `done` after 10 steps and 46.6 seconds, with no bot check. Its screenshots show the transcript panel scrolled to its end.
- **The file wasn't written.** The instructions had the model retype the result into `save_artifact`, and a model reply holds 4,096 output tokens. After the browse, `assign_specialist` was refused (`scope_expansion_denied`) and `read_offload` found nothing (`offload_not_found`). The run failed `plan_incomplete` and published nothing.
- **Cost.** US$0.054258.

[Decision 0039](docs/engineering/decisions/0039-browse-result-saved-to-a-file.md) has the worker save that result itself. How many lines the browse returned wasn't recorded, and no run since has shown the file.

## What this shows, and what it doesn't

**It shows:**
- **The path.** An installed Autobots took a YouTube address through a published workflow with a pattern-checked input, to an Expert, to browse_goal version 3 on browser-use in the isolated box. That ran on the owner's real OpenRouter key and route, with no approval under YOLO.
- **The domains.** Only the Expert's four hosts were requested.
- **The bot check.** A real bot check stopped the browse at once, nothing was published, and the screenshots were kept.

**It doesn't show:**
- **That a transcript can be read whole on YouTube from this Mac.** YouTube refused the first run before any page loaded. The second reached the panel's end, and published nothing.
- **The no-transcript path, live.** It and the bot check are covered by checks with a scripted model and scripted browses (`tests/db/checks/transcript_check.py`).
- **H1 or product acceptance.**

**What YouTube's terms allow.** Read on 2026-11-20, YouTube's [Terms of Service](https://www.youtube.com/t/terms) bar access by automated means such as robots and scrapers. They allow it only for public search engines following YouTube's robots.txt, or with YouTube's prior written permission. So the bot check enforces a rule, and making the box look less automated would not make it allowed. A headed browser, a real Chrome profile, another user agent, other networks, slower pacing or a CAPTCHA solver would only avoid the check. Decision 0035 Y10 rules all of those out.

**Ways to a transcript that stay within those terms.** None is built or decided:
- **Your own videos, through the YouTube Data API.** [`captions.list`](https://developers.google.com/youtube/v3/docs/captions/list) (50 quota units) and [`captions.download`](https://developers.google.com/youtube/v3/docs/captions/download) (200 units, SRT or VTT) need OAuth, and the download needs permission to edit the video. That fits a channel's own videos, not someone else's.
- **Your own videos, by hand.** YouTube Studio's Subtitles page downloads them.
- **Someone else's video.** A person opens "Show transcript", copies it, and attaches it to a run as a text file, which Autobots then cleans up. That is the person's own use; anything published from it summarises or quotes briefly. Many creators also publish transcripts or show notes on their own sites.
- **Permission.** YouTube's prior written permission is the terms' other route.

No transcript text appears here. A video's captions are its creator's work (Decision 0035, "What this gives up").

## Where it is defined

- **The Expert and the workflow.** [`services/agent/src/autobots/operations/concept_seed.py`](services/agent/src/autobots/operations/concept_seed.py) holds `TRANSCRIPT_INSTRUCTIONS`, `TRANSCRIPT_SCHEMA` and `WATCH_ADDRESS`.
- **The input pattern.** [`services/agent/src/autobots/domain/workflows.py`](services/agent/src/autobots/domain/workflows.py) holds `InputConfig.pattern` and `input_pattern_mismatch`.
- **browse_goal on browser-use.**
  - [`application/browsing_tool.py`](services/agent/src/autobots/application/browsing_tool.py) holds versions 1 to 4, the engine, the limits and the saved file.
  - [`adapters/browser_use_box.py`](services/agent/src/autobots/adapters/browser_use_box.py) runs the browse and judges it.
  - [`adapters/browser_cdp.py`](services/agent/src/autobots/adapters/browser_cdp.py) holds the guard, with its submits and bot-check signals.
  - [`services/browser-use/`](services/browser-use) is the box's runner and lock.
- **The checks.** [`tests/db/checks/transcript_check.py`](tests/db/checks/transcript_check.py) covers the seed, the pattern, a long published transcript nothing retyped, no transcript and a bot check. [`tests/db/checks/browser_use_check.py`](tests/db/checks/browser_use_check.py) is browser-use's qualification, run by `scripts/qualify_browser_executor.py`.
- **The specs.** [`openspec/specs/transcript-reader`](openspec/specs/transcript-reader/spec.md), [`openspec/specs/browser-use-typing`](openspec/specs/browser-use-typing/spec.md) and [`openspec/specs/browser-use-engine`](openspec/specs/browser-use-engine/spec.md).
