# Verification — us-1-5-h0-work-records-independent

Change: us-1-5-h0-work-records-independent
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `1018873`, working tree with this change. Static and fixture evidence; no service, database or model call.

## Scenarios

**Prepare honest templates: observed.** `docs/engineering/templates/` holds the work item, manifest, summary and runbook. The work item has all five stages. Together they carry traceable IDs, all five fingerprint fields, review findings, expected and observed results and a runbook link. Fixtures read the real files: `template: true`, `Status: TEMPLATE`, `not_run`, `observed: null`, `pending`, and the "TEMPLATE" labels are present.

**Reject unsupported completion: observed.** Arranged on a disposable work item in the ignored `.checks` tree, using `scripts/evidence.py complete` and starting from the real templates, deleted afterwards:

| Given | Exit | Visible | Status after |
|---|---|---|---|
| Unmodified templates | 1 | "is still a template", "names no evidence id" | `TEMPLATE` |
| `template: true` | 1 | "is a template, not executed evidence" | `IN PROGRESS` |
| A skipped check | 1 | "was skipped", "no passing check covers SP-1" | `IN PROGRESS` |
| Unresolved blocking finding | 1 | "blocking finding F-1 is not resolved" | `IN PROGRESS` |
| Input changed afterwards | 1 | stale `source_manifest_sha256`, `verifier_sha256`, reviewed fingerprint | `IN PROGRESS` |
| Corrected, all current | 0 | `PASS` | `COMPLETE` |

`tests/harness/test_evidence.py`, 23 tests, also covers inconsistent status and result pairs, self-review, runbook staleness, `live` with a fake transport, raw artifact hashes, recognizable secrets, and a hand-written `Status: COMPLETE`.

## Findings

- **Independent review of this story:** none was run. The scenarios ask for templates and validation. The templates define how a review is recorded; a real one comes with US-1.8. If you read US-1.5's title as requiring its own review, that review is outstanding.
- **Not qualified:** US-1.6 owns qualifying manifest validation. No real work item has been validated, and the sample here was arranged. `validate US-1.2` fails with "names no evidence id", as expected for a record that predates this schema.
- **Nothing automatically invokes this validator.** It runs when called, so the `DONE` gate in routine delivery does not read it, by Decision 0003.
- **Pattern-based secret detection** is a backstop for recognizable forms, and does not replace redaction.
- **A pass shows consistency and currency, not correctness.** A hand-edited manifest with matching hashes passes. DH-09.2's runner-derived statuses remain unimplemented; tying manifests to verifier reports belongs with US-1.6 and US-1.8.
- **Runbook:** the added section's commands were run as written.
- This is not H0, H1 or product acceptance.
