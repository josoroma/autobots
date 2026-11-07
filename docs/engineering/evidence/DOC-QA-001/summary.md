# DOC-QA-001 evidence summary — 2026-11-05-doc-qa

Documentation-only work for the user's runtime Q&A request. Implementation sources were inspected at base revision `ecb34900e46c` plus pre-existing working-tree edits. No story status or application behavior changed.

## Requirement coverage

The Q&A explains preserved SP-008, SP-010, SP-011, SP-012 and SP-013 through US-4.2–US-4.7, US-5.1–US-5.4, US-6.2 and US-8.1. These are traceability references, not claims that this documentation task requalifies those product requirements. Delivery follows DH-W01–06; the final manifest records executed documentation checks separately from repository harness checks.

## Reproduction

Run from the repository root with Python 3.12. Follow the validation and harness steps in [the development-harness runbook](../../runbooks/development-harness.md). Diagram source, pinned design provenance and exports are in [the diagram notes](../../../diagrams/runtime-qa/README.md).

| Check | Expected | Observed | Exit |
|---|---|---|---:|
| `python3.12 scripts/specs.py validate` | Valid source-traceable backlog | PASS: 10 epics, 42 stories, 86 tasks | 0 |
| `python3.12 scripts/verify.py --profile harness` | Configuration, backlog and deterministic harness fixtures pass with stable inputs | All three checks passed; inputs stable | 0 |
| `python3.12 .checks/DOC-QA-001/2026-11-05-doc-qa/check-doc-links.py` | Local document links and heading anchors resolve | 92 links checked; no missing targets/anchors | 0 |
| Diagram Design `self_check.py` and `verify-geometry.py`, each HTML | Valid self-contained accessible diagrams without geometry findings | Six checker passes, zero geometry findings; SVG XML/IDs/viewBoxes valid | 0 |
| `node .checks/DOC-QA-001/2026-11-05-doc-qa/render-diagrams.cjs` | Readable desktop/embedded SVG figures, local mobile scrolling, no external requests | Three HTML/SVG figures render; 960×600 SVG images load; no page overflow or external requests | 0 |
| `node .checks/DOC-QA-001/2026-11-05-doc-qa/check-contrast.cjs` | All measured SVG text pairs reach 4.5:1 | Minimum 4.7417:1 across all three figures | 0 |

Diagram command arguments and UTC timestamps are preserved in the manifest and raw reports. The parent and independent reviewer visually inspected the exported figures. `git diff --check` also returned 0; it does not substitute for validation of new untracked documents.

`python3.12 scripts/evidence.py validate DOC-QA-001` returned 0 for the final manifest. This validates record consistency and source fingerprints; it does not establish product acceptance.

## Review and runbook

[Work record](../../work-items/DOC-QA-001.md). Independent reviewer `/root/qa_review` approved the final answers and figures, with no unresolved findings. Two inaccurate symbol labels and overly broad lease-loss wording were corrected. Review confirmed source fingerprint `8e115dbbb75dbce77c9a095a65de7f0b26a75b01c5f612cb6c0403411e7869f9` and documentation fingerprint `68171d832bb4c7cb605ab94c7c1841efd772bd9f9636b2147146c9d9934ca6ac`; the manifest retains the per-file inventory.

Operating behavior is unchanged. Only the specification validation and deterministic harness portions of the existing runbook are exercised for this work item.

## Limits and raw artifacts

This is documentation/static evidence, not live model, database, H1 or product acceptance evidence. The root README and diagram directory are outside the generic harness input list, so a separate per-file documentation hash inventory binds them to review and verification. `scripts/evidence.py` does not automatically rehash that extra inventory on later edits: rerun the documentation checks and review when those files change.

During diagram preparation, muted text on the focal tint measured 4.357:1; changing that pairing to Luma foreground corrected it without changing project tokens. The prepared Playwright headless-shell was missing, so rendering used installed Google Chrome. A direct-SVG full-page capture timed out; final SVGs were successfully rendered as image resources in local HTML, matching their Markdown embedding use. These attempts were not counted as passing checks; the table records the successful final procedure. Exact app fonts were not bundled; offline system-font substitutions are disclosed in the diagram notes. No application tests or paid inference were run, and none was needed for this documentation-only scope.

Raw reports, local check scripts and screenshots are kept under `.checks/DOC-QA-001/2026-11-05-doc-qa/` through review and acceptance. The versioned manifest retains their hashes; this summary retains the observations so the conclusions remain readable if ignored local files are later unavailable. The downloaded design source is pinned under ignored `.checks/diagram-design-source`; no plugin or dependency was installed.
