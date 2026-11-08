# Verification — us-16-4-current-install-sol-s

Change: us-16-4-current-install-sol-s
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Scenarios

| Scenario | Result | Observed |
|---|---|---|
| Backed up, then current | PASS | At the owner's request the assistant ran `.checks/install-current.sh`. It stopped web, API and worker; `local_backup.py keygen` wrote a backup key apart from the backup; `local_backup.py backup` returned `backed_up` for configuration and the five volumes. Then `persistent_install.py apply --project autobots-install` returned `applied` with migrations 36 to 50 on top of 35. Rebuilt and restarted, `persistent_install.py screens` saw Operations read "50 of 50 migrations applied." in the browser as the owner |
| A live pass inside the authorized cap | PASS | `route_qualification --profile openai_gpt_6_1_sol --paid`, 39 calls, each reserved at its 21,504 micro-USD worst case before it was sent. Sol's ledger, shared with 2026-11-07: 281,172 of 1,200,000 micro-USD committed. Today: 11,642 reported, 6 calls without a reported charge, still held at worst case. Each fixture passed three times except `schema_nested`, unsupported three times, as on 2026-11-07. Report: `.checks/route-qualification/sol/report-openai_gpt_6_1_sol.json`; the 2026-11-07 report kept beside it |
| Today's result on Settings → Models | PASS | On the install, as the owner, `install-current.spec.ts` read Sol's route: "Qualified, with the limits below", tested on 2026-11-08, its limits naming both days, its configuration naming openai/gpt-6.1-sol. Screenshot looked at: `.checks/install-screens/models.png`. On a disposable stack, `sol_profile_check.py` read the row as `qualified_with_limits 2026-11-08 US-14.15, US-16.4` after migration 50 |

## Runs

- `python3.12 scripts/verify.py --profile fast`: exit 0.
- `python3.12 scripts/verify.py --profile db`: the first run passed every case of this story, but failed `search.spec.ts`'s check that ⌘K does nothing in a text field: the run list's arrival could take focus from the filter before the key was pressed. The test now waits for the page to settle and asserts focus first. Rerun: exit 0, 667 cases, inputs unchanged.

## Findings

- The backup completed and is encrypted with its manifest signed, but it was not restored into an isolated instance and verified. That needs the backup key, which stays in the owner's hands; the runbook's restore and verify steps remain available. The scenario's wording says "completed, encrypted backup" for that reason.
- No independent review, by the delivery rule.
