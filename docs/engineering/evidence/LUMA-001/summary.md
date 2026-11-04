# LUMA-001 evidence

**Scope:** the approved Luma design contract, existing-doc/backlog integration, exact CSS tokens, and six regenerated dark UI concepts. Application theme behavior remains unimplemented.

[Work record](../../work-items/LUMA-001.md) · [Design contract](../../../../PRD-Design-System.md) · [Exact tokens](../../../design/luma.css) · [Gallery](../../../imagine/index.html) · [Prompts](../../../imagine/prompts.json) · [Artifact manifest](../../../imagine/manifest.json) · [Static verification](verification.json) · [Repository verification](harness-verification.json)

## Document and token review

Independent reviewer `/root/luma_review` checked the supplied CSS against the canonical file and found no material difference: 32 light declarations and 31 dark overrides, including exact alpha values, blue primary/sidebar tokens, unchanged chart colors and inherited radius.

The reviewer checked dark-first versus OS preference, explicit local light/dark persistence, semantic styling, accessibility verification requirements and source links. Existing SP/story IDs and implementation statuses remain intact. DS-01–DS-05, LC-34 and SP-014 express requirements rather than runtime claims.

The existing repository harness does not fingerprint `docs/design/luma.css`; this work item's artifact manifest and verification record explicitly include the CSS hash and compare its complete contents against the user-supplied block.

## Verification

Observed repository checks:

- `python3.12 scripts/specs.py render`: exit 0; 10 epics, 42 stories, 86 tasks.
- `python3.12 scripts/specs.py validate`: exit 0 with the same counts.
- `python3.12 scripts/verify.py --profile harness`: exit 0; project configuration, backlog and all 45 deterministic harness tests passed with stable inputs.

The artifact checker verifies exact CSS, PNG chunk CRCs/dimensions, six-screen prompt coverage, replacement of all six previous images, intact archived originals, local gallery links/anchors, dark root class/canonical stylesheet, alt text and native image dimensions. Its actual results and verifier fingerprint are in `verification.json`. The reproduction script is retained at ignored `.checks/LUMA-001/artifact-check.py`.

Observed artifact check: exit 0; exact supplied CSS matched; all six PNGs and prompt entries passed; all six original images remained intact in the archive; 33 local gallery references, 13 unique IDs, six native dimensions/alt descriptions and 51 Markdown file links resolved. The current harness report still matched its inputs.

## Visual review and limitations

Review covers all six dark screens, primary-action color, legibility, consistent layout and preservation of progress, approval, credential, terminal-state and workflow-version semantics. Generated raster colors approximate the CSS; no exact per-pixel palette claim is made.

The image author and coordinator inspected all six final PNGs. Independent reviewer `/root/luma_review` found no material issue with the final images or gallery and confirmed all 33 references, native dimensions and absence of canonical-variable collisions. The coordinator also confirmed the workflow image's top-right sample-data tag after a reviewer note questioned its presence.

Minor raster typography/texture is concept-art variation. Fictional names, prices, dates, source references and statuses remain labeled sample data. The local gallery is statically checked; browser interaction, first-paint behavior, persisted theme selection, accessibility/contrast conformance and responsive app behavior require the future implementation checks in DS-05.

## Runbook and boundaries

The [local viewing runbook](../../../imagine/README.md#local-viewing-runbook) opens the gallery or individual PNGs. Keep `docs/design/luma.css` at the relative path used by the gallery. The previous warm-green artwork and original metadata remain in [the archive](../../../imagine/archive/README.md).

Used built-in image generation. No app inference credentials were read or changed, no application service/database/container was started, and no product story was marked complete. This update changes the specification and visual artifacts only.
