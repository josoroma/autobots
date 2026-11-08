# Verification — us-15-22-search-palette

Change: us-15-22-search-palette
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 3/3 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 3/3 scenarios observed |
| Coherence    | Follows the proposal; no design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0, after a fix. The first run failed the harness rule that every form control comes from the shared components, because the palette drew a raw `<input>`. It now uses `Input`.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T17:54Z, after a fix. In the first run, the composer spec's `getByLabel("Expert")` also matched the palette's input, which was labelled "Search runs, Experts, workflows and tools". The input is now labelled "Search this workspace". The rerun passed the main suite, the slice suite and the visual walk.
- **`python3.12 scripts/verify.py --profile full`:** exit 0, with 41 browser tests passed, including the appearance keyboard test with Search as the stop after the skip link.

## Scenario: Typed results within the workspace — PASS (browser, disposable stack)

`ops-n` holds a run "Read the quarter notes", an Expert "Reading analyst" and a workflow "Read and summarize". Another workspace holds a run "Read another workspace plan" and an Expert "Reader elsewhere".

`GET /api/v1/search?q=read` as the `ops-n` owner returned:
- runs including the arranged run, with `href` `/runs/<id>`;
- exactly the arranged Expert and the arranged workflow;
- at least one tool, each matching "read" in its title or ID.

The body held neither ID nor title from the other workspace.

## Scenario: ⌘K and the shell button — PASS (browser, disposable stack)

- **⌘K:** with focus outside any field on Home, ⌘K opened the "Search" dialog with its "Results" listbox, and focus went to the combobox.
- **The Search button:** on Runs, Tab reached "Skip to content" first and the Search button next. The button shows "⌘K" and declares `aria-keyshortcuts="Meta+K Control+K"`, and Enter on it opened the dialog. Escape closed it and returned focus to the button.
- **In a text field:** with focus in the Runs filter, ⌘K left the dialog closed.

## Scenario: Keyboard and focus — PASS (browser, disposable stack)

- **Moving:** with "read" typed, the status read "N results." The first option was selected and named by the combobox's `aria-activedescendant`. ArrowDown moved selection and `aria-activedescendant` to the second option, and ArrowUp moved it back.
- **Accessibility:** axe found no violations at WCAG 2.2 AA with the palette open.
- **Enter:** moving to the workflow's option and pressing Enter navigated to `/workflows/<id>` and closed the palette.
- **Escape:** reopened with ⌘K from the focused sidebar "Runs" link, Escape closed it and returned focus to that link.

## Findings

- **Interpretation:** tools are install-wide, so tool results are the same for every workspace. Runs, Experts and workflows are filtered by workspace in SQL.
- **SUGGESTION:** the search has no unit test of its own; its workspace scoping is exercised against the real database in the browser spec.
- **Not established:** H1 and product acceptance.
