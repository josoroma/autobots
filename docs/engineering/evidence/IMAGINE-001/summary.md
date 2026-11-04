# IMAGINE-001 evidence

**Scope:** six generated desktop interface concepts and their local gallery. This is design-artifact evidence, not live application or provider qualification.

**Superseded visual direction:** the original warm-green deliverables are preserved in [the archive](../../../imagine/archive/warm-green-v1/). The active gallery and filenames now use Luma dark under [LUMA-001](../LUMA-001/summary.md). This historical result does not validate the replacement files; use their new manifest and evidence.

[Work record](../../work-items/IMAGINE-001.md) · [Gallery](../../../imagine/index.html) · [Prompt record](../../../imagine/prompts.json) · [Artifact manifest](../../../imagine/manifest.json) · [Static verification](verification.json)

## Review

The coordinator inspected every final screen. Independent reviewer `/root/visual_concept_review` inspected all six images, their source alignment, README, prompt record and gallery HTML.

Review found ambiguous key-storage wording, active-step progress styling and an unhighlighted changed comparison line. Targeted image-generation edits corrected these. The coordinator inspected the returned final revisions, and the independent reviewer confirmed that the findings were resolved. The HTML image dimensions were also aligned to the actual PNGs.

Remaining limits: minor generated-text punctuation, illustrative timestamps/prices/source references, and a desktop-only concept set. HTML responsiveness, alt text, focus styles and reduced-motion handling were inspected statically; browser interaction and accessibility conformance were not tested. The images do not prove implemented controls, runtime capabilities or factual accuracy of sample content.

## Verification

The artifact check reads all PNG chunks, validates CRCs and dimensions, verifies six-screen prompt coverage, resolves gallery links and anchors, checks native image attributes and records SHA-256 hashes. The manifest binds the images and supporting files to the selected source documents. The verification JSON records the actual results and the executed check.

Observed: six valid PNGs, six matching prompt entries, 29 resolving gallery references, 13 unique IDs, six accurate image dimensions/alt descriptions and 26 resolving Markdown file links. No external gallery assets. The check exited 0. Its script is retained in ignored `.checks/IMAGINE-001/artifact-check.py`; the verification record includes its fingerprint. No package configuration or lockfile was introduced by this design task.

The local viewing procedure is documented in the [README](../../../imagine/README.md#local-viewing-runbook). Final PNGs were opened and visually inspected. The gallery was checked as a self-contained local document; it was not exercised in a browser.

## Boundaries

Generated with the built-in image-generation tool. No app inference provider was configured or called, no API key was read, no service/database/container was started, and no product acceptance status was changed. Original generated images remain in the tool's output directory; final selected copies are in `docs/imagine`.
