# Verification — us-14-20-tool-guide-shown-modal

Change: us-14-20-tool-guide-shown-modal
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 6 reqs |
| Correctness | 6/6 scenarios observed |
| Coherence | Followed the proposal. One change, recorded in Decision 0026 G1. The first `db` run showed that making a missing guide break the catalog also broke test fixtures that register their own tools. So `require_guides` now enforces the guides, failing with the tool's name, and the catalog shows a fixture's tool as "Not described yet." |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Every tool carries a guide | PASS | `test_every_registered_and_planned_tool_has_a_full_guide`: all 35 descriptors, registered and planned, `cronjob` included, carry what, when and why that aren't empty. The guides cover exactly the tools that exist.<br>`test_the_catalog_and_each_version_carry_the_guide` passes.<br>The Tools browser suite reads `guide.what` from `GET /api/v1/tools/calculate/versions/1`, and the regenerated OpenAPI document and TypeScript client include `ToolGuideView` (`fast` profile) |
| A tool without a guide fails a test | PASS | `test_a_tool_without_a_full_guide_fails_naming_it`, 3 cases: no guide, an empty what, a blank when. Each raises `MissingGuide` naming `unguided_tool` |
| Choosing a tool opens its modal | PASS | `tools.spec.ts` in `scripts/qualify_web.py`, 42/42:<ul><li>Clicking Calculate puts `?tool=calculate` in the URL, keeping `q`, and opens a `dialog` element named "Calculate". No "Tool detail" side panel renders.</li><li>The modal shows What ("Computes the sum, mean, minimum or maximum of a list of numbers."), When and Why, then inputs and outputs: `operation` Required and Shown, `result` Required.</li><li>A deep link to `/tools?tool=create_github_issue` opens its modal with the repair naming Settings → Keys & vars.</li></ul> |
| Granted to, Copy schema and the full page from the modal | PASS | In the modal:<ul><li>Copy schema copied exactly version 1's input schema.</li><li>"Open as a page" links to `/tools/calculate`, which renders the full detail with the guide.</li><li>`experts.spec.ts` (identity suite, `db` profile) opens `/tools?tool=read_csv` and finds Granted to listing Market watcher, Issue triager and Nightly triage, with axe passing.</li></ul> |
| Closing returns focus to the tool's link | PASS | `tools.spec.ts`: Escape closed it, removed `?tool=` and focused the Calculate link. Reopening and pressing Close, then reopening and clicking the backdrop, each closed it with focus back on the link |
| Accessible in both themes | PASS | `tools.spec.ts`: axe found no violations with the modal open, after setting the stored theme to `light` and to `dark` (checked on `html`). The dialog is a native `dialog` labelled by the tool's title. `showModal` makes the page behind it inert |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/qualify_web.py` | 0 | 42/42 browser tests |
| `python3.12 scripts/verify.py --profile db` | 0 | Passed with inputs stable: app_db 544/544 and identity 670/670. The first run failed, because the provider key check's fixture tool had no guide, and the US-14.5 and Granted to browser tests failed after it. The second run, after the fix above, passed |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed |
| `openspec validate us-14-20-tool-guide-shown-modal` | 0 | Valid |

## Limits

- Not checked on the persistent install until the owner runs `make build` and restarts.
- Not H1 or product acceptance. No independent review ran.
