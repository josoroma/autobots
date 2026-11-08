## Why

US-16.1 implements [Decision 0023 E1](../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#decision) under DS-03. Every Input, Textarea and Select draws an inset bottom line in `--muted-foreground`, which reads as a heavy underline, most of all on the composer's borderless goal field. The owner asked for the sober border the other components have.

## What Changes

- **A `--control-border` token**, light and dark, set just strong enough for DS-03's 3:1 non-text contrast against the page, card and muted surfaces, and no stronger.
- **Field controls** use it as one even 1 px border on all four sides. The `.control-boundary` inset underline is removed. Focus keeps its ring.
- **The composer's goal field** gets the same rounded, even border instead of a transparent one. The composer and sign-in cards drop their `shadow-lg` and `border-input`, and are plain cards like the rest.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-shell`: control borders.

## Impact

- `apps/web/app/globals.css`, `apps/web/components/ui/field.tsx`, `apps/web/components/goal-composer.tsx`, `apps/web/app/sign-in/page.tsx`, `docs/design/studio-extensions.css`.
- `slice-visual.spec.ts` measures boundaries; a new assertion checks no control keeps an inset underline and its four border sides match.
