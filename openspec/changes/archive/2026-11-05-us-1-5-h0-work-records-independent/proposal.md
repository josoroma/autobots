## Why

SP-003 and DH-W01–06 require a proportional work record and evidence that cannot be faked by a template, a stale fingerprint, a skipped check or an open blocking finding. The repository has hand-written records but no reusable templates and no validator, and US-1.6 and US-1.8 need both.

## What Changes

- Templates under `docs/engineering/templates/`: `work-item.md`, `evidence-manifest.json`, `evidence-summary.md` and `runbook.md`. Each is visibly unexecuted, with `template: true` or `Status: TEMPLATE`, `{{placeholder}}` values and `not_run` checks.
- `docs/engineering/evidence/README.md`: the durable redacted evidence and ignored raw-artifact retention contract.
- `scripts/evidence.py`: `fingerprints` prints current input hashes, `validate <id>` lists every reason a work item is not complete, and `complete <id>` sets `Status: COMPLETE` only when validation passes. Exit codes: 0 valid, 1 invalid, 2 unusable request.
- This story delivers the means, not a qualification. US-1.6 qualifies manifest validation with its fault matrix, and US-1.8 exercises it on the baseline.

**Applicability, by Decision 0003:** routine `/ohmyorch:deliver` stories keep their OpenSpec change as their record. These records apply when a story's acceptance or the user asks for them, as US-1.8's does. US-1.5's scenarios ask for templates and validation, and do not ask for an independent review of this story, so none is run. The templates define how one is recorded.

## Capabilities

### New Capabilities

- `work-record-evidence`: work-record and evidence templates, and validation that rejects unsupported completion.

### Modified Capabilities

None.

## Impact

New `scripts/evidence.py`, `docs/engineering/templates/`, `docs/engineering/evidence/README.md` and `tests/harness/test_evidence.py`. Updates the harness runbook, `AGENTS.md` and `CODEBASE.md`. No dependency, service or model call. Existing records under `docs/engineering/work-items/` and `evidence/` predate this schema and are not rewritten.
