## Why

US-15.20 implements [PRD-Studio SE-03](../../../../docs/PRD/PRD-Studio.md#settings), [DS-02 as amended](../../../../docs/PRD/PRD-Design-System.md#ds-02--dark-is-the-default) and [Decision 0022 D2](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision), with DS-04 and DS-05. Appearance offers only Light and Dark. A person can't follow the OS, read documents in a non-serif face, tighten spacing or force reduced motion.

## What Changes

- **Theme:** the theme provider adds System beside Light and Dark. A first visit, and any missing, invalid or unreadable value, is still dark whatever the OS prefers. Only a chosen System follows the OS, live.
- **Before-paint script:** it keeps `system` as a valid stored theme. It also applies `data-serif="off"`, `data-density="compact"` and `data-motion="reduce"` on the root element before paint, reading only those exact values.
- **CSS:**
  - `--document` (serif unless turned off) backs a new `font-document` utility, used for a run's goal and evidence text;
  - compact density sets Tailwind's one `--spacing` step to 0.2rem;
  - forced reduced motion applies the same 0.01 ms rule as the OS media query.
- **Settings → Appearance** gains three controls: System, Light and Dark cards; a "Serif for documents" checkbox with a live sample; and Density and Motion radios. Each stores its choice in the browser, or keeps it for the page when storage can't be written.
- **Tests:** `appearance.spec.ts` covers System, the new preferences, and invalid and unavailable storage. The identity suite's presentation-only test changes every preference.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-application-shell`: the System theme and the presentation preferences.

## Impact

- `app/layout.tsx`, `theme-provider.tsx`, `app/globals.css`, `appearance-control.tsx` and `app/settings/page.tsx`.
- The document text in `run-workspace.tsx` and `run-inspector.tsx`.
- `appearance.spec.ts` and `slice-visual.spec.ts`.
- No API, contract or database change.
