# PRD — shared model providers, credentials and execution policy

**Decision date:** 2026-11-04. **Status:** Finalized requirements; implementation and paid cloud qualification pending.  
**Authority:** Normative for [Next.js](PRD-NextJS.md), [LangChain / Deep Agents](PRD-LangChain-Deep-Agents.md) and the [architecture recommendation](PRD-Comparison-Recommendation.md), alongside the [local Mac deployment contract](PRD-Local-Mac-Deployment.md). This specifies our independent clone, not upstream AutoGPT behavior.

The application, workers, authentication, database, files and durable state run locally on this Mac; **all model inference uses OpenRouter**. Every role defaults to the approved Terra profile. DeepSeek stays approved and isn't offered for new runs until a recorded qualification and a decision bring it back, by [Decision 0013](docs/engineering/decisions/0013-release-closure.md). Before that it was available through explicit selection, by [Decision 0006](docs/engineering/decisions/0006-terra-is-the-default.md). There is no local inference runtime or local-only model profile in scope. Setting a key never starts work or changes model bindings. “Configured” means authentication succeeded, not that model capability or task-quality gates passed. Public documentation/catalog metadata established this revision; paid qualification remains pending.

## MP-01. Approved models and selection

| Profile | Canonical identity | Request identity |
|---|---|---|
| `openrouter_deepseek_flash` — optional | `deepseek/deepseek-v4.1-flash-20261017` | `deepseek/deepseek-v4.1-flash-1017` |
| `openrouter_terra` — default | `openai/gpt-6.1-terra-20261026` | `openai/gpt-6.1-terra` |

[Decision 0004](docs/engineering/decisions/0004-terra-replaces-astra.md) replaced Astra with Terra. The DeepSeek mapping is observed in the [dated public catalog snapshot](research/openrouter-model-catalog.json), and Terra's in the public catalog on 2026-11-05. Do not substitute a moving-family, Pro, batch or routing alias. In particular, Terra’s shorter request ID does not establish an immutable snapshot guarantee.

The registry contains exactly these two profiles. DeepSeek isn't offered for new runs until it's qualified, by [Decision 0013](docs/engineering/decisions/0013-release-closure.md), and a choice saved earlier that names it is refused with no substitute. Provide a per-run profile, an owner/admin workspace default for future runs and advanced versioned role bindings. New workspaces assign all 14 roles to `openrouter_terra`. Persist the canonical role keys `coordinator`, `router`, `planner`, `executor`, `researcher`, `coder`, `reviewer`, `evaluator`, `summarizer`, `memory_curator`, `skill_learner`, `tool_repair`, `workflow_generator` and `general_purpose` consistently across languages.

MVP retrieval uses local Postgres lexical/full-text search. No additional embedding/reranking model or inference endpoint is included.

Resolve each role in this exact order: explicit run-specific role override; otherwise the explicitly selected run-wide profile; otherwise the workspace role override; otherwise the workspace default; otherwise `openrouter_terra`. A run-wide selection applies to every role unless the user supplies a run-specific override. Display the complete effective map before dispatch. Reject local endpoints, unknown profiles and unapproved model IDs. There is no optional-cloud toggle: model-backed work always sends its approved payload to OpenRouter.

Snapshot `provider`, canonical model, resolved wire ID, role map, `role_policy_version`, catalog revision/time, limits and credential reference at admission. Children, compaction, summaries and reviewers inherit this resolved policy; framework defaults cannot introduce another model. Model-policy changes affect future runs. MVP runs keep their model bindings immutable; selecting a different model for unfinished work creates a linked new run with explicit artifact/evidence references instead of rewriting the original transcript or replay history. Resume uses its saved policy and rechecks availability. Credential rotation is separate and follows MP-06.

There is no automatic cross-model, provider or local-runtime fallback; failures pause or fail the affected work. Earlier [Bonsai research](research/LOCAL-MODEL-EVIDENCE.md) and the [Qwen experiment](research/QWEN38-GGUF-TEST-RESULTS.md)—13 qualified cases, one unsupported capability and one failed task—are historical evidence outside the active implementation scope.

