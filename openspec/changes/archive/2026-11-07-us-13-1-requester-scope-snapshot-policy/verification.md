# Verification — us-13-1-requester-scope-snapshot-policy

Change: us-13-1-requester-scope-snapshot-policy
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 2 reqs |
| Correctness | 2/2 reqs covered, each scenario observed on a disposable stack |
| Coherence | Followed `design.md` |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Record the three fields with the proposal | PASS | `tests/db/approval_check.py`, run by `scripts/qualify_identity.py` on a disposable stack, through the real gateway. The stored request holds `requested_by` (the person who started the run), `requested_by_agent` `{"kind": "coordinator"}`, a `scope_snapshot` of the granted tools and paths that hashes to the stored `scope_hash`, `approval-policy/1` with rule `consequential_external_write`, and its 64-character argument hash. Changing any of the five columns afterward fails with `AB002`. A child admitted with a parent run as its actor records the parent's person. In a real browser, an Expert run's card reads `Requested by: you started this run, and Expert "Mail sender", version 2, proposed it.`, with the scope `tools mock_send version 1…` and `Policy version: approval-policy/1, rule consequential external write.`. A run with no Expert names the coordinator. |
| Don't invent what wasn't recorded | PASS (arranged) | A pending request cleared by the superuser with triggers bypassed, as the migration finds an older row. As `autobots_runtime`, clearing a stored requester and filling in `requested_by_agent`, `scope_snapshot` or `policy_version` are each refused as immutable. In the browser the card shows requester, scope and policy as not recorded, beside reason and target. A changed hash answers `409 approval_mismatch`, the view's hash is the one stored, and Reject moves the run on. |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification`, `identity_qualification` (462 cases, none failing), `persistent_apply_qualification`, `supabase_stack_qualification` and the rest passed |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (555), lint, format, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/app_db.py types` | 0 | 449 cases. `packages/db-types` regenerated, and the generated row types match the schema |
| `openspec validate us-13-1-requester-scope-snapshot-policy` | 0 | valid |

## Findings

**Found and fixed during implementation:**

- The first identity run failed because, in `tests/db/approval_check.py`, a loop variable named `value` hid the check's `value()` helper. This was a test bug. It was renamed.
- The legacy arrangement can't bypass the trigger as `autobots_runtime`. It moved into `scripts/qualify_identity.py`, which clears the row as `supabase_admin` and then tries the fill-ins as the runtime role.

**Suggestions, not blocking:**

- A routine's run records no person, and the inbox then says "no person is recorded for this run". No routine approval was exercised here, and routines have no screen in this release (Decision 0009).
- The workflow route passes the signed-in user as `started_by`. No workflow approval's requester was asserted.

## Limits

- **The persistent install wasn't migrated.** It stays at migration 35, and this code can't read approvals there until `apply` runs. Decision 0015 authorizes no persistent change.
- **The policy version is changed by hand.** `tests/test_tools.py` pins the current rules and reason texts to `approval-policy/1`, but a new approval condition elsewhere would need its own bump.
- **The Expert's name is read when the view loads,** not stored. Only its ID and version are snapshots.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
