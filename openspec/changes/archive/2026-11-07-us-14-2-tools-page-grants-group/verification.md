# Verification — us-14-2-tools-page-grants-group

Change: us-14-2-tools-page-grants-group
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 7/7 tasks, 2 reqs |
| Correctness | 3/3 scenarios observed in browser runs, the group grant on a disposable stack |
| Coherence | Followed the proposal. No design.md: no migration, one screen and one editor |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Browse tools by group | PASS | `apps/web/tests/browser/tools.spec.ts`, run by `scripts/qualify_web.py` against the real API app with an arranged membership: the sidebar's Tools link sits directly before Settings and opens `/tools`; Planning, General, Files and Connectors headings list their tools, `calculate` reads "calculate v1", "Available" and "Pure"; choosing the Files group writes `group=files` to the URL and leaves one group; loading `?availability=disabled_by_policy` restores the filter and shows only `browse_goal`; `/tools/calculate` shows version 1, the `operation` input as Required with `enum ["sum","mean","min","max"]` and Shown, `values` as `number[]`, `minItems 1` and Not shown, the `result` output, and the JSON Schema disclosure. axe found no WCAG 2.1 AA violation on the list or the detail |
| Show unavailable tools honestly | PASS | Same run: `create_github_issue` reads "Unavailable: key not set" with "Set GITHUB_REPOSITORY and GITHUB_TOKEN in the worker's environment, then restart the worker and the API.", and its detail names both variables; `browse_goal` reads "Unavailable: disabled by policy" with "Disabled until an isolated executor is qualified." In the Expert editor on the disposable stack, the connector's checkbox is disabled with its reason, and so is the Connectors group |
| A group grant stays explicit | PASS | `apps/web/tests/browser/experts.spec.ts` "US-14.2", run by `scripts/qualify_identity.py` in the `db` profile on a disposable Supabase stack: checking Calculate and "Files group (3 tools)" previews "calculate, publish_artifact, read_run_file, save_artifact, from the group files"; saving makes version 2, listed with "(groups: files)", version 1 unchanged; the stored config holds the four explicit tools and `tool_groups: ["files"]`; axe found no WCAG 2 A/AA violation. Through the BFF, versions naming `create_github_issue` or the Connectors group are refused 422 `expert_tool_unavailable` and the Planning group 422 `expert_tool_group_empty`. That a later group change can't alter a saved version is observed in `tests/test_tool_catalog.py`: the saved config validates back to the same explicit list with no re-expansion, since only a save expands |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `identity_qualification` passed (53 browser tests in its main suite, and the visual suite with no surface findings), with `app_db_qualification`, `persistent_apply_qualification`, `non_mutation_guard` and the rest |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed, 0 failed, 0 skipped |
| `openspec validate us-14-2-tools-page-grants-group` | 0 | valid |

## Findings

**Found and fixed:**
- The contract generator emitted an array of a union as `"a" | "b"[]`, so `grantable_to`, `tool_groups` and the existing validation error's `loc` had wrong TypeScript types. It now parenthesizes them.
- The first `db` run failed the visual suite on the Expert editor in both themes: the two disabled checkboxes were named only by a wrapping label, which its rule doesn't read. They now have ids with `label for`, and the unavailable reason is their description.
- The first `db` run also failed `non_mutation_guard`, because this change's artifacts were written while it ran. The rerun touched nothing.

## Limits

- The Tools screen's browser run uses the real API app with an arranged membership, not real Auth; the Expert run uses the disposable stack's real Auth.
- An Expert version saved before this change that names an unavailable tool can't be revised until the tool is removed or configured, by TC-06.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
