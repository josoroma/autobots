## Why

US-15.21 implements [PRD-Studio SE-02 and SE-05 to SE-07](../../../PRD-Studio.md#settings), with [Decision 0022 D3](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision), PRD 12.1 and SP-014. Settings is one page plus scattered sub-pages. Nothing tells a person when a run waits for them, a member can't see what the workspace keeps, and the shortcuts are undocumented.

## What Changes

- **`GET /v1/retention`** for any member returns the workspace's retention windows and the reader's own role. It is read-only, has no PUT, and changing retention stays on the owner-only Operations route. OpenAPI and the TypeScript client are regenerated, and the BFF's generic `/api/v1` forwarding carries it.
- **A Settings layout** has a "Settings sections" navigation: Appearance, Notifications, Account, Data on this Mac and Keyboard, plus links to Models and Operations.
- **Notifications** stores "Tell me when a run waits for me" in the browser, asks the browser's permission when turned on, and says what the permission allows.
- **A `WaitingNotifier` in the root layout** works while the app is open, with the setting on and permission granted. It polls the app's own `/api/v1/runs?group=needs_you` every 4 seconds and raises one browser notification for each run that newly enters `waiting_approval` or `waiting_input`. Runs already waiting when it starts are only noted. Nothing is sent anywhere else.
- **Data on this Mac** shows the retention summary read-only. The owner gets a link to Operations; a member is told only the owner can change it.
- **Keyboard** lists every shortcut, from one `lib/shortcuts.ts`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: the Settings sections, notifications, data summary and keyboard list.

## Impact

- `api/operation_routes.py` and `contracts/operations.py`, plus the generated contract and client.
- New `app/settings/layout.tsx`, `notifications/`, `data/` and `keyboard/` pages, and the new `settings-nav.tsx`, `notifications-control.tsx`, `waiting-notifier.tsx`, `data-summary.tsx`, `lib/notify.ts` and `lib/shortcuts.ts`, plus `app/layout.tsx`.
- `test_operation_values.py` and `test_app_factory.py`.
- New `tests/db/notify_live.py` and `settings-sections.spec.ts`, and the main browser suite's timeout in `qualify_identity.py`, raised from 240 to 480 seconds.
