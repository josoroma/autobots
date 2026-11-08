# Verification — us-15-19-operations-jobs-chart

Change: us-15-19-operations-jobs-chart
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 3/3 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 3/3 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0. Pytest ran 810 tests, including the jobs chart contract test and the pinned path list.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T16:34Z. Every check passed, including both `operations-jobs.spec.ts` tests and the visual walk of Operations in both themes.
- **`python3.12 scripts/verify.py --profile full`:** exit 0.
- **Palette:** `validate_palette.js` ran on every stack order of the four status tokens. The chosen order has a worst adjacent CVD ΔE of 8.9 in light and 10.4 in dark, and a normal-vision ΔE of 19.6 or more.
- **Visual check:** I looked at the walk's `operations-light.png` and `operations-dark.png`. They show the stacked segments with gaps, the textures, the legend totals and recessive grid lines, and no overlap.

## Scenario: Buckets and series — PASS (browser, disposable stack)

`tests/db/operations_live.py jobs` gave the `ops-n` workspace, set to America/Costa_Rica, runs whose status changes fall a set number of hours before the database clock:
- 1 hour: failed, and cancelled;
- 2 hours: succeeded, and waiting_approval;
- 3 hours: paused (after running at 4 hours), and running;
- 5 hours: waiting_input;
- 30 hours: succeeded, outside the chart.

The read returned timezone America/Costa_Rica and 24 hours. The last hour's label matched the current hour in Costa Rica, both from its `starts_at` and from the browser's clock. The counts, checked in every hour:

| Hours before the current one | Succeeded | Waited | In progress | Failed |
|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 2 (cancelled included) |
| 2 | 1 | 1 | 0 | 0 |
| 3 | 0 | 0 | 2 | 0 |
| 5 | 0 | 1 | 0 | 0 |

Every other hour was zero. The 30-hour change and the earlier "running" change of the paused run weren't counted. The text table's 24 rows gave the same hour labels and numbers as the read, cell by cell.

## Scenario: Jobs per hour with a text alternative — PASS (browser, disposable stack)

Operations showed:
- the heading and a plot with `role="img"`, named "Jobs per hour over the last 24 hours: 1 succeeded, 2 waited for a person, 2 in progress, 2 failed or cancelled.";
- 24 hour groups;
- a legend reading "Succeeded 1", "Waited for a person 2", "In progress 2" and "Failed or cancelled 2";
- textures as well as color: the waited pattern rotated 45° and the failed pattern 135°.

Hovering the column two hours back showed a tooltip with its hour, "Succeeded: 1" and "Waited for a person: 1". The disclosed table gave the same counts. axe found no violations at WCAG 2.2 AA.

## Scenario: Counts only — PASS (browser, disposable stack; unit)

- **Keys:** the response held only `schema_version`, `timezone` and `hours`, and each hour only `starts_at`, `hour`, `succeeded`, `waited`, `failed` and `in_progress`.
- **No identifiers or goal text:** no UUID-shaped text, and neither arranged goal text ("Arranged chart job", "Operations job").
- **Offline:** the unit test pins those fields and refuses an hour label that isn't `HH:00`.

## Findings

- **Interpretation (design.md):** "in progress" counts a run that is now running or paused, in the hour of its latest status change. D14 doesn't say which hour that series belongs to.
- **Interpretation (design.md):** the series wear status tokens, not the Luma chart ramp. That ramp is one hue and fails as a categorical set, while these series mean outcomes. Status tokens are outside the validator's categorical scope; their mitigation is labels, the legend, textures, the tooltip and the table.
- **Not established:** H1 and product acceptance. No model was called.
