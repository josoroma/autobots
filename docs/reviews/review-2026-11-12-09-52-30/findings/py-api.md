# Python: HTTP API

The HTTP layer has 21 files, 3,206 lines and 80 routes in 14 routers, and its skeleton is sound. create_app stays pure for offline OpenAPI generation: it opens nothing, test_app_factory proves this with sockets blocked, and contracts/export.py builds the schema from it. The pool lives in the lifespan. Authentication fails closed. One error envelope never echoes input. Every schema route has a stable operation_id and a response model, and an AST test bans background work in requests. Where an application service exists (workflows, routines, Experts), handlers are thin. The friction sits where no such service exists. run_routes.py and settings_routes.py hold 11 of the 13 SQL statements found in route modules, including the versioned model-policy writes and the model-call reconciliation transaction. post_run (101 lines, complexity 12) assembles the gate for paid work inline. Shared plumbing is copied or in the wrong place: 10 copies of _pool, and the auth dependencies that 73 routes use live in settings_routes, with four ways of resolving the workspace. Error translation is spread over 54 per-module mappings keyed on code strings. app.state and the database handles are untyped (Any). Handlers read os.environ on every request, and five handlers hold two of the pool's five connections at once. The published OpenAPI documents a 422 body the server never sends and no ErrorResponse at all. In-process tests are strong at the boundary but reach only 8 of the 80 operations. [Back to the review](../README.md)

Area `py-api`, revision `d0d85d3863b996e7cfbdb564d6670a7f0c9c8685`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Passes the project's ruff and mypy strict, and every schema route has an operation_id and a response model. However, DH-06's rule that domain decisions stay independent of HTTP is broken in the run and settings routes, and nothing enforces against 7 suppressions, 16 Any signatures or 78 redundant response_model arguments. |
| modules | 3 | One router per feature, composed by a pure factory. But 15 imports between route modules make settings_routes the hub for the authorization of 73 routes, and a Postgres adapter sits inside api/. |
| size | 3 | Most modules are small, but four files exceed 300 lines (486, 417, 380 and 331), post_run (101 lines) and get_local_status (83) dominate, and 17 functions (16 handlers and the _command helper) take six or more parameters. |
| functions | 3 | Most handlers make one application call and map one refusal. post_run, preview_run, post_reconcile, check_run_intent and get_local_status mix validation, SQL, rules and DTO assembly. |
| structure | 3 | The layout follows DH-03's api package, but routes.py and settings_routes.py no longer say what they own, and shared request plumbing has no module of its own. |
| approach | 3 | Idiomatic FastAPI: Annotated dependencies, a lifespan-owned pool, exception handlers and SSE authorized before the first byte. It is undercut by SQL in handlers, an untyped app.state, environment reads per request and split connection ownership. |
| comments | 4 | Every module docstring states its invariant, and comments explain why with story and decision IDs. Two docstrings are stale, and 24% of public functions have docstrings. |
| types | 3 | Pydantic contracts and bounded parameters at the edge. But pools and connections are Any, handlers map dict rows, 7 suppressions sit at DTO construction, and the OpenAPI misdescribes every error body. |
| errors | 3 | One safe envelope that never echoes input or leaks detail. But mapping is spread over 54 per-module translations keyed on code strings, with inconsistent wording. |
| tests | 3 | Strong boundary tests: forged tokens, host, factory purity with sockets blocked, the background-work ban. But only 8 of 80 operations run in-process, and several refusal branches have no test anywhere. |
| maintainability | 3 | Safe and well explained, but the route layer has absorbed use-case logic and duplicated plumbing, so admission and settings changes are slower and riskier than they need to be. |

## Strengths

