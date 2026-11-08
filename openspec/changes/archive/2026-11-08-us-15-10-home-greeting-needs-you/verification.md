# Verification — us-15-10-home-greeting-needs-you

Change: us-15-10-home-greeting-needs-you
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 3 of 3 tasks complete. 1 requirement added to `studio-shell`.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **Arrangement:** `scripts/qualify_identity.py` gives an owner an America/Costa_Rica workspace and the profile name Ada. It adds seven runs a minute apart, newest first:
  - `waiting_input`
  - `paused`
  - `waiting_approval`, with two pending approvals
  - `running`, with one of two plan tasks done
  - `succeeded`, charged US$0.07
  - `succeeded`
  - `failed`
- **"Greeting by the workspace's timezone":** observed in `python3.12 scripts/verify.py --profile db` (exit 0, 558 cases), `home.spec.ts` (passed). The browser clock was fixed to 09:00, 14:00 and 20:00 Costa Rica time.
  - The greeting read "Good morning, Ada", "Good afternoon, Ada" and "Good evening, Ada".
  - The page's `h1` read "What should we work on?" and followed the greeting in document order.
  - axe found no violations.
- **"Greeting boundaries":** observed in `home.spec.ts` (passed). At 04:59, 05:00, 11:59, 12:00, 17:59 and 18:00 local time it read evening, morning, morning, afternoon, afternoon and evening.
- **"Needs you":** observed in `home.spec.ts` (passed).
  - Needs you listed both pending approvals, each with `create_github_issue`, the run's goal and a Review link to `/approvals?approval=<id>`.
  - It listed the `waiting_input` run with "Reply on the run" linking to `/runs/<id>`.
  - It didn't list the paused run.
  - Following each Review link, including the request that isn't first, opened Approvals with that request's detail shown. axe found no violations.
- **"Recent runs":** observed in `home.spec.ts` (passed).
  - Exactly the five newest runs were listed, in order.
  - Their states were Waiting for input, Paused, Waiting for approval, Running and Succeeded.
  - Progress or spend read "US$0.00 spent" three times, then "1 of 2 tasks" and "US$0.07 spent".
  - Each relative time matched "N minutes ago" or similar.
  - The two oldest runs were absent, and axe found no violations.
- **Warning (non-blocking):** "Reply on the run" opens the run's page. The web app has no control yet for answering a `waiting_input` run, although the API has `POST /v1/runs/{run_id}/input`. The link meets this scenario, but replying from the run page is not built.
- **Found during verification, fixed before this record:** the first `db` run failed `slice-inspector.spec.ts`, whose `getByRole('link', { name: 'Runs' })` also matched Home's new "All runs" link. The link now reads "Open the run list", and the rerun passed.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed (exit 0), including `slice-visual` for Home's contrast, axe, keyboard order and zoom in both themes. Needs you and Recent runs are stacked, so Tab never climbs a column.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
