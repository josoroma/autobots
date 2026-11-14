# Lens: module boundaries and dependency direction

Dependencies run in the intended direction at the core but not above it. domain/ (11 modules) imports only the standard library. 25 of the 27 contracts modules import only pydantic, contracts and domain. The two exceptions are contracts/export.py, which imports api.app (the service's one upward import), and contracts/adapters.py, which imports persistence. Above that line, application/ and adapters/ import each other (21 and 26 statements) and application/ imports operations/ 6 times. The worker imports the API entry point to get its configuration. 7 of the 29 function-level imports (in 17 functions) exist only to break five module cycles, and no check reports those cycles. application/goal\_loop.py is the hub. It builds the tool registry from 11 adapter imports, wires Deep Agents, and shares private lifecycle helpers with workflow\_runner and 10 test files. Because the catalog and four API routers depend on it, building the API or the OpenAPI document imports 110 autobots modules, plus deepagents, langchain and langgraph. Business rules also cross layers: the GitHub adapters run approval and receipt SQL through ToolContext's raw connection, the API routes read the workspace model policy six times and write it with their own version check, and the web re-implements the run command guards. The web boundary itself holds: no client module imports a server-only module, pages are thin, and responses are parsed with generated parsers. However, 28 request bodies and 78 API paths are hand-written, and 74 of the 78 generated operations go unused. The layout has drifted from DH-03 (no workers/ or graphs/, operations/ and persistence/ undocumented, no scripts/db/). Five rule path globs match no file, and their harness test checks paths that don't exist. Nothing enforces layer direction. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | DH-06 separation holds for domain by convention only: no lint rule or test checks import direction, and five rule globs fail DH-03's 'test representative paths'. |
| modules | 3 | domain and contracts are clean leaves (two contracts files aside), but application and adapters depend on each other, goal\_loop is a hub, and five cycles sit behind function-level imports. |
| size | 3 | The modules with the most cross-layer edges are also among the largest (goal\_loop: 782 lines, 17 application and 11 adapter imports); the area reviews cover per-file size. |
| functions | 3 | Route handlers such as post\_run run whole use cases, and lifecycle functions are named private while other modules depend on them. |
| structure | 3 | CODEBASE.md documents the real layout, but it differs from DH-03 in five places and the rule globs follow DH-03's paths. |
| approach | 3 | The pure app factory and single BFF are sound; registry, executor and model wiring happen inside application, and configuration is read at call sites. |
| comments | 4 | Every module has a docstring, and 87 of 139 cite a decision, PRD or story ID; of the 7 function-level imports that break a cycle, only goal\_loop.py:433 says why, and tools.py:1 is stale. |
| types | 3 | Generated parsers check responses, but request bodies use no generated types, the pool is Any in 10 copies, and SQL rows are positional tuples. |
| errors | 3 | Typed refusal codes cross layers cleanly, but HTTP mapping is spread over per-router as\_api\_error functions, two of them with the same name. |
| tests | 3 | Parity tests pin the parallel tool tables, but 34 test imports of private names couple tests to internals, and nothing tests layering. |
| maintainability | 3 | Most changes stay in one area. Adding a tool, changing the run lifecycle or changing a request contract touches several layers with no checks to guide the edit. |

## Strengths

- **Pure domain layer.** All 11 modules in services/agent/src/autobots/domain import only the standard library and each other (AST scan: 0 framework imports and 0 imports from other layers). domain/runs.py:22-128 holds the canonical transition table and domain/execution.py:14-49 holds the execution contract. Sources: [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22), [services/agent/src/autobots/domain/execution.py:14](../../../../services/agent/src/autobots/domain/execution.py#L14).
- **Contracts are nearly a leaf, with strict configs.** 25 of 27 contract modules import only pydantic, contracts and domain. contracts/primitives.py:9-10 STRICT\_CONTRACT refuses unknown fields, and request models such as RunRequest (contracts/run\_commands.py:16) forbid extras. Sources: [services/agent/src/autobots/contracts/primitives.py:9](../../../../services/agent/src/autobots/contracts/primitives.py#L9), [services/agent/src/autobots/contracts/run_commands.py:16](../../../../services/agent/src/autobots/contracts/run_commands.py#L16).
- **One OpenRouter factory.** ChatOpenRouter and openrouter.OpenRouter are constructed only in services/agent/src/autobots/adapters/models/factory.py (lines 95-110 and 124). Every other model path goes through that factory, as DH-06 requires. Sources: [services/agent/src/autobots/adapters/models/factory.py:95](../../../../services/agent/src/autobots/adapters/models/factory.py#L95), [services/agent/src/autobots/adapters/models/factory.py:124](../../../../services/agent/src/autobots/adapters/models/factory.py#L124).
- **Pure app factory, lifespan-owned resources, one API composition root.** api/app.py:41-92 builds the app without opening anything and opens and closes the pool in lifespan. api/main.py:37-51 is the only place that wires the environment, membership and storage for the API process. Sources: [services/agent/src/autobots/api/app.py:41](../../../../services/agent/src/autobots/api/app.py#L41), [services/agent/src/autobots/api/main.py:37](../../../../services/agent/src/autobots/api/main.py#L37).
- **Explicit web server/client boundary.** apps/web/lib/bff.ts, session.ts, server-config.ts, service-status.ts and workspace-choice.ts each start with import "server-only", and none of the 39 "use client" modules imports them. lib/ imports no component, app/ has no client module, the largest page is 127 lines (app/page.tsx), and process.env is read only in lib/server-config.ts:11-21. Sources: [apps/web/lib/bff.ts:1](../../../../apps/web/lib/bff.ts#L1), [apps/web/lib/server-config.ts:11](../../../../apps/web/lib/server-config.ts#L11), [apps/web/app/page.tsx:1](../../../../apps/web/app/page.tsx#L1).
- **Single BFF choke point for API traffic.** Every route handler that reaches the API (5 of the 8) forwards through apps/web/lib/bff.ts forward (71-126) or streamFrom (132-175). These apply the Host/Origin/CSRF guard, session, internal token, workspace header, body limits and no-store in one place. The session, workspace and csrf handlers stay local and assemble the guard themselves (XDUP-12 in the duplication lens). Sources: [apps/web/lib/bff.ts:71](../../../../apps/web/lib/bff.ts#L71), [apps/web/lib/bff.ts:132](../../../../apps/web/lib/bff.ts#L132).
- **Responses parsed with generated parsers.** 25 web files import 32 distinct generated parse\* functions (45 imports), for example apps/web/components/run-controls.tsx:3-6 and the parseRunSummary call at :66-68. Sources: [apps/web/components/run-controls.tsx:3](../../../../apps/web/components/run-controls.tsx#L3), [apps/web/components/run-controls.tsx:66](../../../../apps/web/components/run-controls.tsx#L66).
- **Parallel tables pinned by tests.** services/agent/tests/test\_execution\_contract.py:23-29 keeps domain TOOL\_VERSIONS equal to the registry. test\_tool\_catalog.py:23-31 keeps the catalog equal to the registry, and test\_tool\_guides.py:25-28 keeps the guides complete. domain/execution.py:14 names its test. Sources: [services/agent/tests/test_execution_contract.py:23](../../../../services/agent/tests/test_execution_contract.py#L23), [services/agent/tests/test_tool_catalog.py:23](../../../../services/agent/tests/test_tool_catalog.py#L23), [services/agent/tests/test_tool_guides.py:25](../../../../services/agent/tests/test_tool_guides.py#L25), [services/agent/src/autobots/domain/execution.py:14](../../../../services/agent/src/autobots/domain/execution.py#L14).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XMOD-01](#xmod-01) | high | modules | goal\_loop builds the tool registry, so application imports adapters and the API imports the agent runtime | L | medium |
| [XMOD-02](#xmod-02) | high | modules | External tool adapters run approval and receipt SQL through ToolContext's raw connection | M | high |
| [XMOD-03](#xmod-03) | high | types | Web request bodies and paths are hand-written, so the generated contract checks only responses | L | medium |
| [XMOD-04](#xmod-04) | medium | standards | Five rule path globs match no tracked file, and the harness test checks paths that don't exist | S | low |
| [XMOD-05](#xmod-05) | medium | modules | API routes read and write the workspace model policy and run admission orchestration themselves | M | medium |
| [XMOD-06](#xmod-06) | medium | modules | The web re-implements run command guards that the domain owns | M | medium |
| [XMOD-07](#xmod-07) | medium | modules | Run lifecycle helpers are private to goal\_loop but used by workflow\_runner and ten test files | M | medium |
| [XMOD-08](#xmod-08) | medium | approach | Process configuration is read at call sites in four layers, and the worker imports the API entry point to get it | M | medium |
| [XMOD-09](#xmod-09) | medium | standards | Nothing enforces layer direction, and function-level imports hide five cycles | S | low |
| [XMOD-11](#xmod-11) | medium | modules | API routers get shared dependencies from settings\_routes, and each copies the pool accessor | S | low |
| [XMOD-13](#xmod-13) | medium | structure | The service layout and DH-03 disagree in five places | S | low |
| [XMOD-10](#xmod-10) | low | modules | contracts imports api and persistence, and persistence/ holds one row type that its only caller bypasses | S | low |
| [XMOD-12](#xmod-12) | low | structure | operations/ mixes the worker, shared logging, seeding, paid trials and a test double, and inner layers import it | M | low |
| [XMOD-15](#xmod-15) | low | structure | contracts/tools.py is a hub for unrelated modules, and the contract model configs are copied | S | low |
| [XMOD-16](#xmod-16) | low | structure | Three BFF routes duplicate paths the /api/v1 catch-all already forwards | S | low |
| [XMOD-17](#xmod-17) | low | naming | Two CredentialCheck aliases with different signatures name the same concept | S | low |

### <a id="xmod-01"></a>XMOD-01: goal\_loop builds the tool registry, so application imports adapters and the API imports the agent runtime

- **Severity** high · **Dimension** modules · **Effort** L · **Risk** medium · **Occurrences** 21
- **Where:**
  - [services/agent/src/autobots/application/goal_loop.py:19-41](../../../../services/agent/src/autobots/application/goal_loop.py#L19): 11 adapter import statements, mostly tool constants
  - [services/agent/src/autobots/application/goal_loop.py:162-197](../../../../services/agent/src/autobots/application/goal_loop.py#L162): loop\_registry: the whole tool list
  - [services/agent/src/autobots/application/tool_catalog.py:61-79](../../../../services/agent/src/autobots/application/tool_catalog.py#L61): catalog built through loop\_registry with a \_never Delegation and object\_store=object()
  - [services/agent/src/autobots/application/tool_catalog.py:12-13](../../../../services/agent/src/autobots/application/tool_catalog.py#L12): imports assignments (for Delegation) and goal\_loop
  - [services/agent/src/autobots/api/run_routes.py:14](../../../../services/agent/src/autobots/api/run_routes.py#L14): API imports goal\_loop for execution\_block
  - [services/agent/src/autobots/api/tool_routes.py:13](../../../../services/agent/src/autobots/api/tool_routes.py#L13): API imports tool\_catalog and through it goal\_loop (application/search.py:10 does the same for search\_routes)
  - [services/agent/src/autobots/application/routines.py:369](../../../../services/agent/src/autobots/application/routines.py#L369): lazy import that breaks routines -> tool\_catalog -> goal\_loop -> cronjob\_tool -> routines
  - [services/agent/src/autobots/application/experts.py:37](../../../../services/agent/src/autobots/application/experts.py#L37): lazy import that breaks experts -> tool\_catalog -> assignments -> experts (again at :65)
- **Evidence:** An AST count over services/agent/src/autobots, including function-level imports, finds 21 imports from application/ into adapters/; 11 of them are in goal\_loop.py:19-41. tool\_catalog derives the catalog by calling loop\_registry with stand-in arguments:
  ```
  delegation = Delegation(drive=_never, limits=RootLimits(), lease_seconds=0.0)
  return loop_registry(RootLimits(), object_store=object(), delegation=delegation,
                       extra=(APPROVAL_GATE, *browsing))
  ```
  run\_routes.py:14 imports goal\_loop, and tool\_routes.py:13 and search.py:10 import tool\_catalog. As a result, the static import-time closure of autobots.api.app is 110 modules, including deepagents, langchain, langgraph and every tool adapter; contracts/export.py has the same closure. Three of the five hidden cycles pass through this registry wiring (routines.py:369, experts.py:37 and :65, cronjob\_tool.py:40). A third builder, application/tools.py:284-288 default\_registry, is used only by tests.
- **Why it matters:** Adding or changing a tool means editing the run loop module. A broken import in any tool adapter breaks API startup and OpenAPI generation. application cannot be imported or tested without the adapters and the Deep Agents stack. The stand-in arguments are an unwritten second contract with loop\_registry's conditional registration.
- **Recommendation:** Build the registry at the edge and pass it in. Put the full tool list in one composition module that may import application tool modules (for example adapters/tool\_registry.py). Have api/main.py and operations/worker.py build it once, pass it to goal\_loop through LoopConfig and to tool\_catalog as a parameter, and give experts and routines an availability callable, as routines already receives credential\_check. Move execution\_block next to the execution contract (application/runs.py or recovery.py) so the API stops importing goal\_loop. Point test\_execution\_contract.py at the registry the worker uses.
- **Rule check:** python-worker rule: one LangGraph lifecycle still owns execution. domain/execution.py TOOL\_VERSIONS and its parity test (services/agent/tests/test\_execution\_contract.py:23-29) keep comparing against the registry the worker runs. No lease, fence or approval behavior changes.
- **Verification:** confirmed. Re-ran an AST import scan: 21 application-to-adapters statements, 11 in goal\_loop.py:19-41. The module-level closure of autobots.api.app is 110 autobots modules (120 counting package \_\_init\_\_ files) and reaches deepagents, langchain and langgraph; at import time four routers (run, tool, search, workflow) reach goal\_loop. default\_registry (tools.py:284-288) is used only by tests/db and services/agent/tests.

```text
adapters/tool_registry.py: build_registry(limits, *, object_store, delegation, browsing, extra) -> ToolRegistry; the only module that imports every ToolDefinition (10 application and 7 adapter modules)
application/goal_loop.py: run_goal and build_stage take config.registry_factory; no adapter tool imports
application/tool_catalog.py: all_descriptors(registry, environ) and tool_catalog(registry, ...); no goal_loop or assignments import and no stand-ins
application/runs.py: execution_block(connection, run_id)
api/main.py and operations/worker.py: build the factory once (app.state.tool_registry, LoopConfig)
application/experts.py and routines.py: receive require_available as a parameter; lazy imports removed
```

### <a id="xmod-02"></a>XMOD-02: External tool adapters run approval and receipt SQL through ToolContext's raw connection

- **Severity** high · **Dimension** modules · **Effort** M · **Risk** high · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/tool_gateway.py:55-59](../../../../services/agent/src/autobots/application/tool_gateway.py#L55): ToolContext gives every tool connection: Any
  - [services/agent/src/autobots/adapters/github_pulls.py:134-154](../../../../services/agent/src/autobots/adapters/github_pulls.py#L134): return\_to\_review settles the receipt, resets the approval to pending and appends approval.requested
  - [services/agent/src/autobots/adapters/github_pulls.py:122-132](../../../../services/agent/src/autobots/adapters/github_pulls.py#L122): approved\_detail reads approval\_requests
  - [services/agent/src/autobots/application/approvals.py:182-200](../../../../services/agent/src/autobots/application/approvals.py#L182): the application's own reset to pending, using ttl\_seconds and \_enter\_wait
  - [services/agent/src/autobots/application/approvals.py:25](../../../../services/agent/src/autobots/application/approvals.py#L25): DEFAULT\_TTL\_SECONDS = 86\_400, copied into the adapter as interval '1 day'
  - [services/agent/src/autobots/adapters/github_issues.py:101-109](../../../../services/agent/src/autobots/adapters/github_issues.py#L101): approved\_repository reads approval\_requests
  - [services/agent/src/autobots/adapters/remote_files.py:55-61](../../../../services/agent/src/autobots/adapters/remote_files.py#L55): reads app\_private.run\_files
- **Evidence:** github\_pulls.py:137-145:
  ```
  await context.connection.execute(
      "update app_private.tool_receipts set reconciled_at = now() where operation_id = %s", ...)
  cursor = await context.connection.execute(
      "update public.approval_requests set status = 'pending', decided_by = null, "
      "decided_at = null, review_detail = %s, expires_at = clock_timestamp() + interval '1 day' " ...
  ```
  The same approved-to-pending transition exists in approvals.py:182-200, which uses make\_interval(secs => %s) from DEFAULT\_TTL\_SECONDS and calls \_enter\_wait. approval\_requests.status is written at four application sites (approvals.py:185, 208, 299 and runs.py:451) and at this one adapter site. Adapters issue 5 statements against approval, receipt and run-file tables, in 3 modules.
- **Why it matters:** The approval state machine, which the rules say must bind the actual effect, now has a second implementation inside an HTTP client module. A change to approval expiry, events or waiting in approvals.py won't reach the pull-request path. Because the tool port hands out raw SQL access, every new connector can repeat the pattern.
- **Recommendation:** Keep Decision 0022 D15's behavior but move its implementation. Add approvals.approved\_call() and approvals.return\_to\_review() (one transaction, DEFAULT\_TTL\_SECONDS, the same event). Have the gateway load the approved call into ToolContext for approved dispatches, and give remote\_files a tools.stored\_file() helper next to write\_run\_file. Then narrow ToolContext so external adapters get capabilities instead of a connection. Run tests/db/pull\_request\_check.py and approval\_check.py before and after.
- **Rule check:** Preserves the python-worker rule 'approvals bind the actual normalized effect' and Decision 0022 D15 (base\_moved sends the request back to a person with the new diff). The transition moves into application/approvals.py and nothing is relaxed.
- **Verification:** confirmed. Re-read all cited SQL: github\_pulls.py:137-147 settles the receipt and resets the approval with a literal '1 day'; approvals.py:184-199 uses ttl\_seconds and \_enter\_wait; approval status is written at approvals.py:185, 208, 299, runs.py:451 and github\_pulls.py:142. The 5 adapter statements are github\_issues.py:102, github\_pulls.py:123, 137 and 141, and remote\_files.py:58. XDUP-02 reports the same copy from the duplication side.

```text
application/approvals.py: approved_call(connection, operation_id) -> ApprovedCall | None; return_to_review(connection, operation_id, detail) -> None, which settles the receipt, sets pending with DEFAULT_TTL_SECONDS and appends approval.requested
application/tool_gateway.py: ToolContext.approval: ApprovedCall | None, loaded before an approved dispatch
application/tools.py: stored_file(connection, operation_id) beside write_run_file
adapters/github_pulls.py, github_issues.py and remote_files.py: use context.approval and these helpers; no SQL strings
```

### <a id="xmod-03"></a>XMOD-03: Web request bodies and paths are hand-written, so the generated contract checks only responses

- **Severity** high · **Dimension** types · **Effort** L · **Risk** medium · **Occurrences** 28
- **Where:**
  - [apps/web/components/goal-composer.tsx:288-300](../../../../apps/web/components/goal-composer.tsx#L288): run admission body built as an untyped object literal
  - [apps/web/components/run-controls.tsx:62-83](../../../../apps/web/components/run-controls.tsx#L62): hand-built base path and command body
  - [apps/web/lib/service-status.ts:3-10](../../../../apps/web/lib/service-status.ts#L3): the only consumer of generated operations (4 of 78), server-side
  - [packages/api-client/src/runtime.ts:157-172](../../../../packages/api-client/src/runtime.ts#L157): requestJson throws without the ErrorResponse body that screens display
  - [services/agent/src/autobots/contracts/run_commands.py:13-16](../../../../services/agent/src/autobots/contracts/run_commands.py#L13): RunRequest forbids extra fields
  - [services/agent/src/autobots/api/errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29): validation failures become a generic invalid\_request
  - [apps/web/components/goal-composer.tsx:331-333](../../../../apps/web/components/goal-composer.tsx#L331): any 422 becomes a model-or-request refusal (session-panel.tsx:76-77 does the same)
- **Evidence:** goal-composer.tsx:288-298:
  ```
  const reply = await csrfFetch("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ goal_text: draft, budget_micro_usd: budget,
      ...(sessionId === null ? {} : { session_id: sessionId }), ...
  ```
  A grep of apps/web/components finds 28 `body: JSON.stringify(` request bodies in 18 files and 78 hand-written '/api/...' path literals in 31 files. There are 0 references to a generated request type (RunRequest, ExpertCreate, ApprovalDecision, ModelPolicyUpdate, ...) and 0 uses of `satisfies`. The generated client has 78 typed operations, for example generated.ts:9418 admitRun(options, body: RunRequest), and 4 are used, all server-side.
- **Why it matters:** Renaming or retyping a request field in Pydantic regenerates the TypeScript types but breaks no compile. The API then rejects the body (extra='forbid') with a generic 422 invalid\_request (errors.py:29-32), and the screens misreport it: the composer turns any 422 into 'That model or request isn't approved' (goal-composer.tsx:331-333 and 636) and the session panel into 'That request isn't approved' (session-panel.tsx:76-77), which points the person at their model choice rather than at a contract mismatch. Path and method changes are just as invisible to tsc. Drift at the browser-to-API boundary is caught only if a browser test covers that form.
- **Recommendation:** Route browser calls through the generated operations. Use a client-safe options object with baseUrl '/api' and a fetch adapter over csrfFetch, add a runtime error type that carries the parsed ErrorResponse so screens keep their refusal messages, and teach the generator to emit declared header parameters such as Idempotency-Key. Migrate one screen at a time; until a screen moves, type its bodies with `satisfies` and the generated request type.
- **Rule check:** contracts rule: Pydantic/OpenAPI owns the definitions and generated TypeScript consumes them. generated.ts is regenerated by scripts/generate\_contracts.py and never hand-edited; runtime.ts is hand-written. nextjs rule: response parsing, CSRF and same-origin BFF routing through lib/bff.ts all stay.
- **Verification:** revised. Counts reproduced with git grep: 28 bodies in 18 component files, 78 '/api/' literals in 31 files, no generated request type and no `satisfies`; 4 of the 78 generated operations are used, all in lib/service-status.ts. Impact corrected: a drifted body is not shown as 'The request is not valid.' but as 'That model or request isn't approved', because both run screens map every 422 to an approval refusal.

```text
packages/api-client/src/runtime.ts: class ApiRefusal(status, body: ErrorResponse); requestJson throws it and accepts per-call headers
scripts/generate_contracts.py: emit declared header parameters (Idempotency-Key) in each operation
apps/web/lib/api.ts: browserApi: ClientOptions = { baseUrl: "/api", fetch: adapter that uses csrfFetch for writes }
components: await admitRun(browserApi, body), with body typed as RunRequest; catch ApiRefusal for the refusal text
Interim: JSON.stringify({ ... } satisfies RunRequest)
```

### <a id="xmod-04"></a>XMOD-04: Five rule path globs match no tracked file, and the harness test checks paths that don't exist

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [.claude/rules/database.md:5](../../../../.claude/rules/database.md#L5): services/agent/src/autobots/adapters/persistence/\*\*/\* matches 0 files
  - [.claude/rules/model-gateway.md:5](../../../../.claude/rules/model-gateway.md#L5): services/agent/src/autobots/graphs/\*\*/\* matches 0
  - [.claude/rules/model-gateway.md:7](../../../../.claude/rules/model-gateway.md#L7): apps/web/src/app/api/settings/\*\*/\* matches 0
  - [.claude/rules/infrastructure.md:7](../../../../.claude/rules/infrastructure.md#L7): scripts/operations/\*\*/\* matches 0
  - [.claude/rules/infrastructure.md:4](../../../../.claude/rules/infrastructure.md#L4): \*\*/Dockerfile\* matches 0 (forward-looking)
  - [tests/harness/test_assistant_assets.py:52-71](../../../../tests/harness/test_assistant_assets.py#L52): RULE\_PATHS lists DH-03's planned paths such as adapters/persistence/runs.py, graphs/run.py, scripts/operations/backup.sh
  - [tests/harness/test_assistant_assets.py:620-633](../../../../tests/harness/test_assistant_assets.py#L620): asserts that globs match those representative paths, never real files
  - [services/agent/src/autobots/adapters/loop_middleware.py:53-61](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L53): imports and applies the model-attempt retry policy; no model-gateway glob covers adapters/ outside models/
- **Evidence:** Each `paths` glob was matched against `git ls-files`: database.md adapters/persistence/\*\* matches 0 files, model-gateway.md graphs/\*\* and apps/web/src/app/api/settings/\*\* match 0, and infrastructure.md scripts/operations/\*\* and \*\*/Dockerfile\* match 0. The SQL the database rule governs lives in application/ (340 `.execute(` calls in 36 modules), api/ (17 in 5) and adapters/ (13 in 8). Model calls outside adapters/models happen in adapters/loop\_middleware.py and in the paid operations/route\_qualification.py, reasoning\_trial.py and browse\_trial.py, and the Python provider routes are in api/settings\_routes.py. scripts/supabase\_stack.py and scripts/app\_db.py match no infrastructure or database glob. The test passes because RULE\_PATHS lists DH-03's planned paths.
- **Why it matters:** The database rule does not load when application or API SQL is edited, or when scripts/app\_db.py changes. The model-gateway rule (no fallback, fake transports by default, live qualification as a bounded task) does not load for the loop middleware or the paid trials. AGENTS.md and python-worker.md still load there, so the core OpenRouter-only and fake-transport boundaries stay in view, but the path-specific rule text does not. The harness test reads DH-03's planned paths as representatives by design (its comment at test\_assistant\_assets.py:52-53 says it shows only the matcher's reading), so nothing checks that a glob matches a real file.
- **Recommendation:** Point the globs at the code that exists. Make the harness test require every glob to match at least one tracked file, except an explicit allowlist of forward-looking globs such as \*\*/Dockerfile\*, and use real files as representative paths. Update the matching 'Relevant paths' lines in .claude/skills/autobots-model-gateway/SKILL.md:8 and .claude/skills/autobots-docker-local/SKILL.md:8, which repeat the dead globs, in the same change.
- **Rule check:** DH-03: 'Use supported paths frontmatter for scoping and test representative paths'. Only `paths` values change (RULE\_KEYS stays {'paths'}), and the test becomes stricter. No rule text or check is weakened.
- **Verification:** revised. Matched every glob with the test's own glob\_matches against git ls-files: exactly these five match 0 files. Severity lowered from high to medium: AGENTS.md (always loaded) and python-worker.md (services/agent/\*\*) still carry the core model and database boundaries, so the gap is path-specific guidance rather than an unguarded change, and the test documents that it checks only the matcher's reading. Added the two skills that repeat the globs.

```text
database.md paths: supabase/**/*; packages/db-types/**/*; services/agent/src/autobots/application/**/*; services/agent/src/autobots/api/**/*; services/agent/src/autobots/persistence/**/*; scripts/app_db.py; scripts/disposable_db.py
model-gateway.md paths: adapters/models/**/*; application/**/*; adapters/loop_middleware.py; operations/route_qualification.py; operations/reasoning_trial.py; operations/browse_trial.py; api/settings_routes.py; apps/web/app/api/settings/**/* (drop graphs/** and apps/web/src/**)
infrastructure.md: replace scripts/operations/**/* with scripts/supabase_stack.py, scripts/qualify_operations.py, scripts/qualify_backup.py, scripts/qualify_upgrade.py
tests/harness/test_assistant_assets.py: real representative paths, plus 'every glob matches >= 1 git ls-files path unless in FORWARD_LOOKING'
.claude/skills/autobots-model-gateway/SKILL.md and autobots-docker-local/SKILL.md: Relevant paths follow the rule globs
```

### <a id="xmod-05"></a>XMOD-05: API routes read and write the workspace model policy and run admission orchestration themselves

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:120-127](../../../../services/agent/src/autobots/api/run_routes.py#L120): policy read in preview\_run (again at 201-208 in post\_run)
  - [services/agent/src/autobots/api/run_routes.py:177-277](../../../../services/agent/src/autobots/api/run_routes.py#L177): post\_run sequences budget, key readiness, Expert binding, tool availability, policy and offered-profile checks before admit\_run
  - [services/agent/src/autobots/api/settings_routes.py:329-344](../../../../services/agent/src/autobots/api/settings_routes.py#L329): versioned upsert with for update and stale\_version, inside the route
  - [services/agent/src/autobots/api/improvement_routes.py:99-112](../../../../services/agent/src/autobots/api/improvement_routes.py#L99)
  - [services/agent/src/autobots/application/routines.py:352-362](../../../../services/agent/src/autobots/application/routines.py#L352)
  - [services/agent/src/autobots/application/workflow_overview.py:119-136](../../../../services/agent/src/autobots/application/workflow_overview.py#L119)
  - [services/agent/src/autobots/application/workflows.py:364](../../../../services/agent/src/autobots/application/workflows.py#L364)
- **Evidence:** app\_private.model\_policies is read in 9 places. Six are in three API route modules (run\_routes.py:123, 204; settings\_routes.py:295, 364, 395; improvement\_routes.py:102) and three are in application (workflow\_overview.py:120, routines.py:355, workflows.py:364). Each read is followed by the same `resolve_role_policy(workspace_default=row[0] if row else None, workspace_role_overrides=row[1] if row else None, ...)`. The policy is written only at settings\_routes.py:339 and :373, inside the route with its own optimistic version check. api/ issues 17 SQL statements in 5 modules.
- **Why it matters:** The rule for which profiles a run gets is assembled at seven call sites across two layers. A policy change, such as a new override source or a Decision 0019-style default, has to be repeated by hand, and the versioned write can only be tested through HTTP.
- **Recommendation:** Add an application model-policy service and an admission use case. Routes then only parse the request, call the service and map refusals to ApiError.
- **Rule check:** DH-06 'avoid duplicated business rules'. HTTP admission stays separate from durable execution. The optimistic version check and require\_offered (Decisions 0013 and 0019) move unchanged.
- **Verification:** confirmed. Re-read the nine reads and the two versioned writes (settings\_routes.py:339 and :373; the select for update at :331 belongs to the first write). post\_run at 177-277 sequences the checks as stated, and api/ has 17 `.execute(` calls in 5 modules. XDUP-08 covers the same reads from the duplication side.

```text
application/model_policy.py: read_policy(connection, workspace_id) -> WorkspacePolicy; effective_policy(policy, run_overrides, run_profile) -> RolePolicy; update_policy(connection, workspace_id, expected_version, default, overrides), which raises StaleVersion
application/admission.py: admit_request(connection, request, user, settings, environ) -> AdmitResult covering budget, binding, availability, offered profiles and admit_run
api/run_routes.py, settings_routes.py, improvement_routes.py: call these and map refusals
```

### <a id="xmod-06"></a>XMOD-06: The web re-implements run command guards that the domain owns

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/run-controls.tsx:16-36](../../../../apps/web/components/run-controls.tsx#L16): TERMINAL, PAUSABLE and commandsFor
  - [apps/web/components/workflow-monitor.tsx:13](../../../../apps/web/components/workflow-monitor.tsx#L13): its own TERMINAL set, used at :61 to stop polling
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): canonical TERMINAL
  - [services/agent/src/autobots/domain/runs.py:97-128](../../../../services/agent/src/autobots/domain/runs.py#L97): COMMAND\_SOURCES and next\_status
  - [services/agent/src/autobots/contracts/run_workspace.py:166-167](../../../../services/agent/src/autobots/contracts/run_workspace.py#L166): can\_continue: a guard the server already projects
- **Evidence:** run-controls.tsx:16-36, abridged:
  ```
  const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
  const PAUSABLE = new Set(["queued", "running", "waiting_input", "waiting_approval", "verifying"]);
  export function commandsFor(status: string): Command[] {
    if (TERMINAL.has(status) || status === "cancelling") return [];
    if (status === "paused") return ["resume", "cancel"];
  ```
  workflow-monitor.tsx:13 defines another TERMINAL. Both sets are typed as plain strings rather than the generated RunStatus union (generated.ts:8691). The run workspace view already projects one guard, can\_continue.
- **Why it matters:** When the domain table changes (a new state, or pause allowed from another state), the UI offers stale actions or hides valid ones. The server still refuses, so users see 'That is not allowed' instead of the correct control.
- **Recommendation:** Project the allowed user commands from domain.next\_status into the run summary or workspace view, as can\_continue already is, then regenerate the client and render from that field. Type any remaining UI-only status maps with the generated RunStatus union.
- **Rule check:** autobots-nextjs skill: 'do not duplicate Python business-state enums'. DH-06: 'do not invent a second state enum for the UI'. contracts rule: canonical guards are shared. The new field is a contract change, so the client is regenerated, never hand-edited.
- **Verification:** confirmed. The UI's PAUSABLE equals the domain's pause sources today (every state whose NORMAL\_EXITS include PAUSED, domain/runs.py:24-42), so this is drift risk rather than a current bug. No web module imports the generated RunStatus, and commandsFor is also used by run-panel.tsx:130, so the projected field has to reach the run summary as well as the workspace view.

```text
contracts/run_workspace.py (or runs.py): available_commands: list[Literal['pause','resume','cancel']], computed from domain.runs.next_status for Actor.USER
application/run_projection.py: fills the field
components/run-controls.tsx: renders view.available_commands; TERMINAL and PAUSABLE removed
components/workflow-monitor.tsx: stops on a server terminal flag or a Set<RunStatus>
```

### <a id="xmod-07"></a>XMOD-07: Run lifecycle helpers are private to goal\_loop but used by workflow\_runner and ten test files

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 40
- **Where:**
  - [services/agent/src/autobots/application/workflow_runner.py:16-24](../../../../services/agent/src/autobots/application/workflow_runner.py#L16): imports \_finish, \_keep\_lease, \_result, \_run\_status
  - [services/agent/src/autobots/application/workflow_runner.py:298-301](../../../../services/agent/src/autobots/application/workflow_runner.py#L298): drive\_child lazily imports \_drive
  - [services/agent/src/autobots/application/goal_loop.py:417-438](../../../../services/agent/src/autobots/application/goal_loop.py#L417): \_drive reaches run\_workflow through a lazy import
  - [tests/db/review_check.py:21](../../../../tests/db/review_check.py#L21): \_drive, \_settle\_children
  - [tests/db/wake_check.py:16](../../../../tests/db/wake_check.py#L16): \_keep\_lease, with noqa PLC2701
  - [tests/db/assignment_check.py:21](../../../../tests/db/assignment_check.py#L21): \_finish
  - [services/agent/tests/test_plans.py:7](../../../../services/agent/tests/test_plans.py#L7): \_opening
- **Evidence:** An AST count of `from autobots... import _name` finds 40 imports of private names. 6 are in src: 5 in workflow\_runner from goal\_loop and 1 in reasoning\_trial. The other 34 are in 19 test files and come from 9 modules (goal\_loop 11, workflow\_runner 6, tool\_gateway 5, loop\_middleware 5, others 7).
  ```
  from autobots.application.goal_loop import (
      LoopConfig, LoopResult, _finish, _keep_lease, _result, _run_status, loop_registry,
  )
  ```
  goal\_loop.py:433 notes that the runner 'builds on this module's lifecycle', and the two modules import each other.
- **Why it matters:** Two runners share the lease heartbeat and the terminal write, but the names suggest they are local to goal\_loop. A 'private' edit in goal\_loop can break workflow runs and db-profile checks, and tests/db is outside mypy. The mutual import is a permanent cycle.
- **Recommendation:** Give the run lifecycle a public module and a dispatcher, and let the runners receive drive through Delegation instead of importing each other. Tests import the new public names. For the other modules, either promote a helper on purpose or test through the public function.
- **Rule check:** python-worker rule: the lease and fencing code moves verbatim. Run tests/db wake\_check, review\_check and assignment\_check (db profile) before and after.
- **Verification:** confirmed. An AST scan of tracked Python reproduced every count: 40 private-name imports, 6 in src, 34 in 19 test files from 9 modules, and 10 test files importing goal\_loop privates. mypy's files list in services/agent/pyproject.toml is src and tests, so tests/db at the repository root is not type-checked.

```text
application/run_lifecycle.py: keep_lease(), finish(), run_status(), result() for the lease heartbeat and terminal writes
application/run_dispatch.py: drive(connection, database_url, lease, model_factory, config) checks execution_block, then picks workflow, goal or verification, and passes itself as Delegation.drive
application/goal_loop.py: run_goal(), build_stage(), prompts
application/workflow_runner.py: run_workflow(), importing run_lifecycle only
```

### <a id="xmod-08"></a>XMOD-08: Process configuration is read at call sites in four layers, and the worker imports the API entry point to get it

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 26
- **Where:**
  - [services/agent/src/autobots/api/settings.py:1-28](../../../../services/agent/src/autobots/api/settings.py#L1): 'read once ... by the entry point', but it covers 4 variables
  - [services/agent/src/autobots/api/main.py:17-34](../../../../services/agent/src/autobots/api/main.py#L17): DEFAULT\_KEY\_FILE and provider\_context\_from\_environment
  - [services/agent/src/autobots/application/tool_keys.py:29](../../../../services/agent/src/autobots/application/tool_keys.py#L29): DEFAULT\_KEY\_FILE defined again, with its override at 77-78
  - [services/agent/src/autobots/operations/worker.py:29](../../../../services/agent/src/autobots/operations/worker.py#L29): worker imports api.main
  - [services/agent/src/autobots/operations/worker.py:178-186](../../../../services/agent/src/autobots/operations/worker.py#L178): disk readiness read from the environment
  - [services/agent/src/autobots/api/operation_routes.py:86-97](../../../../services/agent/src/autobots/api/operation_routes.py#L86): the same readiness inputs read separately
  - [services/agent/src/autobots/application/experts.py:32](../../../../services/agent/src/autobots/application/experts.py#L32): environ defaults to os.environ (also :58); :55 passes os.environ
  - [apps/web/lib/server-config.ts:11-21](../../../../apps/web/lib/server-config.ts#L11): the web's single config reader, for contrast
- **Evidence:** Per grep, os.environ appears in 26 modules, and 19 distinct AUTOBOTS\_\* variables are read in 10 modules across api, application, adapters and operations. DEFAULT\_KEY\_FILE and its override are defined twice (api/main.py:17-26 and application/tool\_keys.py:29, 77-78). The disk readiness rule reads AUTOBOTS\_MIN\_FREE\_BYTES and AUTOBOTS\_CONFIG\_ROOT separately in the API (operation\_routes.py:87, 95) and in the worker (worker.py:184-185), although the worker's comment says a routine 'waits on the same readiness a person would'. The worker takes its provider context from api/main.py, so it imports every api module (all 20, plus the package), every router included. key\_sources(..., os.environ) is called in 6 places.
- **Why it matters:** No single place lists what a process needs, and defaults can diverge between API and worker. Application functions that default to `environ = os.environ` silently read the real environment in tests unless every caller passes one.
- **Recommendation:** Add a leaf config module that each entry point loads, and pass the config (or the environ Mapping) down. Share one installation\_conditions() between operation\_routes and the worker, define the master-key default once, and move provider\_context\_from\_environment out of api/main.py.
- **Rule check:** model-gateway rule 'Late-resolve credential references per attempt': pass the live environ Mapping, not a startup snapshot, so .env files and process keys are still read per attempt. forbid\_remote\_tracing stays the first call in every entry point.
- **Verification:** revised. Counts reproduced: os.environ in 26 modules, 19 AUTOBOTS\_\* names in 10 modules, key\_sources(..., os.environ) at 6 sites. Corrected the experts.py line (expand\_groups is at :32, not :30) and the worker's reach: its import closure holds all 21 api modules including the package, not 20 of 21.

```text
autobots/config.py (leaf): ProcessConfig.from_environ(environ) with database_url, config_root, min_free_bytes, backup_dir, supabase_url, service_key, master_key_file, stream_seconds and worker settings; provider_context(config, environ)
api/main.py, operations/worker.py, bootstrap_owner.py, concept_seed.py: load it once
application/operations.py: installation_conditions(config, pool, store), used by operation_routes and worker.unattended_refusal
application/*: environ parameters with no os.environ default
```

### <a id="xmod-09"></a>XMOD-09: Nothing enforces layer direction, and function-level imports hide five cycles

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/pyproject.toml:47](../../../../services/agent/pyproject.toml#L47): ruff selects no tidy-imports or import-outside-top-level rule
  - [services/agent/src/autobots/application/cronjob_tool.py:38-42](../../../../services/agent/src/autobots/application/cronjob_tool.py#L38): cronjob\_tool -> operations.worker -> goal\_loop -> cronjob\_tool
  - [services/agent/src/autobots/application/experts.py:37](../../../../services/agent/src/autobots/application/experts.py#L37): experts -> tool\_catalog -> assignments -> experts (again at :65)
  - [services/agent/src/autobots/application/routines.py:369](../../../../services/agent/src/autobots/application/routines.py#L369): routines -> tool\_catalog -> goal\_loop -> cronjob\_tool -> routines
  - [services/agent/src/autobots/application/tool_gateway.py:310](../../../../services/agent/src/autobots/application/tool_gateway.py#L310): tool\_gateway \<-> tool\_uses (again at :402)
  - [services/agent/src/autobots/application/goal_loop.py:433-434](../../../../services/agent/src/autobots/application/goal_loop.py#L433): the only function-level import that says why
- **Evidence:** An AST scan finds 0 cycles among module-level imports, but 29 function-level import statements of autobots modules, in 17 functions across 13 files. 7 of the statements break real cycles: cronjob\_tool/worker/goal\_loop, experts/tool\_catalog/assignments (twice), routines/tool\_catalog/goal\_loop/cronjob\_tool, goal\_loop/workflow\_runner and tool\_gateway/tool\_uses (twice). Only goal\_loop.py:433 explains its import. Package edges outside the intended direction: application -> adapters 21, application -> operations 6, adapters -> operations 2, operations -> api 1, contracts -> api 1, contracts -> persistence 1. No test or lint rule checks any of them; pyproject.toml:47 selects E, F, W, I, B, UP, ASYNC and RUF, and the exploratory ALL run counts 31 PLC0415 hits.
- **Why it matters:** New upward imports and cycles land without notice. Reviewers have to rediscover the intended direction every time, and a function-level import reads like a performance choice when it hides a cycle.
- **Recommendation:** Add a pytest that builds the layer graph with ast, function-level imports included, and checks it against an allowed matrix with today's exceptions as a shrinking baseline. It should also fail on new module cycles. Require a one-line reason on each remaining function-level import. The test needs no new dependency and runs in the fast profile.
- **Rule check:** AGENTS.md: checks don't install anything. An ast test uses only the prepared environment, and the fast profile already runs services/agent tests.
- **Verification:** revised. Reproduced with an AST scan and strongly connected components: no module-level cycle; with function-level imports, five cycles closed by exactly 7 statements. The review's '17 function-level imports' counted functions, not statements (browse\_trial.py:148-158 alone holds 11), so the evidence now gives both and occurrences counts the 7 cycle-hiding imports. All six package-edge counts and the 31 PLC0415 hits match.

```text
services/agent/tests/test_layering.py: ALLOWED = {domain: {}, contracts: {domain}, persistence: {domain, contracts}, application: {domain, contracts, persistence}, adapters: {domain, contracts, persistence, application}, api: {+adapters}, operations: {all}}; BASELINE = {(file, target), ...}; assert edges - ALLOWED <= BASELINE; assert no new strongly connected component
```

### <a id="xmod-11"></a>XMOD-11: API routers get shared dependencies from settings\_routes, and each copies the pool accessor

- **Severity** medium · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 12
- **Where:**
  - [services/agent/src/autobots/api/settings_routes.py:52-88](../../../../services/agent/src/autobots/api/settings_routes.py#L52): current\_workspace, require\_owner and provider\_settings live in the settings feature module
  - [services/agent/src/autobots/api/run_routes.py:10-12](../../../../services/agent/src/autobots/api/run_routes.py#L10): imports operation\_routes and settings\_routes
  - [services/agent/src/autobots/api/run_routes.py:66-70](../../../../services/agent/src/autobots/api/run_routes.py#L66): one of 10 identical \_pool copies
  - [services/agent/src/autobots/api/workflow_routes.py:9-12](../../../../services/agent/src/autobots/api/workflow_routes.py#L9): imports operation\_routes, run\_routes and settings\_routes
  - [services/agent/src/autobots/api/approval_routes.py:38-42](../../../../services/agent/src/autobots/api/approval_routes.py#L38)
  - [services/agent/src/autobots/api/app.py:30-32](../../../../services/agent/src/autobots/api/app.py#L30): the Pool protocol has only open and close, so routes type the pool as Any
- **Evidence:** Per grep of `from autobots.api.settings_routes`, 12 of the 14 router modules import current\_workspace, require\_owner or provider\_settings from settings\_routes.py. run\_routes and workflow\_routes also import operation\_routes.require\_ready, and workflow\_routes imports run\_routes.budget\_error. The same accessor is defined 10 times (approval, artifact, event, expert, improvement, memory, operation, run, routine and workflow routes):
  ```
  def _pool(request: Request) -> Any:
      pool = request.app.state.pool
      if pool is None:
          raise ApiError(503, "service_unavailable", "The database is unavailable.")
      return pool
  ```
- **Why it matters:** Workspace authorization, the most security-relevant dependency, lives in the 417-line provider-settings module, so a settings change ripples into every router's imports. Routers depend on each other instead of being siblings, and the pool is typed Any wherever it is used.
- **Recommendation:** Create api/dependencies.py holding current\_workspace, require\_owner, require\_ready, provider\_settings and a typed database dependency (a Protocol with connection()). Each \*\_routes module then imports only dependencies, errors and security. Move budget\_error to errors.py.
- **Rule check:** Per-operation session and workspace checks stay, since every route still depends on current\_workspace, and require\_internal stays on every router.
- **Verification:** confirmed. 12 routers import from settings\_routes (approval, artifact, event, expert, improvement, memory, operation, routine, run, search, tool, workflow); \_pool is defined in exactly the 10 listed modules; settings\_routes.py is 417 lines and app.py:30-32 declares only open and close. XDUP-20 reports the copied aliases from the duplication side.

```text
api/dependencies.py: current_workspace, require_owner, require_ready, provider_settings, database() -> ConnectionPool (a Protocol with connection())
api/errors.py: budget_error and the other shared mappers
*_routes.py: import dependencies only; no _pool copies and no router-to-router imports
```

### <a id="xmod-13"></a>XMOD-13: The service layout and DH-03 disagree in five places

- **Severity** medium · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [PRD-Development-Harness.md:60](../../../../PRD-Development-Harness.md#L60): src/autobots/{api,domain,application,adapters,workers,graphs,contracts}/
  - [PRD-Development-Harness.md:54](../../../../PRD-Development-Harness.md#L54): scripts/db/
  - [PRD-Development-Harness.md:63](../../../../PRD-Development-Harness.md#L63): packages/db-types/ described as a boundary
  - [CODEBASE.md:25](../../../../CODEBASE.md#L25): documents the seven packages that actually exist
  - [services/agent/src/autobots/application/goal_loop.py:208-246](../../../../services/agent/src/autobots/application/goal_loop.py#L208): the Deep Agents wiring DH-03 places in graphs/
  - [services/agent/src/autobots/operations/worker.py:1](../../../../services/agent/src/autobots/operations/worker.py#L1): the worker DH-03 places in workers/
  - [scripts/persistent_install.py:395](../../../../scripts/persistent_install.py#L395): the persistent install launches autobots.operations.worker
- **Evidence:** DH-03 lists api, domain, application, adapters, workers, graphs and contracts. The code has api, domain, application, adapters, contracts, operations and persistence. (1) workers/ is absent: the process is operations/worker.py, and its logic is in application/worker\_inference.py and worker\_leases.py. (2) graphs/ is absent: build\_stage and create\_deep\_agent are in goal\_loop.py:208-246, and the middleware and checkpointer are in adapters/ (loop\_middleware, tool\_middleware, checkpoints, result\_stream). (3) operations/ and (4) persistence/ are not in DH-03. (5) scripts/db/ is absent: app\_db.py and disposable\_db.py sit in a flat scripts/ with 26 other scripts. DH-03 also omits tests/db, tests/web, tests/faults, tests/qualification and tests/toolchain, and nothing imports packages/db-types.
- **Why it matters:** Rules, skills and reviewers that follow DH-03 look for directories that don't exist (see XMOD-04), and new code has no agreed home for graph wiring or worker composition.
- **Recommendation:** For workers/, operations/, scripts/db/ and the test directories, change the document. operations/worker.py is launched by Makefile:166, the persistent install and four other scripts; app\_db is named in 117 tracked files (24 outside docs/ and openspec/) and disposable\_db in 47 (21). Describe db-types as an exposure and drift artifact. For graphs/, change the code: when goal\_loop is split, put build\_stage and the agent middleware there, which also gives the model-gateway rule a real target. Decide persistence/ together with XMOD-10.
- **Rule check:** DH-03 is an approved PRD, so amending it is the user's decision, recorded under docs/engineering/decisions/; no decision in 0001-0026 governs the package layout. Moves must keep `python -m` entry paths or ship shims, and must not change what checkpoints serialize.
- **Verification:** revised. DH-03's list (PRD-Development-Harness.md:54-63) checked against CODEBASE.md:25 and the tree; a grep of docs/engineering/decisions finds no decision on the layout. The script reference counts (91 and 39) could not be reproduced and are replaced with git grep -l counts; .claude/skills/autobots-model-gateway/SKILL.md:8 also names graphs/\*\*.

```text
DH-03 amendment (user decision): src/autobots/{api,domain,application,adapters,contracts,graphs,operations,persistence}/, where operations = process entry points, operator commands and paid qualification; scripts/ stays flat, with app_db.py and disposable_db.py as the target-checked database operations; tests/{harness,db,web,faults,qualification,toolchain}/
Code: graphs/stage.py (build_stage, SummarizationOff), graphs/middleware.py (from adapters/loop_middleware.py and tool_middleware.py), graphs/checkpoints.py
```

### <a id="xmod-10"></a>XMOD-10: contracts imports api and persistence, and persistence/ holds one row type that its only caller bypasses

- **Severity** low · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/contracts/export.py:9](../../../../services/agent/src/autobots/contracts/export.py#L9): from autobots.api.app import create\_app: the service's only upward import
  - [services/agent/src/autobots/contracts/adapters.py:3-5](../../../../services/agent/src/autobots/contracts/adapters.py#L3): row-to-domain-to-DTO mapper importing persistence.rows
  - [services/agent/src/autobots/persistence/rows.py:8-20](../../../../services/agent/src/autobots/persistence/rows.py#L8): the whole persistence layer: one TypedDict
  - [services/agent/src/autobots/application/run_projection.py:119-120](../../../../services/agent/src/autobots/application/run_projection.py#L119): rebuilds RunRow from a tuple under a type: ignore
  - [scripts/generate_contracts.py:98](../../../../scripts/generate_contracts.py#L98): runs python -m autobots.contracts.export
- **Evidence:** Only 2 of the 27 contract modules import outside pydantic, contracts and domain: export.py:9 and adapters.py:5. persistence/ is a single 12-field TypedDict, and its only production use rebuilds it from a tuple and silences the type:
  ```
  return run_summary_from_domain(run_from_row(dict(zip(_NAMES, row[:-1], strict=True))))  # type: ignore[arg-type]
  ```
  Everywhere else rows are read by position: 269 accesses of the form `row[N]` (grep for `*row[0-9]`) in application, api and adapters, with more under other names such as found[0]. packages/db-types generates row types only for TypeScript, and no package consumes it. contracts/adapters.py also shares its name with the adapters/ layer.
- **Why it matters:** No contract module imports export.py, so loading a DTO never loads the API. The cost is that contracts/ cannot be described or checked as 'imports only domain' without an exception, and the OpenAPI entry point sits where readers look for DTOs. The persistence package suggests typed rows while SQL results stay untyped tuples, and its one type is silenced at its only use.
- **Recommendation:** Move export.py to api/openapi\_export.py, updating scripts/generate\_contracts.py:98 and services/agent/tests/test\_contracts.py:13; the drift check proves the artifact is unchanged. Move the mapper out of contracts and give it a name other than 'adapters'. Then decide what persistence/ is for: either the home of row mappers for the busiest tables, with the database rule glob pointing at it, or removed.
- **Rule check:** contracts rule: generation stays offline (create\_app opens nothing), and generated artifacts are regenerated and compared, never hand-edited.
- **Verification:** revised. Both imports, the type: ignore at run\_projection.py:120 and the only two references to the export module (generate\_contracts.py:98, test\_contracts.py:13) confirmed. Severity lowered from medium to low and impact corrected: export.py is a `python -m` entry that no contract module imports, so the upward edge never loads at DTO import time. Positional access recounted as 269 `row[N]`, not 'at least 286'.

```text
api/openapi_export.py: openapi_document(), main() (python -m autobots.api.openapi_export)
persistence/runs.py: RunRow, run_from_row(), run_summary_from_domain()
contracts/: imports only pydantic, contracts.* and domain.*, enforced by the layering test
```

### <a id="xmod-12"></a>XMOD-12: operations/ mixes the worker, shared logging, seeding, paid trials and a test double, and inner layers import it

- **Severity** low · **Dimension** structure · **Effort** M · **Risk** low · **Occurrences** 8
- **Where:**
  - [services/agent/src/autobots/operations/logs.py:1](../../../../services/agent/src/autobots/operations/logs.py#L1): structured logging and the tracing guard, a leaf concern
  - [services/agent/src/autobots/application/goal_loop.py:89](../../../../services/agent/src/autobots/application/goal_loop.py#L89): application imports operations.logs (also operations.py:23, retention.py:11, routines.py:35, worker\_inference.py:61)
  - [services/agent/src/autobots/adapters/loop_middleware.py:66](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L66): adapters import operations.logs (also result\_stream.py:21)
  - [services/agent/src/autobots/application/cronjob_tool.py:38-42](../../../../services/agent/src/autobots/application/cronjob_tool.py#L38): application lazily imports operations.worker
  - [services/agent/src/autobots/operations/fake_stream.py:1-3](../../../../services/agent/src/autobots/operations/fake_stream.py#L1): fake-transport helper used only by tests and qualifiers
  - [services/agent/src/autobots/operations/route_qualification.py:1-3](../../../../services/agent/src/autobots/operations/route_qualification.py#L1): 'Paid qualification of one OpenRouter route'
  - [Makefile:166](../../../../Makefile#L166): launches python -m autobots.operations.worker
- **Evidence:** The 8 modules are: the worker process (worker.py); operator commands (bootstrap\_owner.py, concept\_seed.py); logging and the tracing guard (logs.py); paid live trials (route\_qualification.py, reasoning\_trial.py, browse\_trial.py); and a streaming fake used only by tests and qualifiers (fake\_stream.py). Inner layers import operations 8 times: 7 imports of logs from application and adapters, plus the lazy import of operations.worker at cronjob\_tool.py:40, which closes the cycle cronjob\_tool -> worker -> goal\_loop -> cronjob\_tool.
- **Why it matters:** Logging is a leaf concern, but here it ties application and adapters to the package that also holds the process entry and paid code, so the rule 'operations sits at the edge' can't be checked. Test support also ships inside the production package without being marked as such.
- **Recommendation:** Move logs.py to a leaf module and fake\_stream.py to a testing module. Moving logs.py also touches six code references outside the package (scripts/qualify\_operations.py, services/agent/tests/test\_final\_review.py, test\_operations.py and test\_worker\_inference.py, tests/db/operations\_worker.py and tests/db/verification\_check.py) and the operations runbook, so update them in the same change or keep a re-export in operations/logs.py for a while. Inject the credential check into cronjob\_tool when the registry is built, so application never imports operations. Leave the command modules where they are: Makefile:166, scripts/persistent\_install.py:395 and :629, and four other scripts launch the worker, and route\_qualification is a documented command.
- **Rule check:** Paid trials stay explicit and unchanged. forbid\_remote\_tracing keeps its behavior and call sites, so there is still no hosted tracing. Entry module paths stay stable for the persistent install.
- **Verification:** revised. Confirmed the 8 inner-layer imports (7 of operations.logs, 1 lazy import of operations.worker) and that fake\_stream is used only by services/agent/tests/test\_worker\_inference.py and tests/db/product\_inference\_worker.py. Severity lowered from medium to low: logs.py is stdlib-only, so the edge is conceptual; the cronjob\_tool -> worker cycle is the substantive part and is planned under XMOD-01 and XMOD-09. Added the external references a move must update.

```text
autobots/logs.py: redact, JsonFormatter, configure_logging, log_event, forbid_remote_tracing, remote_tracing_disabled (stdlib only)
autobots/testing/fake_stream.py: stream_chunks for fake transports
operations/: worker, bootstrap_owner, concept_seed, route_qualification, reasoning_trial, browse_trial (entry points only)
application/cronjob_tool.py: cronjob_tool(credential_check), built by the registry composer with the worker's check
```

### <a id="xmod-15"></a>XMOD-15: contracts/tools.py is a hub for unrelated modules, and the contract model configs are copied

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/contracts/tools.py:12](../../../../services/agent/src/autobots/contracts/tools.py#L12): TOOL\_CONTRACT, imported by 10 other contract modules
  - [services/agent/src/autobots/contracts/tools.py:16-262](../../../../services/agent/src/autobots/contracts/tools.py#L16): built-in and GitHub tool argument models
  - [services/agent/src/autobots/contracts/tools.py:290-387](../../../../services/agent/src/autobots/contracts/tools.py#L290): catalog HTTP DTOs, followed by more tool models at 388-455
  - [services/agent/src/autobots/contracts/approvals.py:9](../../../../services/agent/src/autobots/contracts/approvals.py#L9): VIEW redefined here and in 8 other modules
  - [services/agent/src/autobots/contracts/primitives.py:9-10](../../../../services/agent/src/autobots/contracts/primitives.py#L9): STRICT\_CONTRACT lives here
- **Evidence:** contracts/tools.py (474 lines) interleaves 31 TOOL\_CONTRACT models for model-facing tool arguments with 8 STRICT\_CONTRACT catalog DTOs served over HTTP. Meanwhile the web, market, code, cronjob and browsing tool schemas each have their own module. 10 contract modules import contracts.tools only for TOOL\_CONTRACT, and `VIEW = ConfigDict(extra="forbid", frozen=True)` is defined identically in 9 modules (approvals, experts, improvements, memory, operations, routines, run\_workspace, search, workflows).
- **Why it matters:** An edit to the HTTP catalog view lands in a file of GitHub argument schemas. The two audiences, OpenAPI consumers and model tool calls versioned by TOOL\_VERSIONS, can't be told apart by file location.
- **Recommendation:** Put the three shared configs in contracts/primitives.py. Split contracts/tools.py into a tool\_catalog module for the HTTP DTOs and per-family tool schema modules, matching web\_tools.py and market\_tools.py.
- **Rule check:** contracts rule (generator ownership): contracts/generated/ must stay byte-identical, which scripts/generate\_contracts.py's drift check proves. Model names and schemas don't change.
- **Verification:** confirmed. Counted model\_config lines in contracts/tools.py: 31 TOOL\_CONTRACT and 8 STRICT\_CONTRACT models, plus GrantedTo and ToolGrants with an inline config; 10 modules import TOOL\_CONTRACT from it and VIEW is defined identically in the 9 named modules.

```text
contracts/primitives.py: STRICT_CONTRACT, VIEW, TOOL_CONTRACT
contracts/tool_catalog.py: FieldDescriptor ... ToolCatalog, ToolVersions, GrantedTo, ToolGrants
contracts/builtin_tools.py and contracts/github_tools.py: tool input and output models
```

### <a id="xmod-16"></a>XMOD-16: Three BFF routes duplicate paths the /api/v1 catch-all already forwards

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 15
- **Where:**
  - [apps/web/app/api/settings/[...path]/route.ts:7-16](../../../../apps/web/app/api/settings/[...path]/route.ts#L7): forwards /api/settings/\* to /v1/settings/\*, without the query string
  - [apps/web/app/api/v1/[...path]/route.ts:7-17](../../../../apps/web/app/api/v1/[...path]/route.ts#L7): forwards every /api/v1/\* path, settings included, with its query
  - [apps/web/app/api/models/route.ts:5-7](../../../../apps/web/app/api/models/route.ts#L5)
  - [apps/web/app/api/runs/intent/route.ts:5-7](../../../../apps/web/app/api/runs/intent/route.ts#L5): no component calls it; only a browser test does
  - [apps/web/components/model-policy-panel.tsx:136-137](../../../../apps/web/components/model-policy-panel.tsx#L136): uses the older namespace
  - [.claude/rules/model-gateway.md:6](../../../../.claude/rules/model-gateway.md#L6): scopes the older settings route
- **Evidence:** The settings, models and runs/intent routes were added in US-3.2, after the catch-all, which has forwarded every /v1 path since US-2.5 (git log --diff-filter=A); US-5.3 later moved it onto lib/bff.ts. Components use the older paths 15 times in 5 files (model-policy-panel 4, provider-settings-panel 5, keys-and-vars-panel 3, run-disclosure 2, goal-composer 1). /api/runs/intent has no component caller (apps/web/tests/browser/saved-choice.spec.ts:56 uses it). The settings catch-all also drops the query string, which the v1 catch-all forwards.
- **Why it matters:** The browser uses two URL schemes for one API, and three extra route files have to stay in step with lib/bff.ts.
- **Recommendation:** Use /api/v1 everywhere, delete the three routes, and update the model-gateway rule glob and the browser test in the same change.
- **Rule check:** nextjs rule: every operation still goes through lib/bff.ts forward, so auth and CSRF checks are unchanged. The model-gateway rule's web glob moves to the remaining settings code.
- **Verification:** revised. The duplicate forwarding and the 15 uses in 5 components are confirmed. The history claim was wrong: the catch-all came first (US-2.5) and the three routes were added in US-3.2; corrected. Noted that the settings route drops query strings, so moving to /api/v1 also removes that difference.

### <a id="xmod-17"></a>XMOD-17: Two CredentialCheck aliases with different signatures name the same concept

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/application/cronjob_tool.py:35](../../../../services/agent/src/autobots/application/cronjob_tool.py#L35): Callable[[Any, UUID], Awaitable[str]]
  - [services/agent/src/autobots/application/routines.py:38](../../../../services/agent/src/autobots/application/routines.py#L38): Callable[[UUID], Awaitable[str]]
  - [services/agent/src/autobots/operations/worker.py:190](../../../../services/agent/src/autobots/operations/worker.py#L190): first shape, spelled inline (again at :230)
  - [services/agent/src/autobots/application/cronjob_tool.py:143](../../../../services/agent/src/autobots/application/cronjob_tool.py#L143): ready closure converting one shape to the other (worker.py:203 does the same)
- **Evidence:** The two aliases share a name but take different arguments, and both the worker and cronjob\_tool write a local closure to convert between them.
- **Why it matters:** A function's parameter name doesn't tell the reader which check it expects. mypy catches mismatches, but each new caller writes another conversion closure.
- **Recommendation:** Give the two shapes different names and define them once beside run\_intent in application/provider\_settings.py (for example WorkspaceReadiness for Callable[[UUID], Awaitable[str]] and ConnectionReadiness for Callable[[Any, UUID], Awaitable[str]]), and use the named alias in worker.py instead of the inline Callable. Keep the small closures that bind a connection: they are the honest conversion between the two.
- **Rule check:** none
- **Verification:** revised. Aliases at cronjob\_tool.py:35 and routines.py:38, inline shapes at worker.py:190 and :230, and closures at cronjob\_tool.py:143 and worker.py:203 confirmed. Recommendation narrowed to naming, since a single Protocol would still need the connection-binding closures.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| XMOD-14 | Tool implementations are spread over 17 modules in two layers, named four different ways | Mostly taste, and subsumed by XMOD-01. The counts hold (31 ToolDefinition constructions in 17 modules), but the split follows a rule: external-provider clients sit in adapters/, database-backed and feature tools beside their feature in application/. XMOD-01's registry module becomes the single index of tools, and the proposed package move is churn with checkpoint-path risk that the finding itself defers. The stale docstring at application/tools.py:1 ('Nothing else exists' above five tools) is a single-file comment issue for the py-tools area. |

16 findings were kept, 9 of them revised, and 1 rejected.

## Not covered

This lens covers patterns across the 545 in-scope files. I opened the code behind every cited pattern but did not read every file in full; the area reviews cover single files. Large modules I read only in part include goal\_loop, workflow\_runner, tool\_catalog, tool\_gateway, approvals, run\_routes, settings\_routes, operations/worker, loop\_middleware, the GitHub adapters, goal-composer and run-controls. The Python import analysis is static (ast): it counts module-level and function-level imports, does not run the code, and would miss importlib or other dynamic imports. The 110-module closure counts module-level imports only. The TypeScript analysis covers apps/web app, components and lib with grep; package internals and test files were not graphed. I counted dependencies inside tests/ and scripts/ (sys.path inserts, private-name imports) but did not map them module by module. I did not check whether any LangGraph checkpoint stores classes by import path, so the module moves proposed here carry that open question. The project's PreToolUse hook refused one read-only grep because its pattern named the provider master key file; I reran it on the constant name DEFAULT\_KEY\_FILE. Per the ground rules, I did not rerun verification profiles or any runtime check, and the only file written is scratch output in .checks/reviews/review-2026-11-12-09-52-30/sweep-boundaries/py\_edges.tsv.
