# Decision 0006: Terra is the default model

**Date:** 2026-11-05. **Authority:** explicit user decision in this session: "Make Terra the default", after [the batch of ten goals](../evidence/LIVE-GOAL-1/summary.md#ten-goals-terra-5-of-5-deepseek-0-of-5) and a recommendation to do so.

## Decision

`openrouter_terra` is now the default for all 14 roles, and the last step in resolving a role's model. `openrouter_deepseek_flash` stays approved, selectable for a run, a workspace or a role. The contract still has exactly two approved models, OpenRouter only, with no fallback. Resolution order, freezing and budgets are otherwise unchanged.

This supersedes the DeepSeek default in SP-006, MP-01 and MP-02, and those requirements' IDs stay. [Decision 0004](0004-terra-replaces-astra.md) made Terra selectable, and this makes it the default.

## Why

On one repeated goal at the 512-token limit, Terra succeeded 5 of 5 times with no repairs, and DeepSeek 0 of 5. DeepSeek's reasoning used up the limit on 7 calls, and 3 of its runs had a plan rejected. A default that doesn't complete the goal it was tested on isn't a useful default.

## What this gives up

- **Cost per call:** Terra's listed prices are US$1 / US$5 per 1M tokens, against DeepSeek's US$0.15 / US$0.60. A goal in the batch cost about US$0.006, which isn't typical of larger work.
- **Larger reservations:** each Terra call reserves more against a run's budget, about US$0.043 at the batch's catalog price. That fits the default US$1 per run and US$5 per workspace day, but a very small run limit will be refused sooner.
- **DeepSeek wasn't given a larger limit:** whether it would do better at 2,048 tokens on a real goal is untested.

## What this doesn't establish

- **That Terra is good at the work:** one goal, repeated on one evening, with quality unscored. US-10.1 still decides that.
- **That Terra's strict output is general:** it needs closed objects, as Decision 0004 says, and nothing in the application uses strict output today.
- **H1 or product acceptance.**

## Consequences

- **Saved work:** a saved run's frozen policy isn't rewritten, so a run admitted on DeepSeek stays on DeepSeek.
- **Workspace settings:** a workspace that saved a default or a role override keeps it, including one that chose DeepSeek. Only what has no saved choice resolves to Terra, for new runs. The database stores no default model, so no migration is needed.
- **Experts:** a role an Expert doesn't bind falls through to the workspace, and so to Terra if nothing's saved.
- **Retired Astra selections:** [Decision 0004](0004-terra-replaces-astra.md) already moved those to DeepSeek, and they stay there as saved choices.
- **Left as written:** `PRD-AutoGPT.md`, `PRD-Comparison-Recommendation.md`, `docs/imagine`, `research`, and earlier evidence and archived changes, because they record alternatives or what happened at the time.

## Reversal

Set `DEFAULT_PROFILE` back and reverse the requirement changes in this decision's commit. No data needs changing, as new runs would simply resolve to DeepSeek.
