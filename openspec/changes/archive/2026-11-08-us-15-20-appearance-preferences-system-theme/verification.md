# Verification — us-15-20-appearance-preferences-system-theme

Change: us-15-20-appearance-preferences-system-theme
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 1 modified and 1 added requirement |
| Correctness  | 2/2 requirements, 4/4 new scenarios observed, plus the preserved light/dark scenario |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0.
- **`python3.12 scripts/verify.py --profile full`:** exit 0. The browser suite reported "41 browser tests passed, 0 failed, 0 skipped", including every `appearance.spec.ts` test named below.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T17:01Z.
  - The first `db` run failed one test: my new locator `getByLabel("System")` also matched the sidebar's System section. It now uses role locators, and the rerun passed.
  - `slice-visual.spec.ts` runs only in `db`, so `full` didn't run it.

## Scenario: System follows the OS only once chosen — PASS (browser)

"System follows the OS only once chosen, and a reload restores it before paint", in a browser whose OS prefers light:
- **First load:** rendered dark in every recorded frame, with Dark checked.
- **Choosing System:** rendered light, and stored `system`.
- **The OS switching to dark:** rendered dark live.
- **Reload:** stayed dark in every frame, with System checked.
- **Back to a light OS, then reload:** every frame was light.

No hydration problem was reported.

## Scenario: Invalid or unavailable storage falls back to dark — PASS (browser)

- **Invalid values:** stored "garbage", "" and "System" each rendered dark in every frame, with no light class.
- **Unreadable storage:** rendered dark with no page error, the Light choice worked for the session, and a reload came back dark.
- **Unwritable storage (preferences):** Compact and serif-off applied for the page with no error.
- **Invalid preference values:** `maybe`, `huge` and `fast` were ignored. The page stayed serif, comfortable and dark, with motion running as the OS allows.

## Scenario: Presentation preferences — PASS (browser)

In a fresh browser whose OS allows motion:
- **Defaults:** the document sample's computed font included Georgia, from the serif stack, and "Serif for documents" was checked. The Appearance section's padding was 20px, and a probe transition read 0.3s.
- **After changing all three:** turning serif off, picking Compact and choosing "Always reduce motion" gave a sans font with no Georgia, 16px padding, and a 1e-05s transition. No request was made.
- **After a reload:** the measurements were identical, and all three controls stayed as chosen, with `data-motion="reduce"` on the root.
- **Motion following the OS:** with "Follow this Mac", the transition read 0.3s. Emulating OS reduced motion gave 1e-05s, and turning it off gave 0.3s again.
- **Accessibility:** axe found no violations, WCAG 2.2 AA tags included, in both themes with compact density and sans documents. The existing axe and keyboard tests for `/settings` in dark and light still pass, with the keyboard step moved from Dark up to Light.
- **Visual walk:** Settings passed in both themes, for contrast, keyboard and zoom. I looked at `settings-dark.png`.

## Scenario: Presentation only — PASS (browser, disposable stack)

The identity suite's "changing appearance sends no model or task request, and changes no run or approval" test, as owner A:
- the precondition holds: the run list has a running run and the approval list a pending approval;
- each preference was changed (System, serif off, Compact, always reduce motion) and then restored, and the root attributes were observed;
- no request reached `/api/`;
- the runs, approvals and workflows read before and after were equal.

## Scenario: Preserve an explicit appearance choice — PASS (browser, unchanged)

The existing light and dark persistence tests still pass.

## Findings

- **Interpretation (design.md):** "documents" are a run's goal and its evidence summaries. Page and dialog titles stay serif, as Decision 0021 R5 sets them.
- **Out of scope:** SE-03's "stream text as it's written" isn't part of this story.
- **Not established:** H1 and product acceptance.
