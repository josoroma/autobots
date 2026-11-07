# Decision 0019: Sol as a third profile for browsing, browser-use's dependencies, and a capped live trial

**Date:** 2026-11-07. **Authority:** the owner, who allowed `openai/gpt-6.1-sol-20260929` in their OpenRouter guardrail beside Terra and DeepSeek Flash, asked to try browsing with it, and then chose three options when asked: **Sol as a third approved profile, bound to the `researcher` role that browsing uses, its route qualified live before any run uses it**; **drop the unused `langchain-mcp-adapters` pin** so browser-use can be added; and **US$1 per live browse trial**. This amends [SP-006](../option-b-contract.md#sp-006--approved-model-profiles), [MP-01](../../../PRD-Model-Providers.md#mp-01-approved-models-and-selection) and [Decision 0018](0018-browser-executor.md) B7 and B8.

## Decision

| # | Choice |
|---|---|
| **S1. Profile** | `openrouter_sol`: canonical `openai/gpt-6.1-sol-20260929`, request ID `openai/gpt-6.1-sol`, as OpenRouter's public catalog listed it on 2026-11-07 (US$2 / US$10 per 1M tokens; tools, structured outputs and reasoning supported). No Pro, batch or moving alias stands in for it |
| **S2. Approved set** | Three profiles: DeepSeek Flash, Terra and Sol. Sol is approved but **not offered for new runs until its route is qualified** (S4), with the same refusal DeepSeek has (`model_not_offered`, no substitute) |
| **S3. Researcher's default** | Once Sol is offered, the built-in default for the `researcher` role is Sol; every other role's stays Terra. It sits last in MP-01's order, in place of Terra for that role only: a run's role override, a run-wide profile, a workspace role override and a workspace default all still win |
| **S4. Route qualification** | Sol's route is qualified live with US-3.4's runner and suite, counted at worst case against a cap of **US$1.20** (Terra's; Terra's suite reported US$0.013 and counted US$0.12, and Sol costs twice as much per token). Its stored qualification and limits appear in Settings like the others' |
| **S5. browser-use** | `langchain-mcp-adapters` is removed: nothing imports it (CODEBASE), and its `mcp<2` pin conflicts with every browser-use release that fits `deepagents`. `browser-use==0.13.14` is added, pinned in `uv.lock`. Its telemetry (posthog) and cloud sync are switched off before it is imported, and a test proves no telemetry client is created. Its other providers' SDKs come with it and are never constructed (Decision 0018 BM-02) |
| **S6. Live browse trial** | **One** live `browse_goal` trial with a real model, on the owner's key read from the key file by the trial's own process, through the shared gateway on the `researcher` route (Sol), capped at **US$1** for the run. Read only, starting at `https://example.com/` with `allowed_domains` `example.com` and `iana.org`. A repeat needs the owner's request |

**What "qualified" means for S2.** Sol is offered once US-3.4's suite has run on its route within the cap and its plain text, tool calls (automatic and required), flat structured output and streamed text each passed in all three trials. A capability that failed or isn't supported stays disabled and is listed in its limits, as for Terra and DeepSeek.

**These are the paid calls the delivery rule asks the owner for.** S4's qualification and S6's trial are authorized here, once each, within their caps. Anything beyond them stops and asks.

## Requirements revised

- SP-006 and MP-01: three approved profiles, with S2's offering rule and S3's default.
- `AGENTS.md` and `.claude/rules/model-gateway.md`: "the approved OpenRouter profiles" in place of "two".
- Decision 0018 B7: the dependency is as S5. B8: a real-model run is now authorized as S6, once.

## What this gives up

- **More spend per call.** Browsing on Sol costs about twice Terra's per token.
- **A wider dependency tree.** browser-use brings other providers' SDKs, telemetry code (off) and `pyobjc` on macOS. Removing `langchain-mcp-adapters` changes US-1.3's toolchain record.
- **Three profiles to keep current.** Each is qualified on its own, and Settings shows each one's limits.

## What this doesn't establish

That browsing is reliable. One trial shows one browse on one site. Neither H1 nor product acceptance follows.

## Reversal

Remove Sol from the approved set by migration, as Decision 0004 removed Astra: runs that froze it stop rather than move to another model. Restore the dependency pin by removing browser-use, which disables `browse_goal` again.
