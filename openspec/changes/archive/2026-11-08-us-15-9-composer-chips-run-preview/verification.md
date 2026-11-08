# Verification — us-15-9-composer-chips-run-preview

Change: us-15-9-composer-chips-run-preview
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 5 of 5 tasks complete. 1 requirement added to `run-disclosure`.
- **Order:** `proposal.md`, the spec delta and `tasks.md` were written after the implementation in this session. They describe what was built and were validated before verification.
- **Arrangement:** `scripts/qualify_identity.py` arranges a composer owner whose workspace has the installation key. US$2.90 of a US$5.00 daily cap was charged today, so US$2.10 is left. Its one Expert, "Composer helper", grants `calculate` and `read_csv` and binds the executor to Sol.
- **"Budget choices within the daily cap":** observed in `python3.12 scripts/verify.py --profile db` (exit 0, 553 cases), `composer.spec.ts` (passed).
  - The chip offered US$0.25 to US$2.00 in eight US$0.25 steps, with US$1.00 selected, and "US$2.10 left of today's cap" was shown.
  - The disclosure changed from US$1.00 to US$1.50 on the choice.
  - Run sent `budget_micro_usd: 1500000` and got 202, and `/api/v1/runs/{id}` reports `limit_micro_usd` 1500000.
  - axe found no violations.
  - Unit tests `test_budgets.py` cover the range, the step, the default lowered to what's left, nothing left, and US$5.00 needing US$5.00 left.
- **"A budget outside the range is refused":** observed in `composer.spec.ts` (passed). Each request was changed on its way to the BFF.
  - US$5.25 got 422 `budget_out_of_range`, US$0.10 got 422 `budget_out_of_range` and US$1.10 got 422 `budget_off_step`.
  - US$2.25, above the US$2.10 left, got 409 `budget_above_daily_cap`.
  - Each showed the refusal with "No run started. Your draft is kept.", the goal text was unchanged and the run count didn't change.
  - A budget sent with an explicit limit got 422 `budget_conflict`.
- **"An Expert chip starts a direct session first":** observed in `composer.spec.ts` (passed).
  - With the Expert chosen, the requests went `POST /api/v1/sessions` (`kind: direct`, that Expert), then `POST /api/v1/runs` carrying that session's ID.
  - The run lists as `expert` "Composer helper", and its workspace shows that Expert.
  - With no Expert, only `POST /api/v1/runs` was sent, with no session, and the run lists as `goal`.
- **"Preview what the run would use":** observed in `composer.spec.ts` (passed).
  - With no saved policy, the chips read "Terra · 13 roles" and "Sol · researcher", followed by the goal tools, with no plan tools.
  - Choosing Sol for the run gave "Sol · 14 roles".
  - With the Expert, the tools were exactly `calculate` and `read_csv`, with "Sol · 2 roles" and "Terra · 12 roles".
  - Each came from `/api/v1/run-preview` with `run_profile` or `expert_id`.
  - The fake OpenRouter's log gained only `/models` or `/key` lines while Home and the preview loaded, so no completion was sent.
- **"Attached files as chips":** observed in `composer.spec.ts` (passed). `notes.txt` showed `text/plain` and "11 B", and `rates.csv` showed `text/csv` and "2.0 KB".
- **Found during verification, fixed before this record:**
  - The first `db` run failed. The spec's `getByLabel("Goal")` also matched the "New goal" region, so the test now uses an exact label.
  - Home failed the visual walk and the 400% zoom check, which found 95px of sideways scroll. The chip selects' `px-3` overrode the select's chevron padding, and the selects couldn't shrink.
  - Each select now sits in a shrinkable wrapper, keeps its right padding and truncates. The rerun passed `slice-visual`, covering contrast, axe, keyboard order and zoom, in both themes.
  - The existing spec where Tab goes from the goal to "Model for this run" still passes, as the model chip comes first.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed with all 553 cases. That includes the 74-test main suite and the slice suite, whose runs still send `limit_micro_usd` directly.
- **Budget ceiling:** the per-run ceiling migration (US$1.00 to US$5.00, applied to rows still at the old default) is exercised by the admitted US$1.50 run. `admission_check.py` still sets its own US$1.00 ceiling and passed.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
