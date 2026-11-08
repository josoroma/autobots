# Verification — us-15-1-sidebar-groups-tools-under

Change: us-15-1-sidebar-groups-tools-under
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

- **Completeness:** 5 of 5 tasks complete. 2 requirements: `studio-shell` was added and `tool-catalog` was modified.
- **"Three named groups":** observed. `apps/web/components/sidebar-nav.tsx:28-57` groups the links into Work (named in screen-reader text), Build and System, each list labelled by its name. `tests/browser/tools.spec.ts` asserts the order of all nine links, each named list's links, and `aria-current="page"` on Home. It passed in `python3.12 scripts/verify.py --profile full` (37 browser tests, 0 failed, 0 skipped).
- **"The skip link stays first":** observed. `tools.spec.ts` asserts that the first Tab focuses the skip link, and that after Enter the next Tab lands inside `main`. `appearance.spec.ts` asserts the skip link, then Home, in both themes. Both passed in the same run.
- **"The browser specs follow the decision" and "Browse tools by group":** observed. `tools.spec.ts` asserts Tools directly after Workflows under Build. No spec asserts Tools before Settings (`grep` over `apps/web/tests/browser` finds none). axe reported no violations.
- **"Show unavailable tools honestly":** unchanged behavior. Its existing assertions in `tools.spec.ts` passed in the same run.
- **First verification:** recorded MISMATCH, because the work group was unnamed and skip-link activation was unasserted. Both were fixed by task 1.3 before this record.
- **Environment note:** one `full` run failed `harness_behavior_tests`, in a test that gives a new stub script 0.3 s to start. This Mac's endpoint-security agent was using about 108% CPU, and a new script took 0.49 s to start the first time. A later `full` run and two `harness` runs passed, and no harness file changed.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
- **Limit:** the slice suites in the `db` profile weren't run for this story. Its scenarios are covered by the `full` profile's appearance and tools suites.
