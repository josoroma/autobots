# Decision 0041: A Model source setting, OpenRouter or a local model on this Mac

**Date:** 2026-11-27. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The request:** "a setting in settings page that allows to change from the openrouter models we have been using so far to use a SLM local model (~/Models) like: Inkling 2 Mini and [Bonsai 2.5 27B]". The scope is "all we have done so far", that is, the three live runs.
- **The record:** "Record the decisions", on [the plan's section 10](../../plan/local-models-every-run.md#10-decisions-the-owner-makes). That section recommends an answer to each of L1 to L8, and those answers are recorded here. One is reshaped (A7) so that a model can be tried live on the Local source before it has matched a run.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0035 to 0040. Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse. The owner can change any of them.

This amends [Decision 0019](0019-sol-profile-and-browser-use.md) S2, [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y7, and the requirements below. It schedules nothing yet. Its stories are ingested after A15's measurements ([the plan's P1](../../plan/local-models-every-run.md#9-phases)).

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
| **A8. One model for every role** (L4, D11) | The Local source sets every role to one local profile, since two models don't fit in memory together. A second profile for `researcher` waits until measurements show both fit |
| **A9. Thinking** (L5) | A local route asks the server to turn reasoning off where the model's template allows, and otherwise to return it in its own field, outside the reply. If reasoning still counts against the reply, that route gets a larger output cap, set under A11 |
| **A10. Browsing follows the source** | The admitted endpoint answers on the run's frozen `researcher` route, so on Local, browser-use's calls reach the local model. The box is unchanged and never learns the server's address. Y16 still refuses an image the route isn't qualified for, so on Local, browsing works from text until a local route qualifies for images |
| **A11. Limits per local route** (D5) | The call time (Decision 0034 L4, 300 seconds), the active minutes (L2, 45), the context (L6, 64K) and the output cap (4,096 tokens) are set for each local route from A15's measurements. Until then, today's limits apply |
| **A12. Runs during a switch** (D10) | A model call whose frozen route belongs to the source just switched off is refused at dispatch as `model_source_disabled`. Nothing is sent to either source. The run waits with that reason until the owner switches back, cancels it, or starts a linked new run on the active source (MP-01) |
| **A13. Settings and disclosure** | Settings → Models gains a Model source panel above the provider panel and the model policy. It shows each local profile's state (offered or not, and why), the runs it has matched, the runtime's health with the model ID it serves and whether the pinned SHA-256 matches, the roles it covers, and "US$0.00 per model call", noting that tool calls such as SerpApi, Jina and YouTube still leave the Mac. On Local, the composer's disclosure says nothing goes to OpenRouter, and Home's Services panel shows "Local model ready" from the health check. On Local, nothing is sent to OpenRouter, including its catalog |
| **A14. A local Expert version** (D7) | A version of an Expert written for a local model, such as shorter instructions or a document written in parts, counts as the same Expert if its tool grant and its outputs are unchanged |
| **A15. Measure first** (D4) | Before any story, each model is served by hand and measured with the whole Studio running: reading and writing speed, time to the first token and peak memory at 8K, 32K and 64K, each chat template's tool format, and which thinking switches it honours. The owner lowers Docker's VM memory limit to what Supabase uses plus headroom. The GPU's wired limit stays at the macOS default unless the measurements show it binds. Both are the owner's own settings |
| **A16. The order** | Market watcher, then deep research, then the Transcript, which adds browsing. Only one model is served at a time. Each run's checks are [the plan's section 8](../../plan/local-models-every-run.md#8-qualifying-run-by-run) |
| **A17. Not in this decision** | Choosing a source per run, two local models at once, other runtimes for new models (mlx-lm, MTPLX), images on local routes, a remote or cloud GPU, a citation gate in code (D6), and any model but the two candidates and the baseline. Each needs its own decision |

## Requirements revised

The stories amend these in their own changes:
- **`AGENTS.md`**, "Boundaries that matter", and **the model gateway rule:** model calls use the approved OpenRouter profiles or, on the Local source, offered local profiles, through the shared gateway. There is still no fallback, implicit evaluator, hosted tracing or other provider.
- **PRD-Model-Providers:**
  - Its introduction and MP-01: the source, and resolution within it (A1, A8).
  - MP-02: A3 proves a local route's identity in place of OpenRouter's catalog.
  - MP-04 and MP-05: the setting's states and who changes it (A1, A7, A13).
  - MP-07: US$0 spend and the disclosure (A2, A13).
  - MP-08: a stopped or wrong server (A3).
- **[Option B contract](../option-b-contract.md):** SP-006 (approved profiles, A1) and SP-008 (budgets and qualification, A2, A7, A11).
- **[PRD-Local-Mac-Deployment](../../PRD/PRD-Local-Mac-Deployment.md):** LM-A03, the inference boundary, and its resources section, for the owner-started runtime (A4, A15).
- **[PRD-LangChain-Deep-Agents](../../PRD/PRD-LangChain-Deep-Agents.md):** its scope, which puts local inference engines outside the design.
- **Decision 0019 S2:** the three OpenRouter profiles, plus offered local profiles on the Local source.
- **Decision 0035 Y7:** on Local, the browser box's calls reach the local model (A10).

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
