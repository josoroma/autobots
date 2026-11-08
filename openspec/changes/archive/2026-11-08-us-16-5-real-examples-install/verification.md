# Verification — us-16-5-real-examples-install

Change: us-16-5-real-examples-install
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Scenarios

All on the owner's persistent install, through `persistent_install.py examples --paid` with live OpenRouter calls, and `persistent_install.py screens` in a real browser as the owner.

| Scenario | Result | Observed |
|---|---|---|
| Experts and workflows | PASS | The concept seed created the five Experts and six workflows on the first attempt and kept them on each later one; the owner's earlier Expert and workflow are still there. In the browser, Experts and Workflows list every name. Market watcher and Research analyst each got one new version adding `publish_artifact` (E7), earlier versions kept |
| Real runs under a cap | PASS | Four passes, each reserving US$0.45 from the shared ledger first. Goal 1 on Terra succeeded with `growth.md` published. Goal 2 with Brief writer on Sol failed before the fix (`plan_out_of_scope`), and after it succeeded with `brief.md` published. The workflow run failed twice (`plan_out_of_scope`, then the research step's `no_published_artifact`), and after both fixes reached its gate: the research step published `supabase.md`, and the compare step finished. Total spend 10 + 12 + 5 + 17 calls, 14,437 + 20,589 + 6,781 + 26,574 micro-USD, every call with a reported charge, each pass far under its US$0.45. The key was in no stored row and no log file after any pass. In the browser, Runs shows the goals and the workflow run |
| A pending approval | PASS | One `workflow_approval` request is pending on the workflow run. In the browser, Approvals shows it waiting with "you started this run, and the coordinator proposed it", the run "Workflow Vendor due diligence, version 1", the policy reason and version, the scope, the expiry, and the exact request's fields, JSON and digest. Screenshot looked at: `.checks/install-screens/approvals.png` |

## Defects found and fixed in this story

- **Plans citing criteria by text (E8):** under Sol, and in a delegated step on Terra, `propose_plan` cited `"c1: …"` and invented a criterion from a delivery line, read from the run's checkpoint. Fixed in the system prompt, the opening and `PlanTask.criteria`'s description, with `tests/test_plans.py`; validation unchanged.
- **Experts that save but can't publish (E7):** amended SD-02 and the seed, with `tests/test_concept_seed.py` and `tests/db/concept_seed_check.py`.
- **The command itself:** an Expert now runs through a direct session, as the composer does; a failure before the worker starts cancels what it admitted. The one stray queued run from the first attempt was cancelled through the API, and its US$0.45 hold released after confirming zero model calls since. A slip that removed `goal`'s refuse-other-work guard was caught by the harness and reverted to HEAD.

## Runs

- `python3.12 scripts/verify.py --profile fast`: exit 0.
- `python3.12 scripts/verify.py --profile db`: exit 0, 668 cases, inputs unchanged.

## Findings

- The workflow run is waiting, so the examples' last ledger entry keeps its full US$0.45 held: the shared ledger reads 807,457 of 1,000,000 micro-USD though about 68,000 were spent. Only an output block follows the gate. Settling it after the owner decides is a ledger reconciliation, not done here.
- Two delegated research attempts inside the successful workflow run ended `plan_incomplete` before one succeeded; Runs shows them.
- Nothing here establishes H1, product acceptance or task quality. No independent review, by the delivery rule.
