# Verification — us-15-23-new-run-shortcut

Change: us-15-23-new-run-shortcut
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 3/3 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 3/3 scenarios observed |
| Coherence    | Follows the proposal; no design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T18:19Z, after a fix.
  - **First run:** 12 existing spec locators, `getByRole("button", { name: "Run" })`, also matched "New run" by substring and failed in strict mode. Later tests then saw a key and settings state that the failed tests hadn't restored.
  - **Fix:** those locators now ask for the exact "Run" button. Each still finds the same composer button.
  - **Rerun:** passed, with the main and slice suites clean and the visual walk passing.
- **`python3.12 scripts/verify.py --profile full`:** exit 0, with 41 browser tests passed. The earlier `full` run failed only `non_mutation_guard`, because the specs were edited while it ran.

## Scenario: New run from the shell — PASS (browser, disposable stack)

- **Tab order:** on Runs, Tab reached "Skip to content" first and "New run" next. The button shows "⇧⌘O" and declares `aria-keyshortcuts="Shift+Meta+O Shift+Control+O"`.
- **Opening the composer:** Enter on it went to Home with focus in the "Goal" textbox. On Home, clicking it focused the goal again.
- **Nothing sent:** no non-GET request was made.
- **Accessibility:** axe found no violations at WCAG 2.2 AA.
- **Tab order elsewhere:** the appearance spec's keyboard test now reads skip link, New run, Search, Home.

## Scenario: Not in a text field — PASS (browser, disposable stack)

With "kept text" typed in the Runs filter and focus there, ⇧⌘O left the page on `/runs`, the filter focused and its value "kept text".

## Scenario: The shortcut is shift-command-O — PASS (browser, disposable stack)

From Workflows, with focus outside a field, ⇧⌘O went to Home with focus in the goal. The button's hint read "⇧⌘O", and no non-GET request was made. Settings → Keyboard lists "⇧ ⌘ O" first.

## Findings

- **Note:** the button's name has to contain its visible words, "New run", so any locator for the composer's "Run" button must be exact. The 12 that weren't now are.
- **Not established:** H1 and product acceptance.
