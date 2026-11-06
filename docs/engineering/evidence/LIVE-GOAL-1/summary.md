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

## Trial: 2,048 output tokens, DeepSeek and Terra

**Class: live, on disposable stacks.** Authorized by the user's "Try 2,048 tokens" and "now with openai/gpt-6.1-terra-20261026". Each run had a US$0.25 limit. Run on 2026-11-05 UTC from a scratch worktree at `e83bfd9`, since removed. **No run succeeded, and the trial's changes aren't in this repository, apart from the timeout fix described below.**

The worktree changed `MAX_OUTPUT_TOKENS` to 2,048, let the runner select Terra through `PUT /v1/settings/model-policy`, logged an exception's type and status, and, for run 5 only, set `timeout_ms=120_000`. The diff and raw results are in `.checks/trial-2048/` (ignored, local, no retention beyond this checkout).

| | Run 3 | Run 4 | Run 5 |
|---|---|---|---|
| Model | DeepSeek | Terra | DeepSeek |
| Run, UTC | 23:40 | 23:41 | 23:47 |
| Client timeout | httpx default, 5s | httpx default, 5s | 120s |
| Status | `paused` after 10s | `failed` after 20s | `failed` after 32s |
| Stop reason | `uncertain_acceptance` | `criteria_unmet` | `repair_limit:plan_out_of_scope` |
| Model calls, tool dispatches, repairs | 1, 0, 0 | 6, 5, 1 | 2, 2, 1 |
| Largest output, of which reasoning | none recorded | 169, 0 | 197, 17 |
| Ledger, micro-USD | 0 | 6,825 | 176 |

A second DeepSeek run at 23:44 repeated run 3, and logged `ReadTimeout` with no status after about 5.4s. Run 3 has no such log, so its cause is inferred from the match. Key usage didn't change for either, read about 60 seconds after each run, so no charge is shown for them.

**The 5-second timeout is a defect in this repository's code.** `default_sdk_client` sets no timeout, so the SDK's own `httpx` client applies the 5-second default, well inside the middleware's 120-second bound. A reply that takes longer is recorded as `uncertain_acceptance` and pauses the run. Why these replies were slow isn't established. Run 5's calls took 13.5s and 14.7s for 123 and 197 output tokens, so length doesn't explain it, and the same timeout can apply at 512 tokens.

**Fixed after this trial.** `default_sdk_client` now sets `REQUEST_TIMEOUT_MS`, 130 seconds, above the middleware's bound so that bound decides. This is the one trial change kept in the repository. A fake-transport test covers it, and fails with `5.0` if the setting is removed. No live call has run at 130 seconds: run 5 used 120.

**Run 4, Terra.** It saved a correct report of 99 words, ending in the required line, then called `complete_task` twice, the first of which failed, and stopped. It never called `publish_artifact`, so verification recorded `artifact_missing:report.md`. `SYSTEM_PROMPT` doesn't mention publishing and neither does the goal, which is the likely cause. That's inferred: neither the tools offered nor why `complete_task` failed are recorded.

**Run 5, DeepSeek.** Both of its plans were rejected as `plan_out_of_scope`, which used the run's one repair and stopped it. That means a task named a criterion or tool the goal doesn't allow. Which one isn't recorded, and earlier DeepSeek runs had a plan accepted.

### What this doesn't establish

- **That 2,048 fixes the goal:** DeepSeek never got past planning here, so it didn't reach the work that was cut off before. The largest output in these runs was 197 tokens, so none of them needed more than 512. Only [the nested-schema trial](../US-3.4/summary.md) used more.
- **That Terra needs 2,048:** nothing in its run came near 512.
- **That the 120-second timeout is the right value:** it was chosen to match the middleware's bound, for one run.
- **Repeatability:** one run of each configuration that got past the timeout.

Held in all four runs: no key in any durable row or log file, nothing of the project left behind, other Docker resources unchanged, and the watchdog never fired.

**Spend:** US$0.007001 across these goals, and US$0.00889 with the two above, against ledger figures. Key usage rose by exactly those amounts, to the rounding of its reporting, across the two charged runs.

## Telling the model to publish

**Class: live, on a disposable stack.** Authorized by the user's "Yes, fix publishing", after being told a small paid run would follow, under the same US$0.25 limit. Run on 2026-11-06 UTC at 00:21, on Terra, at the repository's settings: the 512-token limit and the 130-second timeout. Raw result: `.checks/trial-publish/terra-publish.json` (ignored, local).

