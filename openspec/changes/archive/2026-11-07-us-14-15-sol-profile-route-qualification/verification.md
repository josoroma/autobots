# Verification — us-14-15-sol-profile-route-qualification

Change: us-14-15-sol-profile-route-qualification
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 4 reqs |
| Correctness | 4/4 scenarios observed; the removal half of the last one on the repointed-profile path, as below |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Approved, and refused for new runs until qualified | PASS | Before Sol was offered: `scripts/qualify_identity.py` ran the browser suite on a disposable stack with real Auth, and Settings listed `openrouter_sol` with "Approved, and not offered for new runs until it's qualified." (the US-14.15 assertion in `settings.spec.ts`, passed). `services/agent/tests/test_model_policy.py`, with Sol out of the offered set: refusal is `model_not_offered` with "Sol isn't offered for new runs until its route is qualified.", DeepSeek's reason is unchanged, and researcher resolves to Terra. Every new-work path (run creation, Settings, Expert saves, workflows, routines, replays) calls the same `require_offered`, and the workflow route now returns the refused profile's own reason |
| Qualify the route live within its cap | PASS | `python -m autobots.operations.route_qualification --profile openai_gpt_6_1_sol --paid`, once, on 2026-11-07 after a dry run that sent nothing: 39 calls, none retried, no other model; US$0.011482 reported and US$0.140506 counted at worst case against US$1.20. Plain text, tool calls (auto, required, a named conflict), flat structured output, streamed text and tool arguments, continuation, truncation, refusal and cancellation passed 3 of 3; strict nested output was unsupported and stays disabled. Migration 41 stores it as `qualified_with_limits` with its configuration and limits, and the disposable-stack check reads that row back. Settings' route list reads from that table |
| Offered once qualified, with researcher on Sol by default | PASS | `tests/db/sol_profile_check.py`, run by `scripts/app_db.py` in the `db` profile: a run admitted with no model choice froze researcher on `openrouter_sol` with Sol's route (`openai/gpt-6.1-sol`, `openai/gpt-6.1-sol-20260929`) and the other 13 roles on Terra; a run naming Sol was admitted with every role on Sol; a run role override, a run-wide profile, a workspace role override and a workspace default naming Terra each froze researcher on Terra; all three profile checks admit `openrouter_sol`. Settings in the browser lists Sol without "not offered", and the Expert editor lists Sol |
| Frozen runs keep Sol, and removing it stops them | PASS, with the limit below | Same check: a child admitted under the parent's frozen policy kept it exactly, and the worker's `frozen_policy` resolves researcher to Sol on resume. A snapshot whose Sol route points elsewhere is refused, so the run stops instead of moving. Removing Sol outright takes the path a retired profile takes: `test_a_snapshot_frozen_on_the_retired_profile_doesnt_become_another_model` shows a frozen unknown profile refused, as Decision 0004's Astra removal did |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/qualify_web.py` | 0 | the web browser suite passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the Sol cases and the three-profile seed, `identity_qualification` with the Settings assertion, `non_mutation_guard` and the rest passed |
| `openspec validate us-14-15-sol-profile-route-qualification` | 0 | valid |

## Limits

- **Sol wasn't removed by a real migration** to watch a frozen run stop: that needs a build without Sol. The removal path is the retired-profile path, shown for Astra, and a repointed Sol route is shown stopping.
- A workspace that has saved a model policy has a workspace default, which wins over researcher's Sol default, as Decision 0019 S3 orders it.
- The qualification is three trials per fixture on one day; it says nothing about task quality.
- **The persistent install wasn't migrated.** Migrations 38 to 41 wait for the owner.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
