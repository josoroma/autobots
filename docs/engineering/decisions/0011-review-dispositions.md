# Decision 0011: Open questions from earlier reviews, kept as built

**Date:** 2026-11-06. **Authority:** the owner, who was shown what the code does today for each and answered "Accept all as they are".

## Decision

| Item | Question | Decision |
|---|---|---|
| **M8** | Can members choose an earlier Expert version? | No. Only an owner can |
| **M32** | Is `to_version` 0 the interface for "no active version"? | Yes |
| **M33** | Are a reviewer's own text checks enough to gate promotion for now? | Yes, for now. Real held-out replay is later scope, with no story yet |
| **WORKER-INFERENCE-001** | Should `rate_limited` and `provider_error` fail a run after their retries, or pause it? | They fail, and a person starts a linked new run with **Continue in a new run** |

## Corrected

The owner first accepted M33 on being told held-out replay stayed with US-10.1. US-11.12's review found US-10.1 is finished and built no such thing, so that was false. The owner was told, and chose to keep the gate with replay as later scope. The review also found M8 only half built, as a session could still pin a version, and that no screen started a linked run. US-11.12 fixed both to match this decision.

## What this gives up

- **A rate limit ends a run,** where a pause could have resumed it once the limit cleared. The earlier reviewer recommended pausing on `rate_limited` at least.
- **A member can't choose an earlier Expert version,** even where that would be harmless, though they can run in a session an owner pinned to one.
- **A text match can pass a promotion** that a real replay would catch, and nothing is planned yet to replace it.

## Reversal

Each can be changed later under its existing ID. No data depends on these choices.
