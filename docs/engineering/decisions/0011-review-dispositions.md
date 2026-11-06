# Decision 0011: Open questions from earlier reviews, kept as built

**Date:** 2026-11-06. **Authority:** the owner, who was shown what the code does today for each and answered "Accept all as they are".

## Decision

| Item | Question | Decision |
|---|---|---|
| **M8** | Can members choose an earlier Expert version? | No. Only an owner can |
| **M32** | Is `to_version` 0 the interface for "no active version"? | Yes |
| **M33** | Are a reviewer's own text checks enough to gate promotion for now? | Yes, for now. Real held-out replay stays with US-10.1 |
| **WORKER-INFERENCE-001** | Should `rate_limited` and `provider_error` fail a run after their retries, or pause it? | They fail, and a person starts a linked new run |

## What this gives up

- **A rate limit ends a run,** where a pause could have resumed it once the limit cleared. The earlier reviewer recommended pausing on `rate_limited` at least.
- **A member can't reach an earlier Expert version,** even where that would be harmless.
- **A text match can pass a promotion** that a real replay would catch.

## Reversal

Each can be changed later under its existing ID. No data depends on these choices.
