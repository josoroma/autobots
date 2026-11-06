## Why

US-10.2's finding B7: forms were styled one by one, and design claims rested on a few screens. Decision 0009 moves forms to shared components, then captures both-theme screenshots and measures contrast once across all named surfaces, when screens are final. Decision 0010 makes WCAG 2.1 AA the pass line.

## What Changes

- Shared `Input`, `Textarea`, `Select` and `Choice`, and every form moved to them, with a check that no screen draws a raw control.
- A suite that captures every DS-03 surface in use, in dark and light, with contrast measured in default, hover and focus states, and axe at WCAG 2.1 AA.
- What it found is corrected in pairing, not tokens: input boundaries and the light focus ring gain a passing color beside the token.
- The shell reflows at narrow widths, and keyboard, zoom, reduced motion and appearance changes are checked.
- Evidence retained under `docs/engineering/evidence/US-11.11/`, with the revision it came from.
- Two defects found on the way are fixed: a refused reply left unread, which held its connection open, and Home's false "Inference is not configured yet".

## Capabilities

### New Capabilities

- `visual-evidence`: shared form controls, and how final screens are measured and reported in both themes.

### Modified Capabilities

None.

## Impact

`apps/web/components/ui/field.tsx`, 14 components, `app-shell.tsx`, `globals.css`, `app/page.tsx`, a new browser suite and harness test, `scripts/qualify_identity.py` and evidence. No token value, API, schema or model call changes.
