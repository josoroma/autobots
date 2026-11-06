# Verification — us-11-9-run-creation-disclosure-role

Change: us-11-9-run-creation-disclosure-role
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Disclose before starting | PASS | `scripts/qualify_identity.py`, disposable stack, real browser. Home, a real Expert session and a real workflow's editor each show the model, 14 roles, `US$1.00`, MP-07's data categories and `Nothing is sent until you press Run.`. No POST creating a run left the page across all three. The workflow's says data goes only if an agent step runs |
| Choose a model for one run | PASS | Picking DeepSeek updates the disclosure, and pressing Run freezes it: the run workspace lists all 14 roles on DeepSeek's canonical ID and says only the executor's binding dispatches. The workspace default and its version are unchanged |
| Read budgets, costs and errors | PASS (arranged) | The scripted worker raises one 500 on a run, which retries and finishes. The workspace shows `512 output tokens per call`, `8K tokens of context` and `Spend limit: US$1.00`. The inspector shows `Error: provider error` on that attempt, `Reported charge` and `Estimated worst case, not a charge` as separate lines, and an evidence link whose download holds the report. Reasoning metadata arranged on the run, and any key shape, are in neither the route's body nor the page |
| Refuse an unapproved model | PASS | A request changed in flight to name `openai/gpt-unknown` gets a real 422. The page says it isn't approved and keeps the draft, and the run count doesn't change. A direct request naming `openrouter_astra` also gets 422 |

Checks on the final code: `fast` and `harness` exit 0, the identity qualifier's 354 cases and the worker inference qualifier's 40 pass, and `openspec validate` is clean.

## Findings

**A failed attempt reads `failed before acceptance`, with a reported charge of US$0.** That's what the ledger records for a 5xx, by MP-08, and the estimate beside it isn't a charge. An uncertain call would read `none`.

## Limits

- **The context budget is about 8K tokens.** No tokenizer is pinned, and compaction works to a character budget, as its code says.
- **A pick is run-wide, and an Expert's own role bindings stay ahead of it,** by MP-01's order. The disclosure shows those, but the Expert case wasn't asserted with bindings set.
- **Workflows offer no per-run model,** as they freeze the workspace's policy. That's disclosed, and not a choice there.
- **Evidence of kind `receipt` shows as text.** Only an artifact gets a link.
- **Routines start runs with no screen in this release,** so they have no disclosure, by Decision 0009.
- **The model is scripted,** so no real cost was read here. US-11.3's real goal has real ones.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
