# One real goal through the worker

**Class: live, on a disposable stack.** Real OpenRouter calls through the product's API and worker, separate from every mocked result in this repository. Authorized by the user's "Yes, try one goal" and "Yes, add and rerun", under a US$0.25 limit. This doesn't establish H1, product acceptance or US-3.4.

**Outcome: the goal failed twice, the same way.** Both times DeepSeek planned and saved a correct report, and the run stopped before publishing it, so nothing was verified or published. **The cause is DeepSeek's reasoning using up the 512-token output limit**, seen directly in the second run.

| | Run 1 | Run 2 |
|---|---|---|
| Run, 2026-11-05 UTC | 23:09 | 23:25 |
| Code | `2e71720` plus the runner | Run 1's commit plus the per-call record |
| Status | `failed` after 32s | `failed` after 42s |
| Stop reason | `incomplete_output` | `incomplete_output` |
| Model calls, tool dispatches, repairs | 4, 2, 1 | 5, 3, 1 |
| Ledger | US$0.000785 | US$0.001104 |
| OpenRouter's usage for the key, change | US$0.000785 | US$0.001105 |
| Report saved | 833 characters, 116 words | 756 characters, 113 words |

Both used `openrouter_deepseek_flash`, frozen at admission, and the same goal: a report under 150 words comparing SQLite and PostgreSQL for a desktop notes app, with three trade-offs, a recommendation and the last line `Trade-offs covered: 3`, which `report.md` must contain. Each was admitted with `202` from `POST /v1/runs`, using a key saved through the real path. Raw results are in `.checks/live-goal/` (ignored, local, no retention beyond this checkout).

**Total: US$0.001889 of the US$0.25 limit,** and the watchdog never fired. Each call reserved 10,215 micro-USD, about 38 times the largest charge.

## Run 2, call by call

| Call | Finish | Input tokens | Output tokens | Of which reasoning | Tool | Charged, micro-USD |
|---|---|---|---|---|---|---|
| 1 | `tool_calls` | 1,485 | 207 | 0 | `propose_plan` | 112 |
| 2 | **`length`** | 1,733 | **512** | **512** | none | 265 |
| 3 | `tool_calls` | 1,753 | 512 | 301 | `save_artifact` | 265 |
| 4 | `tool_calls` | 2,280 | 359 | 119 | `save_artifact` | 192 |
| 5 | **`length`** | 2,725 | **512** | **512** | none | 270 |

## Cause

Calls 2 and 5 spent the whole allowance on reasoning and returned nothing usable. Call 2 used the run's one repair, and call 5 stopped it. Call 3 only just fit, at exactly 512 tokens. `publish_artifact` and `complete_task` never ran.

Run 1 has no per-call record, but its charges of 115, 265, 138 and 267 fit the same pattern, with calls 2 and 4 cut off. That's inferred, not observed.

This corrects what this file first said. It doubted a cut-off because 512 tokens at the catalog's US$0.60 per million is 307 micro-USD, more than any charge. A 512-token call was in fact charged about 265 here, so the rate applied was lower than that, for a reason not established.

It also matches [the US-3.4 evidence](../US-3.4/summary.md): DeepSeek spent all 512 tokens on reasoning on nested strict output, and low effort didn't help.

## Options, for the owner

MP-07 makes 512 a configurable initial budget, and forbids raising it silently after a truncation, so this needs a decision.

- **A larger output limit:** 2,048 tokens would raise the worst case per call from about US$0.0102 to about US$0.0121. Whether that's enough is untested.
- **Terra for this work:** it used 105 to 125 tokens in US-3.4, at about 5 times the cost per call. It hasn't run a goal.
- **More repairs:** this only pays for more cut-offs, and I wouldn't do it.

## Also observed

- **Held, in both runs:** no key in any checkpoint, event, receipt, file or ledger row (0 rows), or in any log file (0). No step failures, the worker exited 0 on SIGTERM, nothing of the project was left behind and other Docker resources were unchanged.
- **Unexplained in run 2:** the model called `save_artifact` twice and only one receipt and one file version exist, with 3 dispatches against 2 receipts. Tool replies aren't recorded, so why isn't known. It didn't cause the stop.
- **Failed run, no explanation in its events:** the public events are only three status changes. The reason is in `run_usage`.
- **`upstream_provider` is `unknown`** on every call. The SDK's typed reply drops the provider, and the earlier paid runs recorded `null` too.
- **`public.runs.spent_micro_usd` stays 0.** The API and the budget read the ledger instead, so it misleads only anyone reading the column directly.

## What changed for this

`app_private.model_invocations` now records each reply's finish reason, token counts, tool names and count of broken tool calls, with no message content. `qualify_worker_inference` checks this with the fake model, including a run cut off twice.

## Not exercised

Publishing, verification, a succeeded run, the 80% warning, the budget's refusal, Terra, a child run, approvals, compaction, and whether the worker's prompt suits a real model beyond these two tools.
