# Delivery Goal

Written by `ohmyorch delivery`. The field table, Stories, and Next Action are
**derived** from SPECS.md and the gate reporters: refresh them with
`ohmyorch delivery refresh`, never hand-edit. Notes between the AUTHORED
markers are preserved across refreshes.

| Field | Value |
|---|---|
| Target | EPIC-1 |
| Kind | epic |
| Focus | - |
| Status | ACTIVE |
| Reason | - |
| Started | 2026-11-04 |
| Updated | 2026-11-05 |

## Stories

| # | Story | Change | SPECS status | Title |
|---|---|---|---|---|
| 1 | US-1.1 | us-1-1-h0-repository-prerequisite-inventory | DONE | H0 repository and prerequisite inventory |
| 2 | US-1.2 | us-1-2-h0-shared-instructions-development | DONE | H0 shared instructions and development assistant assets |
| 3 | US-1.3 | us-1-3-h0-locked-toolchains-minimal | READY | H0 locked toolchains and minimal scaffolding |
| 4 | US-1.4 | us-1-4-h0-portable-verification-deterministic | BLOCKED | H0 portable verification and deterministic hook adapter |
| 5 | US-1.5 | us-1-5-h0-work-records-independent | READY | H0 work records, independent review and evidence templates |
| 6 | US-1.6 | us-1-6-h1-deliberate-fault-freshness | BLOCKED | H1 deliberate fault and freshness qualification |
| 7 | US-1.7 | us-1-7-h1-disposable-database-compose | BLOCKED | H1 disposable database and Compose guards |
| 8 | US-1.8 | us-1-8-h1-independent-baseline-review | BLOCKED | H1 independent baseline review and exercised runbook |

## Next Action

Action: select
Story: US-1.3
Change: us-1-3-h0-locked-toolchains-minimal
Owner: ohmyorch:product-manager
Command: openspec new change us-1-3-h0-locked-toolchains-minimal; set US-1.3 to IN PROGRESS with a Change: line; /Users/josoroma/sites/autobots/research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch --project-root /Users/josoroma/sites/autobots --session-id 547ae454-e2f5-4d90-8efa-f515e920089d status --change us-1-3-h0-locked-toolchains-minimal
Reason: US-1.3 is READY and has no OpenSpec change

This is the last computed action, for reading only. `ohmyorch delivery next`
recomputes it from the repository on every call.

## Notes

<!-- BEGIN AUTHORED: notes -->
Done at US-1.2 `select`, carried from US-1.1: `.claude/rules/ohmyorch-delivery.md` and `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` were updated for F-11, F-12 and the user's two rulings. US-1.2's plan names these paths and its reviewer covers them.
<!-- END AUTHORED: notes -->
