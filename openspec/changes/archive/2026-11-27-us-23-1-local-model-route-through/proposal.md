# Proposal: a local model route through the shared gateway (US-23.1)

## Why

Decision 0041 lets a run's model calls be answered by a model served on this Mac, with no OpenRouter call. Every later story in EPIC-23 needs a local route in the shared gateway first: qualification (US-23.2), the Model source setting (US-23.3) and the three runs (US-23.4 to US-23.6). A15's measurements chose Bonsai 2.5 as the first local profile.

## What Changes

- **Two local profiles**, approved and not offered: Bonsai 2.5's Q2_0 and Inkling 2 Mini's UD-Q3_K_XL. Each names its Hugging Face repository at its revision, its weights file's SHA-256, its chat template's hash, the model ID `llama-server` reports, and its thinking switch (A2, A3, A9).
- **The one model factory gains a local branch.** It is the same `ChatOpenRouter`, with a loopback client on httpx (already locked). That client posts OpenAI-style chat completions to `http://127.0.0.1:<port>/v1`, with no key and no retries, and reports US$0 as the call's cost. No new dependency.
- **The served model is checked before each call** through `/v1/models`. A different model is refused `model_unavailable`. A port with nothing listening blocks with a new typed reason, `local_model_server_unavailable`, which suspends the run like a missing key. Neither tries another model or source (A3, MP-08).
- **A local call reserves US$0** and keeps its invocation ticket, receipt, `model_calls`, tokens and the run's limits. It reads no OpenRouter catalog and no OpenRouter key (A2).
- **Thinking stays out of the reply.** The profile's switch goes in `chat_template_kwargs`, and any `reasoning_content` the server returns is dropped (A9).
- **One named tool is sent as `required`,** carrying only that tool (the plan's section 5).
- **Not offered until qualified.** The model-policy listing leaves local profiles out, and every choice that names one is refused `model_not_offered` (A7).
- **A runbook section** for the owner's `llama-server`, and the requirement rows Decision 0041 assigns to this story.

## Capabilities

### New Capabilities
- `local-model-route`: a model call answered by an owner-started `llama-server` on loopback, through the shared gateway, its identity checked before each call, at US$0, and with thinking kept out of the reply.

### Modified Capabilities
- None. OpenRouter routes keep every requirement they have, and `local-model-route` states that they're unchanged.

## Impact

- **Python:**
  - `domain/models.py`: profiles and the not-offered messages.
  - `adapters/models/local_server.py` (new) and `adapters/models/factory.py`.
  - `application/worker_inference.py`.
  - `application/model_attempts.py` and `domain/stops.py`: the new failure class.
  - `application/provider_settings.py`: the listing.
- **Contracts:** the `StopCode` and failure enums, and the model profile enum, in OpenAPI and the generated TypeScript client.
- **SQL:** one migration that adds the two profile IDs to the profile checks and inserts their `model_profiles` rows.
- **Docs:**
  - `AGENTS.md` and `.claude/rules/model-gateway.md`;
  - PRD-Model-Providers MP-02, MP-07 and MP-08;
  - option-b-contract SP-008;
  - PRD-Local-Mac-Deployment LM-01, LM-A03 and LM-07;
  - PRD-LangChain-Deep-Agents' scope, 2.2 and 6.3;
  - the `autobots-model-gateway` skill;
  - the local app runbook;
  - `CODEBASE.md`.
- **Not here:** qualification and offering (US-23.2), and the Model source setting with its per-route limits (US-23.3).
