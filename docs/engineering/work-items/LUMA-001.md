# LUMA-001 — Luma design contract and dark concepts

## Plan

Adopt the user's exact shadcn Luma CSS as the canonical palette, with dark as the default. Update relevant PRDs, SPECS, README and frontend harness guidance. Regenerate the six interface concepts and the gallery while preserving their reviewed product semantics and the previous artwork.

## Implemented

Added [PRD-Design-System.md](../../PRD/PRD-Design-System.md) DS-01–DS-05 and the verbatim [token file](../../design/luma.css). Updated the implementation, comparison, provider, deployment and development PRDs; expanded existing SP-014, added LC-34 and extended US-2.5 without changing its status. SPECS retains 10 epics and 42 stories, now with 86 tasks after two explicit theme tasks.

Mapped the design PRD into the local harness sources and linked it from the frontend rule and ingestion guidance. Regenerated backlog navigation. Product code, services and model credentials remain untouched.

The visual deliverable uses six Luma dark concepts, exact local CSS for the gallery, saved prompts, a new manifest and an archive of the superseded warm-green set. Raster art approximates colors; the CSS is authoritative.

## Review and verification

Independent reviewer `/root/luma_review` verified the exact supplied declarations, source alignment, dark-first preference behavior and preserved implementation status. The CSS file is fingerprinted separately in design/artifact evidence because the existing repository harness fingerprints Markdown and tooling, not this CSS path.

Final image review, artifact checks and repository check outcomes are recorded in the [evidence summary](../evidence/LUMA-001/summary.md). Checks qualify documentation and design artifacts only. First-paint, browser persistence, keyboard/contrast and live app qualification remain implementation criteria.

## Runbook

Use the [gallery viewing runbook](../../imagine/README.md#local-viewing-runbook) to inspect the dark concepts. Read DS-01–05 and consume the canonical token file when implementing the frontend; preserve its exact declarations and separately verify both themes in the real app.

For backlog/document changes, run `python3.12 scripts/specs.py render`, `python3.12 scripts/specs.py validate` and `python3.12 scripts/verify.py --profile harness`. Keep raw command output under ignored `.checks/LUMA-001/` and reviewed fingerprints/results under the evidence directory.
