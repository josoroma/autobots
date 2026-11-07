# Decision 0020: Autobots' own browsing loop in place of browser-use

**Date:** 2026-11-07. **Authority:** the owner. When browser-use couldn't be installed, they chose **"Own browsing loop"** over upgrading the OpenRouter SDK or forcing `pydantic`. browser-use 0.13.14, the only release that fits `deepagents`' Anthropic SDK, pins `pydantic==2.13.5`; `openrouter==0.11.46`, the SDK all three routes were qualified on, requires `pydantic<2.13`. This amends [Decision 0017](0017-tool-catalog.md) C3 and C4, [Decision 0018](0018-browser-executor.md) B7 and its admitted-model shape, and [Decision 0019](0019-sol-profile-and-browser-use.md) S5.

## Decision

| # | Choice |
|---|---|
| **L1. No browser-use** | browser-use isn't added, and `langchain-mcp-adapters` stays as it was. No package is added: the loop drives the isolated executor over CDP with the `websockets` client already locked |
| **L2. The loop** | A bounded agent loop in the worker. Each step shows the model the page as text: its URL, title, a cut of its readable text and its links, numbered. The model answers with one action from a fixed set, as a tool call: open a numbered link, go to a URL, scroll, or finish with a summary. Nothing types, submits, signs in, uploads or downloads (Decision 0018 B5) |
| **L3. Admission** | Every step is one admitted call of the run on its frozen `researcher` route, through the same admission the goal loop uses: a reservation, an invocation ticket and receipt, the run's budget and `model_calls`, the shared transport. No other model client exists for browsing |
| **L4. Structured actions** | Actions are tool calls with typed arguments, required on every step. A route whose catalog entry lacks tool support is refused with a typed code before anything is sent. All three routes passed `tool_required` in their qualification |
| **L5. What stays** | Decision 0018's executor, egress proxy, allowed domains, read-only rule, step and time limits, approval on every call and US$1 trial cap all stand. `browse_goal`'s provider becomes `autobots` |
| **L6. An invalid answer** | An answer that isn't exactly one valid action (no tool call, several, an unknown action, or arguments that don't fit) ends the call with `stopped: invalid_action`, keeping the notes so far as the summary, like a refused action. Retrying would spend more on a model already off course |

## Requirements revised

- PRD-Tool-Catalog: "Admitted browser model" becomes the browsing loop (BM-01 to BM-04 restated), and "Autonomous browsing" no longer names browser-use.
- Decision 0019 S5 no longer applies: nothing is removed or added.
- PRD-Tool-Catalog "Autonomous browsing": `stopped` gains `invalid_action` (L6).

## What this gives up

- **browser-use's maturity.** Its element detection, visual grounding and recovery heuristics are years of work. This loop reads text and links only, so pages that render content through scripts or need clicks on non-link elements may be out of reach.
- **Its action vocabulary.** Read-only links, navigation and scrolling only.

## Reversal

If a browser-use release fits the lock later, a decision can add it behind the same admission, and `browse_goal` keeps its contract.
