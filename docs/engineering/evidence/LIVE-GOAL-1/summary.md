# One real goal through the worker

**Class: live, on a disposable stack.** Real OpenRouter calls through the product's API and worker, separate from every mocked result in this repository. Authorized by the user's "Yes, try one goal", under a US$0.25 limit. This doesn't establish H1, product acceptance or US-3.4.

**Outcome: the run failed.** DeepSeek planned and saved a correct report, and the run stopped before publishing it, so nothing was verified or published. It's the first time a goal has reached a real model through the worker.

| | |
|---|---|
| Run | 2026-11-05, 23:09 to 23:10 UTC, on `2e71720` plus the runner, `scripts/live_goal.py` |
| Route | `openrouter_deepseek_flash`, frozen at admission, default for the workspace |
| Goal | A report under 150 words comparing SQLite and PostgreSQL for a desktop notes app, with three trade-offs, a recommendation and the last line `Trade-offs covered: 3`. `report.md` must contain that line |
| Admission | `202` from `POST /v1/runs`, with a key saved through the real path, including OpenRouter's key check |
| Status | `queued`, `running` after 3s, `failed` after 32s |
| Stop reason | `incomplete_output` |
| Counters | 4 model calls, 2 tool dispatches, 1 repair, 0 plan revisions |
| Raw results | `.checks/live-goal/` (ignored, local, no retention beyond this checkout) |

## Spend

| | |
|---|---|
| Ledger | **US$0.000785**, reported on all 4 calls: 115, 265, 138 and 267 micro-USD |
| OpenRouter's usage for the key | US$0.015790768 before, US$0.016576115 afterwards: **the same US$0.000785** |
| Reserved per call | 10,215 micro-USD, about 38 times the largest charge: 32,000 input and 512 output tokens at peak rates |
| Limit | US$0.25. The watchdog never fired |

The figures for the earlier paid qualification rounds were never checked against OpenRouter. The key's total of US$0.015791 before this run is close to the US$0.0154 reported for them, which were runner figures.

## What happened

Receipts show `propose_plan` and `save_artifact` succeeded, in that order. `publish_artifact` and `complete_task` never ran. Which of the 4 calls led to which tool isn't recorded.

The saved `outputs/report.md` had 833 characters and 116 words, with three trade-offs, a recommendation and the required last line, all as asked. That's from reading it: nothing in the product judged it, because verification never started.

## Cause: not established

The middleware stops with `incomplete_output` in two ways. A reply cut off for `length` gets one repair and a second one stops the run, and any other incomplete finish stops it at once. The counters fit a second cut-off. **The charges don't obviously fit it:** 512 output tokens at the catalog's base rate of US$0.60 per million is 307 micro-USD, and no call was charged that much.

So either the rate applied was lower than the catalog's, or a reply stopped short of the limit for another reason. The stack was removed, and neither the ledger nor the worker's log records a call's finish reason, token counts or tool names. **That gap is itself a finding:** a failure like this can't be diagnosed after the fact.

The evidence so far doesn't justify changing the 512-token limit. MP-07 allows revising it, and forbids raising it silently after a truncation.

## Also observed

- **Held:** no key in any checkpoint, event, receipt, file or ledger row (0 rows), or in any log file (0). No step failures, and the worker exited 0 on SIGTERM.
- **Cleanup:** nothing of this project was left behind, and other Docker resources were unchanged.
- **Failed run, no explanation in its events:** the public events are only three status changes. The reason is in `run_usage`.
- **`upstream_provider` is `unknown`** on all 4 calls, so the ledger doesn't say who served them.
- **`public.runs.spent_micro_usd` stays 0.** The API and the budget read the ledger instead, so it misleads only anyone reading the column directly.

## Not exercised

Publishing, verification, a succeeded run, the 80% warning, the budget's refusal, Terra, a child run, approvals, compaction, and whether the worker's prompt suits a real model beyond these two tools.
