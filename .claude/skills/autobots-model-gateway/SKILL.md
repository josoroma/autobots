---
name: autobots-model-gateway
description: Implement or review Autobots OpenRouter routing, role snapshots, credential settings, budgets and tool/structured-output handling using controlled fake transports by default.
---

# One application inference gateway

Relevant paths: `services/agent/src/autobots/adapters/models/**/*`, `services/agent/src/autobots/application/**/*`, `services/agent/src/autobots/graphs/**/*`, `apps/web/app/api/settings/**/*` and `apps/web/src/app/api/settings/**/*`.

Read `.claude/autobots.json`, the mapped providers/contract and selected story. The [provider PRD](../../../PRD-Model-Providers.md) owns exact profile IDs, precedence, endpoints, credential storage and acceptance gates; do not invent adapter defaults.

- All 14 roles initially select `openrouter_deepseek_flash`; only explicit selection enables `openrouter_astra`. Preserve canonical snapshot and wire request IDs. No local inference, alternative provider, embedding service, hidden reviewer model or automatic fallback.
- Freeze role bindings and limits at run admission. Changed models create a linked new run; rotated credentials resolve late through references inside the attempt, never serialized keys/clients in durable state.
- Honor process/dotenv/encrypted-store precedence. Nonblank invalid higher-priority keys block fallback. Missing credentials leave local UI/files/settings usable but block all inference. Save & validate authenticates metadata and checks catalog availability separately; it does not generate text or auto-run the preserved draft.
- Require fresh exact catalog association and supported parameters, `require_parameters=true`, `allow_fallbacks=false`. Omit unsupported Astra sampler settings. Enforce budget reservation/concurrency under locks, accounting for ambiguous outcomes; estimates are not a provider billing guarantee.
- Validate completed tool arguments and structured results before effects. Truncated output or streamed prefixes are not valid results. Qualify named-tool enforcement explicitly; a correct response after ignored parameters is not compatibility success.
- Default tests inject a fake transport and reject real network inference even if the shell contains a key. Live OpenRouter qualification requires an explicitly initiated bounded task and its own evidence.

Return routing/security behavior, credential/error states, budget/replay implications and actual mocked versus live results. This concerns application inference; never reconfigure the developer's assistant credentials or assume these model IDs work in Claude Code.

Failure behavior: templates, skipped tests and missing tools never count as passing evidence, and a fake transport result never qualifies live inference. Report a failed or unavailable check as such; there is no fallback to another model or provider.
