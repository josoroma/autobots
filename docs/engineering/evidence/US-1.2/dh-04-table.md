# US-1.2 DH-04 table

Authored by `ohmyorch:implementer`, persisted verbatim by the coordinator. A final-tree reading, by inspection; only the tool-set test is mechanical. The reviewer repeats the weakest judgments.

| Skill | Trigger | Relevant paths | Prerequisites | Workflow | Expected evidence | Failure behavior |
|---|---|---|---|---|---|---|
| autobots-contracts | yes | yes | yes | yes | yes | yes |
| autobots-docker-local | yes | yes | yes | yes | yes | yes |
| autobots-durable-worker | yes | yes | yes | yes | yes | yes |
| autobots-implement-item | yes | yes | yes | yes | yes | yes |
| autobots-model-gateway | yes | yes | yes | yes | yes | yes |
| autobots-nextjs | yes | yes | yes | yes | yes | yes |
| autobots-plan-change | yes | yes | yes | yes | yes | yes |
| autobots-python | yes | yes | yes | yes | yes | yes |
| autobots-review-change | yes | yes | yes | yes | yes | yes |
| autobots-runbook-evidence | yes | yes | yes | yes | yes | yes |
| autobots-spec-ingest | yes | yes | yes | yes | yes | yes |
| autobots-supabase | yes | yes | yes | yes | yes | yes |
| autobots-verify-change | yes | yes | yes | yes | yes | yes |

| Agent | Scope | Permitted tools | Inputs | Result contract |
|---|---|---|---|---|
| autobots-architect | yes | yes, read-only | yes | yes |
| autobots-database | yes | yes | yes | yes |
| autobots-infrastructure | yes | yes | yes | yes |
| autobots-nextjs | yes | yes | yes | yes |
| autobots-python-worker | yes | yes | yes | yes |
| autobots-reviewer | yes | yes, read-only | yes | yes |
| autobots-spec-ingestor | yes | yes, read-only | yes | yes |

Pre-authoring reading, for the record: relevant paths read `no` for autobots-contracts, -docker-local, -durable-worker, -implement-item, -model-gateway and -review-change. Failure behavior read `no` for autobots-docker-local, -durable-worker, -model-gateway and -python. Every other cell read `yes`. No file outside the plan's named paths needed a change.

Weakest judgments, for the reviewer to repeat:

| File and cell | Basis for `yes` |
|---|---|
| autobots-architect, result contract | Edited in reopen round 1 after review F-1 rejected the earlier reading. Line 16 now names each DH-04 element: findings with paths (requirement mapping, recommended changes with owned paths/interfaces), invariants checked and evidence ("the ownership, transition, compatibility, authorization, receipt, budget and recovery invariants checked with the source evidence for each"), remaining uncertainty (open decisions) |
| autobots-nextjs (agent), result contract | Edited in reopen round 1 after review F-1 rejected the earlier reading. Line 16 now names each element: findings with paths (changed paths/symbols), invariants checked ("the session/workspace, credential, canonical-state and sanitized-event invariants checked"), evidence (actual commands/results), remaining uncertainty (unresolved gaps) |
| autobots-plan-change, failure behavior | Rests on "any acceptance-blocking gap". Reviewer accepted it as thin |
| autobots-reviewer, result contract | Reviewer accepted it as marginal. Not edited; not a named path |

Relevant paths for autobots-nextjs (skill), -python, -plan-change, -runbook-evidence, -spec-ingest, -supabase and -verify-change come from existing text. All 13 skills link to detailed standards. No skill applies a persistent operation, so none needs `disable-model-invocation`, by reading.