**The cause of run 4 is now confirmed by code, and its fix observed once.** `_opening` told the model the goal and criteria, but not the required artifacts or that saving alone delivers nothing, while verification accepts only published files. It now says both when the run may publish. In this run the model called `publish_artifact`, and `report.md` was published, the first artifact a real model has published here.

**Outcome: the goal still failed, for a different reason.** Status `failed` after 23s, stop reason `repair_limit:evidence_invalid`, so verification never ran.

| Call | Tool | Result | Output tokens | Charged, micro-USD |
|---|---|---|---|---|
| 1 | `propose_plan` | **rejected, which used the run's one repair** | 139 | 1,577 |
| 2 | `propose_plan` | accepted | 133 | 1,982 |
| 3 | `save_artifact` | succeeded | 160 | 1,076 |
| 4 | `complete_task` | succeeded | 59 | 669 |
| 5 | `publish_artifact` | succeeded | 25 | 326 |
| 6 | `complete_task` | **`evidence_invalid`, which stopped the run** | 68 | 604 |

**Why those two failed isn't known.** Evidence must be a saved file's path or a succeeded receipt's operation ID, but what the model cited isn't recorded, and neither is the code for the first plan's rejection. Call 4's evidence was accepted and call 6's wasn't, which suggests the published artifact was cited in a form the rule doesn't accept. That's inferred. Run 4 also had a `complete_task` fail, and run 5's plans were rejected, so this looks repeated.

**Total:** US$0.006234 in the ledger, matching key usage. Across all live goals in this record, US$0.015124.

Held: no key in any durable row or log file, nothing of the project left behind, other Docker resources unchanged, and the watchdog never fired. The report is 88 words and ends in the required line, but no check has scored it, and this doesn't establish H1 or product acceptance.

## The first goal to succeed

**Class: live, on a disposable stack.** Authorized by the user's "Yes, record the reasons", after being told one cheap run would follow, under the same US$0.25 limit. Run on 2026-11-06 UTC at 00:38, on Terra, at the 512-token limit and the 130-second timeout. Raw result: `.checks/trial-reasons/terra-reasons.json` (ignored, local).

**Outcome: `succeeded` after 23s.** The run planned, saved, published and verified, with `passed: true` and nothing unmet. `report.md` was published and meets its `must_contain` check. It took 7 calls and 6 dispatches, and the ledger shows US$0.006132, matching key usage. The largest output was 159 tokens. Same limits held as above.

**This isn't a fix taking effect.** Since the failed run above, the only changes record failures. Neither changes what the model is told, so the same setup has now gone 1 of 2, and the difference is the model's own variation.

**The run spent its one repair anyway.** Call 3's `complete_task` failed with `evidence_invalid`, and call 4's succeeded. A second failure of that kind would have stopped it, as it did the run before.

| Call | Tool | Result |
|---|---|---|
| 1 | `propose_plan` | succeeded |
| 2 | `save_artifact` | succeeded |
| 3 | `complete_task` | **`evidence_invalid`, form `artifact:run_path`** |
| 4 | `complete_task` | succeeded |
| 5 | `publish_artifact` | succeeded |
| 6 | `complete_task` | succeeded |
| 7 | none | final reply |

**What the new record shows.** `tool_receipts` now keeps `failure_code` and `failure_detail`: a code and a category, never what the model wrote.

- **It disproves an earlier guess.** The failure came before publishing, so a published artifact's identifier wasn't the cause here.
- **What it narrows:** the model cited an artifact with a reference starting `outputs/` or `inputs/` that matched no saved path. The exact text isn't recorded by design, so why it didn't match is still unknown. A version suffix on the path is one possibility, not an observation.
- **Unrelated gap:** a model is never shown an `operation_id`, the only form `receipt` evidence accepts, so it can't cite a receipt correctly. This run didn't hit that.
- **Not recorded:** refusals that leave no receipt, such as `invalid_arguments`.

**Not established:** that goals succeed reliably, as this is one run of one goal on one model. DeepSeek hasn't completed a goal. The report's quality wasn't scored. Compaction, approvals, child runs and budget refusals weren't exercised. This doesn't establish H1, product acceptance or US-10.1.

**Total across all live goals in this record:** US$0.021256.
