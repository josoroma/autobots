# Plan: the deep research run on local Hugging Face small models

**Date:** 2026-11-19. **Status:** a draft for the owner. Nothing here is implemented, and nothing may be until the owner decides [section 12](#12-decisions-the-owner-makes): today's rules forbid a local model server (see [section 3](#3-why-this-needs-a-decision-first)). Like the other plans in this folder, it is input for a decision and a backlog addition. [Section 13](#13-draft-stories-in-specs-style) holds stories in SPECS style, ready for ingestion once the owner approves.

The aim: repeat the run shown in the video, the Deep research content writer workflow on "langchain for deep agents" ([run 5 of README-Deep-Research-Content-Writer.md](../../README-Deep-Research-Content-Writer.md#the-workflow-execution)), with every model call answered by an open-weight model from Hugging Face served on this Mac, and get the same result. No OpenRouter call, and everything else unchanged. A workspace setting chooses where every model call goes: **OpenRouter**, with today's profiles and defaults, or **Local**, on qualified local models only, never mixed ([section 7.1](#71-the-model-source-setting)). [Section 9](#9-browsing-with-browser-use-locally) adds browsing (`browse_goal`) on [browser-use](https://github.com/browser-use/browser-use), open source and run locally, with a small model. [The browser typing plan](browser-typing-and-flights.md) lets it start without approval and type and submit, behind a Settings checkbox that is on by default, and prices flights with it.

## Contents

1. [The result to match](#1-the-result-to-match)
2. [What changes and what doesn't](#2-what-changes-and-what-doesnt)
3. [Why this needs a decision first](#3-why-this-needs-a-decision-first)
4. [The hardware budget](#4-the-hardware-budget)
5. [Models](#5-models)
6. [Serving them](#6-serving-them)
7. [The local route in Autobots](#7-the-local-route-in-autobots)
8. [Making small models do this run](#8-making-small-models-do-this-run)
9. [Browsing with browser-use, locally](#9-browsing-with-browser-use-locally)
10. [Qualifying without guessing](#10-qualifying-without-guessing)
11. [Phases](#11-phases)
12. [Decisions the owner makes](#12-decisions-the-owner-makes)
13. [Draft stories in SPECS style](#13-draft-stories-in-specs-style)
14. [Risks](#14-risks)
15. [Sources consulted](#15-sources-consulted)

## 1. The result to match

What run 5 did, as observed on 2026-11-19. The token counts come from each child run's Budgets panel. The other figures come from the README and the run pages.

| | Research and write | Check and report | Whole tree |
|---|---|---|---|
| Expert | Deep research writer, version 2 | The same Expert, given artifact IDs | Workflow version 1: input, two agent steps, a transform, an approval gate, output |
| Plan | Six tasks, all completed, one proposal, no refusal | Two tasks, both completed | |
| Tool calls | 37: `google_search` 3, `google_extract` 8, `save_artifact` 12, `read_run_file` 3, `complete_task` 6, `publish_artifact` 4, `propose_plan` 1 | 12: `read_artifact` 4, `read_run_file` 1, `save_artifact` 2, `publish_artifact` 2, `complete_task` 2, `propose_plan` 1 | 49 |
| Tokens | 981,124 in, 20,463 out | 129,446 in, 4,872 out | 1,110,570 in, 25,335 out, in 45 model calls (about 24,700 in per call) |
| Time | About 7 minutes | About 80 seconds | About 9 minutes of agent work, then the owner's approval |
| Spend | US$0.398622 | US$0.054925 | US$0.453547 of US$3.75 |
| Published | `sources.md` (17 sources), `synthesis.md`, `content.md`, `report.md` (degraded: 18 of 30 pages, 60%) | A corrected `content.md` (about 2,150 words, S-01 to S-17) and `review.md` (final status degraded) | Approved by the owner, then succeeded |

**"The same result" means each of these holds:**

| # | Requirement | Checked by |
|---|---|---|
| R1 | The same workflow shape and tool grant. A local variant of the Expert's instructions counts only if the owner accepts it (D7) | Reading the run record |
| R2 | The research step completes all six plan tasks, and no plan refusal ends a run | Code: the run's plan and events |
| R3 | At least 15 numbered sources with excerpts, from up to 30 Google results, and an honest page count | Code: `sources.md` and the tool record |
| R4 | `content.md` has 2,000 to 5,000 words, a linked table of contents whose anchors resolve, an `[S-NN]` for every claim that cites, each resolving to `sources.md`, References and "Why this format" | Code for the counts and links. The owner judges the prose |
| R5 | `report.md`'s status follows the 80% and 15-source rule and agrees with its own counts | Code |
| R6 | The check step reads all four artifacts and publishes a corrected `content.md` and a `review.md`, and every citation still resolves | Code, and the owner reads what it changed |
| R7 | The approval gate holds the result, and the owner decides | The run record |
| R8 | Within the run limits ([Decision 0034](../engineering/decisions/0034-deep-research-like-content-writer.md) L2: 64 model calls, 96 tool dispatches, 45 active minutes), or within limits the owner sets for local routes (D5) | The run record |
| R9 | US$0 in model spend. Tool spend (SerpApi, Jina) is the same as before | Budgets and receipts |

No model judges another model's output: `AGENTS.md` forbids an implicit evaluator. What code can't check is the owner's call.

## 2. What changes and what doesn't

**Unchanged:** the Studio, the API, the worker with its leases, fencing and checkpoints, the LangGraph and Deep Agents loop, the tools and their keys, approvals, artifacts, budgets and receipts, compaction, and the pinned plan (US-16.9).

**Changed:** only what answers each model call.
- **A local route:** a model served on `127.0.0.1` by a runtime the owner starts, the way they start Supabase.
- **A Model source setting** picks OpenRouter or Local for the whole workspace. OpenRouter stays the default, with today's profiles and role defaults.
- **Tool calls still leave the Mac** in either source, since search and page reads are what the run is for.

Kokoro and faster-whisper in `~/Models` are already local, but they produced the film's voice and checked it. They are not part of the app.

## 3. Why this needs a decision first

| Rule | Where | What it says |
|---|---|---|
| Model boundary | [`AGENTS.md`](../../AGENTS.md), "Boundaries that matter" | "All application model calls use the approved OpenRouter profiles (three, by Decision 0019) and the shared gateway. No fallback, local model server, implicit evaluator, hosted tracing or alternative provider." |
| Gateway rule | [`.claude/rules/model-gateway.md`](../../.claude/rules/model-gateway.md) | "Exactly three approved profiles … No alternate provider, local model, hidden model default or fallback." |
| Approved profiles | [SP-006](../engineering/option-b-contract.md#sp-006--approved-model-profiles), [MP-01](../PRD/PRD-Model-Providers.md#mp-01-approved-models-and-selection), [Decision 0019](../engineering/decisions/0019-sol-profile-and-browser-use.md) S2 | Three OpenRouter profiles. One is offered for new runs only once its route is qualified |
| Provider PRD | [PRD-Model-Providers.md](../PRD/PRD-Model-Providers.md) intro and MP-01 | "There is no local inference runtime or local-only model profile in scope." "Reject local endpoints …" "There is no optional-cloud toggle" |
| Catalog contract | [MP-02](../PRD/PRD-Model-Providers.md#mp-02-catalog-and-request-contract) | A paid attempt needs a fresh, exact association with OpenRouter's public catalog |
| Single factory | `adapters/models/factory.py` | "The one OpenRouter factory … Nothing else builds a model client." |

A new decision (0035) would amend SP-006, MP-01, MP-02 and MP-07, `AGENTS.md` and the gateway rule. It would keep what protects runs today:
- **No fallback** between a local route and OpenRouter.
- A run **freezes** its route at admission.
- A local server that is missing or serving the wrong model **blocks** the call; nothing is substituted.
- Every budget except money still applies.

## 4. The hardware budget

**This Mac:**
- An M3 Pro with 36 GiB of unified memory (38,654,705,664 bytes), running macOS 27.2.1.
- The GPU's wired-memory limit is the macOS default (`iogpu.wired_limit_mb` is 0).
- **Docker Desktop's VM may use up to 25.2 GB with 12 CPUs** (`docker info`). Supabase's containers run there, and that memory is shared with any model.

| Consumer | Estimate, to measure in Phase 0 |
|---|---|
| macOS, the Studio (Next.js, API, worker), a browser | 6 to 8 GB |
| Supabase in Docker's VM | What it actually uses, with Docker's limit lowered to fit (D4) |
| Model weights, KV cache and runtime | What's left, about 18 to 22 GB |

**Memory per model at a 64K context** (the context Decision 0034 L6 gives every run):
- **Bonsai 2 27B ternary** (on disk): its weights are 8.8 GB. Its `config.json` has 64 layers, and only 16 of them use full attention and keep a KV cache: 4 KV heads of 256 dimensions. At 16 bits that's 64 KiB per token, about 4.2 GB for 64,000 tokens. The other 48 layers use linear attention, whose state doesn't grow with length. The total is about 13 GB before the runtime's own memory.
- **A 4B to 9B model at 4 bits:** roughly 2.5 to 6 GB of weights, plus a KV cache that depends on its attention layout. Each candidate is measured, not assumed.

**Speed.** The run is mostly reading: 1.11M input tokens against 25K output.
- **Prefill** (processing the prompt) decides the time. With no reuse, at an assumed 500 tokens per second, 1.11M tokens is 37 minutes of prefill alone. A **prefix cache** keeps the processed start of each prompt (instructions, tool schemas, earlier turns), so each call processes mostly its new tokens. This is the most important serving requirement.
- **Decode** (writing the reply): 25,335 tokens take 10 to 21 minutes at an assumed 20 to 40 tokens per second.
- **Measured here before:** Qwen3.8-27B at 4 bits on llama.cpp decoded at about **7.5 tokens per second**, and took about 10 seconds to its first token on a short prompt ([section 5.3](#53-what-this-repository-already-measured)). At that rate, 25,335 output tokens alone take 56 minutes, past L2's 45 active minutes. A 27B model needs multi-token prediction to be fast enough (Bonsai's MTPLX pack has it), or the run needs a model of 9B or less.
- **Expect 20 to 60 minutes per run tree**, against about 9 today. Phase 0 replaces these assumptions with measurements.

**Today's limits would bind:**
- **Call time.** L4 allows 300 seconds per call. A cold 64K prefill at 500 tokens per second (128 s) plus a 4,096-token reply at 20 tokens per second (205 s) takes 333 seconds, which is over the limit.
- **Active time.** L2's 45 active minutes may also be reached.
- D5 decides both.

## 5. Models

### 5.1 Already on this Mac

[`Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed`](https://huggingface.co/Youssofal/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed) is the only general language model in `~/Models`. Per `~/Models/README-MODELS.md`, the Qwen 27B blend and Qwen-Image were removed in October.

| Property | Value, from its files |
|---|---|
| Revision | `03bd60bb82755f2446f5083426dca9708eb8e0fe`, verified by `~/Models/verify-models.py` |
| License | Apache-2.0 |
| Base | Qwen3.8-27B merged with prism-ml's Ternary Bonsai 2 27B. A Qwen3.5-style hybrid of linear and full attention. Also has vision |
| Context | 262,144 positions |
| Tool calls | Its chat template renders tools and expects `<tool_call><function=…><parameter=…>` replies |
| Runtime | MTPLX 2.12.2 only. Its ternary kernels don't load in mlx-lm, generic MLX-VLM or llama.cpp |
| Smoke test | Answered `2 + 2` on 2026-10-11 (`SMOKE-TESTS.json`). Never tried as an agent |

At 27B parameters it is not a *small* model. At 8.8 GB it has a small footprint, so it is the **baseline**: if it can't match run 5, a smaller model is unlikely to.

### 5.2 Candidates to download

These come from [the repository's earlier survey](../../research/HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md#4-smaller-open-weight-models-worth-evaluating) and a search on 2026-11-19. Phase 0 surveys the Hub again, and a model is chosen by qualification ([section 10](#10-qualifying-without-guessing)), not by its name.

| Tier | Candidate | Why | Watch |
|---|---|---|---|
| Small | Qwen3.5 4B and 9B | Apache-2.0, tool calling, long context. Both have MTPLX packs, so one runtime serves them and Bonsai. The 9B is 5.95 GB as MLX 4-bit, or about 8.67 GB as an MTPLX pack | Thinking is on by default under some servers and spends the reply's tokens |
| Small | Granite 4.2 3B | Apache-2.0, tool use and structured-output training, a different family from Qwen. IBM's official q4 MLX is 2.06 GB | Needs explicit sampling and template settings |
| Small | SmolLM3-3B | Apache-2.0, documented tool formats, open training. 1.73 GB as MLX 4-bit | Its Python-style tool format must never be executed. Use a parser-based format |
| Small | Gemma 4 E4B | 4.5B effective parameters, 128K context, native function calling | One hands-on MLX test reported no tool calls in a multi-turn task. Qualify before trusting |
| Small, older | Qwen3-8B, Qwen3-4B | The most tested tool calling at these sizes | Less context headroom |
| Mid (MoE) | Gemma 4 26B A4B | About 4B active parameters, so a small model's speed with a larger model's knowledge | Memory like a 26B |

**What every download must have:**
- A license that allows this use.
- Tool calling in its chat template.
- At least 64K context.
- An MLX or GGUF build pinned by revision and SHA-256, recorded like `~/Models/DOWNLOAD-MANIFEST.json`.
- Thinking that can be turned off or is returned separately.
- A fit within the memory budget.

Each download is approved by the owner (D3), with its size.

### 5.3 What this repository already measured

Two local experiments ran on this Mac on 2026-11-04, before the OpenRouter-only decision. Their reports are marked historical, but their observations stand.

| Experiment | Observed | What it means for this plan |
|---|---|---|
| [Bonsai through MTPLX](../../research/LOCAL-MODEL-EVIDENCE.md), 8K context | Automatic and forced tool calls passed, with tool-result continuation and streamed text. **Strict JSON schema failed (HTTP 400)**: the optional `llguidance` dependency was missing, and MTPLX refused rather than return unconstrained output. A background warmup hit memory pressure, and a later one succeeded | Install and pin MTPLX's `server` extra (`llguidance`) in an isolated environment before Q1, or use tool-call results with server-side validation. Measure memory with the whole Studio running |
| [Qwen3.8-27B Q4_K_M through llama.cpp](../../research/QWEN38-GGUF-TEST-RESULTS.md), 8K context, one slot | 14 of 15 protocol cases passed, including nested strict JSON. Native named `tool_choice` was **unsupported** (only `auto`, `none` and `required`). A bounded invoice audit **failed its semantic check**: the call's shape was valid, but its arithmetic was wrong. Decode about **7.5 tokens per second**, first content about **10 s**. Peak resident memory **16.6 GiB**, with no swap | Valid syntax doesn't mean correct reasoning, so the semantic checks in Q2 matter. A dense 27B is too slow for this run. Use `required` with one permitted tool in place of named choice |
| [Hugging Face SLM survey](../../research/HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md) | Recommended keeping Bonsai first, qualifying structured output separately, and shortlisting Qwen3.5-4B and Granite 4.2 3B for cheaper work. It found no official Qwen3.8 below 27B | The candidates in 5.2 |

**Roles.** The run page says "Only the executor's binding dispatches in this release", so one model answers all 45 calls. One local model per route is enough for this run. The other roles can follow once this one works. Browsing runs on the `researcher` route, and [section 9](#9-browsing-with-browser-use-locally) covers it.

## 6. Serving them

| Runtime | For | Strengths | Gaps to check |
|---|---|---|---|
| **MTPLX 2.12.2** (on disk) | Bonsai, required | OpenAI-compatible API, multi-token-prediction decoding, an SSD session cache for prefixes, paged KV quantization, a localhost bind with `--no-auth` | Its OpenAI bridge can rewrite agent transcripts. Run it with `--agent-rewrites off` and `--tool-prompt-mode native`, so the app alone owns compaction, the plan and the tool set |
| **mlx-lm server** (venv on disk, no model) | MLX builds of small models | Fastest on Apple silicon, prompt cache | Tool-call parsing and constrained output vary by version |
| **llama.cpp `llama-server`** (not installed) | GGUF builds | Grammar- and JSON-schema-constrained output, `--jinja` tool calls, `cache_prompt`, mature | A separate download of each model as GGUF |
| Ollama, LM Studio | Either | Convenient | More moving parts, and their own model stores and update channels |

**What any runtime must pass:**
- OpenAI-compatible `/v1/chat/completions` with `tools`, `tool_choice` `auto` and `required`, streaming, and token `usage` in the reply.
- Structured output by JSON schema or grammar.
- A prefix cache.
- A configured context of at least 64K and replies of up to 4,096 tokens.
- Binding to `127.0.0.1` only, with no telemetry.
- No download at serve time: MTPLX's `--download` is never used, and weights stay pinned on disk.
- Reasoning off, or returned in a separate field.

**Lifecycle.** The owner starts the runtime, since hooks never start services (`AGENTS.md`).
- A runbook gives the exact command per model.
- Home's Services panel adds "Local model: ready / not running" from a health probe.
- A missing server blocks inference the way a missing key does (MP-08).

## 7. The local route in Autobots

Where the stories would change code. Nothing here is done now.

### 7.1 The model source setting

Settings → Models gains one workspace setting, **Model source**, that only an owner or admin can change (MP-05):

| | **OpenRouter** (the default) | **Local** |
|---|---|---|
| Profiles offered | Exactly today's: Terra, and Sol once offered. DeepSeek stays not offered | Qualified local profiles only |
| Role defaults | Today's: every role on Terra, `researcher` on Sol | Set per role from the qualified local profiles (D11), e.g. the deep research model for `executor` and a small model for `researcher` |
| Resolution order | MP-01's, unchanged: run role override, run-wide profile, workspace role override, workspace default, built-in default | The same order, over local profiles only |
| Needs | The OpenRouter key | A running local runtime. No key, and none is read |
| Never sends | Anything to a local runtime | Anything to OpenRouter, including its catalog fetch |
| Home's Services panel | "OpenRouter authenticated" | "Local model ready" from the runtime's health and `/v1/models` |
| Disclosure in the composer | "Sent to OpenRouter: …" as today | "Sent to the local model on this Mac. Nothing goes to OpenRouter." Tool calls still leave the Mac, and it says so |
| Spend | As today | US$0 reserved per model call. Token, call, tool and time limits still apply. Tool spend (SerpApi, Jina) is unchanged |

**Rules that hold in both:**
- **One source at a time.** A run never mixes sources, and neither source ever falls back to the other.
- **A new install starts on OpenRouter** with today's defaults, so nothing changes until the owner switches.
- **Switching to Local is refused** until a qualified local profile covers every role that dispatches: today `executor`, and `researcher` when an Expert grants `browse_goal`. The refusal says what is missing.
- **Saved choices are kept per source.** The workspace default and role overrides are stored for each source, so switching back restores what was there.
- **Runs started before a switch:** recommended is that the source is a hard boundary. A model call whose frozen route is on the source now switched off is refused at dispatch as `model_source_disabled`. The run waits with that reason until the owner switches back, cancels, or starts a linked new run on the active source (MP-01's rule for changed routes). D10 decides.

### 7.2 Where code changes

| Area | File | Change |
|---|---|---|
| Profiles | `domain/models.py` | One `ModelProfileId` per qualified local model (e.g. `local_bonsai_2_27b`). The canonical ID is the Hugging Face repository at its revision, and the wire ID is the served model ID. Offering waits on qualification, as `OFFERED_FOR_NEW_RUNS` does for Sol. A local `ModelRoute` costs nothing |
| Client | `adapters/models/factory.py` | A second branch for local routes: an OpenAI-compatible client with its base URL fixed to the configured loopback port, no SDK retries (the application owns retries), and the same timeout policy. `FORBIDDEN_OPTIONS` still applies. This needs a newly locked dependency such as `langchain-openai`, since only `langchain-openrouter` is locked today |
| Identity | `adapters/models/catalog.py` | OpenRouter's catalog proves identity and parameters today. For a local route, a manifest snapshot does: the served ID from `/v1/models`, the weights' SHA-256 and the chat template's hash. A mismatch refuses the call, with no substitute |
| Budgets | `application/run_admission.py`, `application/loop_policy.py` | Reserve US$0 per local call, and keep the token, call, tool and time limits. Show "US$0.00, local" with the tokens |
| Qualification | `operations/route_qualification.py` | US-3.4's suite (plain text, automatic and required tool calls, flat structured output and streamed text, three trials each) runs against a local route. It needs no `--paid` flag, since nothing is spent, and it gates offering |
| Model source | `contracts/settings.py`, `application/provider_settings.py`, `application/run_admission.py`, `application/worker_inference.py` | The setting, with the default profile and role overrides stored per source. Admission resolves roles over the active source's profiles and freezes the source with the route. Dispatch refuses a call whose source is switched off |
| Settings and disclosure | `apps/web` Settings → Models, the composer's disclosure (`components/runs/disclosure/`) | The Model source control, and local profiles with their qualification and limits. The disclosure follows the source, as in 7.1. Tool calls still leave the Mac, and the text says so |
| Credentials | none | A local route has no key. Its URL is ordinary non-secret configuration |
| Tests | services/agent tests | Fake transports stay the default. A local smoke test runs only on request against a running server, like live qualification |

## 8. Making small models do this run

The five attempts with Terra failed in ways small models make more likely:
- Context thrash with a small context (attempt 1).
- The plan lost at compaction (attempt 2).
- The plan re-proposed without a reason (attempt 4).

**Mitigations, least change first:**
1. **A local version of the Expert.** Save shorter instructions as a new version: one tool per turn, and the document written in parts. It writes an outline, then one section per `save_artifact`, then assembles them. Each reply stays well under 4,096 tokens, using tools the Expert already has. D7 decides whether this still counts as the same Expert.
2. **Constrained tool calls.** Use grammar or JSON-schema decoding when a tool call is required. The existing repair path (one repair per run) covers the rest.
3. **A smaller view per route.** Use 32K instead of 64K for models of 9B or less if quality drops past it (Decision 0034 L6 and L7, set per route by D5). The pinned plan and offloading carry the rest.
4. **Thinking off,** or scoped to the current agent turn, so it doesn't consume the reply.
5. **Split the research step.** A new workflow version with separate "collect" and "write" agent steps gives each child run a shorter history, with no code change.
6. **A citation gate in code.** The reference project repairs citations in code, while Autobots relies on the model and the check step. A gate in code would be new behavior, so it waits for D6.

## 9. Browsing with browser-use, locally

`browse_goal`, the Autonomous browsing tool, is the Studio's other model-driven loop. The owner wants it on [browser-use](https://github.com/browser-use/browser-use), open source and run on this Mac, with a small model.

### 9.1 Where browsing stands

- **[Decision 0018](../engineering/decisions/0018-browser-executor.md) planned browser-use inside an isolated executor:**
  - Chromium in a Playwright image pinned by digest (B1), with per-call caps of 1 CPU, 1 GiB and 300 seconds (B2).
  - An egress proxy that applies the URL guard to every request (B3).
  - The `researcher` route (B4).
  - Read-only actions (B5), and approval on every call (B6).
- **[Decision 0020](../engineering/decisions/0020-own-browsing-loop.md) replaced browser-use with Autobots' own loop** when browser-use 0.13.14 couldn't be installed. It pinned `pydantic==2.13.5`, and `openrouter==0.11.46`, the SDK every route was qualified on, requires `pydantic<2.13`.
- **What that loop does** (`application/browsing_loop.py`):
  - It shows the model the page as text: up to 6,000 characters, 60 numbered links and the last 20 steps.
  - It requires exactly one tool call per step: open a link, go to a URL, scroll, or finish.
  - By default it runs 10 steps in 120 seconds, at most 20 steps in 300.

### 9.2 browser-use today

From PyPI and its README, read on 2026-11-19:

| | browser-use |
|---|---|
| Release | **1.0.6**, 2026-11-16. Five releases since 1.0.2 on 2026-11-11 |
| Engine | `browser-harness` 0.1.13. The model writes **Python** against helpers (`new_tab`, `page_info`, `bu.click(41)`, `js(...)`) and raw CDP, and can save new helpers in a workspace. That is model-written code, steered by page content |
| Defaults that leave the Mac | `Agent(...)` uses the hosted `bu-4.0` model on Browser Use's gateway, and `Browser()` is a Browser Use Cloud browser. A local setup names both: `ChatOpenAI(model, base_url=...)` and `Browser('chromium', headless=True)` |
| Modes | `mode='ultrafast'` acts on accessibility-tree IDs, so it works from text. The default mode's judge reads screenshots unless `use_vision=False` |
| Telemetry | Its README names no switch for 1.0 (0.x used `ANONYMIZED_TELEMETRY=false`). It is checked in P0, and the egress proxy refuses its hosts whatever the setting |
| Pins | `pydantic==2.14.3`, `mcp==2.3.0`, `pydantic-ai-slim[anthropic,google,openai]==2.66.0`, `google-genai==2.34.0`, `browser-harness==0.1.13`. Python 3.11 or later |

### 9.3 Why not in the worker's environment

| Package | browser-use 1.0.6 | Locked today | What blocks it |
|---|---|---|---|
| `pydantic` | `==2.14.3` | 2.12.5 | `openrouter==0.11.46` requires `<2.13`. Its latest, 1.3.194, allows `<3`, but moving to it means qualifying every route again, which Decision 0020 declined |
| `mcp` | `==2.3.0` | 1.30.0 | `langchain-mcp-adapters==0.3.2` holds `mcp<2` |
| New | `pydantic-ai-slim`, `google-genai`, `httpx2`, `browser-harness` | none | A wider tree inside the worker that runs every goal |

The worker must also never run model-written Python. PRD 9.1 disables arbitrary execution outside a qualified isolated executor.

### 9.4 The shape: browser-use in the box, its model calls admitted

```text
browse_goal (worker) ── starts ──▶ isolated executor (Decision 0018)
                                    ├─ Chromium, headless, fresh profile
                                    └─ browser-use 1.0.x, its own pinned environment
                                         │ ChatOpenAI(base_url = admitted endpoint)
                                         ▼
       admitted model endpoint (worker, box network only)
         one admitted call per request on the run's frozen researcher route:
         reservation, invocation ticket, receipt, budget, model_calls (Decision 0020 L3)
                                         │
                                         ▼
       local runtime on 127.0.0.1 (section 6), or OpenRouter for an OpenRouter route
```

browser-use never sees a key or a runtime address, and it reaches the internet only through the egress proxy.

**What stays enforced:**
- **Typing and submitting follow the owner's YOLO setting**, a Settings checkbox that is on by default ([the browser typing plan](browser-typing-and-flights.md), T1):
  - With it on, browser-use may type, click and submit on the allowed domains.
  - With it off, browsing runs on Autobots' read-only loop (that plan's T4), so the proxy never has to see methods inside TLS.

  Either way:
  - The egress proxy connects only to the allowed domains.
  - Chromium's policy disables downloads.
  - The profile is fresh, with no cookies, no host folders and the box's `tmpfs` only, so there is nothing to sign in or pay with.
- **Approval** on every call (B6) only with YOLO off. With it on, a browse starts without approval (that plan's T2), and its domains must fall within the list the owner set in the Expert's grant (that plan's T10).
- The **step and time caps** (B2) and the **URL guard** (B3), always.
- **Stop reasons:** browser-use's outcome maps onto `browse_goal`'s own (`done`, `max_steps`, `max_seconds`, `refused_action`, `invalid_action`, `cancelled`).
- **Nothing reaches Browser Use's cloud.** Its gateway, cloud browser, telemetry and sync hosts are denied by the proxy, and a test proves none is attempted.
- **The same contract.** `browse_goal`'s public contract is unchanged (task, start URL, allowed domains, steps, seconds, summary), so Experts and runs don't change.

### 9.5 Small models for browser-use

| Mode | What the model must do | Candidates |
|---|---|---|
| `ultrafast` (accessibility tree, text) | Act from text quickly, and write short Python | **Qwen3.5 4B** first, **Qwen3.5 9B** if it misreads pages, and Phi-4-mini with constrained decoding |
| Default (screenshots) | Read screenshots and write Python helpers | **Gemma 4 E4B** (takes images), with **Bonsai 2 27B** (on disk, has vision) as the baseline |

browser-use 1.0 asks for code, so code quality matters more than in Autobots' loop, and a coder-tuned small model may beat a general one. Q1 measures that.

Screenshot web agents with their own action format, such as Ai2's MolmoWeb 4B and 8B, don't plug into browser-use. They would need their own loop and their own decision.

**Memory.** A 4B model (about 3.5 GB) beside Bonsai (about 13 GB) fits section 4's budget, as two local profiles on two ports. The box's 1 GiB cap (B2) covers Chromium and browser-use. The model runs on the host.

### 9.6 Compared with Autobots' own loop

| | Autobots' loop (Decision 0020) | browser-use 1.0 in the box |
|---|---|---|
| Reach | Text and links. Pages that render through scripts, or need clicks on non-link elements, may be out of reach | Clicks anything, runs page scripts, can read screenshots |
| Model | One tool call per step. A 4B model is likely enough | Writes Python. Likely 9B, or a model with vision |
| Read only | By its fixed action set | No: it types and submits under the YOLO setting, within the allowed domains ([the browser typing plan](browser-typing-and-flights.md)) |
| Dependencies | None added | Its own pinned environment in the box, reviewed |
| Work | A local profile on the `researcher` route | US-17.6 and US-17.7, plus qualifying the executor for model-written code |

**Recommended:**
1. Run browser-use 1.0 in the box as the engine for pages the text loop can't reach.
2. Keep the text loop as the default for read-mostly tasks.
3. Let the owner pick the engine per Expert or per call (D8).
4. Try a small model on the text loop first, since it needs no new dependency and gives a baseline for browser-use to beat.

## 10. Qualifying without guessing

| Tier | What runs | Passes when |
|---|---|---|
| **Q1. Route** | US-3.4's suite on the local route, three trials. Then throughput and memory: prefill and decode tokens per second, and time to first token at 8K, 32K and 64K, with peak memory from `memory_pressure` and the runtime's own report | Every capability passes in all three trials, and memory stays clear of swap. The results are kept as a qualification fixture, like Terra's and Sol's |
| **Q2. Frozen replay** | The deep research workflow in a disposable environment against recorded tool results, so every candidate reads the same web. Three runs per candidate. R2 to R6 and R8 are scored automatically, with time, calls and peak memory | R2 to R6 and R8 hold in at least two of three runs |
| **Q3. Live** | One owner-approved run of the workflow on the chosen model with real tools, which costs tool spend only. The owner decides the gate | R1 to R9 hold. The owner reads `content.md` and `review.md` beside run 5's |

**What Q2 needs first.** Whether the run record keeps whole tool results must be verified: Studio shows some as "340 bytes, not shown". If it doesn't, a recording run captures them through a recording tool provider, and that run's tool spend is approved by the owner.

**When a model counts:**
- It's **offered** after Q1.
- It **matches run 5** after Q3.

## 11. Phases

| Phase | Work | Exit |
|---|---|---|
| **P0. Decide and measure** (no app code) | The owner's decision record. Download the chosen candidates with pinned revisions. Serve each and measure Q1's throughput and memory by hand. The owner lowers Docker's memory limit | A table of measurements and a shortlist of at most three models |
| **P1. Backlog** | Ingest [section 13](#13-draft-stories-in-specs-style) with `autobots-spec-ingest` from the decision | Stories READY in `SPECS.md` |
| **P2. Local route** | US-17.1, US-17.2 and US-17.3 | A local profile qualified, and the Model source setting switching between OpenRouter and Local |
| **P3. Fit the run** | US-17.4: the frozen replay and the local Expert or workflow versions | Q2 passes for one model |
| **P4. Live** | US-17.5: Q3, then a "Deep research, local" section in the README and optionally a film | R1 to R9 observed |
| **P5. Browsing** | US-17.6 and US-17.7 after D8 and D9. A scripted model first, then one live browse of `example.com` and `iana.org` on the local `researcher` route, as Decision 0019 S6 did | `browse_goal` on browser-use returns its summary with the allowed domains holding and nothing sent to Browser Use's cloud |

## 12. Decisions the owner makes

| # | Question | Options, recommended first |
|---|---|---|
| D1 | Allow local models, and how? | **A Model source setting: OpenRouter (the default, today's profiles and role defaults) or Local (qualified local profiles only). One source at a time, never mixed, never a fallback** · local profiles beside OpenRouter's, chosen per run · no |
| D2 | Which runtimes? | **MTPLX for Bonsai and the Qwen3.5 packs, with its `server` extra (`llguidance`) pinned in an isolated environment.** mlx-lm or llama.cpp only for a model with no MTPLX pack · one runtime per model |
| D3 | Which downloads? | **Bonsai (on disk), plus at most two small models from section 5.2**, each with its size and license shown first |
| D4 | Memory | **Lower Docker's VM limit to what Supabase uses, plus headroom.** Leave the GPU's wired limit at the default unless P0 shows it binds. Both are the owner's own settings |
| D5 | Limits for local routes | **Set per route from P0's measurements:** call time (L4, 300 s today), active minutes (L2, 45 today) and context (L6, 64K today) |
| D6 | A citation and anchor gate in code? | **Not now:** the check step stays responsible, and Q2 shows whether that holds · add one as its own story |
| D7 | Does a local Expert or workflow version count as "the same"? | **Yes, if its tool grant and outputs are unchanged** · no, the instructions must be identical |
| D8 | Which browsing engine? | **browser-use 1.0 in the isolated box beside Autobots' loop, chosen per Expert or per call.** If [the browser typing plan's](browser-typing-and-flights.md#10-decisions-the-owner-makes) T4 is taken, the YOLO setting chooses instead · replace the loop with browser-use · keep only the loop |
| D9 | May model-written code run inside the box? | **Yes, inside the isolated executor only, limited to the allowed domains by the egress proxy and to no downloads by Chromium's policy.** Typing and submitting follow the owner's YOLO setting, on by default ([the browser typing plan](browser-typing-and-flights.md), T1), which amends Decision 0018 B5. It needs the executor qualified for it · no, which rules out browser-use 1.0 |
| D10 | What happens to a run started before a switch of Model source? | **Its calls on the switched-off source are refused as `model_source_disabled`, and it waits until the owner switches back, cancels or starts a linked new run** · it finishes on its frozen source |
| D11 | Local role defaults | **One general model for every role, and a small model for `researcher` once one qualifies for browsing**, all set from Q1 and Q2 · one model for every role |

## 13. Draft stories in SPECS style

For ingestion after the owner's decision record on section 12. The identifiers are proposals, and ingestion assigns the real ones.

### US-17.1: A local model route

As a workspace owner
I want a run to use a model served on this Mac
So that the work costs nothing in model spend and its prompts never leave the Mac.

Acceptance Criteria:

```gherkin
Scenario: A local route answers through the shared gateway
  Given a qualified local profile and its runtime serving the pinned model on 127.0.0.1
  When a run admitted on that profile makes a model call
  Then the call goes to the loopback URL with the frozen wire ID, reserves US$0, and counts its tokens against the run's budgets

Scenario: A different model refuses, with no substitute
  Given the runtime serves a model whose identity differs from the profile's manifest
  When a run on that profile makes a model call
  Then the call is refused as model_unavailable and no other model is tried

Scenario: A stopped runtime blocks inference only
  Given the local runtime isn't running
  When a run on a local profile starts
  Then inference is blocked with a reason to show, and settings, files and other runs are unaffected
```

Dependencies:
- The owner's decision record on section 12

### US-17.2: Local route qualification and offering

As a workspace owner
I want a local profile offered only after its route passes the same suite as Terra and Sol
So that a run never depends on an untested model.

Acceptance Criteria:

```gherkin
Scenario: A local route qualifies without spending
  Given a running local runtime
  When US-3.4's suite runs on the local route three times
  Then each capability's result, throughput, time to first token and peak memory are recorded, and nothing is charged

Scenario: An unqualified local profile isn't offered
  Given a local profile whose route hasn't passed the suite
  When a new run names it
  Then it is refused as model_not_offered
```

Dependencies:
- US-17.1

### US-17.3: A model source setting: OpenRouter or local

As a workspace owner
I want one setting that sends every model call to OpenRouter or to local models only
So that I choose where prompts go, with today's OpenRouter defaults unless I switch.

Acceptance Criteria:

```gherkin
Scenario: OpenRouter is the default, as today
  Given a new workspace
  When its model policy is shown
  Then Model source is OpenRouter, and every role resolves as MP-01 says today: Terra, with researcher on Sol once Sol is offered

Scenario: Local can't be chosen before a local model qualifies
  Given no qualified local profile covers the executor role
  When the owner switches Model source to Local
  Then the switch is refused with the roles that have no qualified local model, and the source stays OpenRouter

Scenario: Local sends nothing to OpenRouter
  Given Model source is Local and the local runtime is serving its pinned model
  When a run runs to the end
  Then every model call went to the local runtime, no request reached OpenRouter, including its catalog, and the composer said so before Run

Scenario: A run on a switched-off source waits
  Given a run admitted on an OpenRouter route is waiting for an approval
  When the owner switches Model source to Local and approves
  Then its next model call is refused as model_source_disabled, the run waits with that reason, and nothing is sent to either source

Scenario: Switching back restores saved choices
  Given role overrides saved under OpenRouter
  When the owner switches to Local and back to OpenRouter
  Then the OpenRouter overrides are as they were
```

Dependencies:
- US-17.2

### US-17.4: A frozen-web replay of the deep research workflow

As a workspace owner
I want candidate models compared on the same recorded web pages
So that differences come from the model, not from what the web returned that day.

Acceptance Criteria:

```gherkin
Scenario: A replay scores a run without a model judge
  Given recorded tool results for the deep research workflow and a disposable environment
  When the workflow runs on a candidate route
  Then the plan's completion, the source count, the word count, the table of contents' anchors, every citation's target and the report's status rule are scored in code
```

Dependencies:
- US-17.3

### US-17.5: Deep research on a local model, live and documented

As a workspace owner
I want the deep research workflow run once live on the qualified local model
So that I can see it match the OpenRouter run, or see where it falls short.

Acceptance Criteria:

```gherkin
Scenario: The live run is compared with run 5
  Given the owner approves one live run on the chosen local model
  When the workflow runs and the owner decides its approval
  Then R1 to R9 of the plan are recorded against run 5's figures, and the README reports the outcome as observed
```

Dependencies:
- US-17.4

### US-17.6: An admitted model endpoint for the browser box

As a workspace owner
I want every model call browser-use makes to be an admitted call of the run
So that browsing spends, counts and stops under the same budgets and receipts as everything else.

Acceptance Criteria:

```gherkin
Scenario: A request from the box is one admitted call
  Given a browse_goal call running browser-use in the isolated executor on a run's frozen researcher route
  When browser-use sends a chat completion to the endpoint
  Then it is admitted as one call of the run, with a reservation, an invocation ticket and a receipt, counted in model_calls, and answered by that route only

Scenario: A request past the run's limits is refused
  Given the run's budget, model calls or time is exhausted, or the run is cancelled
  When browser-use sends another request
  Then the endpoint refuses it with a typed reason, browser-use stops, and browse_goal reports its stop reason

Scenario: Only the box can reach the endpoint
  Given the endpoint is serving a browse
  When a request reaches it from anywhere but that browse's executor network
  Then it is refused
```

Dependencies:
- US-17.1, for a local route only. An OpenRouter route needs none ([the browser typing plan](browser-typing-and-flights.md#10-decisions-the-owner-makes), T11)
- Decision 0018 and Decision 0020 as amended by D8 and D9

### US-17.7: browse_goal on browser-use in the isolated executor

As a workspace owner
I want browse_goal able to run browser-use inside the isolated executor
So that pages Autobots' text loop can't reach are readable, within the allowed domains.

Acceptance Criteria:

```gherkin
Scenario: The domains and the box hold
  Given browser-use is driving the box's Chromium on an allowed domain
  When a page or the model goes to a host outside the allowed domains, or starts a download
  Then the egress proxy or Chromium's policy refuses it, and the browse continues or stops with refused_action

Scenario: Nothing reaches Browser Use's cloud
  Given a browse on the local researcher route
  When it runs to the end
  Then the proxy log shows no request to Browser Use's gateway, cloud browser, telemetry or sync hosts

Scenario: The contract is unchanged
  Given an Expert granted browse_goal
  When it browses on browser-use
  Then the call takes the same inputs, waits for approval as the YOLO setting says, and returns a summary and one of the same stop reasons
```

Dependencies:
- US-17.6

## 14. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| **Quality gap** | A small model may not write a 2,000-word, evidence-backed guide with correct citations, and its check step may miss overclaims | Q2 and Q3, the owner's reading, and Bonsai as the baseline |
| **Speed** | Runs of 30 to 60 minutes bump into call-time and active-time limits | Prefix caching, D5's per-route limits, and a split workflow |
| **Memory pressure** | Docker, the Studio and the model compete. Swapping slows everything | D4. Never serve past the memory fit (MTPLX's `--allow-swap` stays off) |
| **Runtime churn** | MTPLX and MLX change quickly | Pin the runtime and weights versions in a manifest, and qualify again after any change |
| **Licenses** | Terms differ by model | Show each license before a download (D3) |
| **Local exposure** | Any process on this Mac can call a loopback server | One-owner Mac. No key in the workspace. Untrusted page text reaches prompts exactly as it does today |
| **"Local" covers models only** | An owner may read Local as "nothing leaves the Mac", but search and page reads still do | The setting and the composer's disclosure say tool calls still leave the Mac |
| **"Free" is partial** | SerpApi and Jina still charge per call | R9 counts tool spend separately |
| **Model-written code in the box** | browser-use 1.0 runs Python the model writes, steered by page text | The box's isolation is the only guard: no host folders, no keys, and egress through the proxy to the allowed domains only (D9). With YOLO on, it may also type and submit there ([the browser typing plan](browser-typing-and-flights.md#12-risks)) |
| **Cloud by default** | A missing `llm` or `Browser(...)` sends work to Browser Use's gateway or cloud browser | The proxy denies those hosts, and US-17.7 proves none is attempted |
| **browser-use churn** | Five releases in a week, and a 1.0 rewrite | Pin the exact version in the box's environment, and qualify again on every change |

## 15. Sources consulted

- **This repository:**
  - `AGENTS.md`, `.claude/rules/model-gateway.md`, the [option B contract](../engineering/option-b-contract.md) and [PRD-Model-Providers.md](../PRD/PRD-Model-Providers.md).
  - Decisions [0019](../engineering/decisions/0019-sol-profile-and-browser-use.md) and [0034](../engineering/decisions/0034-deep-research-like-content-writer.md).
  - `services/agent/src/autobots/domain/models.py`, `adapters/models/factory.py`, `adapters/models/catalog.py`, `operations/route_qualification.py` and `services/agent/uv.lock`.
  - [README-Deep-Research-Content-Writer.md](../../README-Deep-Research-Content-Writer.md).
  - The earlier local research: [LOCAL-MODEL-EVIDENCE.md](../../research/LOCAL-MODEL-EVIDENCE.md), [QWEN38-GGUF-TEST-RESULTS.md](../../research/QWEN38-GGUF-TEST-RESULTS.md) and [HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md](../../research/HUGGINGFACE-SLM-STRUCTURED-OUTPUT.md).
  - `contracts/settings.py` and `application/provider_settings.py`.
  - The run pages captured for the film on 2026-11-19: Budgets and Usage of runs `91961372`, `2b92ee84` and `36377769`.
- **This Mac:**
  - `~/Models/README-MODELS.md`, `DOWNLOAD-MANIFEST.json` and `SMOKE-TESTS.json`.
  - Bonsai's `config.json`, `chat_template.jinja` and `README.md`.
  - `~/Models/.runtimes/mtplx-serve-help.txt`.
  - `docker info`, and `sysctl hw.memsize iogpu.wired_limit_mb`.
- **The web:**
  - [5 Small Language Models for Agentic Tool Calling (KDnuggets)](https://www.kdnuggets.com/5-small-language-models-for-agentic-tool-calling).
  - [Small Language Models for Agentic AI in 2026 (Future AGI)](https://futureagi.com/blog/small-language-models-agentic-ai-2025/).
  - [A hands-on survey of Gemma 4 E4B and Qwen3.5 against Qwen3-8B under mlx_lm.server](https://github.com/changtimwu/livekit-nv-models/issues/8).
  - [Small Language Models for Agentic Systems: a survey](https://arxiv.org/pdf/2510.03847).
  - [Bonsai's model card](https://huggingface.co/Youssofal/Ternary-Bonsai-2-27B-MTPLX-Optimized-Speed).
- **Browsing:**
  - [browser-use on GitHub](https://github.com/browser-use/browser-use) and [on PyPI](https://pypi.org/project/browser-use/), version 1.0.6 and its pins, read on 2026-11-19.
  - [browser-harness](https://github.com/browser-use/browser-harness).
  - [The openrouter SDK on PyPI](https://pypi.org/project/openrouter/), 1.3.194, `pydantic<3,>=2.11.2`.
  - [MolmoWeb (Ai2)](https://allenai.org/blog/molmoweb).
  - Decisions [0018](../engineering/decisions/0018-browser-executor.md) and [0020](../engineering/decisions/0020-own-browsing-loop.md), `application/browsing_loop.py`, `contracts/browsing.py`, and `services/agent/pyproject.toml` and `uv.lock`.
