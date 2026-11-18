## Why

US-15.23 implements [PRD-Studio SH-02](../../../../docs/PRD/PRD-Studio.md#shell), with [Decision 0022 D3 and D16](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision) and DS-04. Starting a goal means first going to Home and finding the composer.

## What Changes

- **A New run button** sits in the shell directly after the skip link, before Search, showing "⇧⌘O" and declaring `aria-keyshortcuts`.
- **⇧⌘O, or Shift+Ctrl+O, does the same as the button** from anywhere except a text field: on Home it focuses the goal, and elsewhere it opens `/?new=1`.
- **The composer** focuses its goal when it arrives with `new=1`, then drops the marker from the address. Nothing is sent.
- **Shortcut list:** Settings → Keyboard lists ⇧⌘O.
- **Specs:** `appearance.spec.ts`'s tab order is now skip link, New run, Search, Home. `search.spec.ts` and `settings-sections.spec.ts` follow.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: the New run shortcut.

## Impact

- New `new-run.tsx`, plus `app-shell.tsx`, `goal-composer.tsx` and `lib/shortcuts.ts`.
- `appearance.spec.ts`, `search.spec.ts`, `settings-sections.spec.ts`, the new `new-run.spec.ts`, and the browser list in `qualify_identity.py`.
