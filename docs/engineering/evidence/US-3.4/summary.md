# US-3.4: paid qualification of the DeepSeek route

**Class: live.** Real OpenRouter calls through the real factory, adapter and SDK, separate from every mocked result in this repository. Run on 2026-11-05, authorized by the owner: DeepSeek only, runner cap US$0.50, and a US$1 limit the owner set on the key.

This is partial evidence for US-3.4, and **the story isn't complete**. Harness and qualification results don't establish H1 or product acceptance.

| | |
|---|---|
| Route | `openrouter_deepseek_flash`: request ID `deepseek/deepseek-v4.1-flash-1017`, canonical `deepseek/deepseek-v4.1-flash-20261017` |
| Pins | `langchain-openrouter==0.2.9`, `openrouter==0.11.46`, `uv.lock` on this branch |
| Routing | `require_parameters=true`, `allow_fallbacks=false`, no retries |
| Limits | 512 output tokens, the shared application limit |
| Runner | `autobots.operations.route_qualification`: 39 calls from `c7034f1`, then 4 more with its `--only` option, added in the commit holding this file |
| Calls | 43, none retried, no other model tried |
| Reported charges | **US$0.002766**, from `usage.cost` on 40 calls. Not checked against OpenRouter's dashboard. |
| Counted against the cap | US$0.007374: the above plus worst-case US$0.001536 for each of the 3 cancelled calls, whose charge is unknown |
| Raw results | `.checks/route-qualification/deepseek/` (ignored, local, no retention beyond this checkout) |

## Results

| Fixture | Trials passed | What happened |
|---|---|---|
| Plain text | 3/3 | |
| Tool, automatic | 3/3 | One valid call each |
| Tool, required | 3/3 | Trial 1 returned two calls, though the prompt asked for none. Parallel calls can occur. |
| **Named tool against a conflicting prompt (MP-A07)** | 3/3 | Two competing tools, a system prompt forbidding `Weather`, selector set to `Weather`. It called `Weather` each time, which shows the selector was enforced in these trials. |
| Strict schema, flat | 3/3 | Valid against the schema. Compliance doesn't by itself prove the server enforced it. |
| **Strict schema, nested** | **0/4** | **Failed under the 512-token limit.** See below. |
| Streaming text | 3/3 | 7 content chunks, assembled correctly |
| Streaming tool arguments | 3/3 | Valid, but in only 2 chunks, so **real fragmentation wasn't stressed here**. Only the fake transport covers it. |
| Tool-result continuation | 3/3 | A value only the tool knew came back in the answer, tied to its call ID |
| Truncation | 3/3 | `finish_reason=length` at a 16-token limit |
| Refusal | 3/3 on rerun | See below |
| Cancellation | 3/3 | Our side stopped after 3 chunks. **This doesn't show the provider stopped or what it charged**, so each stays at the worst case. |

**Nested schema.** All 4 trials ended `finish_reason=length` at 512 output tokens with no parsable JSON. The one trial that recorded it reported 553 reasoning tokens against 512 output tokens, so reasoning used the whole allowance. A flat schema used about 221 tokens. So strict nested output isn't qualified at this limit, and whether it works with a larger allowance wasn't tested. SP-008 anticipates this: mandatory reasoning consumes the output allowance, and truncated output is incomplete.

**Refusal.** The 3 trials of the full run scored `failed`, and that was the runner's bug: its word list missed the typographic apostrophe in "can’t". Those failures stay in `report.json`. The 3 reruns, with the classifier fixed, all declined, in text only: `finish_reason=stop` and no `refusal` field. So **a decline can't be detected from the protocol on this route**. Only reading the text shows it.

## Not established