## MP-02. Catalog and request contract

Before each paid attempt, use public catalog metadata no older than five minutes. Match the configured **non-batch** request ID to the exact requested `canonical_slug`; reject missing entries, drift or ambiguous mappings as `model_unavailable`. If metadata cannot be refreshed after expiry, block the new paid call. Never silently substitute. Public alias metadata cannot guarantee hard snapshot pinning at the provider; surface that limitation and record the observed mapping.

Use Chat Completions at `https://openrouter.ai/api/v1/chat/completions`, with server-side Bearer authentication. [OpenRouter authentication](https://openrouter.ai/docs/api_reference/authentication) documents this API base and authentication mechanism.

Every request must include:

```json
{
  "model": "<validated request ID>",
  "provider": {
    "require_parameters": true,
    "allow_fallbacks": false
  }
}
```

Do not send a `models` fallback array, automatic routing names, provider plugins or implicit server tools. OpenRouter documents that unsupported parameters can otherwise be ignored and provider fallback defaults to enabled. These settings intentionally narrow that behavior. They do not pin one upstream host across separate requests; record the actual upstream provider per attempt when reported, otherwise record `unknown`. No baseline zero-data-retention guarantee is claimed. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

Maintain capabilities per model and qualified route. The current Terra catalog does not advertise `temperature`, `top_p` or `parallel_tool_calls`; omit them instead of copying another profile's settings. Serialize application tool execution where required without assuming that parameter is available. Reject required unsupported capabilities before dispatch. JSON requests use the qualified `response_format.json_schema` shape and independent final validation. [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

Preserve opaque provider reasoning metadata needed for tool continuation as access-controlled protocol state, with the original ordering and content where the pinned SDK passes it on. Terra's encrypted `id` is removed by that SDK, a stated limit by [Decision 0013](docs/engineering/decisions/0013-release-closure.md). Do not display it as private thoughts or put it in ordinary activity logs. Present concise decision summaries and evidence instead. [Reasoning continuation requirements](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## MP-03. Configuration precedence

Resolve `OPENROUTER_API_KEY` server-side. Native Mac application processes share an absolute `AUTOBOTS_CONFIG_ROOT`, resolved deployment mode and bootstrap policy. Do not let Python infer a different root from its current directory. The official self-hosted Supabase Compose stack supplies local Postgres/Auth/storage; this contract does not introduce Supabase Cloud or a remote application deployment.

The repository's `.env.example` implementation template must contain an empty server-only entry; the real `.env` is ignored by version control:

```dotenv
# Leave empty to configure OpenRouter through the app; inference needs a key.
OPENROUTER_API_KEY=
```

Do not put a real key in the template or in a `NEXT_PUBLIC_` variable. No key or `.env` file is created by this specification update.

Precedence, first non-whitespace value wins:

1. Existing process environment.
2. `.env.$NODE_ENV.local` in the configuration root.
3. `.env.local`, except in `test` mode.
4. `.env.$NODE_ENV`.
5. `.env`.
6. The authorized workspace’s encrypted app credential.

Use Next.js’s documented environment-file precedence, with the explicit product rule that whitespace-only candidates are absent. The Python bootstrap and every worker must reproduce the same order and normalization before constructing providers. A nonempty but invalid higher-priority credential **blocks** OpenRouter; it must not silently fall through to an app credential. [Next.js environment loading](https://nextjs.org/docs/app/guides/environment-variables).

The installation environment key is usable only by workspaces explicitly authorized for that installation credential. Settings are read-only for that source. Never expose it through `NEXT_PUBLIC_*`, rewrite `.env` from the UI, or return it in a settings response. Environment changes require a coordinated restart of relevant servers/workers. App credential rotations take effect on the next attempt without restart.

## MP-04. Settings flow and states

The settings flow follows [DS-01–DS-05](PRD-Design-System.md): shadcn Luma, dark by default, explicit light/dark preference and semantic component/state tokens. Credential status remains understandable through text and icons in either mode. Appearance changes are local UI preferences; they neither validate credentials nor initiate inference.

**Settings → Models → OpenRouter** displays source, authentication status, catalog availability, permitted models and qualification status separately. Missing credentials never block the local UI, onboarding, files or settings, but **every model call pauses as `credentials_required`**. Open setup from Settings or when the user attempts model-backed work without credentials. If environment-managed, show that status and validation controls without a key field. If missing, show a password input and **Save & validate**. Clear the input after submission; no local/session storage, persisted form state, analytics capture or raw-key response.

The server validates a submitted draft through authenticated `GET https://openrouter.ai/api/v1/key`, an account/key metadata request, plus the public catalog. This is not a model inference or paid completion. [Current-key API](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key).

Commit an authentication-valid draft encrypted, even if the catalog is temporarily unavailable; show the catalog error separately and block new paid inference until fresh metadata exists. An invalid draft must not replace a previously valid stored credential. A key-validation network failure leaves the draft uncommitted and the previous credential unchanged. Do not mislabel temporary validation failure as invalid credentials.

After saving, return to the composer with its draft and pending model selection preserved. **Save & validate never launches a run.** The user selects Run to authorize bounded cloud execution; restoring a draft or reopening the app must not trigger a paid request.

| State | Meaning and behavior |
|---|---|
| `missing` | No effective authorized key; local UI/files/settings remain available, all inference is `credentials_required`. |
| `validating` | Credential authentication check is in flight; prevent duplicate mutation. |
| `configured` | Authentication succeeded; show independent catalog and inference-qualification status. |
| `invalid` | Explicit authentication rejection; block cloud, show source-specific correction. |
| `unavailable` | Key service or credential storage cannot currently be reached; retain last known state and block unverified use. |

Offer **Validate**, **Replace key** and **Disconnect** where applicable. Disconnect removes the workspace app credential and prevents subsequent cloud attempts using it; it neither deletes nor overrides an environment key. Explain that distinction in the UI. Already dispatched requests may finish; cancellation cannot promise to undo provider charges.

## MP-05. Application APIs and authorization

The loopback-only product boundary uses these endpoints. The native Python service exposes corresponding `/v1` paths behind the authenticated Next.js `/api` boundary; equivalent semantics are mandatory in either architecture. Local Supabase Auth supplies application identity; credentials are accessed through the server, never directly by browser Supabase clients.

| Endpoint | Contract |
|---|---|
| `GET /api/settings/model-providers` | Safe source/status, credential reference/version, catalog age and qualification metadata only. |
| `PUT /api/settings/model-providers/openrouter/credential` | Transient draft key plus expected settings version; validate, encrypt and commit atomically. |
| `DELETE /api/settings/model-providers/openrouter/credential` | Disconnect app credential with concurrency check; do not alter environment configuration. |
| `POST /api/settings/model-providers/openrouter/validate` | Revalidate effective credential and metadata; no inference. |
| `GET /api/models` | Authorized profiles, canonical/request identities, availability and capabilities; no provider secrets. |
| `PUT /api/settings/model-policy` | Versioned workspace-default or advanced role-policy update. |

Credential/policy mutations require workspace owner/admin authority, authenticated session, Host/Origin validation, CSRF protection, scope checks and optimistic version checks; stale writes return conflict. Cross-workspace credential IDs must fail authorization. MVP permits `http://127.0.0.1:3000` with same-origin server endpoints and strict loopback binding; no LAN exposure. Secret input is transient. Any future non-loopback exposure requires TLS and is outside scope; OpenRouter traffic always uses HTTPS. Enforce request-size limits and body/header redaction; errors never echo upstream request dumps.

## MP-06. Secret storage and durable execution

Store `ProviderCredential` in local Supabase Postgres as `app_private.provider_credentials`, encrypted using AES-256-GCM, a unique nonce per encryption and authenticated associated data containing workspace, provider, credential ID and version. Persist ciphertext, nonce, tag, key-version reference, timestamps and status; omit plaintext. Use maintained cryptographic libraries and reject authentication failures. Access this private schema through direct server SQL with least-privilege database roles; exclude it from PostgREST exposure and Realtime publications, and deny browser/anonymous/authenticated client roles. Never send the Supabase server/service key to a browser or agent.

The Mac bootstrap generates a cryptographically random **32-byte master key** once at `~/Library/Application Support/Autobots/secrets/provider-master.key`, outside the repository and agent workspace. Its parent is `0700`, file `0600`; create exclusively and never overwrite an existing key. Configure the shared absolute host location through `AUTOBOTS_PROVIDER_MASTER_KEY_FILE` for native Next.js, Python and workers. Keep the key separate from Supabase's database volume and application sandbox. Remote/distributed deployment and cloud secret storage are outside this Mac-only scope.

If encrypted rows exist and the master key is missing, do not generate a replacement; report unavailable storage. Missing permissions/key access disables secret writes and affected reads, never plaintext fallback. Backup/restore procedures must preserve the encryption key separately from database ciphertext. Agent tools cannot read the key directory, environment files, credential tables or runtime process environments.

Durable runs/checkpoints contain credential references and source scope, not secrets or provider-client instances. At each attempt, resolve the current authorized credential version, decrypt transiently and construct the client inside the execution boundary. Record the version used in the attempt audit. Rotation may affect the next attempt; it does not rewrite a run’s provider/model policy. Workflow/LangGraph replay must never serialize a key or reuse a stale captured client.

## MP-07. Disclosure, resources and spend

Every run-creation screen shows selected OpenRouter models/roles, budget and external payload categories: selected instructions, conversation/context excerpts, retrieved material, tool outputs and required protocol metadata. App records remain local; selected inference payloads necessarily leave the Mac. Apply workspace data-scope restrictions before request assembly. Starting a bounded run authorizes its model calls without per-iteration confirmation. Existing approvals for tool effects remain unchanged.

Initial limits are **8K total context**, **512 maximum output tokens per call** and **two OpenRouter inference slots**. These are configurable initial application budgets, not physical model capacities or local GPU constraints. A user may revise context/output allowances within qualified model limits and the displayed spending budget; snapshot that revision and never silently increase allowances after truncation. Calls inherit root task loop, tool, child and active-time limits. Reasoning allocations fit the qualified output budget; mandatory-reasoning models have no reasoning-off control, and reasoning-related truncation remains incomplete.

Default cloud caps are **US$1 per run** and **US$5 per workspace UTC day**, configurable by authorized administrators. Reserve worst-known input/output cost, including billable reasoning and supported per-request charges, under a database lock before dispatch. Keep the local ledger in private `app_private` tables with direct server access, excluded from PostgREST and Realtime. Count every attempt and descendant against root/workspace budgets. Reserve conservatively across eligible route prices; unavailable or unbounded pricing blocks new paid calls.

Warn at 80%; pause at 100%, including committed spend plus outstanding reservations. Settle against reported usage/cost when available, retain unresolved reservations after ambiguous failures and reconcile rather than inventing a charge. Display estimates separately from reported charges. These are application admission controls, not a guarantee against every OpenRouter billing overrun or a substitute for provider account limits. No actual cloud token charges were measured in this research.

## MP-08. Failure and recovery

| Condition | Required handling |
|---|---|
| Missing effective key | Pause all model calls as `credentials_required`; preserve drafts and local app access. |
| `401` | Mark effective credential invalid; stop cloud attempts, no alternate-source fallback. |
| `402` | Report insufficient credits; pause, preserve work, no model substitution. |
| `429` | At most two retries, respecting `Retry-After`, root deadline and reserved budget. |
| `5xx` or network failure before accepted output | At most two bounded retries when classified safe; record each attempt. |
| Partial SSE or uncertain acceptance | Persist attempt status and accumulated output; no automatic redispatch until classified/reconciled. |
| Catalog drift/missing model | `model_unavailable`; require explicit correction. |
| Incomplete/invalid tool arguments | Do not execute; record a bounded repair or failure under run policy. |

Retries never bypass budgets or change the selected model. Streamed prefixes are progress, not executable arguments or committed results. Parse and validate completed tool calls, enforce permissions/approvals, and use operation receipts to prevent duplicate effects. A model retry does not establish that a tool failed to execute. Cancellation stops new admission and reports uncertainty for already dispatched model/tool work.

## MP-09. Acceptance evidence

These gates are implementation requirements, not completed tests:

| ID | Required evidence |
|---|---|
| MP-A01 | Environment-only configuration works; source precedence matches Next.js/Python/workers, including whitespace and test-mode rules. |
| MP-A02 | Missing-key UI saves a valid key, persists after reopening, rotates without restart and disconnects only the app credential. |
| MP-A03 | Invalid nonempty environment key blocks app fallback; an invalid draft preserves the prior valid app key. |
| MP-A04 | Key authentication succeeds independently of inference; catalog outage preserves an authenticated save but blocks stale-catalog dispatch. |
| MP-A05 | Canonical drift, missing IDs and batch/moving substitutions fail before any paid request. |
| MP-A06 | Tools, strict schemas, SSE, cancellations, truncation and tool-result continuation pass on each enabled route; arithmetic and negative task fixtures remain separate quality gates. |
| MP-A07 | Named tool selection uses a two-tool counterexample with conflicting prompt preference; a single matching call cannot prove enforcement. Unsupported selectors fail honestly. |
| MP-A08 | All model calls use the approved OpenRouter boundary; no local inference/embedding endpoint or model fallback exists. All 14 defaults resolve to Terra and freeze in the snapshotted map. In this release a run dispatches through one route, its `executor` binding, and a summarizer that differs pauses it with `route_not_bound` ([Decision 0009](docs/engineering/decisions/0009-release-scope-from-blocking-findings.md)). |
| MP-A09 | Concurrent admission, retry, child execution and UTC rollover cannot bypass reservations/caps; ambiguous billing stays explicit. |
| MP-A10 | Restart/replay retains references and receipts without secrets/client serialization; rotation versions remain auditable. |
| MP-A11 | Browser/network/log/checkpoint/export inspection finds no stored raw keys; workspace/CSRF/version attacks fail; master-key loss never creates plaintext storage. |
| MP-A12 | Missing credentials preserve local UI/files/settings but pause every model call. Local Supabase data volumes survive restart; private credentials are inaccessible through PostgREST, Realtime and browser roles. |

Use mocked adapters for deterministic credential/error/replay tests and a separately authorized, bounded paid qualification for actual provider behavior. Metadata flags or successful authentication cannot replace that evidence. Retain the Qwen named-choice fallback and arithmetic failure as regression fixtures, not passing capability claims.

## MP-10. Closure and implementation handoff

| Decision | Requirement status | Remaining gate |
|---|---|---|
| OpenRouter only; Terra default, DeepSeek not offered for new runs until qualified | Closed | Implement and test all 14 role bindings/inheritance. |
| Canonical mapping and no fallback | Closed | Fresh-catalog preflight and drift tests. |
| Environment-first/in-app credential setup | Closed | UI, authorization, encryption and restart/rotation tests. |
| Budget, disclosure and error policy | Closed | Reservation concurrency, replay and failure tests. |
| Mac-only app/data; local Supabase Docker | Closed | Apply deployment contract, private-schema isolation and local backup/restart tests. |
| Cloud runtime/task capability | Qualification pending | Bounded paid protocol and task evaluations. |
| Application delivery | Not implemented | Build the selected companion architecture and pass its release gates. |

The requirements are ready for implementation. Neither credentials, a configured cloud provider nor passing paid inference is claimed to exist because this PRD is finalized.
