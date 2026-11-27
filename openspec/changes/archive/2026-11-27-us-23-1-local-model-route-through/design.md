# Design: a local model route (US-23.1)

## Context

- **Every model client comes from one factory.** `adapters/models/factory.chat_model` builds a `ChatOpenRouter` on OpenRouter's SDK client.
- **The worker builds a client per call.** `application/worker_inference.InferenceSource` prepares each attempt against a cached OpenRouter catalog (`prepared`), reads the workspace's OpenRouter key (`open_attempt`) and reserves the catalog's worst case.
- **The loop settles each call from the reply.** `adapters/loop_middleware` reads `response_metadata["cost"]`. A reply without a cost is left uncertain (`model_attempts.run_attempt`).
- **Browsing reaches the same path.** The admitted browser endpoint (US-17.2) calls `role_route` and `AttemptModel`, so a local route serves it with no change of its own.

## Goals / Non-Goals

**Goals:** a local route through the same factory, admission and ledger. Its identity is checked before each call. A stopped server gives a typed reason. Thinking is switched off where the model allows and kept out of the reply. Local profiles aren't offered.

**Non-Goals:**
- qualification and offering (US-23.2);
- the Model source setting, the "only local" rules and per-route limits (US-23.3). Until then a local route runs under today's limits;
- starting the server (the owner does, by the runbook).

## Decisions

### D1. The same `ChatOpenRouter`, with a loopback client

`ChatOpenRouter` accepts any client with `chat.send` and `chat.send_async`:
- A non-streaming reply may be a plain dict.
- A streamed chunk needs only `model_dump(by_alias=True)`.
- It reads reasoning only from a `reasoning` field, so llama-server's `reasoning_content` is never mapped into a message.

`adapters/models/local_server.py` holds `LoopbackClient`, on the httpx already locked. It:
- posts `/v1/chat/completions` to `http://127.0.0.1:<port>`, with no Authorization header and no retries;
- removes OpenRouter-only parameters (`provider`, `route`, `plugins`, `session_id`, `trace`, `reasoning`);
- adds the profile's `chat_template_kwargs`;
- sends one named tool as `required` with only that tool;
- removes `reasoning_content` from messages and deltas;
- writes `cost: 0` and `provider: "local"` into the usage it returns, so the ledger settles US$0.

`ChatOpenRouter` insists on a non-empty key string. A fixed placeholder fills that slot inside the process, and it is never sent.

**Rejected:** `langchain-openai`. It's a new locked dependency, and the client it brings would duplicate `ChatOpenRouter`'s message conversion, tool binding and usage handling.

### D2. Identity and a stopped server, before each call

`served_model(port)` reads `/v1/models` before the client is built for an attempt:
- A model ID other than the profile's raises `ModelUnavailable`, which becomes `model_unavailable`.
- A refused, timed-out or cut-off connection (any httpx transport error) raises `LocalServerUnavailable`, which becomes a new `FailureClass.LOCAL_MODEL_SERVER_UNAVAILABLE`. Its `StopCode` is `local_model_server_unavailable`, disposed SUSPEND like `model_unavailable`, because the owner starting the server resolves it.

Both happen in `open_attempt`, before the reservation could be sent anywhere, so nothing reaches the server's chat endpoint. The weights' SHA-256 and the template hash are pinned in the profile and checked by the runbook's `verify-models.py`. Hashing 7 to 14 GB before each call isn't affordable, and A3's per-call check is the served model ID.

### D3. Profiles

`ModelProfileId` gains `local_bonsai_2_5_27b` and `local_inkling_2_mini`. `ModelProfile` gains an optional `LocalServing`, which holds:
- the repository, revision, file and its SHA-256;
- the chat template's SHA-256, as `llama-server` reports it in `/props`;
- the thinking switch, as `chat_template_kwargs`.

The `canonical_id` is `<repository>@<revision>/<file>` and the `wire_id` is the served model ID:
- `bonsai-2.5-27b-q2_0`;
- `inkling-2-mini-ud-q3_k_xl`.

The runbook's `--alias` sets those IDs. Neither profile is in `OFFERED_FOR_NEW_RUNS`, and each has a not-offered message.

### D4. Worker inference

`prepared` no longer fetches the catalog for a local profile:
- It checks options against the local parameter set: `max_tokens`, `temperature`, `top_p`, `seed` and `stop`. OpenRouter's `reasoning` is refused.
- It returns a worst case of 0, with no price tier.

`open_attempt` reads no credential for a local profile, and `reject_key` is skipped. `_refusal` skips the run intent, which is the OpenRouter key, and the catalog. `_input_rate` returns 0.

The port is `AUTOBOTS_LOCAL_MODEL_PORT`, default 9931, read from the worker's environment. The request timeout sits above `MODEL_CALL_SECONDS`, so the loop's bound decides, as for OpenRouter.

### D5. Not offered, and out of every choice

`require_offered` already refuses unoffered profiles everywhere new work names one: run admission, `model_policy`, and the Expert routes. The model-policy listing (`provider_settings`) leaves out a local profile that isn't offered, so no picker lists it. DeepSeek's listing is unchanged.

### D6. SQL

Migration `20261127000068_local_model_profiles.sql`:
- adds both IDs to the three profile checks: `model_profiles`, `model_policies.default_profile` and `model_invocations.profile`;
- inserts their `model_profiles` rows, as Sol's migration did.

Nothing is rewritten.

## Risks / Trade-offs

- **A future `ChatOpenRouter` may stop accepting a duck-typed client.** It's pinned at 0.2.9, and the tests exercise the real class with the loopback client.
- **A local call may take longer than the loop's 300 seconds,** and be interrupted before US-23.3 sets its limits. That's acceptable before the setting exists, because no local profile is offered until US-23.2.
- **`/v1/models` per call adds one loopback round trip,** a few milliseconds.

## Migration Plan

The migration only adds. Reversal: the profiles stay approved and unused. Nothing offers them until US-23.2.
