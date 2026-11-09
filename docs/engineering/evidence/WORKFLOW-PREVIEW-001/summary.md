# WORKFLOW-PREVIEW-001: choosing a workflow brings its preview into view

**Date:** 2026-11-08. **Status:** done. **Scope:** a small fix the owner asked for ("why workflows preview doesnt work?"), outside the OhMyOrch delivery loop. This short record follows DH-W01–06.

## Plan

**Observed on the persistent install,** with the owner signed in to the browser pane:
- Preview requested the workflow's steps, the request answered 200, and the panel rendered the right steps.
- The panel sits under the list. With seven workflows its heading was about 1,124 px down a 496 px viewport.
- The Preview link uses `scroll={false}`, so nothing visible changed, and the click looked broken.

**Ruled out:** on a disposable database, every seeded concept workflow's published and draft preview builds without error.

## Implementation

`apps/web/components/workflows-panel.tsx`: when the chosen workflow changes, its preview heading is focused and scrolled into view, smoothly unless reduced motion is set. That also tells a screen reader where focus went. Changing the version keeps the place.

## Review

No independent review ran: the owner asked for the fix directly.

## Verification

| Check | Exit | Observed |
|---|---|---|
| `apps/web/tests/browser/workflow-list.spec.ts`, "the preview's version switch shows each version's steps in order", in the `db` profile's identity suite | 0 | Passed. After clicking Preview, the preview heading is focused and in the viewport |
| `python3.12 scripts/verify.py --profile db` | 0 | Passed (identity 670/670, app_db 544/544), in the same run as US-14.19 |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed |

## Limits

Not re-checked on the persistent install until the owner rebuilds the web app (`make build`, then `make stop && make start`).
