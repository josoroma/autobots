# Verification — us-14-12-goal-driven-browsing

Change: us-14-12-goal-driven-browsing
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 7/7 tasks, 4 reqs |
| Correctness | 4/4 scenarios observed; two halves arranged, as below |
| Coherence | Followed the proposal. One addition: browsing needs the owner's switch `AUTOBOTS_BROWSER_EXECUTOR=enabled` as well as a current qualification, so a report left in `.checks` doesn't turn it on (runbook). The metered count now follows approval, so a call waiting for a person isn't counted twice. No design.md |

## Scenarios

All rows are from `scripts/qualify_browse_goal.py`, which ran 17 of 17 cases on the final code. It used a disposable database, the real gateway, approvals, loop middleware and admission, the real isolated executor reaching `https://example.com/`, and a scripted model.

| Scenario | Result | Observed in |
|---|---|---|
| A read-only browse is summarised and recorded | PASS | An Expert-bound run's call was approved, then browsed example.com with `allowed_domains` example.com. Results:<ul><li>The call succeeded with `stopped: done`, `source: third_party` and the model's summary, untruncated.</li><li>Visited was `["https://example.com/"]`, with 2 steps and 2 model calls.</li><li>The model was shown the real page as text, under the title "Example Domain", with a numbered link.</li><li>Exactly one tool use was metered: provider `autobots`, group `browsing`. Its public input was only `start_url`, `allowed_domains` and `max_steps`. Its public output was only `stopped`, `steps` and `visited_count` (1).</li><li>Both model calls were `researcher` invocations on `openrouter_sol`, `succeeded`, so the steps are the run's model spend.</li><li>No browser container was left.</li></ul>Offline: `test_a_call_starts_one_session_for_its_domains_and_always_removes_it` shows a query string dropped from visited URLs |
| Outside its domains, a submission, an invalid answer and its limits | PASS, one half arranged | Each was its own approved call:<ul><li>Opening a link to iana.org, outside `example.com`: `refused_action` after 2 calls, keeping "so far".</li><li>`type_text`: `refused_action` after 1 call.</li><li>Plain text: `invalid_action` after 1 call.</li><li>`max_steps` 2: `max_steps` after 2 calls.</li><li>`max_seconds` 10 with slow steps: `max_seconds`, keeping "slow".</li><li>No container was left after any of them.</li></ul>**Arranged:** the action set has no submission, so "a submission that gets past the action set" was arranged as a navigation the proxy refuses. `go_to https://localtest.me/` was inside the call's domains, but the name resolves to loopback, so the egress proxy refused it. The call ended `refused_action` after 1 call. The request guard refusing non-GET requests and bodies is US-14.13's qualified behaviour |
| Granted only through an Expert, approved on every call | PASS, one half arranged | **Arranged:** a run granted `browse_goal` with no Expert behind it, since no product path grants it that way (plain goals and workflows don't list it). It was denied `expert_grant_required`, with 0 containers and 0 model calls. The Expert's call returned `approval_pending`. The approval request was `arbitrary_execution` and showed `task`, `start_url`, `allowed_domains`, `max_steps` and `max_seconds`. There were 0 containers, 0 invocations and 0 model calls until it was approved |
| Stays disabled while unqualified | PASS | With the switch off, `browse_goal` read `disabled_by_policy` with reason `isolated_executor_not_qualified`, provider `autobots`, not registered. Saving an Expert naming it was refused `expert_tool_unavailable`. The catalog's providers were within TC-03's six. Offline tests:<ul><li>`test_the_registry_refuses_arbitrary_execution_whose_executor_isnt_qualified`.</li><li>`test_browsing_needs_the_owners_switch_as_well_as_a_report`.</li><li>`test_qualified_it_is_registered_expert_only_metered_and_always_approved` (the other state).</li></ul>The Tools screen shows the new repair text (`tools.spec.ts`, in the web suite). `browser_use` is gone from the contract, the generated client and the screen |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/qualify_browse_goal.py` | 0 | 17 of 17 cases, no executor container or network left, other Docker resources untouched |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy (155 files), pytest (750), lint, typecheck, contract drift and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` (467 cases), `identity_qualification`, `persistent_apply_qualification`, `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed |
| `openspec validate us-14-12-goal-driven-browsing` | 0 | valid |

## Limits

- **No real model was called,** so nothing was spent. The live trial with Sol is US-14.16.
- The live check reached only example.com through the proxy. The refused navigation to iana.org never left the browser, since the loop refused it first.
- `browse_goal` stays off on this Mac's persistent install until the owner sets `AUTOBOTS_BROWSER_EXECUTOR=enabled` for the API and worker.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
