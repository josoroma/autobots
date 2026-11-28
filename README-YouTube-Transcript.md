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

The Transcript reader turns a YouTube watch address into `transcript.md`, the video's captions as polished prose, and `transcript-timed.md`, every caption line with its timestamp ([Decision 0040](docs/engineering/decisions/0040-polished-transcript.md)). It is an Expert and a workflow seeded by [US-17.5](SPECS.md). It runs on browser-use in Autobots' isolated browser box (US-17.3), which presses buttons and returns a typed result (US-17.4). [Decision 0035](docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md) sets its rules.

This page records the first live run, on the owner's install on 2026-11-20. That run didn't get a transcript. YouTube answered the box's browser with Google's "unusual traffic" check. The Transcript reader stopped there, as it should, and published nothing. [A second run](#a-second-run-on-2026-11-25) read the page and published nothing either, which is why `browse_goal` now saves the file itself. [A third run](#a-third-run-on-2026-11-25) published the whole transcript, and [two more](#two-polished-runs-on-2026-11-26) polished it into prose. [Two local models](#two-local-models-on-2026-11-28) did the same on this Mac at US$0, once the browse task named YouTube's own page selectors and the local route sent one system message.

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
- [A third run, on 2026-11-25](#a-third-run-on-2026-11-25)
- [Two polished runs, on 2026-11-26](#two-polished-runs-on-2026-11-26)
- [Two local models, on 2026-11-28](#two-local-models-on-2026-11-28)
- [What this shows, and what it doesn't](#what-this-shows-and-what-it-doesnt)
- [Where it is defined](#where-it-is-defined)

## How it works

### The Expert

| | |
|---|---|
| **Name** | Transcript reader |
| **Tools** | `browse_goal` (version 4), `read_run_file`, `append_to_file`, `publish_artifact`. No `save_artifact`, so the model can't write a transcript whole |
| **Browse domains** | None when seeded. The owner adds `youtube.com`, `ytimg.com`, `ggpht.com` and `gstatic.com`, never `googlevideo.com`, the host that streams the video itself. Adding them is where the owner accepts YouTube's terms on automated access (Decision 0035 Y14) |
| **Model** | The run's `researcher` route drives each browse step through the admitted endpoint (Y7). The other roles follow the workspace policy. On Local, the browse steps reach the local model (Decision 0041 A10) |

Its instructions ask for five things:

1. **One browse.** One `browse_goal` call on the watch address, within those four hosts. It passes an output schema for the title and the lines, each with `time` and `text`. Its task is one python cell for browser-use's REPL: open the address, press the description's "Show transcript" button, wait for the panel, read each line's timestamp and text from YouTube's own selectors, and deliver the result from the REPL with `finish_from_repl`, never retyped. If that finds no lines, it presses "...more" and "Show transcript" and reads the panel. When YouTube renames those elements, only the fallback is left.
2. **A bot check.** If the browse stops with `bot_check`, say so and publish nothing. Never try to pass it.
3. **No transcript.** If no lines come back, say the video offers no transcript and publish nothing.
4. **The timed file.** The same `browse_goal` call carries a `save`, so the worker writes `transcript-timed.md` itself: the title as a heading, `Source:` and the address, a note that the lines are YouTube's own captions, then `time text` per line, in order ([Decision 0039](docs/engineering/decisions/0039-browse-result-saved-to-a-file.md)).
5. **The prose.** The model reads the timed file 60 lines at a time with `read_run_file`, and after each read adds the polished prose of those lines to `transcript.md` with `append_to_file`. The first section opens with the title, the source and a note that the text is edited from YouTube's own captions. Polishing keeps every point, example, number and name in the speaker's words and order, removes filler words, stutters and false starts, fixes punctuation and plainly misheard words, and breaks paragraphs where the topic turns. It never summarises, adds anything or guesses who is speaking. Then the timed file is published, and the prose last, so the run page shows the prose as its result. A 44-minute video takes about a dozen more model calls than the timed file alone, and a video over about three hours reaches a run's 64 model calls (Decision 0040 P4, P5, P7).

The seed keeps an Expert that exists, so a Transcript reader seeded earlier changes only when its owner saves a new version with these instructions.

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

[Decision 0039](docs/engineering/decisions/0039-browse-result-saved-to-a-file.md) has the worker save that result itself. How many lines this browse returned wasn't recorded.

## A third run, on 2026-11-25

After US-21.1, the install ran commit `dc75422`, and the owner saved Transcript reader version 3 with the new seeded instructions. Its browse domains and the box's browser were unchanged. The owner authorized one run on the same video, up to US$0.25 (execution `e6176aa7…`, step run `d6682abf…`):

| Time (UTC) | Event |
|---|---|
| 23:40:37 | Workflow **Transcript** version 1 started, and its agent step was delegated to the Transcript reader |
| 23:40:40 | The step proposed a one-task plan |
| 23:40:45 | `browse_goal` version 4 started without approval, under YOLO, on browser-use in the box, within `youtube.com, ytimg.com, ggpht.com, gstatic.com` |
| 23:41:33 | The browse ended `done` after 8 steps and 47.6 seconds, with no bot check. The worker saved `outputs/child-1/transcript.md`, with 320 items. The model saw the path and the count, and no line |
| 23:41:35 | `publish_artifact` published that file as `transcript.md`, 51,325 bytes |
| 23:41:37 | The task completed, and the step and the workflow succeeded |

**The file.** Its shape was checked without printing it:
- **The top.** It starts with the title as a heading, the source address and the note that the lines are YouTube's own captions.
- **The lines.** Then come 320 timed lines in order, from 0:00 to 44:11, the video's end. None is empty or repeated, and the longest gap between two timestamps is 12 seconds.
- **Not compared word for word** with YouTube's panel.

**Cost.** US$0.051799, against the US$0.25 budget.

## Two polished runs, on 2026-11-26

After US-22.1 the owner authorized a run that polishes the same 44-minute video into prose, up to US$0.75, and a second one to record it for a film. Both ran on the box's browser within the same four hosts, around 02:35 and 03:15 UTC.

| | Run 4 | Run 5 |
|---|---|---|
| **Install** | Commit `71a554b`, Transcript reader version 4 | Commit `0e76a90`, Transcript reader version 5 |
| **Execution** | `58e97526…` | `c776d40f…` |
| **Browse** | `done` in 12 steps, with no bot check. The worker saved 320 lines to `transcript-timed.md` | `done`, with no bot check. 320 lines saved |
| **Polishing** | Six reads of 60 lines with `read_run_file`, and after each an `append_to_file` call: `transcript.md` versions 1 to 6. No `save_artifact` | The same, six reads and six adds |
| **Published** | `transcript.md`, then `transcript-timed.md` | `transcript-timed.md`, then `transcript.md` |
| **Prose** | 8,068 words, 91 paragraphs | 8,049 words, 87 paragraphs |
| **Cost** | US$0.161306, in 31 model calls | US$0.155325 |

**What changed between them.** Run 4 published the prose first, so its run page showed the timed file as the Result, since the page shows the newest published file. Commit `0e76a90` changed the instructions to publish the timed file first. The owner saved them as version 5, with a Purpose that names both files, and run 5's Result is the prose. The step ran for about three and a half minutes.

**The prose.** It was checked without printing it:
- **The words.** Runs 4 and 5 kept 8,068 and 8,049 of the captions' 8,074 words. Nothing was summarised.
- **The numbers.** Every number in the captions is in the prose, 73 of them in run 4.
- **The layout.** No timestamps. The title and the source address are at the top, with the note that the text is edited from YouTube's own captions.
- **Not compared word for word.** The captions had almost no "um" or "uh" to remove, so most of the polishing is punctuation, capitals and paragraphs.

## Two local models, on 2026-11-28

The owner asked for the Transcript reader on a 12-minute video with both local models, one after the other, and for improvements where a run failed. The workspace was on the Local source (Decision 0041), at commit `38dbf78`. Each run chose its model in **Model for this run**, and llama-server served that model alone, by the [runbook's command](docs/engineering/runbooks/local-app.md). Every run used the box's browser within the same four hosts, at US$0.

| | Run | Result | Time | Browse | Model calls | Tokens in / out |
|---|---|---|---|---|---|---|
| **Inkling 2 Mini**, Transcript reader version 5 | `34e993b3…` | Failed, `plan_incomplete` | 7 min 44 s | 19 steps, then `max_seconds`, with nothing saved | 24 | 143,681 / 4,667 |
| **Inkling 2 Mini**, version 6 | `2998a5ae…` | **Succeeded** | 8 min 57 s | 3 steps in 72 s, 99 lines saved | 15 | 186,368 / 5,821 |
| **Bonsai 2.5**, version 6 | `53373dac…` | Failed, `provider_error` | 1 min 48 s | Refused before its first step | 5, three refused | 6,566 / 756 |
| **Bonsai 2.5**, version 6, one system message | `12127536…` | **Succeeded** | 10 min 4 s | 2 steps in 61 s, 99 lines saved | 14 | 155,342 / 4,767 |

**Why Inkling's first run failed.** browser-use 1.0.6 drives the page by having the model write Python in its REPL. Told only to press "...more" and "Show transcript" and read the panel, Inkling wrote a cell on each of 19 steps, and the screenshots show the same top of the watch page from step 3 to the end. No description opened and no panel appeared. The browse used its 300 seconds, so nothing was saved and the plan stayed incomplete.

**Version 6.** The owner's Transcript reader was saved as version 6, whose browse task is one python cell with YouTube's own selectors. The transcript button sits in `ytd-video-description-transcript-section-renderer`, and the panel's lines are `transcript-segment-view-model` elements in YouTube's current layout. They were read from the live page first: all 99 lines load at once, from 0:00 to 12:41. The seed now holds the same text (`TRANSCRIPT_TASK`).

**Why Bonsai's first run failed.** pydantic_ai 2.66, inside browser-use, sends each instruction part as its own system message. So every browse request opens with two. Bonsai 2.5's chat template refuses any system message after the first, and llama-server answered HTTP 500 three times. Inkling's template accepts two. The local route now joins leading system messages into one before the server sees them ([`local_server.py`](services/agent/src/autobots/adapters/models/local_server.py), `one_leading_system`). It changes nothing on OpenRouter.

**The files.** Both successful runs saved the same `transcript-timed.md`, byte for byte, with the title, the source, the captions note and 99 timed lines. The prose was checked without printing it:

| | Inkling 2 Mini | Bonsai 2.5 |
|---|---|---|
| **Words** | 2,384, in 19 paragraphs | 2,375, in 27 paragraphs |
| **Captions' words kept** | 2,278 of 2,364 | 2,278 of 2,364 |
| **Each tenth of the captions** | 94% to 99% of its words, in order | 95% to 99%, in order |
| **Sections** | Two `append_to_file` calls | Two, a short first one and the rest |

Neither has a timestamp or a repeated paragraph. Both start with the title, the source and the note that the text is edited from YouTube's own captions. Both corrected the captions' misheard "Quen 3.827B" to "Qwen 3.8 27B". One "3.87B" in the captions also left the prose, and which model the speaker meant there wasn't checked.

**What it doesn't show.** These are one run per model on one short video. They were Expert sessions, not the Transcript workflow, so they don't deliver US-23.6, whose live run, replays and example.com browse remain. The prose wasn't compared word for word with YouTube's panel. Inkling was quicker: it generates about 18 tokens a second here, and Bonsai about 12.

## What this shows, and what it doesn't

**It shows:**
- **The path.** An installed Autobots took a YouTube address through a published workflow with a pattern-checked input, to an Expert, to browse_goal version 3 on browser-use in the isolated box. That ran on the owner's real OpenRouter key and route, with no approval under YOLO.
- **The domains.** Only the Expert's four hosts were requested.
- **The bot check.** A real bot check stopped the browse at once, nothing was published, and the screenshots were kept.
- **A whole transcript.** In the third run the worker saved every caption line itself, and the model published the file without a line passing through it ([Decision 0039](docs/engineering/decisions/0039-browse-result-saved-to-a-file.md)).
- **Polished prose.** In runs 4 and 5 the model wrote the prose a section at a time with `append_to_file`, and kept all but 25 of the captions' words ([Decision 0040](docs/engineering/decisions/0040-polished-transcript.md)).
- **On this Mac.** Inkling 2 Mini and Bonsai 2.5 each browsed, saved and polished a transcript at US$0, with version 6's browse task ([Two local models](#two-local-models-on-2026-11-28)).

**It doesn't show:**
- **That it works every time.** YouTube refused the first run before any page loaded, and may refuse a later one. Runs 3 to 5 are successes on one video.
- **That the prose is faithful.** A model can drop or change a sentence. The timed file is published beside it, to check against.
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

- **The Expert and the workflow.** [`services/agent/src/autobots/operations/concept_seed.py`](services/agent/src/autobots/operations/concept_seed.py) holds `TRANSCRIPT_INSTRUCTIONS`, `TRANSCRIPT_TASK`, `TRANSCRIPT_SCHEMA` and `WATCH_ADDRESS`.
- **The input pattern.** [`services/agent/src/autobots/domain/workflows.py`](services/agent/src/autobots/domain/workflows.py) holds `InputConfig.pattern` and `input_pattern_mismatch`.
- **browse_goal on browser-use.**
  - [`application/browsing_tool.py`](services/agent/src/autobots/application/browsing_tool.py) holds versions 1 to 4, the engine, the limits and the saved file.
  - [`adapters/browser_use_box.py`](services/agent/src/autobots/adapters/browser_use_box.py) runs the browse and judges it.
  - [`adapters/browser_cdp.py`](services/agent/src/autobots/adapters/browser_cdp.py) holds the guard, with its submits and bot-check signals.
  - [`services/browser-use/`](services/browser-use) is the box's runner and lock.
- **The checks.** [`tests/db/checks/transcript_check.py`](tests/db/checks/transcript_check.py) covers the seed, the pattern, a long transcript saved with nothing retyped and polished in sections, the prose as the run's result, no transcript and a bot check. [`tests/db/checks/browser_use_check.py`](tests/db/checks/browser_use_check.py) is browser-use's qualification, run by `scripts/qualify_browser_executor.py`.
- **The specs.** [`openspec/specs/transcript-reader`](openspec/specs/transcript-reader/spec.md), [`openspec/specs/browser-use-typing`](openspec/specs/browser-use-typing/spec.md) and [`openspec/specs/browser-use-engine`](openspec/specs/browser-use-engine/spec.md).
