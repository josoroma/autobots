# Decision 0004: Terra replaces Astra

**Date:** 2026-11-05. **Authority:** explicit user decision in this session: "Yes, replace Astra", after asking for an OpenAI model that's "not so expensive not so cheap but good" and approving a paid test of it.

## Decision

The second approved model profile is now `openrouter_terra`, in place of `openrouter_astra`:

| Profile | Canonical | Request ID | Input / output per 1M, on 2026-11-05 |
|---|---|---|---|
| `openrouter_deepseek_flash`, default for all 14 roles | `deepseek/deepseek-v4.1-flash-20261017` | `deepseek/deepseek-v4.1-flash-1017` | US$0.15 / US$0.60, doubling in weekday peak windows |
| `openrouter_terra`, by explicit selection | `openai/gpt-6.1-terra-20261026` | `openai/gpt-6.1-terra` | US$1 / US$5 |

The contract still has exactly two approved models, OpenRouter only, with no fallback. Everything else about selection, freezing and budgets is unchanged. This supersedes the Astra mapping in SP-006, MP-01 and MP-02, and those requirements' IDs stay.

## Why

Astra costs ten times as much, at US$10 / US$50, and was never called. Terra ran the [US-3.4 fixtures](../evidence/US-3.4/summary.md) live and passed all 12 test types.

## What this doesn't establish

- **That Terra is good at the work:** the evidence is protocol behavior, 3 trials per fixture on one day, with no task quality measured. US-10.1 still decides that.
- **That Terra runs here:** no goal has run with it through the worker. US-3.4 stays open.
- **Strict output as a general capability:** Terra refused nested schemas with open objects with a `400`, and passed with every object closed. Nothing in the application uses strict output today. Anything that starts to must close its objects.

## Consequences

- **Saved work:** a saved run's frozen policy isn't rewritten, as the contract forbids using a migration to swap a model. A run bound to Astra stops with no call sent, and continuing it means a linked new run.
- **Workspace settings:** a workspace default or role override that chose Astra returns to DeepSeek, not to Terra, so nobody moves to a model they didn't choose.
- **History:** recorded invocations keep `openrouter_astra`, because that's what ran.
- **Immutable Experts:** a published Expert version naming Astra can't be used for new work, and needs a new version. None exist on this machine.
- **Prices:** this table is what the catalog showed that day. The application reads the current price before a call and reserves against the highest rate that can apply. [The dated entries](../../../research/openrouter-model-catalog-2026-11-05.json) hold the full rate windows.
- **Left as written:** `PRD-AutoGPT.md`, `PRD-Comparison-Recommendation.md`, `docs/imagine`, `research`, and earlier evidence and archived changes still say Astra, because they record alternatives or what happened at the time.

## Reversal

Add a migration restoring the Astra row and constraints, and reverse the code and requirement changes in this decision's commit. Astra would then need its own paid qualification, worst case about US$6 for the corpus.
