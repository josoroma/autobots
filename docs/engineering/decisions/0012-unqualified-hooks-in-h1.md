# Decision 0012: Unqualified hooks in H1

**Date:** 2026-11-06. **Authority:** the owner, who chose this when US-11.12's review showed that the sources and the project disagree.

## Decision

The harness PRD asked for an unqualified Claude integration to be explicitly inactive. This project's hooks are installed and firing as guardrails, and Claude's own crash, timeout and Stop recursion behavior isn't qualified.

H1 may be assessed with them on, reported as **configured and not qualified**. DH-A03 stays partial, so H1 can only read as met with that limit stated. Script fixtures are never reported as actual event delivery.

H1.3, DH-A03, Option B's gate paragraph and the Option B contract are revised to match, with their IDs kept. `PRD-Comparison-Recommendation.md` and older story text in `SPECS.md` say the same thing in earlier words, and read under this decision without being rewritten.

## What this gives up

Nothing has shown what Claude does if a hook crashes or times out, or how Stop recursion behaves. A hook is a guardrail here, not a guarantee, as the harness already says.

## Reversal

Qualify the behavior on a disposable fixture, or turn the hooks off, under the same IDs.
