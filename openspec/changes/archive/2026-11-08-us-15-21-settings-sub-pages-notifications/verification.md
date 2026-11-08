# Verification — us-15-21-settings-sub-pages-notifications

Change: us-15-21-settings-sub-pages-notifications
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 4/4 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0. Pytest ran 811 tests, including the retention summary test.
- **`python3.12 scripts/verify.py --profile db`:** run twice.
  - **First run:** three failures, all fixed:
    - the side-by-side Settings layout let Tab climb from the section list back up to the first control, which the visual walk flagged on Settings and Models; the navigation is now stacked above the page;
    - headless Chromium reports notification permission as denied even after `grantPermissions`, so the browser's permission is now arranged through a stub;
    - member C belongs to two workspaces, so the API asked them to choose one; the Data test now uses reader F, a member of workspace A only.
  - **Second run:** exit 0 at 2026-11-08T17:27Z. Every check passed, including the visual walk.
- **`python3.12 scripts/verify.py --profile full`:** exit 0, with 41 browser tests passed. It ran after the layout change.

## Scenario: Sub-navigation — PASS (browser, disposable stack)

As member C, Settings shows a "Settings sections" navigation listing Appearance, Notifications, Account, Data on this Mac and Keyboard, with Appearance marked current. Its second list links to Models (`/settings/models`) and Operations (`/operations`). Each link points to its page. Following Keyboard reaches `/settings/keyboard` and marks it current. axe found no violations at WCAG 2.2 AA.

## Scenario: Notify while the app is open — PASS (browser, disposable stack, with the permission arranged)

- **Setup:** the browser's Notification API is replaced by a stub, set to granted or denied, that records each notification instead of showing it. Headless Chromium can't grant a real permission. The `ops-n` owner turned on "Tell me when a run waits for me", which read "This browser allows the app's notifications.", then opened Home and waited one poll.
- **Granted:** `tests/db/notify_live.py` admitted two runs, and their worker moved them through REQUEST_APPROVAL and REQUEST_INPUT. Exactly two notifications appeared: "A run waits for your approval" and "A run waits for your input", each tagged with its own run and status. Five seconds later there were still exactly two.
- **Nothing off the Mac:** every request the page made went to the app's own origin.
- **Denied, setting on:** the setting read "This browser blocks…". Two new waiting runs raised no notification in 10 seconds.
- **Granted, setting off:** two new waiting runs raised no notification in 10 seconds.

## Scenario: Data on this Mac — PASS (browser, disposable stack; unit)

Reader F (a member of A only) and owner A both opened Data on this Mac:
- both read the same retention text;
- the summary has no input, select, textarea or button, and `PUT /api/v1/retention` was refused;
- only the owner saw "Change retention on Operations" linking to `/operations`, and the reader saw "Only the workspace owner can change retention.";
- axe found no violations.

The unit test confirms the route returns the windows and the reader's role for a member and for an owner, and answers 405 to PUT.

## Scenario: Keyboard — PASS (browser, disposable stack)

Settings → Keyboard lists 6 shortcuts, each with its keys and a description:
- J;
- K;
- ↓ ↑;
- ⌘ ↵ (approve);
- ⌘ ⌫ (reject);
- Tab.

These are every keyboard handler the app has: the Approvals keys and the skip link. axe found no violations.

## Findings

- **Arranged:** the browser's notification permission is stubbed, because headless Chromium doesn't honor a granted permission. The polling, baseline, one-per-run rule and the setting gate all run as shipped.
- **WARNING:** a member of two workspaces gets "Choose a workspace" from member APIs like this one, as the app has no workspace chooser in client requests yet. This change didn't introduce that, and it doesn't fix it.
- **Interpretation (design.md):** notifications come from polling every 4 seconds, as there is no workspace-wide event stream.
- **Not established:** H1, product acceptance, or real OS notification delivery.
