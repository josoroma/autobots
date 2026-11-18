# Evidence contract

This defines what a work item's evidence holds and how long it lasts, per [DH-09.2](../../PRD/PRD-Development-Harness.md#dh-092-fingerprints-manifests-and-retained-artifacts). Directories here that lack the `autobots.work-evidence/v1` manifest predate this schema and were not rewritten. Routine `/ohmyorch:deliver` stories keep their archived OpenSpec change as their record, by [Decision 0003](../decisions/0003-openspec-only-delivery.md); this contract applies when a story's acceptance or the user asks for it.

## Durable, versioned

`docs/engineering/evidence/<work-item-id>/` holds `<evidence-id>.json` and `summary.md`, from [the templates](../templates/). The summary preserves the observed assertions and reproduction details, so a result never depends only on a raw log. Failures, errors, skips and limits stay in it.

Never save credentials, `.env` contents, provider keys, user content or unredacted transcripts. Validation refuses recognizable key patterns, which is a backstop and does not replace redaction.

## Raw, ignored

`.checks/<work-item-id>/<evidence-id>/` holds large redacted logs and screenshots. It is Git-ignored and is never the sole proof.

- **Reference:** `checks[].artifacts` names each file by `path` and `sha256`. Every check also names its run in `source`: `report`, re-read from the verifier's report by `validate`, or `manual`, which must keep such an artifact.
- **Retention:** keep raw artifacts through review and acceptance, and longer for an unresolved failure or release gate. The manifest's `raw_artifacts.retention` states the policy for that evidence.
- **Availability:** `raw_artifacts.availability` is `not_created`, `available`, `deleted` or `unavailable`. Record a later deletion by changing it, and leave the hashes in place. When it is `available`, validation checks each file's hash. A manual check needs `available`, so evidence relying on one stops validating once its artifact is deleted, which is visible and deliberate.

## Classes

The verifier assigns each step its class, and evidence copies it. `verification_class` is `static`, `mock`, `disposable`, `local_runtime` or `live`. `model_transport` is `none`, `mock` or `openrouter_live`. Only a `live` check may use `openrouter_live`, and a `live` check must use it, so a fake model cannot satisfy a live provider gate.

## Fingerprints

`python3.12 scripts/evidence.py fingerprints` prints the current hashes. The source manifest covers the verifier's input set, except records that change after verification: `SPECS.md`, `CODEBASE.md`, work items and runbooks. A runbook has its own revision hash. Hashes make evidence attributable and detect stale inputs; they do not prove an assertion was correct.

## Validating

`python3.12 scripts/evidence.py validate <work-item-id>` lists every reason the work item is not complete. `complete` runs the same validation and sets `Status: COMPLETE` only if there are none. See [the harness runbook](../runbooks/development-harness.md#validate-completion-evidence).
