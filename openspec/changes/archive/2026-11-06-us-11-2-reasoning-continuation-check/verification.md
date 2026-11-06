# Verification — us-11-2-reasoning-continuation-check

Change: us-11-2-reasoning-continuation-check
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Check the continuation request | PASS | Fake transport through the real SDK: `tests/test_reasoning_trial.py` reports survived for unchanged metadata, and dropped, naming where, for removed, shortened, reordered or changed metadata and an unsent message. `scripts/qualify_worker_inference.py` runs the real `worker.main`, with metadata on every tool reply: every continuation of the run compared survived, and the marker reached no process log or activity event |
| Trial each enabled route live | PASS | Real OpenRouter calls on both routes. Result below |
| Report loss honestly | PASS | Terra reads as `lost` and DeepSeek's reply with no metadata as `not_exercised`. LC-23's text is unchanged, and the owner is told in this story's report |
| Stop at the shared cap | PASS (arranged) | A fake-transport ledger whose remainder is below the trial's worst case: no request and no ledger entry, reported as `not_run`, including when earlier spend is what fills it. The real ledger is far from the cap, so this hasn't happened live |

Checks on the final code: `fast` and `harness` exit 0, the worker inference qualifier's 40 cases pass, and `openspec validate` is clean. After the live runs only a line wrap changed in the runner, with the same prompt.

## Live result

Run on 2026-11-06, on the key in `.env`, authorized by Decision 0009. Configuration on both routes: required parameters on, no fallbacks, no retries, 512 output tokens, one tool with `tool_choice: auto`, `langchain-openrouter` 0.2.9, `openrouter` 0.11.46. Raw reports: `.checks/reasoning-trial-round1` and `.checks/reasoning-trial-round2`, ignored and local, holding only paths, counts and kinds.

| Route | Prompt | Trial | Outcome | Metadata kinds | Reported charge (micro-USD) |
|---|---|---|---|---|---|
| DeepSeek `deepseek/deepseek-v4.1-flash-1017` | Simple | 1 | not exercised, none returned | | 26 |
| | Simple | 2 | survived | `reasoning.text` | 32, 10 |
| | Needs thought | 1–3 | survived, each | `reasoning.text` | 43, 25; 50, 20; 49, 26 |
| Terra `openai/gpt-6.1-terra` | Simple | 1–2 | not exercised, none returned | | 153; 153 |
| | Needs thought | 1–3 | **lost, each** | `reasoning.summary`, `reasoning.encrypted` | 297, 242; 302, 228; 302, 243 |

**Spend:** 17 calls, all settled with a reported charge. The shared ledger stands at **US$0.002201** of US$1. Key usage read `0.856401823` before and `0.858598285` afterward, a rise of US$0.002196, which is close to the ledger and read shortly after the last call, so it may still be settling.

## Findings

**Terra loses the encrypted item's `id`.** In all 3 trials that returned metadata, `reasoning_details[1].id` was sent back removed, and nothing else differed. The removal is in the pinned SDK: `_strip_ephemeral_reasoning_ids` in `langchain_openrouter/chat_models.py` deletes an `id` starting with `rs_`, and this repository doesn't call it. A fake-transport test reproduces it. **Each continuation still worked**, returning the value only the tool knew. By this story's own rule an altered field isn't survived, so LC-23 stays partial on Terra.

**No source decides what follows.** Whether to work around the SDK or revise LC-23 is the owner's, and this change does neither.

**The first prompt exercised little.** A simple prompt returned no metadata on Terra at all. A prompt needing some thought brought it out, so a run with little to reason about shows nothing either way.

## Limits

- **Four DeepSeek and three Terra comparisons on one day,** at one reply shape each. Streaming wasn't tried live, and the worker doesn't stream.
- **The live trial runs the real factory and SDK but not the worker.** Only the fake-transport qualifier runs the worker's whole path, including checkpoints.
- **The cap's refusal is arranged** against a small ledger.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
