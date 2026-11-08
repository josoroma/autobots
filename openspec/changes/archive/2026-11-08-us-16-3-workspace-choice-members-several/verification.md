# Verification — us-16-3-workspace-choice-members-several

Change: us-16-3-workspace-choice-members-several
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Scenarios

Observed in Chromium by `tests/browser/workspace-choice.spec.ts` in the `db` profile, against the real API and a disposable stack. Member P was arranged in `qualify_identity.py` in two workspaces: their own, holding a run "Only in workspace P", and runs-g's, whose runs include "Spend fully reported".

| Scenario | Result | Observed |
|---|---|---|
| Choose, then work | PASS | Signed in with nothing chosen, the sidebar said "Choose a workspace". After choosing P, Runs showed "Only in workspace P" and not G's runs, still after a reload. The cookie held P's ID, HttpOnly and SameSite=Strict |
| Change the workspace | PASS | Choosing G in the sidebar: Runs showed "Spend fully reported" and not P's run, and the cookie held G |
| The browser's choice is still checked | PASS | With the cookie set to a workspace P doesn't belong to, `/api/v1/runs` returned 403 `forbidden`, and the body didn't contain that workspace. `/api/workspace` with valid CSRF also refused it, with 403 |
| Only a same-origin, CSRF-checked request sets the choice | PASS | Without the CSRF token: 403 `missing_csrf`. From another origin: 403. The cookie stayed P |
| One workspace needs no choice | PASS | runs-g, a member of one workspace: no chooser, Runs worked, no cookie set |

## Runs

- `python3.12 scripts/verify.py --profile fast`: exit 0.
- `python3.12 scripts/verify.py --profile db`: the first run passed all five new tests but failed `identity.spec.ts`'s account footer test. That test expected the old rule that a member of two workspaces works in the first one. Decision 0023 E3 drops that implicit default, so the test now checks "No workspace" before a choice and the chosen workspace's role after it. Rerun: exit 0, 667 cases passed, inputs unchanged during the run.

## Findings

None blocking. A member of several workspaces who hasn't chosen sees member reads, such as readiness and the approvals badge, as unavailable until they choose; the sidebar asks them to. No independent review, by the delivery rule.