- **Astra:** not called, and not authorized. It's still a selectable profile in the code, so "each enabled route" isn't met while it stays selectable.
- **"Unsupported capabilities remain disabled":** results are recorded, but no capability switch in the code acts on them.
- **Upstream provider:** the adapter reported `provider: null` on every call, so MP-A06's actual provider isn't recorded.
- **Product paths:** nothing here ran through the worker, the admission ledger or `AdmittedModel`. MP-A09's concurrent admission wasn't touched. The runner keeps its own simple ledger.
- **Quality:** no task quality, arithmetic or negative-task fixtures, which are separate gates (US-10.1).
- **Review:** the runner has had no independent review.
- **Repeatability:** 3 trials of each fixture on one day.

## Decisions for the owner

1. **The 512-token limit:** nested plans fail at it. Options are raising the output allowance, lowering reasoning effort if the route honors it, or accepting that strict nested output stays disabled. Either change needs a recorded policy revision.
2. **Astra:** qualify it separately, or remove it from what can be selected.
3. **US-3.4's status:** it stays `BLOCKED`, with its `External:` line, until these are decided.

## Second round: Terra, and DeepSeek at low reasoning

**Class: live.** Run on 2026-11-05, authorized by the owner, who named `deepseek/deepseek-v4.1-flash-20261017` and `openai/gpt-6.1-terra-20261026`. Shared runner cap US$0.60, inside the US$1 key limit. Runner from `60b5b5c`, then its fixture additions in the commit holding this text.

**This is qualification only. `openai/gpt-6.1-terra` isn't one of the application's approved profiles, and `PROFILES` didn't change.** The app can't select it.

| | |
|---|---|
| Terra route | Request ID `openai/gpt-6.1-terra`, canonical `openai/gpt-6.1-terra-20261026`, US$1 / US$5 per 1M tokens |
| Calls | 49: Terra 46, DeepSeek 3. None retried, no other model tried |
| Reported charges | **US$0.012614**, not checked against OpenRouter's dashboard |
| Counted against the cap | US$0.120134, including worst-case amounts for 7 refused requests and 3 cancelled streams, whose charges weren't reported |
| Raw results | `.checks/route-qualification/round2/` (ignored, local) |

| Fixture | Terra | DeepSeek |
|---|---|---|
| Plain text, automatic and required tools | 9/9 | 9/9, one trial made two calls |
| Named tool against a conflicting prompt | 3/3 | 3/3 |
| Strict schema, flat | 3/3 | 3/3 |
| **Strict schema, nested** | **3/3 with closed objects. Refused with `400` otherwise** | **0/7: 4 at default reasoning and 3 at low. Ran out of tokens** |
| Output tokens used on nested | 105–125 of 512 | All 512 |
| Streaming text | 3/3, 39 chunks | 3/3, 7 chunks |
| Streaming tool arguments | 3/3, 15 chunks, so really fragmented | 3/3, 2 chunks |
| Continuation, truncation | 6/6 | 6/6 |
| Refusal | 3/3, in text only | 3/3 on rerun, in text only |
| Cancellation | Our side stopped. Provider stop and charge unknown | Same |
| Average reported charge per settled call in the corpus | about US$0.00029 | about US$0.00006 |

**The `400`.** Terra refused nested schemas in 7 of 7 tries: 3 with the runner's first models, 3 with those models without list lengths, and 1 with them. My first explanation, list-length keywords, was wrong. The request sent had no `additionalProperties: false` on any object. With every object closed, it passed 3 of 3. OpenRouter's error text was only "Provider returned error", so the cause is inferred from that one change, not stated by the provider. A flat schema with no such field passed, so the rule isn't simply "every schema needs it".

**DeepSeek at low reasoning.** `reasoning: {effort: "low"}` was accepted and changed almost nothing: 504–552 reasoning tokens, against 553 by default. **An accepted parameter didn't reduce reasoning here**, so this isn't the fix at this limit. Closed objects weren't tried on DeepSeek, as its failure was running out of tokens. A larger output allowance is still untested.

### Second-round limits

- Three trials per fixture on one day, and no task quality, arithmetic or negative-task fixtures. This doesn't show either model is good at the work.
- That a route refuses some schemas suggests it validates them, but doesn't prove it enforces them on output.
- Nothing here ran through the worker, the admission ledger or `AdmittedModel`, and Terra can't: it isn't a profile.
- `provider` was `null` on every call, on both routes.

