# DOC-QA-001 — Runtime loops, depth and tools developer Q&A

Status: COMPLETE
Evidence: 2026-11-05-doc-qa

## Plan

DH-W01. Written before drafting the documentation.

- **Source:** User request for `README-QA.md` with diagrams; explanatory coverage of US-4.2–US-4.7, US-5.1–US-5.4, US-6.2 and US-8.1; preserved SP-008, SP-011, SP-012 and SP-013. This documentation work item does not change story requirements or status.
- **Behavior and invariants:** Explain current runtime cycles, stopping conditions, depth, tool choice, enforcement and developer debugging with code links. Distinguish implementation observations, source requirements and unqualified behavior.
- **Scope:** New README and local diagram assets, plus this proportional DH-W01–06 record and evidence. Preserve pre-existing working-tree edits. No application, API, schema, configuration or operational behavior changes.
- **Verification:** Read relevant sources and implementation; independently review the final documentation; check local links and SVG/HTML geometry/accessibility, visually inspect rendered diagrams, run specification validation and the harness profile. Reuse the development-harness runbook; no services, database changes, dependency installs or model calls.
- **Diagram source:** Adapt the requested cathrynlavery/diagram-design skill at `f24d98b05e2d7a5e68c2dedfe46e5b7173f50118`, downloaded to ignored `.checks/diagram-design-source`. User selected the existing Autobots design system before drawing.

## Implementation

DH-W02. Base revision `ecb34900e46c`, including existing user changes inspected read-only.

- Added `README-QA.md`: 20 questions covering runtime cycles, stopping states, root limits, depth, tool inventory/selection/enforcement, retries, receipts, verification, recovery, approvals, workflows, compaction and debugging.
- Added `docs/diagrams/runtime-qa/`: three HTML/SVG figures, provenance and MIT notice. Adapted the requested design to exact Luma light colors and disclosed offline system fonts.
- Added this record and `docs/engineering/evidence/DOC-QA-001/`. Application, contract, schema, configuration, backlog and existing user edits are unchanged.
- Research observed current limitations rather than repairing them: no semantic stagnation detector, no automatic candidate-verification repair, imprecise crash elapsed-time accounting, and child summary counters not providing complete attribution.

## Review

DH-W03. Authors `/root` (Q&A/records) and `/root/qa_diagrams` (assets); independent reviewer `/root/qa_review`. Read-only research assistants did not author implementation.

- Review found two incorrect symbol labels, corrected to `_operation_id()` and `validate_graph()`, and requested narrower lease-loss wording to preserve late receipt reconciliation. All three were corrected. Reviewer also inspected the rendered figures.
- Final reviewed source and documentation fingerprints are recorded in the evidence manifest and review artifact. The separate documentation inventory is necessary because the generic harness input list does not include the new root README or `docs/diagrams/`.

## Verification

DH-W04. Evidence retained under `docs/engineering/evidence/DOC-QA-001/`. Final command results are recorded in its manifest/summary: specifications and harness passed, 92 local links/anchors passed, all six upstream diagram checks passed, all figures rendered and their text contrast passed. `scripts/evidence.py validate DOC-QA-001` returned 0. Classes are static documentation, local browser rendering and deterministic harness checks with model transport `none`; no new product acceptance claim. No application tests, services, database fixtures or live model runs are required by this documentation-only change.

## Runbook

DH-W05. Operating behavior is unchanged. On 2026-11-05 (America/Costa_Rica), exercised `python3.12 scripts/specs.py validate` and `python3.12 scripts/verify.py --profile harness` from [the existing development-harness runbook](../runbooks/development-harness.md); both returned 0. Other runbook profiles were outside this documentation scope. Diagram inspection is a documentation check, not an application operating procedure.
