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
