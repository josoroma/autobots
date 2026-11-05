# Delivery Goal

Written by `ohmyorch delivery`. The field table, Stories, and Next Action are
**derived** from SPECS.md and the gate reporters: refresh them with
`ohmyorch delivery refresh`, never hand-edit. Notes between the AUTHORED
markers are preserved across refreshes.

| Field | Value |
|---|---|
| Target | EPIC-4 |
| Kind | epic |
| Focus | - |
| Status | ACTIVE |
| Reason | - |
| Started | 2026-11-05 |
| Updated | 2026-11-05 |

## Stories

| # | Story | Change | SPECS status | Title |
|---|---|---|---|---|
| 1 | US-4.1 | us-4-1-atomic-run-admission-canonical | DONE | Atomic run admission and canonical transition commands |
| 2 | US-4.2 | us-4-2-fenced-worker-ownership-durable | DONE | Fenced worker ownership and durable checkpoints |
| 3 | US-4.3 | us-4-3-bounded-goal-planning-model | DONE | Bounded goal planning and model/tool loop |
| 4 | US-4.4 | us-4-4-versioned-tool-registry-operation | DONE | Versioned tool registry and operation receipts |
| 5 | US-4.5 | us-4-5-private-artifacts-staged-publication | DONE | Private artifacts with staged publication and reconciliation |
| 6 | US-4.6 | us-4-6-sanitized-event-replay-run | READY | Sanitized event replay and run workspace |
| 7 | US-4.7 | us-4-7-pause-cancellation-interrupted-run | READY | Pause, cancellation and interrupted-run recovery |
| 8 | US-4.8 | us-4-8-verify-first-durable-goal | BLOCKED | Verify the first durable goal-to-artifact slice |

## Next Action

Action: select
Story: US-4.6
Change: us-4-6-sanitized-event-replay-run
Owner: main-session
Command: openspec new change us-4-6-sanitized-event-replay-run; set US-4.6 to IN PROGRESS with a Change: line
Reason: US-4.6 is READY and has no OpenSpec change

This is the last computed action, for reading only. `ohmyorch delivery next`
recomputes it from the repository on every call.

## Notes

<!-- BEGIN AUTHORED: notes -->
None.
<!-- END AUTHORED: notes -->
