# Verification — us-14-19-cronjob-tool-manages-workspace

Change: us-14-19-cronjob-tool-manages-workspace
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension | Status |
|---|---|
| Completeness | 7/7 tasks, 9 reqs |
| Correctness | 9/9 scenarios observed on a disposable database with no model |
| Coherence | Followed the proposal. Additions:<ul><li>The approval policy moved to `approval-policy/2`, with a new rule `action_marked` for per-call approval. Migration 53 admits that rule, and the policy tests and the approvals browser test now expect version 2.</li><li>`cronjob` joined the execution contract's tool table. Adding a tool keeps older checkpoints valid.</li><li>The public row types were regenerated for `routines.removed_at`.</li></ul> |

## Scenarios

The "DB" rows come from `tests/db/cronjob_check.py` (10 cases), which `scripts/app_db.py` runs in the `db` profile. It drives the real gateway, approvals, leases and routine service, and an Expert that grants `cronjob`. No model is called.

| Scenario | Result | Observed in |
|---|---|---|
| The catalog lists cronjob under Automation | PASS | **DB:** filtering by `automation` gives exactly `cronjob` 1, `autobots`, `reversible_internal_write`, `free_local`, no network, approval `by_action`, grantable to `expert`.<br>**Offline:** `test_the_catalog_lists_it_under_automation_for_experts_only` shows the six public fields. The Tools page labels the group "Automation" and the approval "Some actions wait for a person" (`fast` profile: type check and lint) |
| list runs without approval and stays in the run's workspace | PASS | **DB:** it returned only this workspace's two routines, with 0 approval requests. The other workspace's routine was absent |
| Every other action waits for a person's approval | PASS | **DB:**<ul><li>create, update, pause, resume, run and remove each returned `approval_pending`.</li><li>Each request's target named the action and the routine. create's and update's arguments carried the schedule, and the rule was `action_marked`.</li><li>The routines were unchanged, with 0 occurrences.</li><li>A rejected pause returned `approval_rejected` and changed nothing.</li><li>A remove after an approved pause waited for its own approval.</li></ul>**Offline:** `test_each_action_takes_its_own_fields` (7 cases) checks that `approval_when` holds for every action but list |
| create and update follow the routine service's validation | PASS | **DB, after approval:**<ul><li>Another workspace's target was refused `routine_target_not_found`, wider tools `routine_scope_widened`, an unknown timezone `timezone_unknown` and a stale version `routine_version_conflict`. None of them saved a routine.</li><li>A valid create saved version 1, with the run's starter as `created_by`, and a valid update saved version 2.</li></ul>**Offline:** 12 malformed inputs are refused before the gateway |
| pause and resume set enabled | PASS | **DB:** an approved pause set `enabled` false. An approved run on it was refused `routine_paused`, and an approved resume set it true |
| run admits one occurrence now, by the scheduled path's rules | PASS | **DB:**<ul><li>An approved run returned `admitted` with a run id, with exactly 1 admitted occurrence.</li><li>A second run, while that run was active, returned `skipped_overlap`.</li><li>With the credential check returning `credentials_required`, run returned `blocked` with that reason.</li><li>The admitted run had 0 model invocations.</li></ul> |
| remove marks a routine removed and keeps its history | PASS | **DB:**<ul><li>An approved remove set `removed_at` and `enabled` false. The routine was in neither cronjob's list nor `list_routines`.</li><li>After its `evaluated_until` was moved 3 hours back, evaluation admitted nothing for it.</li><li>Its 1 version and 3 occurrences remain. A later pause was refused `routine_not_found`, and a create reusing its name succeeded.</li></ul> |
| Granted only through an Expert | PASS | **DB:** a run with no Expert behind it was refused `expert_grant_required`, with 0 approval requests |
| Only public fields reach the tool-use record | PASS | **DB:** across 43 tool-use rows, the input keys were only `action`, `name` and `routine_id`, and the output keys only `routine_id`, `run_id` and `status`. The fake goal and input strings appeared in no row, `tool.use` event or tool-use listing |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile db` | 0 | Passed with inputs stable: `app_db_qualification` 544/544 and `identity_qualification` 670/670. The first run failed three things, fixed as follows:<ul><li>Drifted row types: regenerated with `scripts/app_db.py types`.</li><li>The approvals browser test expecting policy version 1: updated to version 2.</li><li>The slice test "an answer alone can't succeed" timed out once. It passed on the rerun, and nothing in this change touches it</li></ul> |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed |
| `openspec validate us-14-19-cronjob-tool-manages-workspace` | 0 | Valid |

## Limits

- No routine was created on the persistent install, and no paid run started. Migration 53 is for the owner to apply with `make migrate`.
- Not H1 or product acceptance. No independent review ran.
