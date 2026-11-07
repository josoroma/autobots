# Verification — us-14-14-admitted-model-browser-use

Change: us-14-14-admitted-model-browser-use
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 6/6 tasks, 3 reqs |
| Correctness | 5/5 scenarios observed |
| Coherence | Followed the proposal and Decision 0020. No design.md. The change keeps its original ID, which still says browser-use |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Each step is an admitted call | PASS | `tests/db/browsing_loop_check.py`, run by `scripts/app_db.py` in the `db` profile with the real `LoopMiddleware`, admission, ledger and run usage, a scripted model and scripted pages. A run admitted with no model choice froze researcher on `openrouter_sol`. Three steps (`open_link`, `scroll`, `finish`) produced three `model_invocations` rows with role `researcher`, profile `openrouter_sol`, wire `openai/gpt-6.1-sol`, status `succeeded`, 1000 reserved and 100 charged each, tool names recorded. The run's `model_calls` was 3, and the loop ended `done` with the model's summary. Each request held the page as text: address, title, text and `[1] More information -> …`. The transport half: `test_a_browsing_step_reaches_the_transport_on_the_researcher_route_with_tools_required` sends a step through the real SDK over a mock transport, on the researcher's wire ID with `require_parameters` and no fallbacks. `test_browsing_binds_the_runs_frozen_researcher_route` shows `role_route` takes the route from the run's frozen policy |
| An uncertain outcome follows the existing rules | PASS | Same check: a step whose call failed as a partial stream stopped the loop with `partial_stream`. Its invocation was `uncertain` with 1000 still reserved, and the model was called once |
| No other model path | PASS | Same check: an `AdmittedModel` over the scripted model, called outside admission, raised `UnadmittedModelCall` with 0 model calls. A run with a 10 µUSD budget was refused `budget_exceeded` with no invocation row and 0 model calls. The loop module builds no client: it takes a step callable, and `admitted_steps` wraps the attempt model it's given (`test_an_unadmitted_call_never_reaches_the_model`) |
| Actions are required tool calls, refused on a route lacking tool support | PASS | On the mock transport, the request's tools were exactly `open_link`, `go_to`, `scroll` and `finish` with `tool_choice: required`. Each tool's schema forbids extra properties. `test_a_researcher_route_without_tools_is_refused_before_anything_is_sent`: a catalog entry without `tools` makes `role_route` return `unsupported_request_option` before any key is read or request sent. `test_a_run_without_a_researcher_binding_has_no_browsing_route` returns `route_not_bound` |
| An answer that isn't one valid action ends the call | PASS | `test_anything_but_one_valid_action_ends_the_call_with_no_further_step` covers 7 answers: plain text, an unknown action, link 0, a link past the list, an extra argument, two tool calls, and an invalid tool call. Each ends `invalid_action` after 1 request, with the next scripted reply unused. Refused navigations end `refused_action` and keep the notes so far |

The CDP page was also checked against the real isolated executor, once, outside any profile. It reached example.com and then iana.org through the proxy and returned the title, text and 26 links. Its containers were removed afterwards. `test_the_cdp_page_reads_text_and_links_and_scrolls_its_window` shows it evaluates only its fixed reader.

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy (152 files), pytest (722), contract drift and the rest passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the five browsing cases, `identity_qualification`, `persistent_apply_qualification`, `non_mutation_guard` and the rest passed |
| `openspec validate us-14-14-admitted-model-browser-use` | 0 | valid |

## Limits

- **No real model was called.** The live browse is US-14.16.
- **`browse_goal` isn't registered.** Nothing calls the loop from a run yet; that is US-14.12.
- "Scroll" moves the window of page text the model is shown. It doesn't scroll the browser, so content loaded on scroll isn't read.
- The executor's qualification fingerprint is unchanged: the page lives in its own module.
- No package was added or removed.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
