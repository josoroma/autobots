## Why

US-10.2's findings B4 and B5: only some stories had an independent review, Gate 0's approval was voided by later source changes, and earlier reviews left 41 minors and four decisions open. Decision 0009 chose one independent review of the final code, which also repeats Gate 0 and settles those.

## What Changes

- One independent review of the final code, by reviewers who didn't author it, bound to a fingerprint.
- Gate 0's checks and the harness runbook repeated on that revision, with evidence that `scripts/evidence.py` validates.
- A stated outcome for each of the 41 minors, majors M8, M30, M32 and M33, and WORKER-INFERENCE-001.
- Claude's crash and timeout hook behavior marked not qualified, and the record handed to US-10.2's assessment.
- Whatever the review finds blocking is fixed, reviewed again and bound anew.

## Capabilities

### New Capabilities

- `final-review`: what binds a final review to a revision, what it must settle, and what refuses a stale or unresolved result.

### Modified Capabilities

None.

## Impact

Evidence under `docs/engineering/evidence/US-11.12/`, a work item, and fixes only where the review requires them. It leaves H1 and product acceptance to be assessed afterward.
