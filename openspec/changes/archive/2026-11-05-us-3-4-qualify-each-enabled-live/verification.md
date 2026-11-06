# Verification — us-3-4-qualify-each-enabled-live

Change: us-3-4-qualify-each-enabled-live
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-05

Verified by the main session, with no independent review, per Decision 0003. Base revision `f96cfe2`, working tree with this change. No paid call was made during this verification: the scenarios are scored from live reports already recorded, in `.checks/route-qualification/` and `.checks/trial-2048/` (ignored, local).

Commands: `pytest tests/test_route_qualification.py` (27 passed), `python3.12 scripts/verify.py --profile fast` (exit 0, inputs stable), `--profile harness` (exit 0, harness evidence only), `openspec validate` (valid).

## Scenarios

**Qualify real adapter behavior: observed from recorded live reports.** Authorized by the owner, under runner caps. Both reports have `evidence_class: live`, separate from the fake-transport results.

- DeepSeek, `deepseek/deepseek-v4.1-flash-1017`: 39 calls in the corpus, US$0.002158 reported. Tools, flat schema, streaming, continuation, truncation and cancellation passed. Refusal failed 3 of 3 on the runner's own bug and passed 3 of 3 on rerun, and both results are kept. Nested schema: 0 of 13 across the three rounds.
- Terra, `openai/gpt-6.1-terra`: 39 calls in the corpus, US$0.009626 reported. All passed except nested schema with open objects, refused with `400`. Closed objects passed 6 of 6 across two rounds.
- **Unsupported capabilities remain disabled:** Decision 0005 records DeepSeek's nested strict output as unsupported. `test_no_application_code_asks_for_strict_output` passes, and failed when a request for it was temporarily added. It's a source check, not a runtime switch.
- **Each enabled route:** `test_every_approved_profile_has_a_route_to_qualify` passes, and failed when a route's ID was temporarily changed.

**Test forced selection honestly: observed from recorded live reports.** Two competing tools, `Weather` and `ClockTime`, with a system prompt forbidding `Weather` and a question about the time, selector set to `Weather`. Each route called only `Weather` in 3 of 3 trials. The fixture passes only when `Weather` is the sole call, so an automatic match on `ClockTime` can't pass it. This shows the selector was enforced in these trials.

## Findings

No critical issues. `design.md` isn't applicable: it's optional, and this change is two tests and documents. Code pattern consistency: the new tests follow the file's style, and ruff passes.

Warnings, none blocking the scenarios:

- **MP-A06 isn't fully met.** It asks strict schemas to pass on each enabled route, and DeepSeek's nested schemas don't. The owner accepted this in Decision 0005, under the scenario's "remain disabled".
- **DeepSeek's streamed tool arguments arrived in 2 chunks.** The fixture ran and passed, but real fragmentation on that route is covered only by the fake transport. Terra's arrived in 15.
- **Cancellation:** `provider_stop_observed` is false on both routes, and each cancelled call stays at its worst-case charge.
- **The upstream provider** is `null` in every report.
- **MP-A09** wasn't exercised on a live route.
- **Run before the timeout fix:** the corpus ran with the 5-second client timeout fixed in `f96cfe2`. No fixture has run live at 130 seconds. A slower reply would have been recorded as an error, so this affects what could have failed, not the passes above.
- **Three trials per fixture on one day,** and the runner has had no independent review.

## Limits

Harness and fast results are local evidence only. This doesn't establish H1 or product acceptance. Task quality stays with US-10.1. No real goal has succeeded on either model, as `docs/engineering/evidence/LIVE-GOAL-1/summary.md` records, and US-3.4's scenarios don't require one.
