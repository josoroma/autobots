# Plan: the deep research run on local Hugging Face small models

**Date:** 2026-11-19. **Status:** a draft for the owner. Nothing here is implemented, and nothing may be until the owner decides [section 11](#11-decisions-the-owner-makes): today's rules forbid a local model server (see [section 3](#3-why-this-needs-a-decision-first)). Like the other plans in this folder, it is input for a decision and a backlog addition. [Section 12](#12-draft-stories-in-specs-style) holds stories in SPECS style, ready for ingestion once the owner approves.

The aim: repeat the run shown in the video, the Deep research content writer workflow on "langchain for deep agents" ([run 5 of README-Deep-Research-Content-Writer.md](../../README-Deep-Research-Content-Writer.md#the-workflow-execution)), with every model call answered by an open-weight model from Hugging Face served on this Mac, and get the same result. No OpenRouter call, and everything else unchanged.

## Contents

1. [The result to match](#1-the-result-to-match)
2. [What changes and what doesn't](#2-what-changes-and-what-doesnt)
3. [Why this needs a decision first](#3-why-this-needs-a-decision-first)
4. [The hardware budget](#4-the-hardware-budget)
5. [Models](#5-models)
6. [Serving them](#6-serving-them)
7. [The local route in Autobots](#7-the-local-route-in-autobots)
8. [Making small models do this run](#8-making-small-models-do-this-run)
9. [Qualifying without guessing](#9-qualifying-without-guessing)
10. [Phases](#10-phases)
11. [Decisions the owner makes](#11-decisions-the-owner-makes)
12. [Draft stories in SPECS style](#12-draft-stories-in-specs-style)
13. [Risks](#13-risks)
14. [Sources consulted](#14-sources-consulted)

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

**Changed:** only what answers each model call. A run gets a **local route**: a model served on `127.0.0.1` by a runtime the owner starts, the way they start Supabase. Tool calls still leave the Mac, since search and page reads are what the run is for.

Kokoro and faster-whisper in `~/Models` are already local, but they produced the film's voice and checked it. They are not part of the app.

## 3. Why this needs a decision first

| Rule | Where | What it says |
|---|---|---|
| Model boundary | [`AGENTS.md`](../../AGENTS.md), "Boundaries that matter" | "All application model calls use the approved OpenRouter profiles (three, by Decision 0019) and the shared gateway. No fallback, local model server, implicit evaluator, hosted tracing or alternative provider." |
| Gateway rule | [`.claude/rules/model-gateway.md`](../../.claude/rules/model-gateway.md) | "Exactly three approved profiles … No alternate provider, local model, hidden model default or fallback." |
| Approved profiles | [SP-006](../engineering/option-b-contract.md#sp-006--approved-model-profiles), [MP-01](../PRD/PRD-Model-Providers.md#mp-01-approved-models-and-selection), [Decision 0019](../engineering/decisions/0019-sol-profile-and-browser-use.md) S2 | Three OpenRouter profiles. One is offered for new runs only once its route is qualified |
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

These are the ones a search on 2026-11-19 surfaced. Phase 0 surveys the Hub again, and a model is chosen by qualification ([section 9](#9-qualifying-without-guessing)), not by its name.

| Tier | Candidate | Why | Watch |
|---|---|---|---|
| Small | Qwen3.5 4B and 9B | Apache-2.0, tool calling, long context | Thinking is on by default under some servers and spends the reply's tokens |
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

**Roles.** The run page says "Only the executor's binding dispatches in this release", so one model answers all 45 calls. One local model per route is enough for this run. The other roles, such as `researcher` for `browse_goal`, can follow once this one works.

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

| Area | File | Change |
|---|---|---|
| Profiles | `domain/models.py` | One `ModelProfileId` per qualified local model (e.g. `local_bonsai_2_27b`). The canonical ID is the Hugging Face repository at its revision, and the wire ID is the served model ID. Offering waits on qualification, as `OFFERED_FOR_NEW_RUNS` does for Sol. A local `ModelRoute` costs nothing |
| Client | `adapters/models/factory.py` | A second branch for local routes: an OpenAI-compatible client with its base URL fixed to the configured loopback port, no SDK retries (the application owns retries), and the same timeout policy. `FORBIDDEN_OPTIONS` still applies. This needs a newly locked dependency such as `langchain-openai`, since only `langchain-openrouter` is locked today |
| Identity | `adapters/models/catalog.py` | OpenRouter's catalog proves identity and parameters today. For a local route, a manifest snapshot does: the served ID from `/v1/models`, the weights' SHA-256 and the chat template's hash. A mismatch refuses the call, with no substitute |
| Budgets | `application/run_admission.py`, `application/loop_policy.py` | Reserve US$0 per local call, and keep the token, call, tool and time limits. Show "US$0.00, local" with the tokens |
| Qualification | `operations/route_qualification.py` | US-3.4's suite (plain text, automatic and required tool calls, flat structured output and streamed text, three trials each) runs against a local route. It needs no `--paid` flag, since nothing is spent, and it gates offering |
| Settings and disclosure | `apps/web` Settings → Models, the composer's disclosure (`components/runs/disclosure/`) | Local profiles with their qualification and limits. "Sent to the local model on this Mac" in place of "Sent to OpenRouter" for model calls. Tool calls still leave the Mac, and the text says so |
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

## 9. Qualifying without guessing

| Tier | What runs | Passes when |
|---|---|---|
| **Q1. Route** | US-3.4's suite on the local route, three trials. Then throughput and memory: prefill and decode tokens per second, and time to first token at 8K, 32K and 64K, with peak memory from `memory_pressure` and the runtime's own report | Every capability passes in all three trials, and memory stays clear of swap. The results are kept as a qualification fixture, like Terra's and Sol's |
| **Q2. Frozen replay** | The deep research workflow in a disposable environment against recorded tool results, so every candidate reads the same web. Three runs per candidate. R2 to R6 and R8 are scored automatically, with time, calls and peak memory | R2 to R6 and R8 hold in at least two of three runs |
| **Q3. Live** | One owner-approved run of the workflow on the chosen model with real tools, which costs tool spend only. The owner decides the gate | R1 to R9 hold. The owner reads `content.md` and `review.md` beside run 5's |

**What Q2 needs first.** Whether the run record keeps whole tool results must be verified: Studio shows some as "340 bytes, not shown". If it doesn't, a recording run captures them through a recording tool provider, and that run's tool spend is approved by the owner.

**When a model counts:**
- It's **offered** after Q1.
- It **matches run 5** after Q3.

## 10. Phases

| Phase | Work | Exit |
|---|---|---|
| **P0. Decide and measure** (no app code) | Decision 0035. Download the chosen candidates with pinned revisions. Serve each and measure Q1's throughput and memory by hand. The owner lowers Docker's memory limit | A table of measurements and a shortlist of at most three models |
| **P1. Backlog** | Ingest [section 12](#12-draft-stories-in-specs-style) with `autobots-spec-ingest` from the decision | Stories READY in `SPECS.md` |
| **P2. Local route** | US-17.1 and US-17.2 | A local profile qualified and offered |
| **P3. Fit the run** | US-17.3: the frozen replay and the local Expert or workflow versions | Q2 passes for one model |
| **P4. Live** | US-17.4: Q3, then a "Deep research, local" section in the README and optionally a film | R1 to R9 observed |

## 11. Decisions the owner makes

| # | Question | Options, recommended first |
|---|---|---|
| D1 | Allow local models? | **Local profiles beside the OpenRouter ones, never as a fallback** · local only for this install · no |
| D2 | Which runtimes? | **MTPLX for Bonsai, plus one of mlx-lm or llama.cpp for the small models, chosen by P0's measurements** · one runtime only |
| D3 | Which downloads? | **Bonsai (on disk), plus at most two small models from section 5.2**, each with its size and license shown first |
| D4 | Memory | **Lower Docker's VM limit to what Supabase uses, plus headroom.** Leave the GPU's wired limit at the default unless P0 shows it binds. Both are the owner's own settings |
| D5 | Limits for local routes | **Set per route from P0's measurements:** call time (L4, 300 s today), active minutes (L2, 45 today) and context (L6, 64K today) |
| D6 | A citation and anchor gate in code? | **Not now:** the check step stays responsible, and Q2 shows whether that holds · add one as its own story |
| D7 | Does a local Expert or workflow version count as "the same"? | **Yes, if its tool grant and outputs are unchanged** · no, the instructions must be identical |

## 12. Draft stories in SPECS style

For ingestion after Decision 0035. The identifiers are proposals, and ingestion assigns the real ones.

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
- Decision 0035

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

### US-17.3: A frozen-web replay of the deep research workflow

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
- US-17.2

### US-17.4: Deep research on a local model, live and documented

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
- US-17.3

## 13. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| **Quality gap** | A small model may not write a 2,000-word, evidence-backed guide with correct citations, and its check step may miss overclaims | Q2 and Q3, the owner's reading, and Bonsai as the baseline |
| **Speed** | Runs of 30 to 60 minutes bump into call-time and active-time limits | Prefix caching, D5's per-route limits, and a split workflow |
| **Memory pressure** | Docker, the Studio and the model compete. Swapping slows everything | D4. Never serve past the memory fit (MTPLX's `--allow-swap` stays off) |
| **Runtime churn** | MTPLX and MLX change quickly | Pin the runtime and weights versions in a manifest, and qualify again after any change |
| **Licenses** | Terms differ by model | Show each license before a download (D3) |
| **Local exposure** | Any process on this Mac can call a loopback server | One-owner Mac. No key in the workspace. Untrusted page text reaches prompts exactly as it does today |
| **"Free" is partial** | SerpApi and Jina still charge per call | R9 counts tool spend separately |

## 14. Sources consulted

- **This repository:**
  - `AGENTS.md`, `.claude/rules/model-gateway.md`, the [option B contract](../engineering/option-b-contract.md) and [PRD-Model-Providers.md](../PRD/PRD-Model-Providers.md).
  - Decisions [0019](../engineering/decisions/0019-sol-profile-and-browser-use.md) and [0034](../engineering/decisions/0034-deep-research-like-content-writer.md).
  - `services/agent/src/autobots/domain/models.py`, `adapters/models/factory.py`, `adapters/models/catalog.py`, `operations/route_qualification.py` and `services/agent/uv.lock`.
  - [README-Deep-Research-Content-Writer.md](../../README-Deep-Research-Content-Writer.md).
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
