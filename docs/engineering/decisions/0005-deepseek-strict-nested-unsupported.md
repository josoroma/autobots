# Decision 0005: DeepSeek's strict nested output is unsupported

**Date:** 2026-11-05. **Authority:** explicit user decision in this session: "Yes, record it", to the question "Record DeepSeek's strict nested output as unsupported?", after being told this would also clear US-3.4's `External:` line and that a code switch was available on request.

## Decision

Strict nested JSON output on `openrouter_deepseek_flash` is recorded as **unsupported, and it stays disabled**.

"Disabled" here means nothing in the application asks for it: outside the qualification runner, no code calls `with_structured_output`, sets `response_format` or binds tools with `strict`. There's no runtime switch that enforces this, but `test_no_application_code_asks_for_strict_output` fails if application code starts asking for it. Anything that starts using strict output on this route needs a passing qualification or a switch first.

On `openrouter_terra`, strict nested output works only with every object closed, as [Decision 0004](0004-terra-replaces-astra.md) says.

## Why

[The US-3.4 evidence](../evidence/US-3.4/summary.md) has DeepSeek at 0 of 13 trials: 7 at the 512-token limit, which ran out of tokens, and 6 at 2,048, which returned a parsed reply with the wrong `place`. US-3.4's own scenario expects unsupported capabilities to remain disabled, so this settles the story without changing its acceptance.

## What this gives up

Stated plainly, because the sources still ask for more:

- **MP-A06** says strict schemas pass on each enabled route. For DeepSeek's nested schemas, that's not met. Flat schemas passed.
- **The default model has this gap:** DeepSeek is the default for all 14 roles. Plans and other nested tool arguments aren't strict, and rely on server validation as SP-008 requires.

## What this doesn't establish

- **Why the 2,048-token replies were wrong:** only one literal value was tried.
- **That a real goal works:** no goal has succeeded on either model, as [the live goal record](../evidence/LIVE-GOAL-1/summary.md) shows.
- **The evidence's other limits**, which stay open and aren't settled here:
  - Whether the provider stopped on a cancelled call, and what it charged.
  - The upstream provider, unrecorded on every call.
  - Concurrent admission on a live route (MP-A09).
  - Real fragmentation of DeepSeek's streamed tool arguments, covered only by the fake transport.

## Consequences

- **US-3.4's `External:` dependency is removed:** usable credentials exist and the paid rounds were authorized. Any further paid qualification still needs its own authorization.
- **US-3.4 can move to `READY`** through `promote`, not by hand.
- **Delivering US-3.4 doesn't establish H1 or product acceptance.** Task quality stays with US-10.1.

## Reversal

Requalify the route with a passing nested fixture and record it, or add a switch and enable it. The route's results stay in the evidence either way.
