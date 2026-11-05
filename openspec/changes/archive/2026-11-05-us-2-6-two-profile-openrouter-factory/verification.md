# Verification — us-2-6-two-profile-openrouter-factory

Change: us-2-6-two-profile-openrouter-factory
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `be2efe9`, working tree with this change. Mock class only: a fake transport through the real `ChatOpenRouter` and `openrouter` SDK. No model was called, and no credential was used.

## Scenarios

**Resolve the approved role map: observed.** A new workspace gives exactly the 14 PRD roles, all on DeepSeek. Tests show each step of the order: workspace default, then workspace role override, then run-wide selection over those, then run role override over everything. Local, wire-ID, automatic-router, empty and unknown profiles, and an unknown role, are refused. The frozen map can't be changed after resolution. `EffectiveRolePolicy` shows the complete map, and its role and profile enums are generated into TypeScript.

**Reject drift and implicit routing: observed on mocks.**
- Blocked as `model_unavailable`: a catalog over five minutes old, one dated in the future, a missing entry, canonical drift and an ambiguous mapping. A catalog exactly at the limit passes. A drifted Astra with a healthy DeepSeek in the same catalog is refused, and DeepSeek is not substituted.
- Refused: `model`, `models`, `route`, `plugins`, `provider`, `base_url`, `api_key`, `transforms` and `preset` as options, any unknown option, and Astra's `temperature`, `top_p` and `parallel_tool_calls`, which its catalog entry lacks.
- On the wire, through the fake transport: the URL is exactly `https://openrouter.ai/api/v1/chat/completions`, `model` is the wire ID, and `provider` is `{"require_parameters": true, "allow_fallbacks": false}`, with no `models`, `route` or `plugins`.
- Hidden defaults: `OPENROUTER_API_BASE` and `OPENROUTER_API_KEY` set in the environment do not change the factory's route or key. `max_retries` is 0.
- A static test finds no inference client built outside `factory.py`.
- The dated real catalog in `research/` parses to both approved associations, and shows Astra's missing sampler support.

`full` exit 0 under `env -i`, `fast` and `harness` exit 0.

## Findings

- **No live catalog fetch exists,** so "fresh" is enforced on a snapshot handed to the factory. The story's tasks say mocked. Whichever story adds the fetch, or US-3.4's qualification, owns the real one.
- **The snapshot at admission isn't persisted yet.** `RolePolicy` is frozen in memory, and MP-01's stored snapshot with provider, catalog revision, limits and credential reference comes with run admission.
- **`checked_options` refuses rather than omits** an unsupported option. MP-02 says to omit Astra's sampler settings, which is satisfied by never sending them by default. A caller explicitly asking for one is refused. If role code later shares options between profiles, it must build them per profile.
- **Not verified on OpenRouter:** that it honors `provider.require_parameters`, or that these IDs route. US-3.4 owns live qualification, and needs a paid-call decision.
- **`max_tokens` and `reasoning`** pass through only when the catalog lists them. Their shapes aren't validated yet.
- This is not H1 or product acceptance.
