# Delivery Goal

Written by `ohmyorch delivery`. The field table, Stories, and Next Action are
**derived** from SPECS.md and the OpenSpec change artifacts: refresh them with
`ohmyorch delivery refresh`, never hand-edit. Notes between the AUTHORED
markers are preserved across refreshes.

| Field | Value |
|---|---|
| Target | EPIC-20 |
| Kind | epic |
| Focus | - |
| Status | BLOCKED |
| Reason | no progress: next action 'verify' for US-20.1 unchanged across 4 stop attempts |
| Started | 2026-11-25 |
| Updated | 2026-11-25 |

## Stories

| # | Story | Change | SPECS status | Title |
|---|---|---|---|---|
| 1 | US-20.1 | us-20-1-stealth-browser-box | IN PROGRESS | A stealth browser in the box |
| 2 | US-20.2 | us-20-2-check-that-clears-itself | BLOCKED | A check that clears by itself |
| 3 | US-20.3 | us-20-3-quiet-page | BLOCKED | Quiet on the page |
| 4 | US-20.4 | us-20-4-scoreboard-owner-runs | BLOCKED | A scoreboard the owner runs |

## Next Action

Action: verify
Story: US-20.1
Change: us-20-1-stealth-browser-box
Command: /ohmyorch:opsx-verify us-20-1-stealth-browser-box; with no CRITICAL issue, run a separate Bash call: openspec archive us-20-1-stealth-browser-box -y
Reason: 10/10 tasks complete; verify, then archive

This is the last computed action, for reading only. `ohmyorch delivery next`
recomputes it from the repository on every call.

## Notes

<!-- BEGIN AUTHORED: notes -->
None.
<!-- END AUTHORED: notes -->
