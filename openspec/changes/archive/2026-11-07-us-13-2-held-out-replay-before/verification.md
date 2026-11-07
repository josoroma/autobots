# Verification — us-13-2-held-out-replay-before

Change: us-13-2-held-out-replay-before
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 2 reqs |
| Correctness | 2/2 reqs covered, each scenario observed on a disposable stack with a scripted model |
| Coherence | Followed `design.md`, with one deviation recorded below |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Gate promotion on a real replay | PASS | `tests/db/improvement_check.py`, run by `scripts/qualify_identity.py` on a disposable stack with Storage, with the scripted model in `tests/db/goal_loop_script.py`. A memory proposal that passed its checks is refused with `replay_required` when no replay ran. A held-out task whose goal is the evidence run's goal is refused with `task_drawn_from_proposal`, and another workspace gets `candidate_not_found`. While its run is queued, promotion is refused with `replay_running`. In the replay run, `search_memory` returns the proposal as a `proposal` hit, while a run's search outside the replay finds nothing. The run is verified like any other, from its published artifact, and ends `succeeded`. The replay reads `passed`, promotion succeeds, and the version's provenance names the replay. A skill replay's run opens with the proposal marked as reference. A proposal with no reviewer cases passes its checks and is still refused with `replay_required`, so text checks can't pass it alone. A reviewer's failing case still fails one. |
| Refuse without a passing replay | PASS | A replay of a second version finds it in place of the active one, then its run ends `failed` with no plan. Promotion is refused with `replay_failed`. Searches still find version 1 and not the new text. Rollback to 0 and back to 1 both work. A later passing replay promotes it. |

No paid replay ran. Every model call here was scripted.

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification`, `identity_qualification` (516 cases, all passed), `persistent_apply_qualification`, `supabase_stack_qualification`, `non_mutation_guard` and the rest passed |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (555), lint, typecheck, contract drift, API client and web unit tests passed |
| `openspec validate us-13-2-held-out-replay-before` | 0 | valid |

## Findings

**Deviation from `design.md`:** the improvement check moved from `scripts/app_db.py` to `scripts/qualify_identity.py`. A replay run is verified from Storage, which the database-only qualifier lacks. Its first run failed with `storage_unavailable`, so the replay read `failed`. `app_db.py` keeps the anonymous-read denial.

**Found and fixed:**
- `replay_state` first counted `succeeded` as a terminal failure, which would have read a part-finished replay as failed. The type check exposed the code, and the logic was fixed before any run.
- The test reran regression on a proposal that had already passed, now that text cases are optional. It got its own proposal.
- One `db` run failed `non_mutation_guard`, because that test was edited while the run was going. The rerun touched nothing and passed.

**Suggestion, not blocking:** `POST /v1/improvements/{id}/replay` and its readiness check were exercised by OpenAPI generation and the app factory test, not by an HTTP call against a stack.

## Limits

- **No paid replay was run,** and a live one is unqualified. A replay's runs spend for real only when an owner requests one on a stack with a key.
- **A replay uses the default loop's tools,** not the Expert's, as Decision 0016 states.
- **"Drawn from" matches exact goal text,** after whitespace and case are normalized.
- **The persistent install wasn't migrated.** It stays at migration 35, behind US-13.1's migration and this one.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
