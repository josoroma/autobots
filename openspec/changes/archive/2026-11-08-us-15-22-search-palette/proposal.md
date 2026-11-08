## Why

US-15.22 implements [PRD-Studio SR-01 and SH-02](../../../PRD-Studio.md#search), with [Decision 0022 D3](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision), DS-04 and SP-014. There's no way to jump to a run, Expert, workflow or tool from the keyboard.

## What Changes

- **`GET /v1/search?q=`** for any member of the workspace returns typed results, up to five of each kind. Each result has its kind (run, expert, workflow or tool), ID, a public title, a detail (a run's state or a tool's ID) and the app path it opens.
  - **Runs, Experts and workflows:** read with the workspace in every SQL statement; runs match on their goal, the others on their name.
  - **Tools:** the newest version of each catalog tool, matched on title or ID.

  OpenAPI and the TypeScript client are regenerated. The BFF's generic `/api/v1` forwarding carries it.
- **A Search button** sits in the shell, after the skip link and before the main navigation, showing "⌘K" and declaring `aria-keyshortcuts`. ⌘K, or Ctrl+K, opens the same palette from anywhere except a text field.
- **The palette** is a modal `<dialog>`:
  - a combobox over a listbox;
  - the arrows move the active option, which `aria-activedescendant` names;
  - Enter opens the active result, and Escape closes it;
  - focus returns to wherever it was before the palette opened;
  - a status line announces the count.
- **The typing check** that Approvals used moves into `lib/keyboard.ts`, and Settings → Keyboard lists ⌘K.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: the search palette.

## Impact

- New `application/search.py`, `contracts/search.py` and `api/search_routes.py`, plus `api/app.py`, the generated contract and client, and `test_app_factory.py`.
- New `search-palette.tsx` and `lib/keyboard.ts`, plus `app-shell.tsx`, `approvals-panel.tsx` and `lib/shortcuts.ts`.
- The search arrangement in `qualify_identity.py` and the new `search.spec.ts`. In `appearance.spec.ts` and `settings-sections.spec.ts`, the new Search stop and the new shortcut.