- **A pure factory with lifespan-owned resources, proven offline.** [services/agent/src/autobots/api/app.py:41-92](../../../../services/agent/src/autobots/api/app.py#L41) builds the app without I/O and opens the pool only in the lifespan (49-62). [contracts/export.py:22-30](../../../../services/agent/src/autobots/contracts/export.py#L22) generates OpenAPI from create_app(). [services/agent/tests/test_app_factory.py:10-102](../../../../services/agent/tests/test_app_factory.py#L10) blocks sockets and pins the set of paths, and [test_api.py:156-180](../../../../services/agent/tests/test_api.py#L156) shows the pool opens and closes with the lifespan.
- **One safe error envelope with fixed text.** [services/agent/src/autobots/api/errors.py:19-40](../../../../services/agent/src/autobots/api/errors.py#L19) returns ErrorResponse with server-chosen messages, never echoes rejected input (line 31) and exposes nothing on unexpected errors ([test_api.py:124-129](../../../../services/agent/tests/test_api.py#L124), 137-154). [settings_routes.py:91-92](../../../../services/agent/src/autobots/api/settings_routes.py#L91) documents why the messages are fixed.
- **Authentication fails closed at the edge.** [security.py:20-30](../../../../services/agent/src/autobots/api/security.py#L20) makes deny-all the default membership. Lines 38-45 compare the internal token in constant time, and lines 48-67 accept only HS256 with exp, sub and aud required. settings.py:12 makes empty secrets fail closed. [test_api.py:54-92](../../../../services/agent/tests/test_api.py#L54) covers wrong-secret, wrong-audience, expired, none-algorithm and no-expiry tokens.
- **Requests never own long-running work, and a test enforces it.** [routes.py:1](../../../../services/agent/src/autobots/api/routes.py#L1) and [run_routes.py:1](../../../../services/agent/src/autobots/api/run_routes.py#L1) state the rule. [test_api.py:201-210](../../../../services/agent/tests/test_api.py#L201) parses every api module and rejects BackgroundTasks, create_task, run_in_executor and threads.
- **Thin handlers where an application service exists.** [workflow_routes.py:223-299](../../../../services/agent/src/autobots/api/workflow_routes.py#L223), [routine_routes.py:54-131](../../../../services/agent/src/autobots/api/routine_routes.py#L54) and [expert_routes.py:95-101](../../../../services/agent/src/autobots/api/expert_routes.py#L95) each make one dependency-checked call and one refusal mapping, and the application owns the SQL. This is the target shape for the run and settings routes.
- **A stable, explicit contract surface.** All 78 schema routes declare an operation_id and a response model (for example [run_routes.py:170-176](../../../../services/agent/src/autobots/api/run_routes.py#L170)). The 18 create-and-command mutations, admission among them, require a bounded Idempotency-Key header ([run_routes.py:63](../../../../services/agent/src/autobots/api/run_routes.py#L63)), settings writes carry an expected version instead, and admission answers 202 as Option B asks.
- **Streams authorize before the first byte and re-validate live frames.** [event_routes.py:226-241](../../../../services/agent/src/autobots/api/event_routes.py#L226) refuses with a status, not an empty stream. _live_frame (145-170) re-validates NOTIFY payloads as the typed ResultTextDelta and never moves the replay cursor, and _frames closes the listener in finally (173-182).
- **Docstrings and comments state invariants and cite sources.** Module docstrings such as [event_routes.py:1](../../../../services/agent/src/autobots/api/event_routes.py#L1), [artifact_routes.py:1](../../../../services/agent/src/autobots/api/artifact_routes.py#L1) and [operation_routes.py:1](../../../../services/agent/src/autobots/api/operation_routes.py#L1), and comments such as [run_routes.py:215](../../../../services/agent/src/autobots/api/run_routes.py#L215), [run_routes.py:249](../../../../services/agent/src/autobots/api/run_routes.py#L249) and [approval_routes.py:85](../../../../services/agent/src/autobots/api/approval_routes.py#L85), explain why, with story and decision IDs.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PAPI-01](#papi-01) | high | approach | Route handlers own SQL, transactions and use-case rules | M | high |
| [PAPI-02](#papi-02) | high | functions | post_run packs nine admission concerns into one 101-line handler | M | high |
| [PAPI-03](#papi-03) | high | types | The OpenAPI document misdescribes every error response | S | high |
| [PAPI-04](#papi-04) | medium | duplication | The gate for model-backed work is rebuilt in five handlers | M | high |
| [PAPI-05](#papi-05) | medium | errors | Error translation is per module and keyed on code strings | M | medium |
| [PAPI-06](#papi-06) | medium | modules | Shared request dependencies live in feature route modules | S | medium |
| [PAPI-07](#papi-07) | medium | duplication | Request plumbing is copied into each route module | S | low |
| [PAPI-08](#papi-08) | medium | types | app.state is an untyped bag, and the pool and connections are Any | M | medium |
| [PAPI-09](#papi-09) | medium | types | Seven type-check suppressions where application results return plain str | S | low |
| [PAPI-10](#papi-10) | medium | approach | Handlers read configuration from os.environ on every request | S | low |
| [PAPI-11](#papi-11) | medium | approach | Connection ownership is split between dependencies, handlers and streams | M | medium |
| [PAPI-12](#papi-12) | medium | size | run_routes.py and settings_routes.py each bundle several features | M | low |
| [PAPI-13](#papi-13) | medium | size | get_local_status computes, authorizes, queries and maps in 83 lines | S | low |
| [PAPI-15](#papi-15) | medium | tests | In-process tests reach 8 of 80 operations | M | low |
| [PAPI-14](#papi-14) | low | types | get_approvals maps untyped rows field by field in the handler | S | low |
| [PAPI-16](#papi-16) | low | duplication | The session token is decoded twice with separate settings | S | medium |
| [PAPI-17](#papi-17) | low | comments | Two docstrings describe an earlier state of the code | S | low |
| [PAPI-18](#papi-18) | low | functions | check_run_intent keeps branches its own dependency makes unreachable | S | low |
| [PAPI-19](#papi-19) | low | standards | Every route states its response type twice, and FastAPI rules are not enforced | S | low |
| [PAPI-20](#papi-20) | low | naming | One dependency goes by several names, and two different things are called Settings | S | low |
| [PAPI-21](#papi-21) | low | duplication | Domain facts are restated as literals in run_routes.py | S | low |

### <a id="papi-01"></a>PAPI-01: Route handlers own SQL, transactions and use-case rules

- **Severity** high · **Dimension** approach · **Effort** M · **Risk** high · **Occurrences** 13
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:305-345](../../../../services/agent/src/autobots/api/settings_routes.py#L305): put_model_policy: version check, row lock and upsert in the handler
  - [services/agent/src/autobots/api/settings_routes.py:348-379](../../../../services/agent/src/autobots/api/settings_routes.py#L348): reset_model_policy_overrides repeats lock, check and upsert
  - [services/agent/src/autobots/api/run_routes.py:433-474](../../../../services/agent/src/autobots/api/run_routes.py#L433): post_reconcile: receipt lookup, FOR UPDATE select and reconcile in one handler transaction
  - [services/agent/src/autobots/api/run_routes.py:120-144](../../../../services/agent/src/autobots/api/run_routes.py#L120): preview_run queries model_policies and expert_versions directly
  - [services/agent/src/autobots/api/run_routes.py:291-296](../../../../services/agent/src/autobots/api/run_routes.py#L291): _require_run existence query in the route module
  - [services/agent/src/autobots/api/run_routes.py:377-392](../../../../services/agent/src/autobots/api/run_routes.py#L377): post_resume orders the recovery preconditions in the handler
  - [services/agent/src/autobots/api/event_routes.py:197-199](../../../../services/agent/src/autobots/api/event_routes.py#L197): run status query inside the stream loop
  - [services/agent/src/autobots/api/improvement_routes.py:99-114](../../../../services/agent/src/autobots/api/improvement_routes.py#L99): policy read, resolve and offered check in post_replay
- **Evidence:** Counted with grep: route modules hold 13 SQL statements and 3 transactions. That excludes the LISTEN at event_routes.py:139 and the adapter membership.py. They split as run_routes.py 5, settings_routes.py 6, improvement_routes.py 1 and event_routes.py 1. The whole versioned model-policy write path is in handlers:
    async with pool.connection() as connection, connection.transaction():
        cursor = await connection.execute("select version from app_private.model_policies where workspace_id = %s for update", ...)
        if current != body.expected_version:
            raise ApiError(409, "stale_version", ...)
        await connection.execute("insert into app_private.model_policies ... on conflict (workspace_id) do update ...")
- **Why it matters:** The model-policy table is read or written from 9 places in api/ and 3 in application/, so a column or rule change means editing HTTP code. No other entry point (worker, cronjob tool, script) can reuse the versioned write or the idempotent reconciliation without going through HTTP. These statements run only through HTTP, in browser specs and qualification scripts. They never run in the fast profile, because the tests/db checks call application functions directly.
- **Recommendation:** Move each statement into the application module that owns the table, and leave handlers to parse, authorize, call one function and map refusals. The model-policy read, save and reset, with the expected-version check and the row lock, go to a new application/model_policy.py that raises a typed stale-version refusal. The reconciliation flow (receipt, FOR UPDATE, reconcile, store_receipt) goes to application/reconciliation.py. The run existence and status reads go to application/runs.py and run_projection.py, and the preview's Expert lookup goes to application/experts.py. Add in-process tests for the moved functions before moving them, and keep the db and operations profiles as the proof.
- **Rule check:** DH-06 'Keep domain decisions independent of HTTP' and the Python rule's layer separation. The optimistic version check, the FOR UPDATE lock and the operation receipt move unchanged, so no guardrail is weakened. SQL stays the schema owner, and no migration is involved.
- **Verification:** confirmed. 13 statements and 3 transactions recounted with grep (run_routes 5, settings_routes 6, improvement_routes 1, event_routes 1); model_policies appears 9 times in api/ and 3 in application/.

```text
application/model_policy.py: read_policy(conn, ws) -> StoredPolicy; save_policy(conn, ws, expected_version, default, overrides) -> StoredPolicy; reset_overrides(conn, ws, expected_version) -> StoredPolicy; workspace_role_policy(conn, ws, *, run_overrides=None, run_profile=None) -> RolePolicy
application/reconciliation.py: reconcile_oldest_uncertain_call(conn, *, workspace_id, actor_id, run_id, idempotency_key, charged_micro_usd) -> int
application/runs.py: require_run(conn, ws, run_id) (raises RunNotFound); run_projection.run_status(conn, run_id) -> RunStatus | None
application/experts.py: latest_config(conn, ws, expert_id) -> ExpertConfig
api/settings_routes.put_model_policy: validate body -> save_policy -> _policy_state (about 12 lines)
```

### <a id="papi-02"></a>PAPI-02: post_run packs nine admission concerns into one 101-line handler

- **Severity** high · **Dimension** functions · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:177-277](../../../../services/agent/src/autobots/api/run_routes.py#L177): 101 lines, C901 12, 6 parameters, no docstring
  - [services/agent/src/autobots/api/run_routes.py:185-197](../../../../services/agent/src/autobots/api/run_routes.py#L185): request-shape and budget-versus-limit rules on their own connection
  - [services/agent/src/autobots/api/run_routes.py:198-200](../../../../services/agent/src/autobots/api/run_routes.py#L198): key readiness gate
  - [services/agent/src/autobots/api/run_routes.py:209-239](../../../../services/agent/src/autobots/api/run_routes.py#L209): owner-only version pin, binding resolution, tool availability from os.environ
  - [services/agent/src/autobots/api/run_routes.py:240-251](../../../../services/agent/src/autobots/api/run_routes.py#L240): policy resolution and offered check, 422 versus 409
  - [services/agent/src/autobots/api/run_routes.py:252-277](../../../../services/agent/src/autobots/api/run_routes.py#L252): admission, conflict mapping, type-ignored DTO
- **Evidence:** The checks run in this order:
  1. Session and Expert shape (185-186).
  2. Budget xor limit, plus the daily cap on its own connection (187-197).
  3. Key readiness (198-200).
  4. Workspace policy read with raw SQL (201-208).
  5. Owner-only version pin through request.app.state.membership (211-216).
  6. Expert binding, with ExpertRefused mapped by code suffix (217-227).
  7. Tool availability against os.environ (228-239).
  8. Offered profiles (240-251).
  9. Admission and conflict mapping (252-270).

  Finally it builds RunAccepted with a type: ignore (275).
- **Why it matters:** This is the gate for paid work and an authorization point, yet no in-process test reaches POST /v1/runs, and the session_required branch appears in no test anywhere. Every new admission rule lands mid-function, and which refusal wins depends on implicit ordering.
- **Recommendation:** Extract an admission use case in the application layer. It takes a plain input dataclass and returns the admission result or raises a typed refusal. The handler only gathers dependencies (role, provider settings, environment), calls it and maps refusals. Before moving any code, test the use case branch by branch with fakes in the fast profile.
- **Rule check:** DH-06 'Keep HTTP admission separate from durable execution': admission stays in the request and still only records intent. The Decision 0011 owner-only pin and the PK-02 tool refusal move with their comments, and server idempotency stays the duplicate-submit mechanism.
- **Verification:** confirmed. 101 lines, C901 12, six parameters and the nine-step order confirmed, and session_required appears in no test; plan it with PAPI-01 and PAPI-04, which share the admission gate.

```text
application/run_admission.py
  @dataclass(frozen=True) AdmissionInput(goal_text, limit, budget, session_id, expert_id, expert_version, run_profile, criteria, artifacts, documents, continues_run_id)
  async def admit_from_request(conn, gate, *, workspace_id, user_id, role, key, data) -> AdmissionResult
    _choose_limit(data, remaining) -> int            # budget xor limit, require_budget
    _expert_binding(conn, workspace_id, data, role)  # owner-only pin, resolve_binding, require_available
    _policy(conn, workspace_id, binding, data)       # workspace_role_policy + require_offered
  raises AdmissionRefused(code, kind)
api/run_routes.post_run (about 20 lines): role = await membership.role_in(...); result = await admit_from_request(...); return RunAccepted(...)
```

### <a id="papi-03"></a>PAPI-03: The OpenAPI document misdescribes every error response

- **Severity** high · **Dimension** types · **Effort** S · **Risk** high · **Occurrences** 78
- **Where:**
  - [services/agent/src/autobots/api/errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29): every validation failure returns ErrorResponse {code, message}
  - [services/agent/src/autobots/api/app.py:78-91](../../../../services/agent/src/autobots/api/app.py#L78): routers included with no responses= declaration
  - [services/agent/src/autobots/api/security.py:44-45](../../../../services/agent/src/autobots/api/security.py#L44): 401 on every route, undeclared
  - [services/agent/src/autobots/api/run_routes.py:170-176](../../../../services/agent/src/autobots/api/run_routes.py#L170): admitRun declares only 202 yet raises 403, 404, 409, 422 and 503
  - [services/agent/src/autobots/contracts/export.py:22-30](../../../../services/agent/src/autobots/contracts/export.py#L22): ErrorResponse added as a loose component that no operation references
- **Evidence:** Read from contracts/generated/openapi.json with a python3.12 -I script: all 78 operations document 422 as #/components/schemas/HTTPValidationError ({detail: [...]}), and none references ErrorResponse. Yet errors.py:29-32 answers every validation failure with ErrorResponse, and handlers raise ApiError with 401, 403, 404, 409 and 503, which no operation declares. The generated client exports parseHTTPValidationError for a body the server never sends, and its generated parseErrorResponse is unused by the web.
- **Why it matters:** Option B SP-009 makes the generated OpenAPI the public schema source, but error bodies are outside it. The BFF and the screens therefore parse code by hand, and a renamed field or error shape would never show up as contract drift. The published 422 shape is wrong for all 78 operations.
- **Recommendation:** Declare the real error envelope once. Pass a shared ERROR_RESPONSES mapping (401, 403, 404, 409, 422 and 503 to ErrorResponse) to include_router in create_app. Declaring 422 also stops FastAPI from emitting its default validation schema. Then regenerate contracts/generated and the TypeScript client with the generator and let consumers use the generated parser. Runtime behavior does not change. Narrowing per-route error codes can come later.
- **Rule check:** contracts.md and DH-06: Pydantic/OpenAPI owns the public API and generated TypeScript consumes it. The generated files are regenerated, never hand-edited. Codes and messages stay the fixed server text that errors.py requires.
- **Verification:** confirmed. Generated openapi.json read: 78 operations all document 422 as HTTPValidationError and none references ErrorResponse; parseErrorResponse and parseHTTPValidationError are unused outside generated.ts.

```text
# api/errors.py
ERROR_RESPONSES = {status: {"model": ErrorResponse, "description": text} for status, text in ((401, "Not authorized"), (403, "Forbidden"), (404, "Not available"), (409, "Conflict"), (422, "Invalid request"), (503, "Unavailable"))}
# api/app.py
for item in ROUTERS: app.include_router(item, responses=ERROR_RESPONSES)
# regenerate contracts/generated/openapi.json and packages/api-client/src/generated.ts with the generator
```

### <a id="papi-04"></a>PAPI-04: The gate for model-backed work is rebuilt in five handlers

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** high · **Occurrences** 13
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:198-200](../../../../services/agent/src/autobots/api/run_routes.py#L198): key gate, first wording
  - [services/agent/src/autobots/api/run_routes.py:374-376](../../../../services/agent/src/autobots/api/run_routes.py#L374): same gate on resume
  - [services/agent/src/autobots/api/improvement_routes.py:96-114](../../../../services/agent/src/autobots/api/improvement_routes.py#L96): gate, policy select, resolve, offered check, second wording
  - [services/agent/src/autobots/api/workflow_routes.py:352-365](../../../../services/agent/src/autobots/api/workflow_routes.py#L352): budget check and gate, third wording
  - [services/agent/src/autobots/api/settings_routes.py:389-407](../../../../services/agent/src/autobots/api/settings_routes.py#L389): gate, policy select, resolve and offered check, returned as a code
  - [services/agent/src/autobots/api/run_routes.py:201-208](../../../../services/agent/src/autobots/api/run_routes.py#L201): policy select in admission
  - [services/agent/src/autobots/api/run_routes.py:121-127](../../../../services/agent/src/autobots/api/run_routes.py#L121): policy select in preview
  - [services/agent/src/autobots/api/workflow_routes.py:10](../../../../services/agent/src/autobots/api/workflow_routes.py#L10): imports budget_error from run_routes
- **Evidence:** Counted with grep, 13 sites in four groups:
  - 4 handlers call settings.run_intent(...) and then raise ApiError(409, code, ...) when the code is not ready, using 3 different messages.
  - 4 handlers select default_profile and role_overrides from app_private.model_policies, then call resolve_role_policy(workspace_default=row[0] if row else None, ...). application/ has 3 more copies of this read.
  - 3 handlers call require_offered(policy.bindings.values()).
  - 2 handlers call require_budget against remaining_daily_micro_usd, sharing budget_error across route modules.
- **Why it matters:** Whether paid work may start is one product rule, but each entry point applies its own subset of the checks, with its own status and wording. Resume skips the offered check, and workflows check the key only when a step needs a model. A change to readiness or to the offered profiles must be repeated consistently in five handlers and three application modules.
- **Recommendation:** Name the gate in the application layer, with one function per deliberate variant, and call it from the handlers: workspace_role_policy, require_model_ready, an offered-policy check and chosen_limit. Make the deliberate differences explicit parameters, not missing lines. Move budget_error to the shared error module.
- **Rule check:** DH-06 'Avoid ... duplicated business rules'. The worker still re-checks key readiness before dispatch (run_routes.py:373), and refusal codes stay the same, so the browser specs that assert them keep passing.
- **Verification:** confirmed. Four raise sites with three messages, four policy selects (plus three in application/), three require_offered calls and two budget checks recounted: 13 sites.

```text
application/model_gate.py: require_model_ready(settings, ws) -> None (raises GateRefused(code)); workspace_role_policy(conn, ws, *, run_overrides=None, run_profile=None, require_offered=True) -> RolePolicy; chosen_limit(conn, ws, budget) -> int (raises BudgetRefused)
```

### <a id="papi-05"></a>PAPI-05: Error translation is per module and keyed on code strings

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 54
- **Where:**
  - [services/agent/src/autobots/api/errors.py:24-40](../../../../services/agent/src/autobots/api/errors.py#L24): only the generic handlers are central
  - [services/agent/src/autobots/api/run_routes.py:73-90](../../../../services/agent/src/autobots/api/run_routes.py#L73): as_api_error returns an ApiError or re-raises (line 90)
  - [services/agent/src/autobots/api/settings_routes.py:91-117](../../../../services/agent/src/autobots/api/settings_routes.py#L91): a second as_api_error, plus a HANDLED tuple so callers avoid its re-raise
  - [services/agent/src/autobots/api/workflow_routes.py:82-96](../../../../services/agent/src/autobots/api/workflow_routes.py#L82): seven returns chained on code strings; getattr for a typed field
  - [services/agent/src/autobots/api/improvement_routes.py:42-44](../../../../services/agent/src/autobots/api/improvement_routes.py#L42): 404 when the code ends with not_found
  - [services/agent/src/autobots/api/run_routes.py:226](../../../../services/agent/src/autobots/api/run_routes.py#L226): same suffix rule inline
  - [services/agent/src/autobots/api/memory_routes.py:58-59](../../../../services/agent/src/autobots/api/memory_routes.py#L58): any MemoryRefused becomes the Expert-not-found message
  - [services/agent/src/autobots/api/approval_routes.py:156-159](../../../../services/agent/src/autobots/api/approval_routes.py#L156): a third wording for IdempotencyConflict
- **Evidence:** Counted with grep: 54 `raise ... from None` translations across 10 route modules. IdempotencyConflict is mapped in 6 places with 3 wordings. Four places choose 404 over 409 with error.code.endswith("not_found"), and four more compare codes for equality. Two functions named as_api_error are typed -> ApiError but end with `raise error`, so their callers narrow their except clauses to avoid that path.
- **Why it matters:** Adding a refusal code means finding the right local mapper. A not-found code that does not end in not_found silently becomes 409, and a new MemoryRefused code would be reported as a missing Expert. The same conflict reads differently depending on the route, and none of these mappers has a test.
- **Recommendation:** Make errors.py the one place that turns refusals into responses. Register a handler per refusal type, backed by a table from code to status and fixed message, with route-specific wording only where it is deliberate. Give refusals a typed category (not_found, conflict, invalid, unavailable) instead of inferring it from a code suffix. Handlers then let refusals propagate, which removes most try/except blocks. Cover the table with one parametrized test.
- **Rule check:** DH-06 'centralize error handling ... expose safe typed errors' and Option B's 'stable safe error codes'. Codes and statuses stay as they are, and messages stay fixed server text, so nothing submitted is echoed.
- **Verification:** confirmed. 54 'from None' raises in 10 modules, six IdempotencyConflict mappings with three wordings and four endswith('not_found') checks recounted.

```text
# application/refusals.py (no HTTP)
class Refusal(Exception): code: str; kind: Literal["not_found", "conflict", "invalid", "unavailable"]
# api/errors.py
STATUS = {"not_found": 404, "conflict": 409, "invalid": 422, "unavailable": 503}
MESSAGES: Mapping[str, str] = {"idempotency_conflict": "This key was already used with different content.", ...}
app.add_exception_handler(Refusal, refusal_response)
```

### <a id="papi-06"></a>PAPI-06: Shared request dependencies live in feature route modules

- **Severity** medium · **Dimension** modules · **Effort** S · **Risk** medium · **Occurrences** 15
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:52-85](../../../../services/agent/src/autobots/api/settings_routes.py#L52): current_workspace, require_owner and provider_settings, imported by 12 route modules
  - [services/agent/src/autobots/api/operation_routes.py:100-103](../../../../services/agent/src/autobots/api/operation_routes.py#L100): require_ready, imported by the run and workflow routes
  - [services/agent/src/autobots/api/workflow_routes.py:9-12](../../../../services/agent/src/autobots/api/workflow_routes.py#L9): imports from three other route modules
  - [services/agent/src/autobots/api/security.py:87-95](../../../../services/agent/src/autobots/api/security.py#L87): second workspace check, by path parameter and is_member
  - [services/agent/src/autobots/api/operation_routes.py:288-293](../../../../services/agent/src/autobots/api/operation_routes.py#L288): third: the header or the first workspace
  - [services/agent/src/autobots/api/operation_routes.py:133-135](../../../../services/agent/src/autobots/api/operation_routes.py#L133): calls the dependency by hand and repeats the owner check
  - [services/agent/src/autobots/api/expert_routes.py:138-143](../../../../services/agent/src/autobots/api/expert_routes.py#L138): owner check inline, also run_routes.py:211-216
  - [services/agent/src/autobots/api/membership.py:7-47](../../../../services/agent/src/autobots/api/membership.py#L7): Postgres adapter inside the HTTP package
- **Evidence:** Counted with grep, there are 15 imports between route modules:
  - 12 modules take their workspace, owner or provider dependencies from settings_routes.
  - 2 take require_ready from operation_routes.
  - 1 takes budget_error from run_routes.

  Workspace resolution exists in four forms:
  - require_workspace_member (security.py:87)
  - current_workspace (settings_routes.py:52)
  - get_readiness's first-workspace rule (operation_routes.py:288-293)
  - a manual call to the dependency in get_local_status (operation_routes.py:133)

  Walking the factory's routes shows 73 of 80 routes depend on current_workspace.
- **Why it matters:** The authorization gate for 73 routes sits in a 417-line settings module. Splitting settings or operations therefore touches every router's imports, and readers must look for workspace rules in four places. The three inline owner checks can drift from require_owner's role test and wording.
- **Recommendation:** Create api/dependencies.py for request plumbing: the database pool, current_workspace, require_owner, a named readiness-workspace variant, an optional owner workspace for Operations, provider settings and require_ready. Import it from every router, so route modules import only dependencies and application code. Keep the readiness rule deliberately different, but named and colocated. Move PostgresMembership to adapters/ behind the MembershipStore protocol.
- **Rule check:** DH-03 places adapters under src/autobots/adapters, and DH-06 asks for explicit ownership and narrow interfaces. This is a move with no semantic change: header verification, owner checks and the SH-04/HM-05 readiness rule stay as written. Add the current_workspace tests first.
- **Verification:** confirmed. 15 imports between route modules recounted; a dependency walk of the pure factory confirms 73 of 80 routes depend on current_workspace.

```text
api/dependencies.py: db_pool, current_workspace, readiness_workspace (SH-04), require_owner, optional_owner_workspace, provider_settings, keys_and_vars_settings, require_ready; aliases MemberWorkspace, OwnerWorkspace, CurrentUser, IdempotencyKey, Db
adapters/membership.py: PostgresMembership(pool_provider)
```

### <a id="papi-07"></a>PAPI-07: Request plumbing is copied into each route module

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 24
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:66-70](../../../../services/agent/src/autobots/api/run_routes.py#L66): _pool, one of 10 identical copies
  - [services/agent/src/autobots/api/event_routes.py:48-52](../../../../services/agent/src/autobots/api/event_routes.py#L48): copy
  - [services/agent/src/autobots/api/workflow_routes.py:68-72](../../../../services/agent/src/autobots/api/workflow_routes.py#L68): copy
  - [services/agent/src/autobots/api/routes.py:97-99](../../../../services/agent/src/autobots/api/routes.py#L97): inline 503 check
  - [services/agent/src/autobots/api/settings_routes.py:290-292](../../../../services/agent/src/autobots/api/settings_routes.py#L290): model-policy route says provider settings are unavailable
  - [services/agent/src/autobots/api/search_routes.py:30-32](../../../../services/agent/src/autobots/api/search_routes.py#L30): inline 503 check
  - [services/agent/src/autobots/api/improvement_routes.py:93](../../../../services/agent/src/autobots/api/improvement_routes.py#L93): Idempotency-Key header spelled inline; 5 modules define the same Key alias
  - [services/agent/src/autobots/api/tool_routes.py:28](../../../../services/agent/src/autobots/api/tool_routes.py#L28): Member alias; artifact, event and run routes call the same dependency Workspace
- **Evidence:** Counted with grep:
  - _pool(request) is defined identically in 10 modules.
  - 8 more inline `if pool is None: raise ApiError(503, ...)` checks use 3 different messages.
  - The Idempotency-Key header alias is defined in 5 modules and spelled out once more.
  - 17 module-level aliases in 9 modules redefine Workspace, Member, Owner or User.
- **Why it matters:** Changing the unavailable-database response or the idempotency header bounds means editing up to 18 sites. The copies already disagree: model-policy routes report that provider settings are unavailable.
- **Recommendation:** Export one pool dependency and the shared aliases from api/dependencies.py, delete the local copies, and use one message per condition.
- **Rule check:** none
- **Verification:** revised. 10 _pool copies, 8 inline 503 checks with 3 messages and 6 Idempotency-Key spellings confirmed; the dependency aliases recount to 17, not 22. Shares api/dependencies.py with PAPI-06.

```text
Db = Annotated[Pool, Depends(db_pool)]; IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]; MemberWorkspace, OwnerWorkspace, CurrentUser
```

### <a id="papi-08"></a>PAPI-08: app.state is an untyped bag, and the pool and connections are Any

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 45
- **Where:**
  - [services/agent/src/autobots/api/app.py:30-32](../../../../services/agent/src/autobots/api/app.py#L30): the Pool protocol declares open and close, not connection()
  - [services/agent/src/autobots/api/app.py:72-75](../../../../services/agent/src/autobots/api/app.py#L72): the factory declares four state attributes
  - [services/agent/src/autobots/api/main.py:42-50](../../../../services/agent/src/autobots/api/main.py#L42): entry point replaces membership and adds stream_seconds, object_store and provider_context after the factory
  - [services/agent/src/autobots/api/membership.py:10](../../../../services/agent/src/autobots/api/membership.py#L10): PostgresMembership(state: Any)
  - [services/agent/src/autobots/api/operation_routes.py:77-83](../../../../services/agent/src/autobots/api/operation_routes.py#L77): probe_times created on app.state by a request
  - [services/agent/src/autobots/api/operation_routes.py:162](../../../../services/agent/src/autobots/api/operation_routes.py#L162): nested getattr for the catalog fetcher
  - [services/agent/src/autobots/api/artifact_routes.py:40](../../../../services/agent/src/autobots/api/artifact_routes.py#L40): getattr fallback for object_store
  - [services/agent/src/autobots/api/event_routes.py:173-187](../../../../services/agent/src/autobots/api/event_routes.py#L173): pool: Any and listener: Any through the stream helpers
- **Evidence:** 15 files make 38 direct request.app.state.* accesses, 24 of them for the pool. Another 7 accesses use getattr fallbacks, 5 of them for attributes the factory never declares (stream_seconds, probe_times and object_store three times). ruff ANN401 reports 16 Any signatures in api/, including all 10 `_pool -> Any` copies.
- **Why it matters:** mypy strict cannot check any handler call on the pool, the connections or the membership store, so a renamed method or a missing attribute surfaces as a runtime 500. The getattr fallbacks make 'not configured' and 'misspelled' look the same. Production wiring is split between create_app and main.py, so tests build a different object graph from the one uvicorn runs.
- **Recommendation:** Declare process resources once in an AppResources dataclass. The factory builds it from explicit parameters, stores it once on app.state, and handlers read it through one typed dependency; the lifespan still opens and closes the pool. Give the Pool protocol a typed connection(), and give the membership adapter a pool provider instead of the whole state.
- **Rule check:** The Python rule says schema generation is offline and resources belong in the lifespan. The factory still opens nothing, as test_app_factory.py keeps proving, and the object store and catalog fetchers already open their clients per call.
- **Verification:** revised. 38 direct accesses in 15 files and 16 ANN401 hits confirmed; of the 7 getattr fallbacks, 5 read attributes the factory never declares, since settings and provider_context are declared.

```text
@dataclass class AppResources: settings: Settings; membership: MembershipStore; provider_context: ProviderContext | None = None; object_store: ObjectStore | None = None; stream_seconds: float = 60.0; probe_times: ProbeTimes = field(default_factory=ProbeTimes); pool: Pool | None = None  # set by lifespan
def create_app(resources: AppResources | None = None, *, pool_factory=default_pool) -> FastAPI
def app_resources(request: Request) -> AppResources
class Pool(Protocol): async def open/close; def connection(self) -> AbstractAsyncContextManager[Connection]
```

### <a id="papi-09"></a>PAPI-09: Seven type-check suppressions where application results return plain str

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:275](../../../../services/agent/src/autobots/api/run_routes.py#L275): status=result.status  # type: ignore[arg-type]
  - [services/agent/src/autobots/api/run_routes.py:328](../../../../services/agent/src/autobots/api/run_routes.py#L328): same
  - [services/agent/src/autobots/api/settings_routes.py:415](../../../../services/agent/src/autobots/api/settings_routes.py#L415): code=code  # type: ignore[arg-type]
  - [services/agent/src/autobots/api/search_routes.py:41](../../../../services/agent/src/autobots/api/search_routes.py#L41): kind=hit.kind  # type: ignore[arg-type]
  - [services/agent/src/autobots/api/operation_routes.py:172](../../../../services/agent/src/autobots/api/operation_routes.py#L172): OperationCondition(...)  # type: ignore[arg-type]
  - [services/agent/src/autobots/api/operation_routes.py:180](../../../../services/agent/src/autobots/api/operation_routes.py#L180): openrouter=openrouter  # type: ignore[arg-type]
  - [services/agent/src/autobots/api/routes.py:61](../../../../services/agent/src/autobots/api/routes.py#L61): cast(Literal["owner", "member"], role)
- **Evidence:** The contract fields are typed RunStatus, Literal unions and SearchKind. The values come from application types declared str:
  - AdmissionResult.status (application/runs.py:70)
  - Condition.state (application/operations.py:81), whose comment lists the three allowed values
  - Hit.kind (application/search.py:17)
  - ProviderSettings.run_intent -> str (application/provider_settings.py:231)
  - the role tuple from workspaces_with_roles (application/profiles.py:54)
- **Why it matters:** mypy strict cannot catch a new or misspelled status, condition state, search kind or intent code. Pydantic rejects the value while building the response, and the user gets a 500. The suppressions are undocumented first-party exceptions.
- **Recommendation:** Type the application results with the domain enum or shared Literal aliases: RunStatus, a condition-state alias, the search kinds, an intent-code alias and a workspace-role alias. Alternatively, convert explicitly at the application edge. Then remove the ignores and the cast. Strict mode's warn_unused_ignores will flag any that remain, which acts as the ratchet.
- **Rule check:** DH-06 asks for explicit enums or unions and for narrow, documented typing exceptions. Domain enums and DTOs stay separate types; only the application results gain precise annotations.
- **Verification:** confirmed. Six type: ignore[arg-type] and one cast confirmed against the str-typed application results they adapt.

### <a id="papi-10"></a>PAPI-10: Handlers read configuration from os.environ on every request

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 9
- **Where:**
  - [services/agent/src/autobots/api/operation_routes.py:86-87](../../../../services/agent/src/autobots/api/operation_routes.py#L86): data root from AUTOBOTS_CONFIG_ROOT
  - [services/agent/src/autobots/api/operation_routes.py:95](../../../../services/agent/src/autobots/api/operation_routes.py#L95): int(os.environ.get("AUTOBOTS_MIN_FREE_BYTES", ...)) per request
  - [services/agent/src/autobots/api/operation_routes.py:177-182](../../../../services/agent/src/autobots/api/operation_routes.py#L177): AUTOBOTS_BACKUP_DIR read twice
  - [services/agent/src/autobots/api/run_routes.py:231](../../../../services/agent/src/autobots/api/run_routes.py#L231): tool key sources from the live environment
  - [services/agent/src/autobots/api/settings_routes.py:180](../../../../services/agent/src/autobots/api/settings_routes.py#L180): ToolKeySettings receives os.environ
  - [services/agent/src/autobots/api/tool_routes.py:31-37](../../../../services/agent/src/autobots/api/tool_routes.py#L31): os.environ used as the key map, or returned when the pool is missing
  - [services/agent/src/autobots/api/settings.py:1](../../../../services/agent/src/autobots/api/settings.py#L1): 'read once from the environment by the entry point'
  - [services/agent/src/autobots/api/main.py:31](../../../../services/agent/src/autobots/api/main.py#L31): a startup snapshot, process_environment, already exists
- **Evidence:** Counted with grep, request paths read os.environ 9 times across 5 route modules: operation_routes.py:87, 95, 178 and 182; run_routes.py:231; search_routes.py:34; settings_routes.py:180; tool_routes.py:35 and 37. This count excludes the live tracing check at operation_routes.py:170, which may read the live environment on purpose.
- **Why it matters:** A malformed AUTOBOTS_MIN_FREE_BYTES raises ValueError inside require_ready. Every guarded admission (runs, workflow executions, retention apply) and the local-status page then fail with 500, instead of the process failing at start. Tests have to monkeypatch the process environment. And the process environment has two sources, live os.environ and ProviderContext's snapshot, which can diverge.
- **Recommendation:** Parse data_root, min_free_bytes and backup_dir once in load_settings. Expose a snapshot of the process environment through the resources object, and pass it to key_sources and ToolKeySettings. If the tracing check reads the live environment on purpose, keep it live and say so in a comment.
- **Rule check:** Decisions 0024 K1 and 0025 V3 fix the key order: Settings, then the process environment, then the .env files. The order stays; only how the process environment reaches the handlers changes.
- **Verification:** confirmed. Nine request-path os.environ reads in five modules confirmed; int() of AUTOBOTS_MIN_FREE_BYTES runs inside require_ready on every guarded admission.

```text
@dataclass(frozen=True) class Settings: ...; data_root: Path; min_free_bytes: int; backup_dir: str; process_environment: Mapping[str, str]
```

### <a id="papi-11"></a>PAPI-11: Connection ownership is split between dependencies, handlers and streams

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:79-85](../../../../services/agent/src/autobots/api/settings_routes.py#L79): provider_settings holds a pooled connection for the whole request
  - [services/agent/src/autobots/api/run_routes.py:198-201](../../../../services/agent/src/autobots/api/run_routes.py#L198): post_run opens a second connection while holding it
  - [services/agent/src/autobots/api/run_routes.py:374-377](../../../../services/agent/src/autobots/api/run_routes.py#L374): post_resume, then _command opens another (309)
  - [services/agent/src/autobots/api/improvement_routes.py:96-99](../../../../services/agent/src/autobots/api/improvement_routes.py#L96): post_replay
  - [services/agent/src/autobots/api/workflow_routes.py:351-363](../../../../services/agent/src/autobots/api/workflow_routes.py#L351): post_execution
  - [services/agent/src/autobots/api/settings_routes.py:389-411](../../../../services/agent/src/autobots/api/settings_routes.py#L389): check_run_intent, twice
  - [services/agent/src/autobots/api/app.py:35-38](../../../../services/agent/src/autobots/api/app.py#L35): pool max_size=5
  - [services/agent/src/autobots/api/event_routes.py:130-142](../../../../services/agent/src/autobots/api/event_routes.py#L130): one unpooled LISTEN connection per open stream
- **Evidence:**   async def provider_settings(request: Request) -> AsyncIterator[ProviderSettings]:
        ...
        async with pool.connection() as connection:
            yield ProviderSettings(connection, context)
  Five handlers that take this dependency also call _pool(request).connection() or pool.connection(), so each holds two of the pool's five connections. get_readiness already builds ProviderSettings on its own single connection (operation_routes.py:306-313).
- **Why it matters:** Five concurrent requests to these handlers can each hold one connection and wait for a second until psycopg_pool's default 30-second timeout expires. They then fail with 500, and every other request stalls meanwhile. This comes from reading the code; it was not observed. Streams add one direct database connection each, outside the pool and with no cap.
- **Recommendation:** Give each request a single owner for its connection. The simplest fix is to construct ProviderSettings on the connection the handler opens, as get_readiness does. The alternative is one per-request connection dependency shared by the settings object and the handler; it changes how statements group into transactions, so write tests first. For streams, cap concurrent listeners in the resources object, or move LISTEN to one lifespan-owned connection that fans out to a queue per stream.
- **Rule check:** DH-06: own pools in process lifecycles and bound concurrency. The pool stays lifespan-owned, and no readiness or key check is removed.
- **Verification:** confirmed. Five handlers hold the provider_settings connection while opening a second one, against a pool of five; inferred from code, not observed.

### <a id="papi-12"></a>PAPI-12: run_routes.py and settings_routes.py each bundle several features

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:1-486](../../../../services/agent/src/autobots/api/run_routes.py#L1): 486 lines: preview, admission, reads, commands, reconciliation, labels and messages
  - [services/agent/src/autobots/api/run_routes.py:93-108](../../../../services/agent/src/autobots/api/run_routes.py#L93): budget messages and profile labels
  - [services/agent/src/autobots/api/run_routes.py:396-474](../../../../services/agent/src/autobots/api/run_routes.py#L396): two reconciliation routes
  - [services/agent/src/autobots/api/settings_routes.py:1](../../../../services/agent/src/autobots/api/settings_routes.py#L1): docstring says 'The exact MP-05 routes'
  - [services/agent/src/autobots/api/settings_routes.py:52-117](../../../../services/agent/src/autobots/api/settings_routes.py#L52): shared dependencies and error mapping
  - [services/agent/src/autobots/api/settings_routes.py:174-257](../../../../services/agent/src/autobots/api/settings_routes.py#L174): keys and vars (PK-07)
  - [services/agent/src/autobots/api/settings_routes.py:267-379](../../../../services/agent/src/autobots/api/settings_routes.py#L267): model policy with SQL (MD-02, MD-03)
  - [services/agent/src/autobots/api/settings_routes.py:382-417](../../../../services/agent/src/autobots/api/settings_routes.py#L382): run intent
- **Evidence:** Both files exceed 300 lines (486 and 417). Together they hold 21 of the 80 routes, 11 of the 13 SQL statements in route modules, 8 of the 17 PLR0913 hits, the only C901 hit and 3 of the 6 type ignores in api/.
- **Why it matters:** Changes to unrelated features (keys and vars versus model policy, admission versus reconciliation) collide in the same file, and the settings module's own docstring no longer describes it.
- **Recommendation:** Split by feature once the shared dependencies have moved out. Keep every path and operation_id, so the generated contract stays byte-identical, and prove it with the contract drift check.
- **Rule check:** Option B keeps the exact provider routes, and a file split changes no path or operation_id. DH-06 asks for small, cohesive modules.
- **Verification:** confirmed. 21 routes, 11 SQL statements, 8 PLR0913 hits, the only C901 and 3 of 6 ignores confirmed; workflow_routes.py (380) and operation_routes.py (331) also pass 300 lines but are single-feature.

```text
api/run_routes.py (preview, admit, get); api/run_command_routes.py (input, pause, resume, cancel + _command); api/run_reconcile_routes.py (effect evidence, model-call reconcile); api/provider_routes.py (OpenRouter credential, validate, models); api/keys_and_vars_routes.py; api/model_policy_routes.py (get, put, reset, run intent); api/dependencies.py (shared); budget and profile text from the domain
```

### <a id="papi-13"></a>PAPI-13: get_local_status computes, authorizes, queries and maps in 83 lines

- **Severity** medium · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/api/operation_routes.py:117-199](../../../../services/agent/src/autobots/api/operation_routes.py#L117): 83 lines
  - [services/agent/src/autobots/api/operation_routes.py:124](../../../../services/agent/src/autobots/api/operation_routes.py#L124): 'database up' read from conditions[0] and conditions[1]
  - [services/agent/src/autobots/api/operation_routes.py:133-135](../../../../services/agent/src/autobots/api/operation_routes.py#L133): manual current_workspace call and inline owner check
  - [services/agent/src/autobots/api/operation_routes.py:136-153](../../../../services/agent/src/autobots/api/operation_routes.py#L136): eight reads in one block
  - [services/agent/src/autobots/api/operation_routes.py:166-199](../../../../services/agent/src/autobots/api/operation_routes.py#L166): response assembly
- **Evidence:**   conditions = await _installation_conditions(request)
    database_up = conditions[0].state == "ok" and conditions[1].state == "ok"
    ...
    if database_up:
        workspace_id = await current_workspace(request, user_id, x_autobots_workspace)
        if await request.app.state.membership.role_in(user_id, workspace_id) != "owner":
- **Why it matters:** What 'database up' means depends on the order of a list built elsewhere, the owner rule is re-implemented outside require_owner, and the D5 values cannot be tested without running the whole route.
- **Recommendation:** Split the route into three parts: a dependency that yields the owner's workspace, or None when the database is down; one application read that returns the workspace values as a dataclass; and a pure mapper to LocalStatus. Return named conditions instead of a positional list.
- **Rule check:** The module's own rule stays: it answers with the database down (operation_routes.py:1). Decision 0022 D5's value set is unchanged.
- **Verification:** revised. The handler spans 83 lines (117-199) and makes eight reads in its block, not seven; positional conditions[0] and [1] and the inline owner check confirmed.

```text
api/dependencies.optional_owner_workspace(...) -> UUID | None
application/operations.read_workspace_operations(conn, ws) -> WorkspaceOperations(counts, policy, delayed, qualifications, workers, migrations, storage_used)
InstallationConditions(NamedTuple): database, schema, hold, adapter, storage, disk
_local_status(conditions, ops | None, catalog, disk, probes) -> LocalStatus  # pure
get_local_status: about 15 lines
```

### <a id="papi-15"></a>PAPI-15: In-process tests reach 8 of 80 operations

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/tests/test_api.py:17-51](../../../../services/agent/tests/test_api.py#L17): settings, membership fake, token and client helpers local to this file
  - [services/agent/src/autobots/api/settings_routes.py:63-64](../../../../services/agent/src/autobots/api/settings_routes.py#L63): workspace_required: no test anywhere
  - [services/agent/src/autobots/api/run_routes.py:185-186](../../../../services/agent/src/autobots/api/run_routes.py#L185): session_required: no test anywhere
  - [services/agent/src/autobots/api/tool_routes.py:76](../../../../services/agent/src/autobots/api/tool_routes.py#L76): tool_version_not_found: no test anywhere
  - [services/agent/src/autobots/api/artifact_routes.py:41-42](../../../../services/agent/src/autobots/api/artifact_routes.py#L41): storage_unavailable: no test anywhere
  - [services/agent/tests/test_readiness.py:19-57](../../../../services/agent/tests/test_readiness.py#L19): the same fixtures copied again
- **Evidence:** The in-process suites call 8 operations: GET /v1/health, /v1/session, /v1/profile, PUT /v1/profile, /v1/workspaces/{id}, /v1/readiness, /v1/retention and /v1/operations/local-status. Grep finds workspace_required, session_required, tool_version_not_found, storage_unavailable and routine_name_taken in no file under services/agent/tests, tests, apps/web/tests or scripts. current_workspace, which 73 routes depend on, has no in-process test of its header-mismatch or ambiguous-workspace branches.
- **Why it matters:** Status mapping, the owner-only pins and the workspace gate are verified only through browser specs in the db profile, or not at all. The refactors proposed above therefore have no fast safety net.
- **Recommendation:** Add an api_client fixture to conftest, with settings, a fake membership, a fake pool and a token helper. Use it for a table test of current_workspace's three branches, parametrized tests of every refusal-to-status mapping, and post_run branch tests against a fake admission use case once that is extracted. Keep the db-profile checks for SQL behavior.
- **Rule check:** DH-06: tests use injected fakes, no real time and no paid calls. These tests run in the fast profile with sockets blocked by conftest, so they add no database or model use.
- **Verification:** confirmed. In-process suites call exactly 8 operations, and the five codes appear in no test, web or script file.

### <a id="papi-14"></a>PAPI-14: get_approvals maps untyped rows field by field in the handler

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/api/approval_routes.py:61-115](../../../../services/agent/src/autobots/api/approval_routes.py#L61): 54-line handler
  - [services/agent/src/autobots/api/approval_routes.py:78-111](../../../../services/agent/src/autobots/api/approval_routes.py#L78): 30 row[...] lookups on dict[str, Any]
  - [services/agent/src/autobots/api/approval_routes.py:86-89](../../../../services/agent/src/autobots/api/approval_routes.py#L86): exceeds_review_limit evaluated twice per row
  - [services/agent/src/autobots/api/approval_routes.py:91](../../../../services/agent/src/autobots/api/approval_routes.py#L91): timestamps formatted to strings in the route
  - [services/agent/src/autobots/api/approval_routes.py:45-58](../../../../services/agent/src/autobots/api/approval_routes.py#L45): _requester reads nested dict keys
- **Evidence:** application.approvals.list_approvals returns list[dict[str, Any]]. The handler builds each ApprovalView with 30 row[...] lookups, works out truncation twice and calls .isoformat() on two timestamp columns.
- **Why it matters:** A renamed key in the row dict surfaces only as a runtime KeyError, the truncation choice (exceeds_review_limit, computed twice) lives in the HTTP layer, and no test asserts arguments_truncated.
- **Recommendation:** Return a typed row (a frozen dataclass) from list_approvals and move the row-to-view mapping into one function that computes truncation once. Keep the row type and the DTO type distinct.
- **Rule check:** Option B SP-009: adapters make conversion explicit rather than treating a database row as an API response. The typed row and the DTO remain separate types.
- **Verification:** revised. 30 row lookups and the double exceeds_review_limit call confirmed; a typed row can't make mypy check SQL column names and ApprovalView validates at runtime, so severity lowered to low.

```text
application/approvals.py: @dataclass(frozen=True) ApprovalRow(...); list_approvals(...) -> list[ApprovalRow]
api/approval_routes.py: def _view(row: ApprovalRow, viewer: UUID) -> ApprovalView
```

### <a id="papi-16"></a>PAPI-16: The session token is decoded twice with separate settings

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/api/security.py:58-64](../../../../services/agent/src/autobots/api/security.py#L58): current_user: HS256, audience, required claims
  - [services/agent/src/autobots/api/security.py:76-82](../../../../services/agent/src/autobots/api/security.py#L76): session_email decodes again without the required-claims option
- **Evidence:** session_email repeats `jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"], audience="authenticated")` after current_user has already verified the same token with `options={"require": ["exp", "sub", "aud"]}`.
- **Why it matters:** Any future verification change, such as an issuer, leeway or a second algorithm, must be made in both places. Today the second decode is safe only because it depends on current_user.
- **Recommendation:** Decode once in a verified_claims dependency, which FastAPI caches per request, and derive current_user and session_email from it.
- **Rule check:** The verification options stay the same, and the bad-token tests in test_api.py:69-92 stay as the guard.
- **Verification:** confirmed. Two jwt.decode calls with different options confirmed; session_email is safe today only through its current_user dependency.

### <a id="papi-17"></a>PAPI-17: Two docstrings describe an earlier state of the code

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:1](../../../../services/agent/src/autobots/api/settings_routes.py#L1): 'The exact MP-05 routes', yet the module also holds PK-07, MD-02/03, run intent and shared dependencies
  - [services/agent/src/autobots/api/settings_routes.py:388](../../../../services/agent/src/autobots/api/settings_routes.py#L388): 'run admission is a later story', yet run_routes.post_run admits runs
- **Evidence:** settings_routes.py:1 reads "The exact MP-05 routes, behind the BFF." settings_routes.py:388 reads "It admits nothing: run admission is a later story."
- **Why it matters:** Readers trust module docstrings here because most are accurate, and these two send them to the wrong place for admission and for what the module owns.
- **Recommendation:** Update both when the module is split, keeping the story and decision references.
- **Rule check:** Ground rule: stories and decisions stay cited; only the stale statements change.
- **Verification:** confirmed. Both statements confirmed stale: the module also holds PK-07, MD-02/03 and shared dependencies, and run_routes.post_run admits runs.

### <a id="papi-18"></a>PAPI-18: check_run_intent keeps branches its own dependency makes unreachable

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:79-83](../../../../services/agent/src/autobots/api/settings_routes.py#L79): provider_settings already raises 503 when the pool is missing
  - [services/agent/src/autobots/api/settings_routes.py:390-391](../../../../services/agent/src/autobots/api/settings_routes.py#L390): pool re-read and tested again
  - [services/agent/src/autobots/api/settings_routes.py:408-411](../../../../services/agent/src/autobots/api/settings_routes.py#L408): budget stays None only if the pool disappears mid-request
- **Evidence:** The handler takes `settings: Settings`, whose dependency refuses when request.app.state.pool is None. It then re-reads the pool and guards on `pool is not None` twice.
- **Why it matters:** The budget=None case of RunIntentCheck looks reachable during a database outage but is not, which misleads anyone reasoning about the composer's states.
- **Recommendation:** Drop the second checks and use the connection the settings object already holds (see the connection-ownership finding), or make the dependency optional if a no-database answer is wanted.
- **Rule check:** none
- **Verification:** confirmed. provider_settings refuses when the pool is missing, so check_run_intent's two pool checks and budget=None are unreachable short of shutdown mid-request.

### <a id="papi-19"></a>PAPI-19: Every route states its response type twice, and FastAPI rules are not enforced

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 78
- **Where:**
  - [services/agent/pyproject.toml:47](../../../../services/agent/pyproject.toml#L47): ruff selects no FAST, C90, PLR09 or ANN401 rules
  - [services/agent/src/autobots/api/run_routes.py:280-283](../../../../services/agent/src/autobots/api/run_routes.py#L280): response_model=RunSummary and -> RunSummary
  - [services/agent/src/autobots/api/workflow_routes.py:146-147](../../../../services/agent/src/autobots/api/workflow_routes.py#L146): same pattern
- **Evidence:** The exploratory `ruff --select ALL`, run on api/ only, reports FAST001 on 78 routes whose response_model repeats the return annotation. It also reports 17 PLR0913, 16 ANN401 and 1 C901 hits, none of which the project's selection at pyproject.toml:47 enforces.
- **Why it matters:** FastAPI serializes with response_model while mypy checks the annotation, so editing one without the other makes them disagree silently.
- **Recommendation:** Make the return annotation the single source, which is FastAPI's default. Enable ruff's FAST rules for services/agent, and adopt argument and complexity thresholds with a baseline once the dependency aliases have cut handler parameter counts.
- **Rule check:** DH-06: Ruff is the lint gate, check and format are separate gates, and safe autofix stays an explicit operation.
- **Verification:** confirmed. ruff --select ALL on api/ reports 78 FAST001, 17 PLR0913, 16 ANN401 and 1 C901, and pyproject.toml:47 selects none of them.

### <a id="papi-20"></a>PAPI-20: One dependency goes by several names, and two different things are called Settings

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:88](../../../../services/agent/src/autobots/api/settings_routes.py#L88): Settings alias names ProviderSettings
  - [services/agent/src/autobots/api/settings.py:11](../../../../services/agent/src/autobots/api/settings.py#L11): Settings is also the process configuration class
  - [services/agent/src/autobots/api/run_routes.py:181](../../../../services/agent/src/autobots/api/run_routes.py#L181): parameter settings is ProviderSettings here
  - [services/agent/src/autobots/api/security.py:39](../../../../services/agent/src/autobots/api/security.py#L39): and the process Settings here
  - [services/agent/src/autobots/api/event_routes.py:40](../../../../services/agent/src/autobots/api/event_routes.py#L40): Workspace = current_workspace
  - [services/agent/src/autobots/api/workflow_routes.py:63](../../../../services/agent/src/autobots/api/workflow_routes.py#L63): Member = the same dependency
  - [services/agent/src/autobots/api/run_routes.py:73](../../../../services/agent/src/autobots/api/run_routes.py#L73): public as_api_error; four modules use _error for the same role
- **Evidence:** Counted with grep:
  - 3 modules alias current_workspace as Workspace and 4 as Member.
  - 2 error mappers are public as_api_error, and 4 are private _error.
  - 1 alias reuses the name Settings for ProviderSettings.

  Handlers also name the same values workspace or workspace_id, and user or user_id.
- **Why it matters:** settings.run_intent(...) and settings.jwt_secret appear in the same package with different types under one name, which slows reading and invites wrong imports.
- **Recommendation:** Rename the alias to something like ProviderSettingsDep, and standardize on MemberWorkspace, OwnerWorkspace, CurrentUser, workspace_id and user_id when the aliases move to api/dependencies.py.
- **Rule check:** none
- **Verification:** confirmed. 3 Workspace and 4 Member aliases, 2 as_api_error and 4 _error mappers, and the Settings alias for ProviderSettings confirmed.

### <a id="papi-21"></a>PAPI-21: Domain facts are restated as literals in run_routes.py

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:93-97](../../../../services/agent/src/autobots/api/run_routes.py#L93): budget messages spell out US$0.25, US$5.00 and the step
  - [services/agent/src/autobots/api/run_routes.py:104-108](../../../../services/agent/src/autobots/api/run_routes.py#L104): profile display labels
  - [services/agent/src/autobots/api/run_routes.py:160](../../../../services/agent/src/autobots/api/run_routes.py#L160): PROFILE_LABELS[profile] lookup
- **Evidence:** BUDGET_MESSAGES restates BUDGET_MIN_MICRO_USD, BUDGET_MAX_MICRO_USD and BUDGET_STEP_MICRO_USD (domain/budgets.py:5-7) as text. PROFILE_LABELS covers exactly the three ModelProfileId members, and the web repeats the same labels in three components (apps/web/components/run-list.tsx:76, experts-panel.tsx:296, expert-editor.tsx:23).
- **Why it matters:** If a fourth profile joins the domain, as Sol did under Decision 0019, preview_run raises KeyError and returns 500 until someone finds this table. A changed budget range would leave the refusal text wrong.
- **Recommendation:** Give ModelProfile a label in domain/models.py and format the budget messages from the domain constants. The web can then show the label that the preview already returns.
- **Rule check:** Decision 0022 D11's budget range and the set of profiles are unchanged; only the source of their text moves.
- **Verification:** revised. Both tables and the KeyError path confirmed; the domain constants are named BUDGET_MIN_MICRO_USD, BUDGET_MAX_MICRO_USD and BUDGET_STEP_MICRO_USD, now quoted correctly.

## Rejected during verification

None. Every finding held up at its cited lines and was kept. Where a count, an excerpt, a location, the wording of the impact or the severity changed, the finding is marked revised and its verification line says what changed.

## Not covered

This review is static. I ran no tests, mypy or uvicorn, so the pool-exhaustion scenario and the per-request ValueError from AUTOBOTS_MIN_FREE_BYTES are inferred from the code, not observed. To count route dependencies (73 of 80 depend on current_workspace), I imported create_app with services/agent/.venv/bin/python -I. That is project code run by the venv interpreter rather than a script that only reads files; the factory opens nothing, as test_app_factory proves. I inspected contracts/generated/openapi.json and packages/api-client/src/generated.ts read-only, with python3.12 -I and grep. The application modules the routes call were read only around the cited lines: runs, provider_settings, operations, approvals, reconciliation, model_admission, artifacts, search, experts, workflows and domain/models. Their own quality is not judged here. test_readiness.py and test_operation_values.py were read in part. I searched the browser specs, tests/db checks and qualification scripts for error codes but did not read them. metrics.md and PRD-Development-Harness.md (DH-03 to DH-06) were read in the relevant sections only. The PRD sources the code cites (MP-05, PK-07, MD-02/03, SH-04, HM-05) were not opened; their IDs come from the code's own comments.
