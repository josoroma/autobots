# Verification — us-12-1-stop-offering-deepseek-new

Change: us-12-1-stop-offering-deepseek-new
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Leave it out of every choice | PASS | `scripts/qualify_identity.py`, disposable stack, real browser. No DeepSeek option on Home's model choice, the workspace default, a role override or the Expert editor. A session and Continue in a new run use the same disclosure component as Home, so they're covered by reading it, not by their own assertion |
| Refuse it through the API | PASS | A real API. The workspace default, a role override, a run's `run_profile` and an Expert's binding each answer 422 `model_not_offered` saying DeepSeek isn't offered until qualified. The stored policy keeps its version |
| Refuse a saved choice without substituting | PASS (arranged) | The database holds a default naming DeepSeek, as a write can't now. A new run answers 409 with the same reason, the run list is unchanged, and the policy is unchanged. A workflow and a routine occurrence on an Expert's saved binding refuse with `model_not_offered`, with no run, and the saved choice stands. Choosing Terra on the screen clears it. A session's run on an Expert's saved binding goes through the same line as a new run, and has no assertion of its own |
| Leave admitted runs as they are | PASS (arranged) | Runs admitted directly on DeepSeek, as they were before this: `qualify_worker_inference.py` runs one through the real worker and SDK on a fake transport, sending DeepSeek's wire ID. `qualify_upgrade.py` resumes one. A child under a frozen DeepSeek policy is admitted on that route. `PROFILES` still holds it |
| Keep its record visible | PASS | Settings shows DeepSeek's stored status, date, configuration and limits, and lists it as approved and not offered. Operations shows its limits |
| Keep the qualification runner working | PASS | `tests/test_route_qualification.py` runs the runner on a fake transport, and the runner never goes through what stops new runs. No paid call |

Checks on the final code: `fast`, `harness` and `app_db.py qualify` exit 0, the identity qualifier's 420 cases and the worker inference qualifier's 45 pass, and `openspec validate` is clean.

## Findings

- **A saved choice stops new work until its owner changes it,** with no substitute. Decision 0013 doesn't name this. It's my reading of MP-01's no-fallback rule, recorded in the decision and reported to the owner.
- **`scripts/live_goal.py --profile openrouter_deepseek_flash` is now refused,** as it sets the workspace default through the API. Qualifying DeepSeek through the product path has no route until a decision gives it one. The direct runner still works.
- **Tests that used DeepSeek as the other model** now arrange it in the database: `saved-choice.spec.ts` for role effects, since no screen can make a role differ now.

## Not exercised

Nothing live. This story makes no paid call.
