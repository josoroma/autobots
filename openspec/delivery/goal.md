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
| 3 | US-1.3 | us-1-3-h0-locked-toolchains-minimal | DONE | H0 locked toolchains and minimal scaffolding |
| 4 | US-1.4 | us-1-4-h0-portable-verification-deterministic | DONE | H0 portable verification and deterministic hook adapter |
| 5 | US-1.5 | us-1-5-h0-work-records-independent | DONE | H0 work records, independent review and evidence templates |
| 6 | US-1.6 | us-1-6-h1-deliberate-fault-freshness | DONE | H1 deliberate fault and freshness qualification |
| 7 | US-1.7 | us-1-7-h1-disposable-database-compose | DONE | H1 disposable database and Compose guards |
| 8 | US-1.8 | us-1-8-h1-independent-baseline-review | READY | H1 independent baseline review and exercised runbook |

## Next Action

Action: select
Story: US-1.8
Change: us-1-8-h1-independent-baseline-review
Owner: main-session
Command: openspec new change us-1-8-h1-independent-baseline-review; set US-1.8 to IN PROGRESS with a Change: line
Reason: US-1.8 is READY and has no OpenSpec change

This is the last computed action, for reading only. `ohmyorch delivery next`
recomputes it from the repository on every call.

## Notes

<!-- BEGIN AUTHORED: notes -->
From 2026-11-05: OpenSpec-only delivery in the main session, per Decision 0003.
<!-- END AUTHORED: notes -->
