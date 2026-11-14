# Decision 0027: Choices made while delivering refactor items R-01 to R-20

**Date:** 2026-11-14. **Authority:** the owner, by delegation. They asked to work "from R-01 to R-20" of [the code-quality review's refactor plan](../../reviews/review-2026-11-12-09-52-30/refactor-plan.md) and to "take responsible and senior and hard decisions that require a human interaction for me".

Each choice below is one the plan left to the owner. Where two options were close, the one that keeps current behavior, adds no dependency or is easier to reverse was chosen. A later owner decision replaces any of them.

| # | Item | Choice | Why |
|---|---|---|---|
| **D1. Web unit tests** | [R-01](../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-01) | Web unit tests stay on Node's own test runner (`node --test`), over modules without JSX, selected by glob. Vitest and Testing Library are not adopted now. A component test that needs a DOM belongs in a browser suite until a story pins and records a component-test tool | It is what the project already runs, it needs no new dependency, and DH-06's mention of Vitest is not yet backed by a pinned install. Pure logic moves out of components into `lib/` modules, as R-13 and R-16 did, so it stays testable |
| **D2. Run admission keys** | [R-18](../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-18) | The composer, the session panel and Continue keep one idempotency key until the outcome of a press is known. A known outcome, accepted or refused, ends that key, so the next deliberate press starts a new run. While a request is pending, the Run button is disabled and a second press does nothing | US-4.1's acceptance is about the server: one key and request hash give one admission. Nothing records a per-press rule for the screens, and per-press keys let a lost reply turn into a second paid run. Keeping the key only until the outcome is known still lets a person start the same goal twice on purpose |
