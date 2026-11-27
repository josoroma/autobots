# Decision 0041: A Model source setting, OpenRouter or a local model on this Mac

**Date:** 2026-11-27. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The request:** "a setting in settings page that allows to change from the openrouter models we have been using so far to use a SLM local model (~/Models) like: Inkling 2 Mini and [Bonsai 2.5 27B]". The scope is "all we have done so far", that is, the three live runs.
- **The record:** "Record the decisions", on [the plan's section 10](../../plan/local-models-every-run.md#10-decisions-the-owner-makes). That section recommends an answer to each of L1 to L8, and those answers are recorded here. One is reshaped (A7) so that a model can be tried live on the Local source before it has matched a run.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0035 to 0040. Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse. The owner can change any of them.

This amends [Decision 0019](0019-sol-profile-and-browser-use.md) S2, [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y7, and the requirements below. It schedules EPIC-23, ingested after A15's measurements ([the plan's P1](../../plan/local-models-every-run.md#9-phases)).

## Context

- **Today every model call goes to OpenRouter.** `AGENTS.md`, [the model gateway rule](../../../.claude/rules/model-gateway.md), [PRD-Model-Providers](../../PRD/PRD-Model-Providers.md) and SP-006 rule out a local model server. [The earlier plan's section 3](../../plan/local-small-models.md#3-why-this-needs-a-decision-first) lists each rule.
- **Browsing already goes through the gateway.** Every chat call browser-use makes in the box reaches an endpoint the worker serves, and is admitted on the run's frozen `researcher` route (Y7, US-17.2). So a local route in the gateway reaches browsing too, without changing the box.
- **The candidates are the publishers' claims.**
  - Inkling 2 Mini: 26.4B parameters, 3.4B active, released 2026-11-20. Its official weights are in NVIDIA formats, and its card names GGUF builds for llama.cpp on a Mac.
  - Ternary Bonsai 2.5 27B: released 2026-11-24. Its Q2_0 GGUF runs on stock llama.cpp from release b11556.
  - [The plan's section 3](../../plan/local-models-every-run.md#3-the-two-models) has the details.
- **This Mac.** An M3 Pro with 36 GiB, which also runs the Studio and Supabase in Docker.
- **Nothing has been measured.** Neither model has been downloaded or run here.

## Decision

| # | Choice |
|---|---|
| **A1. Model source** (L1, D1) | A workspace setting, **Model source**: **OpenRouter**, with today's profiles and role defaults, or **Local**, with qualified local profiles only. One source at a time. A run never mixes them, and neither falls back to the other. A new install starts on OpenRouter, so nothing changes until the owner switches. Only an owner or admin changes it (MP-05). The default profile and role overrides are kept per source, so switching back restores them |
| **A2. The local route** | The shared gateway answers a local profile from an OpenAI-compatible server on `127.0.0.1`, through the one model factory, with no SDK retries. Admission, invocation tickets, receipts, `model_calls`, compaction and the tools are unchanged. A local call reserves US$0, and its tokens, calls, tool dispatches and time still count against the run's limits. A local route has no key, and its port is ordinary non-secret configuration |
| **A3. Identity** | A local profile names the Hugging Face repository at its revision, the weights file's SHA-256 and the chat template's hash, and the model ID the server reports. Before a call, the gateway checks `/v1/models`. A different model is refused `model_unavailable`, with no substitute. A server that isn't running blocks inference with a reason to show, and leaves settings, files and other work alone (MP-08) |
| **A4. The runtime** (L2) | llama.cpp's `llama-server`, release b11556 or later, for both models, bound to `127.0.0.1` only. PrismML's fork is used only if Q2_0 falls short and PQ2_0 measures better. Ollama is used only if llama.cpp can't serve Inkling's looped layers. MTPLX stays for the Bonsai 2 baseline already in `~/Models`. The owner starts the server with a runbook command, as with Supabase. The Studio and hooks never start it and never download weights (`AGENTS.md`) |
| **A5. Downloads** (L3) | llama.cpp, Bonsai 2.5's Q2_0 (about 7.5 GB) and one Inkling 2 Mini GGUF that fits. Before each is fetched, its size, source and license are shown and the owner says yes. Each is pinned in `~/Models` with its revision and SHA-256 in `DOWNLOAD-MANIFEST.json`, and checked by `verify-models.py`. No weights enter the repository, a run's files or evidence |
| **A6. Inkling's policy** (L7) | Before Inkling is downloaded, the owner reads Thinking Machines' Model Acceptable Use Policy, as Decision 0035 Y14 had the owner read YouTube's terms |
| **A7. Offered, matched and switching** (L6, reshaped) | A local profile is **offered** once US-3.4's suite passes on its route three times, at no spend. Switching to Local is refused until offered profiles cover `executor`, and also `researcher` while any Expert grants `browse_goal`. The refusal names what is missing. A profile has **matched** a run once that run's live check holds on the Local source. Settings shows which runs each profile has matched, and a README claims only those. The recommended L6 made matching a gate, but a live check runs on the Local source itself, so a gate would make it impossible to run |
| **A8. One model for every role** (L4, D11) | The Local source sets every role to one local profile, since two models don't fit in memory together. A second profile for `researcher` waits until measurements show both fit. So on Local, role overrides aren't offered. The Local default profile answers every role, a workspace role override can't be saved, and a run that names a role override is refused `model_not_offered`. OpenRouter's saved overrides are kept (A1) |
| **A9. Thinking** (L5) | A local route asks the server to turn reasoning off where the model's template allows, and otherwise to return it in its own field, outside the reply. If reasoning still counts against the reply, that route gets a larger output cap, set under A11 |
| **A10. Browsing follows the source** | The admitted endpoint answers on the run's frozen `researcher` route, so on Local, browser-use's calls reach the local model. The box is unchanged and never learns the server's address. Y16 still refuses an image the route isn't qualified for, so on Local, browsing works from text until a local route qualifies for images |
| **A11. Limits per local route** (D5) | The call time (Decision 0034 L4, 300 seconds), the active minutes (L2, 45), the context (L6, 64K) and the output cap (4,096 tokens) are set for each local route from A15's measurements. Until then, today's limits apply |
| **A12. Runs during a switch** (D10) | A model call whose frozen route belongs to the source just switched off is refused at dispatch as `model_source_disabled`. Nothing is sent to either source. The run waits with that reason until the owner switches back, cancels it, or starts a linked new run on the active source (MP-01) |
| **A13. Settings and disclosure** | Settings → Models gains a Model source panel above the provider panel and the model policy. It shows each local profile's state (offered or not, and why), the runs it has matched, the runtime's health with the model ID it serves and whether the pinned SHA-256 matches, the roles it covers, and "US$0.00 per model call", noting that tool calls such as SerpApi, Jina and YouTube still leave the Mac. On Local, the composer's disclosure says nothing goes to OpenRouter, and Home's Services panel shows "Local model ready" from the health check. On Local, nothing is sent to OpenRouter, including its catalog |
| **A14. A local Expert version** (D7) | A version of an Expert written for a local model, such as shorter instructions or a document written in parts, counts as the same Expert if its tool grant and its outputs are unchanged |
| **A15. Measure first** (D4) | Before any story, each model is served by hand and measured with the whole Studio running: reading and writing speed, time to the first token and peak memory at 8K, 32K and 64K, each chat template's tool format, and which thinking switches it honours. The owner lowers Docker's VM memory limit to what Supabase uses plus headroom. The GPU's wired limit stays at the macOS default unless the measurements show it binds. Both are the owner's own settings |
| **A16. The order** | Market watcher, then deep research, then the Transcript, which adds browsing. Only one model is served at a time. Each run's checks are [the plan's section 8](../../plan/local-models-every-run.md#8-qualifying-run-by-run) |
| **A17. Not in this decision** | Choosing a source per run, two local models at once, other runtimes for new models (mlx-lm, MTPLX), images on local routes, a remote or cloud GPU, a citation gate in code (D6), and any model but the two candidates and the baseline. Each needs its own decision |
| **A18. Required tool calls on a local route** | A call that requires a tool call, by `tool_choice` `required` or a named tool, is enforced by the local route itself. It asks the server for a reply constrained by a JSON schema to one call of a tool the request offers, or of the named tool only, with arguments matching that tool's parameters, and turns that reply into the tool call. A reply cut off by its output cap is reported as cut off, as on any route. A reply that otherwise doesn't parse or doesn't match fails that call, and the route never repairs it, retries it or passes it on as text. A call that leaves the choice to the model is sent as before. This is the route's behaviour, not a run's option, so US-3.4's suite qualifies the route as the gateway sends it (A7). Structured output, nested schemas included, is not changed by this row |

## Set from the measurements

A15's measurements ran the same day: [both models on this Mac](../../../research/LOCAL-MODELS-INKLING-BONSAI.md). These are the session's choices under A11, from what was measured. The owner can change any of them.

| Route | Offered? | Context | Output cap | Call time | Active time | Calls and tools |
|---|---|---|---|---|---|---|
| **Bonsai 2.5, Q2_0**, every role (A8) | When US-3.4's suite passes three times (A7). It passed every by-hand probe | 64K, as today | 4,096 tokens, with thinking off by `enable_thinking: false` (A9) | 1,800 seconds. A reply of 4,096 tokens took up to 17 minutes to write at 62K, and reading 30,000 new tokens up to 11 minutes | 240 minutes. Deep research is expected to take 1.5 to 3 hours | As today (Decision 0034 L2) |
| **Inkling 2 Mini, UD-Q3_K_XL** | Not until US-3.4's suite passes. Under llama.cpp 1.1.0 a required tool call failed, so the suite can't pass yet | 64K | 8,192 tokens, because reasoning can't be turned off and counts against the reply (A9) | 1,800 seconds | 240 minutes | As today |

## The owner's later choices

- **2026-11-27, US-23.2:** "Start US-23.2", answering whether to start Bonsai 2.5's server and qualify its route. It meets the External dependency US-23.2 carried: `llama-server` is started by the runbook command (A4), with its weights checked against `~/Models/DOWNLOAD-MANIFEST.json` (A5), and the route's qualification is asked for.
- **2026-11-27, after US-23.2:** "Decide it", answering "Should I record the decision for option 1 (have local routes enforce required tool calls themselves, then requalify Bonsai), or deliver US-23.3 first?" US-23.2 had recorded Bonsai 2.5's route as not qualified, because llama.cpp 1.1.0 didn't enforce a required tool call for its template. That answer records A18 and asks for Bonsai 2.5's route to be qualified again, against `llama-server` started by the runbook command (A4). A18 also answers US-23.5's open question on tool calls constrained to their schema: a local route sends the constraint with a required tool call, and it's the route's behaviour, not the run's.

## Requirements revised

The stories amend these in their own changes:
- **`AGENTS.md`**, "Boundaries that matter", and **the model gateway rule:** model calls use the approved OpenRouter profiles or, on the Local source, offered local profiles, through the shared gateway. There is still no fallback, implicit evaluator, hosted tracing or other provider.
- **PRD-Model-Providers:**
  - Its introduction and MP-01: the source, and resolution within it (A1, A8).
  - MP-02: A3 proves a local route's identity in place of OpenRouter's catalog.
  - MP-02's local routes: a required or named tool call is enforced by the route (A18).
  - MP-04 and MP-05: the setting's states and who changes it (A1, A7, A13).
  - MP-07: US$0 spend and the disclosure (A2, A13).
  - MP-08: a stopped or wrong server (A3).
- **[Decision 0005](0005-deepseek-strict-nested-unsupported.md)'s "nothing in the application asks for it":** it still holds for every OpenRouter route. On a local route, A18's constraint on a required tool call is the one request outside the qualification runner that sets `response_format`, and the local route's flat structured output passed qualification (A7).
- **[Option B contract](../option-b-contract.md):** SP-006 (approved profiles, A1) and SP-008 (budgets and qualification, A2, A7, A11).
- **[PRD-Local-Mac-Deployment](../../PRD/PRD-Local-Mac-Deployment.md):** LM-A03, the inference boundary, and its resources section, for the owner-started runtime (A4, A15).
- **[PRD-LangChain-Deep-Agents](../../PRD/PRD-LangChain-Deep-Agents.md):** its scope, which puts local inference engines outside the design.
- **Decision 0019 S2:** the three OpenRouter profiles, plus offered local profiles on the Local source. US-23.3 applies it: on Local, the offered local profiles are the approved set.
- **Decision 0035 Y7:** on Local, the browser box's calls reach the local model (A10). US-23.3 applies it: the admitted endpoint answers on the run's frozen local `researcher` route.
- **Rows found at ingestion that say "OpenRouter only" too:**
  - PRD-Local-Mac-Deployment LM-01, LM-06 and LM-A06;
  - option-b-contract SP-007, under which a missing OpenRouter key blocks every inference path, which is not so on Local;
  - PRD-LangChain-Deep-Agents 2.2's outcomes 7 to 9, and 6.3's OpenRouter-only model factory;
  - PRD-Tool-Catalog BM-01 and BM-03, for the browser model's route;
  - PRD-Studio HM-05 and MD-01, for Home's service chip and the model's facts;
  - the `autobots-model-gateway` skill.

  Each is amended by the story whose behavior it describes.

## What this gives up

- **Speed.** Expect a run to take several times as long as on OpenRouter.
- **Quality, perhaps.** Neither model may match Terra on deep research. Neither card claims Spanish, so the Market watcher may not pass.
- **Memory.** About 15 GB for Inkling, beside Supabase, the Studio and the box, may push this Mac into swap. Docker gets less.
- **Mixing.** A run can't use a local model for some calls and OpenRouter for the rest.
- **A rule that was easy to check.** "OpenRouter only" becomes "the active source only", enforced at admission and at dispatch.
- **Images while browsing on Local,** until a local route qualifies for them.

## What this doesn't establish

That either model runs on this Mac, serves tool calls or matches any run. Nothing has been downloaded, served or measured. The figures are the publishers'. Nothing here establishes H1 or product acceptance.

## Reversal

Set Model source back to OpenRouter, and every run is as it was before. Removing the local branch from the gateway leaves OpenRouter runs unchanged. The owner can delete the weights in `~/Models`.
