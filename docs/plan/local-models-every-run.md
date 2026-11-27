# Plan: every live run on a local model, chosen in Settings

**Date:** 2026-11-27. **Status:** decided the same day as [Decision 0041](../engineering/decisions/0041-local-model-source.md), which records [section 10](#10-decisions-the-owner-makes)'s answers. Nothing is implemented, downloaded or measured yet. The stories wait for P0's measurements.

The aim is to repeat the three live runs on a model served on this Mac, with no OpenRouter call:
- the deep research content writer;
- the Market watcher Costa Rica;
- the YouTube transcript, polished.

One setting in **Settings → Models** chooses where every model call goes: **OpenRouter**, as today, or **Local**. The two candidates are [Inkling 2 Mini](https://huggingface.co/thinkingmachines/Inkling-2-Mini) and [Ternary Bonsai 2.5 27B](https://prismml.com/news/bonsai-2-5-27b).

This builds on [the local small models plan](local-small-models.md) of 2026-11-19. That plan designed the same setting for the deep research run alone. Its rules for the setting ([7.1](local-small-models.md#71-the-model-source-setting)), its map of code changes ([7.2](local-small-models.md#72-where-code-changes)), its fixes for long runs ([8](local-small-models.md#8-making-small-models-do-this-run)) and its qualification tiers ([10](local-small-models.md#10-qualifying-without-guessing)) still hold, and this plan doesn't repeat them. This plan adds:
- what has changed since;
- the two new models;
- the other two runs;
- one order of work for all three runs.

## Contents

1. [What changed since 2026-11-19](#1-what-changed-since-2026-11-19)
2. [The runs to repeat](#2-the-runs-to-repeat)
3. [The two models](#3-the-two-models)
4. [This Mac](#4-this-mac)
5. [How a local model plugs in](#5-how-a-local-model-plugs-in)
6. [The setting in Settings → Models](#6-the-setting-in-settings--models)
7. [Fitting each run](#7-fitting-each-run)
8. [Qualifying, run by run](#8-qualifying-run-by-run)
9. [Phases](#9-phases)
10. [Decisions the owner makes](#10-decisions-the-owner-makes)
11. [Draft stories](#11-draft-stories)
12. [Risks](#12-risks)
13. [Sources](#13-sources)

## 1. What changed since 2026-11-19

| Then | Now | What it means here |
|---|---|---|
| browser-use was planned for the box, and its model calls were a draft story | browser-use 1.0 runs in the box ([Decision 0035](../engineering/decisions/0035-browser-use-typing-and-transcripts.md)). Every model call it makes goes to an endpoint the worker serves and is admitted on the run's frozen `researcher` route (Y7, US-17.2, done) | Once the shared gateway can answer from a local route, browsing uses it with **no change to the box**. The box never learns the local runtime's address. The worker runs natively on the Mac, so it reaches `127.0.0.1` |
| One live run: deep research | Three. The Market watcher Costa Rica (2026-11-20) and the Transcript workflow (runs 4 and 5, 2026-11-26, [Decisions 0039](../engineering/decisions/0039-browse-result-saved-to-a-file.md) and [0040](../engineering/decisions/0040-polished-transcript.md)) | Each run needs its own "same result" check ([section 2](#2-the-runs-to-repeat)) |
| Bonsai 2 27B on MTPLX was the only local candidate | Inkling 2 Mini (2026-11-20) and Ternary Bonsai 2.5 27B (2026-11-24). Bonsai 2.5's Q2_0 build runs on **stock llama.cpp** | One runtime can serve both models ([section 5](#5-how-a-local-model-plugs-in)). The Bonsai 2 pack in `~/Models` stays as a baseline |
| The plan's draft IDs were US-17.1 to US-17.7 | EPIC-17 went to browser-use, so those IDs belong to other stories now. The local route was never ingested | [Section 11](#11-draft-stories) uses new draft IDs |

**Unchanged: a decision comes first.** Each of these still rules out a local model server:
- [`AGENTS.md`](../../AGENTS.md);
- [the model gateway rule](../../.claude/rules/model-gateway.md);
- [PRD-Model-Providers](../PRD/PRD-Model-Providers.md) MP-01, MP-02 and MP-07;
- SP-006.

[Section 3 of the earlier plan](local-small-models.md#3-why-this-needs-a-decision-first) lists every rule a decision amends. The protections stay:
- no fallback between sources;
- a run freezes its route at admission;
- a missing or wrong local model blocks the call, with nothing substituted.

## 2. The runs to repeat

The figures are what each run's README records from OpenRouter, where every role ran on Terra (`openai/gpt-6.1-terra`), except browsing on Sol (`openai/gpt-6.1-sol`).

| Run | Roles it uses | Observed on OpenRouter | "The same result" means |
|---|---|---|---|
| [Deep research content writer](../../README-Deep-Research-Content-Writer.md), workflow run 5, 2026-11-19 | `executor` | 45 model calls and 49 tool calls. 1,110,570 tokens in and 25,335 out. About 9 minutes. US$0.453547 | [R1 to R9 of the earlier plan](local-small-models.md#1-the-result-to-match): six plan tasks done, at least 15 sources, 2,000 to 5,000 cited words, a check step, the approval gate |
| [Market watcher Costa Rica](../../README-Market-Watcher-Costa-Rica.md), Expert run, 2026-11-20 | `executor` | 8 model calls and 22 tool calls, 2 of them market reads and 16 calculations. 153,771 tokens in and 3,690 out. 1 minute 16 seconds. US$0.061958 | `market-note.md` is published, in Costa Rican Spanish. Every figure in it appears in a `market_history` or `calculate` result. The calculations are tool calls, not the model's arithmetic |
| The same Expert as a workflow step | `executor` | 9 model calls. 184,635 tokens in and 4,422 out. 90 seconds. US$0.068171 | As above, inside a workflow execution |
| [Transcript](../../README-YouTube-Transcript.md), run 5, 2026-11-26 | `researcher` for the browse, `executor` for the rest | The browse of a 44-minute video ended `done` with no bot check, and the worker saved 320 timed lines. Then 8,049 words of prose were added 60 lines at a time. About three and a half minutes. US$0.155325. The README doesn't record its token counts, so P0 reads them from the run's Budgets panel | `transcript-timed.md` has all 320 lines, with none empty or repeated. `transcript.md` is published last and is the run's Result. Its prose covers every 60-line section, in order, with nothing summarized. The owner reads it beside run 5's |

**What no code can check:** whether the prose is faithful, whether the Spanish reads as Costa Rican, and whether the deep research document is good. As in the earlier plan, no model judges another model's output (`AGENTS.md` forbids an implicit evaluator). The owner reads each one.

## 3. The two models

Read from their pages on 2026-11-27. Every figure below is the publisher's own claim. Nothing here has been run on this Mac.

| | Inkling 2 Mini | Ternary Bonsai 2.5 27B |
|---|---|---|
| Publisher, date | Thinking Machines Lab, 2026-11-20 | PrismML, 2026-11-24. Based on Qwen3.8 27B |
| Size | 26.4B parameters, **3.4B active** per token (5.4B counting its loops) | 27.36B, dense |
| Shape | A looped mixture of experts. 24 layers, of which the middle 12 run three times. 8 of 128 experts per token. Local and global attention. Takes images | Hybrid attention, about 75% linear and 25% full. Weights are ternary {−1, 0, +1}. Takes images through an optional `mmproj` file |
| Official weights | One 19.5 GB safetensors file in NVFP4 and MXFP8, formats made for NVIDIA's GPUs | GGUF and MLX packs |
| On a Mac | The card points to Unsloth's GGUF builds for llama.cpp, and to Ollama and Exo on Apple silicon. Which quantization fits, its size and its tool parser are found in P0. The card warns: "Support for looped models in local runtimes is new" | **Q2_0 GGUF on stock llama.cpp from release b11556.** "Older stock builds load Q2_0 without any warning and produce garbage." PQ2_0 and the 5.93 GB PTQ1_0 need PrismML's llama.cpp fork. An MLX 2-bit pack has its own loader |
| Download | Unknown until a GGUF is chosen. At 4 bits, 26.4B parameters come to about 15 GB by arithmetic | About 7.5 GB for Q2_0, from the repository's file list. P0 confirms the exact size |
| Context | Up to 1M tokens | 262K tokens |
| Tool calls | Made for agents. The card reports MCP Atlas 82.7% and BrowseComp 79.0%. It doesn't state the tool-call format, so P0 reads `chat_template.jinja` | A stated focus. The card reports an average of 77.2 over τ²-Bench, τ³-Bench, BFCL v3, BFCL v4 and AppWorld, against 77.7 for FP16. The format is in PrismML's Bonsai-demo scripts, which P0 reads |
| Thinking | "Setting reasoning effort to its minimum does not fully disable reasoning" | On by default, at `xhigh` or `medium`, with no `low`. "A small cap such as 256 tokens ends generation mid-thought." The MLX example turns it off with `enable_thinking=False` |
| Speed on Apple | Not stated | M5 Pro on llama.cpp (PQ2_0): 30.2 tokens a second to write and 416 to read a 512-token prompt. M4 Pro with multi-token prediction: 29.2 to write. This Mac is an M3 Pro, so P0 measures it here |
| Memory | "Apple silicon devices with 32GB or more memory" | Not stated for Apple |
| Spanish | "General multilingual support", and "Output quality can be lower outside English" | Not stated |
| License | Apache 2.0, plus Thinking Machines' Model Acceptable Use Policy, which the owner reads | Apache 2.0 |
| The card's own warnings | It is "less reliable than larger models at following detailed instructions". It "may take destructive actions" without confirmation. It recommends limits on output tokens and agent turns, and a sandbox | Benchmarks were run with thinking on at `xhigh` |

**Neither is small by parameter count.** Bonsai 2.5 is small on disk, and Inkling is small in active parameters per token. Both fit the aim: a model that runs on this Mac.

**The baseline stays.** `Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed` in `~/Models` (8.2 GiB, on MTPLX 2.12.2) passed tool calls in the [earlier test](../../research/LOCAL-MODEL-EVIDENCE.md), and failed strict JSON schema without `llguidance`. A new model should beat it.

## 4. This Mac

Observed on 2026-11-27:
- An Apple M3 Pro with 36 GiB of memory (38,654,705,664 bytes), on macOS 27.2.1.
- The GPU's wired-memory limit is the macOS default (`iogpu.wired_limit_mb` is 0).
- 111 GiB of disk is free.
- `~/Models` holds the Bonsai 2 pack, Kokoro and faster-whisper.

[Section 4 of the earlier plan](local-small-models.md#4-the-hardware-budget) leaves about 18 to 22 GB for a model once macOS, the Studio and Supabase in Docker have their share. Docker's VM may use up to 25.2 GB, so lowering its limit is D4 there.

| Model | Weights | Context memory at 64K | Fits? |
|---|---|---|---|
| Bonsai 2.5, Q2_0 | About 7.5 GB | If it keeps Bonsai 2's layout, 16 full-attention layers keep a cache of about 4.2 GB, and the linear layers' state doesn't grow. P0 measures it | Yes, about 12 GB |
| Inkling 2 Mini, about 4 bits | About 15 GB | Unknown. Local attention keeps part of it short. P0 measures it | Tight. Likely only with Docker's limit lowered, and only one model at a time |
| Both at once | | | No. **One local model serves every role**, so one runtime runs at a time |

**Speed.** The deep research run reads 1.11M tokens and writes 25K. At this Mac's speeds, reading dominates, so a **prompt cache** that keeps each call's unchanged start is the most important thing a runtime offers. At 416 tokens a second, with no cache, reading alone would take about 45 minutes. Inkling reads and writes with 3.4B active parameters, which should be faster than a dense 27B model. Its loops and a new runtime path make that a guess until P0.

## 5. How a local model plugs in

```text
Settings → Models: Model source  ( OpenRouter | Local on this Mac )
                                          │ frozen with the route at admission
worker, native on the Mac                 ▼
  ├─ executor calls ─────────▶ shared gateway ─┬─▶ OpenRouter                     (OpenRouter)
  │                                            └─▶ llama-server on 127.0.0.1/v1   (Local)
  └─ admitted endpoint (US-17.2) ──▶ same gateway, researcher route
        ▲
        └── browser-use in the box: its chat calls, which never see a key or the runtime's address
```

**One seam.** The model factory gains a branch for an OpenAI-compatible base URL on loopback, as [7.2 of the earlier plan](local-small-models.md#72-where-code-changes) says. Admission, budgets, receipts, the admitted endpoint, compaction and the tools stay as they are. A local call reserves US$0 and still counts its tokens, calls and time.

**One runtime: llama.cpp's `llama-server`, release b11556 or later**:
- Bonsai 2.5's Q2_0 needs exactly that.
- Inkling's GGUF builds name llama.cpp too, if that release serves looped models. If it doesn't, Ollama serves Inkling instead, at the cost of its own model store.
- `llama-server` speaks OpenAI's chat format, renders tool calls from the model's own template (`--jinja`), constrains output to a JSON schema, keeps a prompt cache and binds to `127.0.0.1`.
- What it lacks: an [earlier test](../../research/QWEN38-GGUF-TEST-RESULTS.md) on Qwen3.8-27B passed 14 of 15 protocol cases. Naming a single tool in `tool_choice` was unsupported, so the gateway sends `required` with one tool instead.
- llama.cpp isn't installed today. Installing it is a download the owner approves.

**Weights in `~/Models`.** Each model sits in its own folder with its revision. `DOWNLOAD-MANIFEST.json` records its SHA-256, and `verify-models.py` checks it. The Studio never downloads weights or starts the runtime. The owner starts it with a runbook command, as with Supabase, since `AGENTS.md` keeps hooks from starting services.

**Identity.** A local profile names the Hugging Face repository at its revision, the file's SHA-256 and the chat template's hash. The gateway checks `/v1/models` before a call. If the runtime is serving a different model, the call is refused.

## 6. The setting in Settings → Models

Today the page shows the OpenRouter provider panel, then the model policy (`apps/web/app/settings/models/page.tsx`). A **Model source** panel goes above both:

```text
Model source                                            Owner or admin only
(•) OpenRouter    Today's profiles: Terra, with Sol for browsing.
( ) Local         Models served on this Mac. Nothing goes to OpenRouter.

    Local model     Inkling 2 Mini    Qualified 2026-12-xx · llama-server · 64K context
                    Bonsai 2.5 27B    Not qualified: no run of the suite yet
    Runtime         Ready: serving "inkling-2-mini" on 127.0.0.1:9931, pinned SHA matches
    Roles           executor and researcher use the local model
    Spend           US$0.00 per model call. Token, call, tool and time limits still apply.
                    Tool calls (SerpApi, Jina, YouTube) still leave the Mac.
```

The earlier plan's rules hold ([7.1](local-small-models.md#71-the-model-source-setting)):
- OpenRouter is the default, and a new install starts there.
- One source at a time, never mixed, never a fallback.
- Saved choices are kept per source, so switching back restores them.
- The composer's disclosure follows the source.
- Home's Services panel shows "Local model ready" from the runtime's health check.

**Two rules are new, now that browsing exists:**
- **Switching to Local needs both roles covered.** It is refused until a qualified local profile covers `executor`, and also `researcher` when any Expert grants `browse_goal`, as the Transcript reader does. The refusal names what is missing.
- **The local profile answers the browser box too.** The admitted endpoint answers on the run's frozen `researcher` route, so on Local, browser-use's calls reach the local model. Y16 still refuses an image the route isn't qualified for, so browser-use works from text until a local route qualifies for images.

## 7. Fitting each run

**Start with the Market watcher.** It has the fewest calls and the least reading. Its numbers come from tools, so a small model's arithmetic doesn't matter. The open question is language: neither card claims Spanish, and Inkling warns about quality outside English. The owner reads the note.

**Deep research is the long one.** It needs everything in [section 8 of the earlier plan](local-small-models.md#8-making-small-models-do-this-run):
- a version of the Expert's instructions that writes the document in parts;
- tool calls constrained to their schema;
- thinking kept out of the reply;
- possibly 32K of context instead of 64K.

Decision 0034's limits will likely bind: 300 seconds a call (L4) and 45 active minutes (L2). D5 of the earlier plan sets them per local route from P0's measurements.

**The Transcript adds browsing.**
- **The browse.** browser-use 1.0's model writes Python against the page, then finishes with a typed value (`finish_from_repl`), and the worker saves the 320 lines (Decision 0039). On Sol, the browse took 8 steps in run 3 and 12 in run 4. A local model has to write working code against YouTube's transcript panel. That is the riskiest step in this plan, and P5 qualifies it on the qualification hosts first.
- **The prose.** The model reads 60 lines at a time and adds their prose with `append_to_file`, so no single reply holds the whole transcript. About 1,300 words per section must fit in a 4,096-token reply. A model that thinks inside that cap runs out, so thinking has to be off or kept out of the cap.

**Thinking, for both models.**
- **Bonsai 2.5** thinks by default, and a small cap cuts it off mid-thought.
- **Inkling** can't fully turn thinking off.
- **The fix.** The local route asks `llama-server` to return reasoning in its own field, and turns it off where the template allows. P0 checks the switches each model honours. If reasoning still counts against the reply, the local route gets a larger output cap, which is D5's call.

## 8. Qualifying, run by run

The earlier plan's three tiers apply to each run: Q1 route, Q2 frozen replay and Q3 live ([its section 10](local-small-models.md#10-qualifying-without-guessing)).

| Run | Q1, the route | Q2, frozen replay (no spend) | Q3, live (tool spend only, owner approves) |
|---|---|---|---|
| All | US-3.4's suite against `llama-server`: plain text, automatic and required tool calls, flat structured output and streaming, three trials each. Plus reading and writing speed, time to the first token and peak memory at 8K, 32K and 64K | | |
| Market watcher | | The run's recorded `market_history` results, replayed. A code check: every figure in the note appears in a tool result. Three runs | One Expert run and one workflow step. The owner reads the Spanish |
| Deep research | | As the earlier plan's Q2: R2 to R6 and R8 in two of three runs | As the earlier plan's Q3: R1 to R9 |
| Transcript, prose | | Run 5's saved `transcript-timed.md` as input, with no browse. A code check: one append per 60-line section, in order, and a word count near run 5's 8,049. Three runs | |
| Transcript, browse | A scripted browse, then one live browse of `example.com` and `iana.org` on the local `researcher` route, as Decision 0019 S6 did | | One Transcript run on a video the owner names, with the owner's OK, as for runs 4 and 5 |

**A scoreboard compares the models.** It covers Inkling, Bonsai 2.5 and the Bonsai 2 baseline: pass or fail per row, time, calls and peak memory. A model is **offered** after Q1. It **matches a run** after that run's Q3. The setting can switch to Local once one model is offered for both roles.

## 9. Phases

| Phase | Work | Exit |
|---|---|---|
| **P0. Decide and measure** (no app code) | The owner's decision record. With approval for each download: llama.cpp b11556 or later, Bonsai 2.5's Q2_0 and one Inkling GGUF that fits. Pin each in `~/Models`. Serve each by hand. Read each chat template for its tool format and thinking switches. Measure Q1's speed and memory with the whole Studio running | A table of measurements, and a go or no-go for each model |
| **P1. Backlog** | Ingest [section 11](#11-draft-stories) with `autobots-spec-ingest` from the decision | Stories READY in `SPECS.md` |
| **P2. The local route and the setting** | LS-1, LS-2 and LS-3 | One local profile qualified, and Settings → Models switching sources |
| **P3. Market watcher** | LS-4 | Q2 and Q3 pass |
| **P4. Deep research** | LS-5 | Q2 passes for one model, then Q3 |
| **P5. Transcript** | LS-6: the browse on the local `researcher` route, then the prose | Q1's browse, Q2's prose and Q3 pass |
| **P6. Tell it** | A "Local" section in each run's README and on the Pages site, with the scoreboard | Published |

P3 to P5 can't overlap, since only one model is served at a time.

## 10. Decisions the owner makes

[Decision 0041](../engineering/decisions/0041-local-model-source.md) records the recommended answers, as its rows A1 to A17. It reshapes L6 (its A7): a model's matched runs are shown rather than required, because a live check runs on the Local source itself.

| # | Question | Options, recommended first |
|---|---|---|
| L1 | Allow local models, and how? | **A Model source setting: OpenRouter (the default) or Local. One source at a time, never mixed, never a fallback**, as the earlier plan's D1 · local profiles chosen per run · no |
| L2 | Which runtime? | **`llama-server`, release b11556 or later, for both models.** PrismML's fork only if Q2_0 falls short and PQ2_0 measures better. Ollama only if llama.cpp can't serve Inkling's loops. MTPLX stays for the Bonsai 2 baseline only · one runtime per model |
| L3 | Which downloads? | **llama.cpp, Bonsai 2.5's Q2_0 (about 7.5 GB) and one Inkling GGUF**, each shown with its size, source and license before it is fetched · Bonsai 2.5 only, which needs about half the memory |
| L4 | One local model or one per role? | **One model for every role.** Two don't fit in memory together · Inkling for `executor` and Bonsai 2.5 for `researcher`, if P0 shows they fit |
| L5 | Thinking | **Off where the template allows, otherwise returned in its own field, with a larger output cap for that route if it still counts** · leave it on, with the larger cap |
| L6 | Which runs must a model match before it counts as qualified for Local? | **Market watcher and deep research for `executor`, and the Transcript's browse for `researcher`** · Market watcher only, with the rest shown as not yet matched |
| L7 | Inkling's acceptable use policy | The owner reads it before downloading, as Decision 0035 Y14 did for YouTube's terms |
| L8 | Still open from the earlier plan | D4 (Docker's memory limit), D5 (limits per local route), D7 (a local version of an Expert counts as the same Expert), D10 (runs started before a switch). Its D8 and D9 were settled by Decision 0035 |

## 11. Draft stories

The IDs are drafts. Ingestion assigns the real ones in a new epic. The full Gherkin for LS-1 to LS-3 is in [section 13 of the earlier plan](local-small-models.md#13-draft-stories-in-specs-style), as its drafts US-17.1 to US-17.3, and this plan adds one scenario to LS-3.

| Draft | Story | Depends on |
|---|---|---|
| LS-1 | A local model route through the shared gateway, served by `llama-server` | The decision |
| LS-2 | Local route qualification and offering, at no spend | LS-1 |
| LS-3 | The Model source setting in Settings → Models | LS-2 |
| LS-4 | The Market watcher on a local model | LS-3 |
| LS-5 | The deep research workflow on a local model | LS-3 |
| LS-6 | The Transcript workflow on a local model | LS-3 |

The scenario LS-3 adds:

```gherkin
Scenario: The browser box's model calls follow the source
  Given Model source is Local, and a qualified local profile covers the researcher role
  When a run's browse_goal starts browser-use in the box and it sends a chat completion to the admitted endpoint
  Then the call is admitted on the run's frozen local researcher route, answered by the local runtime, reserves US$0, and nothing reaches OpenRouter
```

LS-4, LS-5 and LS-6 share one shape:

```gherkin
Scenario: A frozen replay matches the run's checks
  Given Model source is Local, the runtime serves the pinned model, and the run's recorded tool results or saved input
  When the run is replayed three times in a disposable environment
  Then the run's code checks in section 8 hold in at least two of the three, with time, calls and peak memory recorded

Scenario: A live run matches the OpenRouter run
  Given Model source is Local and the owner approves the run's tool spend
  When the run runs on real tools
  Then its code checks hold, no request reaches OpenRouter, its model spend is US$0.00, and the owner reads its result beside the OpenRouter run's
```

## 12. Risks

- **Neither model may match Terra on deep research.** The Market watcher is the likeliest to pass. The Transcript's browse is the least likely, since it needs model-written code.
- **Inkling on a Mac is new.** Its official weights are in NVIDIA formats, and its card calls local support for looped models new. The Mac path rests on third-party GGUF builds.
- **Bonsai 2.5's Q2_0 fails silently on old llama.cpp builds.** The runbook checks `llama-cli --version`, and the gateway's identity check pins the runtime.
- **Memory.** About 15 GB of Inkling beside Supabase, the Studio and Chromium in the box may push this Mac into swap. P0 measures it with everything running.
- **Time.** Expect a run to take several times as long as on OpenRouter. The call and active-time limits need to be set per route.
- **The benchmarks are the publishers'.** Their Apple numbers come from M4 Pro and M5 Pro chips, and this is an M3 Pro.
- **Spanish.** Neither card claims it, so the Market watcher may need the owner's judgment, or a model that isn't qualified for it.

## 13. Sources

- [Inkling 2 Mini model card](https://huggingface.co/thinkingmachines/Inkling-2-Mini) and [its files](https://huggingface.co/thinkingmachines/Inkling-2-Mini/tree/main), read 2026-11-27.
- [PrismML: Bonsai 2.5 27B](https://prismml.com/news/bonsai-2-5-27b), [its GGUF card](https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF) and [its MLX pack](https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-mlx-2bit), read 2026-11-27. Not yet read: PrismML's Bonsai-demo scripts, which the GGUF card calls the source of truth for serving and tool calls. P0 reads them.
- [The local small models plan](local-small-models.md), 2026-11-19.
- [Decision 0035](../engineering/decisions/0035-browser-use-typing-and-transcripts.md) Y7 and Y16, and US-17.2 in `SPECS.md`: the admitted endpoint.
- [Decision 0039](../engineering/decisions/0039-browse-result-saved-to-a-file.md) and [Decision 0040](../engineering/decisions/0040-polished-transcript.md): the Transcript's saved lines and its prose.
- [README-Deep-Research-Content-Writer.md](../../README-Deep-Research-Content-Writer.md), [README-Market-Watcher-Costa-Rica.md](../../README-Market-Watcher-Costa-Rica.md) and [README-YouTube-Transcript.md](../../README-YouTube-Transcript.md): the observed runs.
- `services/agent/src/autobots/domain/models.py`: today's profiles and roles. `apps/web/app/settings/models/page.tsx`: today's Models page.