### Second-round decisions for the owner

1. **Whether Terra replaces Astra,** which keeps the contract's two models. Or whether it becomes the default, at about 5 times DeepSeek's cost per call in this corpus. Either needs a recorded decision.
2. **DeepSeek's output allowance,** if it stays the default: test a larger one.

### Correction

**The application's second model changed after this was recorded.** [Decision 0004](../../decisions/0004-terra-replaces-astra.md) made Terra an approved profile, replacing Astra, so this file's statements that Terra isn't a profile, and that Astra is selectable, describe that moment.

The runner's worst-case estimate used DeepSeek's base rate, though the catalog shows that rate doubling in weekday peak windows. It's since been fixed. Reported charges are unaffected, and neither round came near its cap. The per-call cost comparison is from one afternoon, so it may not hold at other hours.

## Third round: nested schemas at 2,048 output tokens

**Class: live.** Run on 2026-11-05, authorized by the user's "Try 2,048 tokens" and "now with openai/gpt-6.1-terra-20261026", from a scratch worktree at `415eaf0`, with only `OUTPUT_TOKENS` changed. **The shared limit in this repository is still 512.** Raw results are in `.checks/trial-2048/` (ignored, local).

| | DeepSeek | Terra |
|---|---|---|
| Nested schema, open objects | 0/3: parsed, wrong `place` | Refused with `400`, 3 of 3 |
| Nested schema, closed objects | 0/3: parsed, wrong `place` | 3/3 |
| Finish reason of replies | `stop`, all 6 | `stop`, the 3 that replied |
| Output tokens, of which reasoning | 341–658, 227–561 | 112–116, 32–35 |
| Reported charges | US$0.001474 | US$0.002147 |
| Counted against the cap | US$0.001474 | US$0.057443, with worst-case amounts for the 3 refused requests |

**DeepSeek.** The cut-off is gone, as 2,048 tokens left room, and every trial went over 512, so that limit can't hold this output. It still fails: all 6 returned `São José, 東京` where the prompt asks for exactly `São José, 東京 "quoted"`. So a parsed reply wasn't an exact one here. The fixture stops at its first failed check and doesn't record task counts or criteria, so those aren't known. Whether the quotes were the cause isn't established. Only the literal value was tried.

**Terra.** The same as at 512, so the larger limit changed nothing it needed.

What happened when the limit was tried on a real goal is in [the live goal record](../LIVE-GOAL-1/summary.md#trial-2048-output-tokens-deepseek-and-terra). This round doesn't change US-3.4's status.

## Outcome

**This replaces the opening's "the story isn't complete" and the decisions listed above.** The owner decided them: Terra replaced Astra in [Decision 0004](../../decisions/0004-terra-replaces-astra.md), and DeepSeek's strict nested output is unsupported and stays disabled in [Decision 0005](../../decisions/0005-deepseek-strict-nested-unsupported.md). The shared limit stays 512.

| Fixture group | DeepSeek | Terra |
|---|---|---|
| Tools, including named against a conflicting prompt | Pass | Pass |
| Strict schema, flat | Pass | Pass |
| Strict schema, nested | **Unsupported, disabled** | Pass with closed objects only |
| Streaming, continuation, truncation | Pass | Pass |
| Refusal | Pass on rerun, in text only | Pass, in text only |
| Cancellation | Our side stopped | Our side stopped |

Two tests guard this in `services/agent/tests/test_route_qualification.py`: application code can't start asking for strict output, and an approved profile can't lack a route to qualify. Both were confirmed failing on a temporary break.

**Still open, and not settled by this story:** whether the provider stopped on a cancelled call and what it charged, the upstream provider, concurrent admission on a live route (MP-A09), and real fragmentation of DeepSeek's streamed tool arguments, covered only by the fake transport. No real goal has succeeded on either model. Three trials per fixture on one day. This doesn't establish H1, product acceptance or task quality, which stays with US-10.1.

