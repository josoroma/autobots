# Delivery Goal

Written by `ohmyorch delivery`. The field table, Stories, and Next Action are
**derived** from SPECS.md and the gate reporters: refresh them with
`ohmyorch delivery refresh`, never hand-edit. Notes between the AUTHORED
markers are preserved across refreshes.

| Field | Value |
|---|---|
| Target | EPIC-16 |
| Kind | epic |
| Focus | - |
| Status | BLOCKED |
| Reason | US-16.4 needs the owner to run .checks/install-current.sh (stop web/API/worker, back up the persistent install, guarded apply of migrations 36-50, rebuild and restart). The project's hook keeps the install's keys and app.env out of the assistant's commands. Then resume with /ohmyorch:deliver EPIC-16. |
| Started | 2026-11-08 |
| Updated | 2026-11-08 |

## Stories

| # | Story | Change | SPECS status | Title |
|---|---|---|---|---|
| 1 | US-16.1 | us-16-1-sober-control-borders | DONE | Sober control borders |
| 2 | US-16.2 | us-16-2-schema-readiness-against-every | DONE | Schema readiness against every shipped migration |
| 3 | US-16.3 | us-16-3-workspace-choice-members-several | DONE | Workspace choice for members of several workspaces |
| 4 | US-16.4 | us-16-4-current-install-sol-s | IN PROGRESS | A current install with Sol's live qualification |
| 5 | US-16.5 | us-16-5-real-examples-install | BLOCKED | Real examples on the install |

## Next Action

Action: implement
Story: US-16.4
Change: us-16-4-current-install-sol-s
Owner: main-session
Command: /ohmyorch:opsx-apply us-16-4-current-install-sol-s
Reason: gate implementation: 1/3 tasks complete

This is the last computed action, for reading only. `ohmyorch delivery next`
recomputes it from the repository on every call.

## Notes

<!-- BEGIN AUTHORED: notes -->
None.
<!-- END AUTHORED: notes -->
