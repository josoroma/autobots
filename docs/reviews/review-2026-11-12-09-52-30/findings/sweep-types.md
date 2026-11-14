# Lens: types and contracts at boundaries

The HTTP contract is the best-defended boundary in the repository. All 247 Pydantic contract models refuse unknown fields. The contract primitives match JavaScript's integer and timestamp limits. The generated TypeScript parsers really validate, 25 component files parse their GET replies with them, and the web code has no explicit any, no ts-ignore and no eslint-disable. Types stop protecting the code at the other boundaries. In the browser, writes bypass the generated client because its runtime discards the error envelope and status. As a result, 29 fetched-JSON replies are cast and 28 request bodies are built without the generated request types. The generator also drops the value types of 10 map fields, and the runtime never checks those values. In the service, the SQL boundary is Any: 225 `connection: Any` annotations, 178 positional row reads and one row type. Persisted JSON (events, role-policy snapshots and idempotency receipts) is written and read as untyped dicts with silent fallbacks. State vocabularies travel as str and are bridged by 12 `type: ignore[arg-type]` and 2 casts. Provider replies, the LangChain model hooks and three of the five SSE frame kinds are read as Any. Another 42% of the in-scope Python (scripts, repository tests and hooks) is never type-checked, though most of it is annotated. Pydantic models suit JSON that crosses a process or release boundary (persisted documents, provider replies). TypedDict rows suit SQL reads. Frozen dataclasses suit parsed domain values such as routine triggers and workflow block configs. This is a static review, so it establishes no runtime behavior and no H1 or product acceptance. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | DH-06's explicit parsing holds for GET reads and every API request body, but 29 cast replies, untyped SQL rows and 42% of Python outside mypy miss it, and no lint rule covers assertions or explicit Any. |
| modules | 3 | The contracts, domain and application split is clear. But the generated client is bypassed for writes, and vocabularies are re-declared in each layer. |
| approach | 3 | Generate, then parse, is the right approach and reads use it. Writes, SSE frames, persisted JSON and provider replies fall back to dicts and casts. |
| comments | 4 | Boundary comments explain intent well (runtime.ts, primitives.py, adapters.py). A few comments stand in for types, and the 18 src suppressions give no reason. |
| types | 3 | The HTTP contract pipeline is a model to copy. SQL rows, persisted JSON, provider replies, browser writes and typed maps fall outside it. |
| errors | 3 | The API has one safe error envelope. On the web it is cast in 19 places, and the generated runtime turns every non-2xx reply into a ContractError, so contract drift looks like an outage. |
| tests | 3 | The shared cross-language fixtures are exemplary but cover 4 of 170 schemas. Browser specs read API JSON through casts, and test doubles need 21 arg-type suppressions. |
| maintainability | 3 | Changing a contract is safe for reads but risky for writes, SQL row shapes, persisted documents and string vocabularies, where nothing fails at compile time. |

## Strengths

- **Reads are parsed with the generated validators.** 25 component files call 32 distinct generated parsers on fetched replies, GET replies among them, for example `parseRunWorkspace(await reply.json())` at apps/web/components/run-workspace.tsx:194. apps/web/components/tool-catalog.tsx:156 `useLoaded(path, parse)` couples fetch, parser and a `loading | unavailable | ready` union. apps/web/components/tool-uses.tsx:127 types the body `unknown` before parsing it. Sources: [apps/web/components/run-workspace.tsx:194](../../../../apps/web/components/run-workspace.tsx#L194), [apps/web/components/tool-catalog.tsx:156](../../../../apps/web/components/tool-catalog.tsx#L156), [apps/web/components/tool-uses.tsx:127](../../../../apps/web/components/tool-uses.tsx#L127).
- **A real runtime validator behind the generated types.** packages/api-client/src/runtime.ts checks UUID and offset date-time formats, safe integers, enums, anyOf and `additionalProperties: false`. packages/api-client/tests/contract.test.ts:22 asserts that a cast cannot stand in for validation, and scripts/generate\_contracts.py `check` detects drift between the Pydantic models and the generated client. Sources: [packages/api-client/tests/contract.test.ts:22](../../../../packages/api-client/tests/contract.test.ts#L22).
- **Cross-language boundary fixtures.** contracts/fixtures/boundary-cases.json (29 cases) runs in both services/agent/tests/test\_contracts.py:30-36 and packages/api-client/tests/contract.test.ts:8-20. contracts/fixtures/credential-precedence.json does the same for key precedence (apps/web/tests/unit/credential-precedence.test.ts:9). Sources: [services/agent/tests/test_contracts.py:30-36](../../../../services/agent/tests/test_contracts.py#L30), [packages/api-client/tests/contract.test.ts:8-20](../../../../packages/api-client/tests/contract.test.ts#L8), [apps/web/tests/unit/credential-precedence.test.ts:9](../../../../apps/web/tests/unit/credential-precedence.test.ts#L9).
- **Contract primitives aligned with JavaScript.** services/agent/src/autobots/contracts/primitives.py:10-32 defines STRICT\_CONTRACT, MAX\_SAFE\_INTEGER, MicroUsd and UtcTimestamp, whose JSON Schema pattern the TypeScript validator then enforces. Every one of the 247 contract models sets extra="forbid", so a private field cannot leak through a DTO. Sources: [services/agent/src/autobots/contracts/primitives.py:10-32](../../../../services/agent/src/autobots/contracts/primitives.py#L10).
- **Explicit row, domain and DTO mapping.** services/agent/src/autobots/contracts/adapters.py:8-42 has `run_from_row` (an unknown stored status raises) and `run_summary_from_domain`, which names each public field so a new domain field stays private by default. This is the pattern to spread to the 178 positional row reads. Sources: [services/agent/src/autobots/contracts/adapters.py:8-42](../../../../services/agent/src/autobots/contracts/adapters.py#L8).
- **One safe error envelope on the API.** services/agent/src/autobots/api/errors.py:24-40 maps ApiError, request validation, HTTP and unexpected errors to ErrorResponse without echoing input. 78 of 80 routes declare a response\_model, and no route reads `request.json()` by hand. Sources: [services/agent/src/autobots/api/errors.py:24-40](../../../../services/agent/src/autobots/api/errors.py#L24).
- **No escape hatches, strict compilers.** apps/web has 0 explicit `any`, 0 `@ts-ignore` or `@ts-expect-error` and 0 `eslint-disable`. apps/web/tsconfig.json:7-9 and packages/api-client/tsconfig.json enable strict, noUncheckedIndexedAccess and exactOptionalPropertyTypes. mypy strict covers services/agent src and tests (services/agent/pyproject.toml:49-52), and all 18 `type: ignore` in src name an error code. Sources: [apps/web/tsconfig.json:7-9](../../../../apps/web/tsconfig.json#L7), [services/agent/pyproject.toml:49-52](../../../../services/agent/pyproject.toml#L49).
- **Untrusted input typed as object or unknown, then narrowed.** .claude/hooks/dispatch.py:46-55 `resolve_path(root, raw: object)` checks type, length and NUL bytes before use. apps/web/app/api/workspace/route.ts:35-38 reads the body as `unknown` and narrows it with the `isWorkspaceId` type guard (apps/web/lib/workspace-choice.ts:13). Sources: [.claude/hooks/dispatch.py:46-55](../../../../.claude/hooks/dispatch.py#L46), [apps/web/app/api/workspace/route.ts:35-38](../../../../apps/web/app/api/workspace/route.ts#L35), [apps/web/lib/workspace-choice.ts:13](../../../../apps/web/lib/workspace-choice.ts#L13).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XTYP-01](#xtyp-01) | high | types | Browser writes bypass the generated client: request bodies are hand-built and replies are cast | L | medium |
| [XTYP-02](#xtyp-02) | high | types | Generated map types and runtime checks drop value schemas | S | medium |
| [XTYP-03](#xtyp-03) | high | types | Persisted JSON documents have no schema shared by writer and reader | M | high |
| [XTYP-04](#xtyp-04) | high | types | The SQL boundary is untyped: Any connections and positional rows | L | medium |
| [XTYP-14](#xtyp-14) | high | errors | A contract mismatch on a read looks like an outage | M | medium |
| [XTYP-05](#xtyp-05) | medium | types | State vocabularies travel as plain str and are bridged with suppressions | M | medium |
| [XTYP-06](#xtyp-06) | medium | types | Web label maps are keyed by string and duplicated; the generated enum types go unused | S | low |
| [XTYP-07](#xtyp-07) | medium | types | Event-stream frames are a contract that nothing declares | S | medium |
| [XTYP-08](#xtyp-08) | medium | types | Open dictionaries in public contracts are validated by hand and re-read by string keys | M | medium |
| [XTYP-09](#xtyp-09) | medium | types | External provider replies are read as Any and coerced field by field | M | medium |
| [XTYP-10](#xtyp-10) | medium | types | Public timestamps come in three forms, and only one is checked for UTC | S | medium |
| [XTYP-11](#xtyp-11) | medium | types | The LangChain model hooks on the paid path are typed Any | S | low |
| [XTYP-12](#xtyp-12) | medium | standards | 42% of the in-scope Python is never type-checked, though most of it is annotated | M | low |
| [XTYP-13](#xtyp-13) | medium | tests | Shared cross-language fixtures cover 4 of 170 schemas | M | low |
| [XTYP-15](#xtyp-15) | low | comments | Comments stand in for types, and suppressions give no reason | S | low |
| [XTYP-16](#xtyp-16) | low | duplication | The lax contract config is copied into 18 places | S | low |
| [XTYP-17](#xtyp-17) | low | tests | Test doubles need suppressions because collaborators are typed as concrete classes | S | low |
| [XTYP-18](#xtyp-18) | low | tests | Browser specs read API JSON through casts and local shapes | S | low |

### <a id="xtyp-01"></a>XTYP-01: Browser writes bypass the generated client: request bodies are hand-built and replies are cast

- **Severity** high · **Dimension** types · **Effort** L · **Risk** medium · **Occurrences** 29
- **Where:**
  - [apps/web/components/goal-composer.tsx:311](../../../../apps/web/components/goal-composer.tsx#L311): RunAccepted cast to { run\_id: string }; parseRunAccepted exists
  - [apps/web/components/experts-panel.tsx:97](../../../../apps/web/components/experts-panel.tsx#L97): SessionView cast to { id: string } and pushed to /sessions/${id}; same cast at :144, expert-editor.tsx:201 and goal-composer.tsx:273
  - [apps/web/components/session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65): third hand-built POST /v1/runs, with its own cast
  - [apps/web/components/continue-run.tsx:53](../../../../apps/web/components/continue-run.tsx#L53): RunAccepted cast with replayed?: boolean
  - [apps/web/components/workflow-editor.tsx:254-258](../../../../apps/web/components/workflow-editor.tsx#L254): unvalidated error body spread into a typed result: return { view: null, ...failure }
  - [apps/web/components/run-controls.tsx:39-42](../../../../apps/web/components/run-controls.tsx#L39): cast error message returned for display
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): non-2xx throws ContractError and never reads the ErrorResponse body
  - [apps/web/lib/csrf-fetch.ts:6](../../../../apps/web/lib/csrf-fetch.ts#L6): the BFF's own CSRF reply is cast
- **Evidence:** ESLint with assertionStyle never reports 44 type assertions in non-test web code. 29 of them sit on fetched JSON: 19 error envelopes in 15 files, 7 success bodies, 2 on the run event stream and page, and the CSRF reply. The other 15 are 5 casts that compensate for weak generated map types, 4 DOM, event or URL narrowings, 5 safe narrowings of unknown input and 1 fetch-wrapper type; the 4 non-null assertions are harmless. 28 request bodies in 18 files are `body: JSON.stringify({...})`. grep finds 0 references to the generated RunRequest, SessionCreate, ApprovalDecision, ExpectedVersion or ModelPolicyUpdate types. Only 4 of the 78 generated operations are used, all server-side in lib/service-status.ts.
  ```
  const accepted = (await reply.json()) as { run_id: string };      // goal-composer.tsx:311
  const failure = (await reply?.json().catch(() => null)) as {      // goal-composer.tsx:318
    code?: string; message?: string; } | null;
  if (!response.ok) {                                               // runtime.ts:168-170
    throw new ContractError(path, `request failed with status ${response.status}`);
  ```
- **Why it matters:** A renamed or removed response field compiles and fails late. A SessionView without `id` sends the user to /sessions/undefined from 4 call sites, a non-string `message` reaches React as a child, and workflow-editor spreads arbitrary keys over `view`. Request drift is invisible to tsc. It surfaces as a 422 `invalid_request`, which goal-composer.tsx:331 reports as a refused model or request. The cause is structural: the generated runtime discards the error envelope and the status and takes no per-call headers such as Idempotency-Key. So every component re-implements the write path: three times for POST /v1/runs and four times for POST /v1/sessions.
- **Recommendation:** Make the generated client the only path to the API. (1) In runtime.ts, read the body of a non-2xx reply, parse it as ErrorResponse and throw a typed ApiError {status, code, message}. Keep ContractError for shape mismatches only, and accept per-call headers and a signal. (2) Have scripts/generate\_contracts.py pass those options through, then regenerate. (3) Add a browser client in apps/web/lib with baseUrl "/api" and the CSRF header on mutations. Move the 3 run-admission and 4 session-creation calls first, then the rest. Type BFF-only bodies and envelopes (/api/session, /api/workspace, /api/csrf, bff.ts safeError) with a small parser or `satisfies ErrorResponse`. (4) Ratchet with `@typescript-eslint/consistent-type-assertions: [error, {assertionStyle: never}]` for components and lib, using a per-file baseline, and add a ts-reset-style declaration so `Response.json()` returns `Promise<unknown>`.
- **Rule check:** nextjs.md and DH-06 require generated API types with runtime parsing at untrusted boundaries and forbid blanket type assertions that conceal contract mismatches. contracts.md says generated TypeScript consumes the Pydantic contract. generated.ts is regenerated by scripts/generate\_contracts.py, never edited by hand. BFF CSRF checks stay, and server idempotency remains the correctness mechanism. continue-run's handling of 5xx as an unknown outcome is kept through ApiError.status.
- **Verification:** confirmed. Recounted from the saved ESLint report: 44 non-test assertions, 29 of them on fetched JSON (19 error envelopes in 15 files, 7 success bodies, 2 on the stream and event page, 1 CSRF reply). 28 `body: JSON.stringify` in 18 files, and no web reference to RunRequest, SessionCreate, ApprovalDecision, ExpectedVersion, ModelPolicyUpdate or parseRunAccepted. Only lib/service-status.ts calls generated operations (4 of 78). XWEB-01 and XMOD-03 report the same gap from their lenses.

```text
// packages/api-client/src/runtime.ts
export class ApiError extends Error { status: number; code: string }   // a refusal: the parsed ErrorResponse
export class ContractError extends Error { path: string }               // a shape mismatch only
export interface CallOptions { headers?: Record<string, string>; signal?: AbortSignal }
export async function requestJson(options, method, path, body?, call?: CallOptions): Promise<unknown>
// apps/web/lib/api.ts: browserClient(): ClientOptions with baseUrl "/api" and a CSRF-aware fetch
// goal-composer.tsx
const accepted = await admitRun(browserClient(), body satisfies RunRequest, { headers: { "Idempotency-Key": key } });
// catch (error) { if (error instanceof ApiError) setOutcome(OUTCOMES[error.code] ?? "error"); }
```

### <a id="xtyp-02"></a>XTYP-02: Generated map types and runtime checks drop value schemas

- **Severity** high · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 10
- **Where:**
  - [scripts/generate_contracts.py:46-47](../../../../scripts/generate_contracts.py#L46): any object without properties becomes Record&lt;string, unknown&gt;
  - [packages/api-client/src/runtime.ts:71-78](../../../../packages/api-client/src/runtime.ts#L71): extra keys are refused only when additionalProperties is false; a value schema is never checked
  - [apps/web/components/model-policy-panel.tsx:130](../../../../apps/web/components/model-policy-panel.tsx#L130): role\_overrides cast to Record&lt;string, string&gt;; also :55, and :251 casts a value
  - [apps/web/components/expert-editor.tsx:116](../../../../apps/web/components/expert-editor.tsx#L116): role\_bindings cast
  - [apps/web/components/experts-panel.tsx:331](../../../../apps/web/components/experts-panel.tsx#L331): role\_bindings cast
  - [apps/web/components/workflow-monitor.tsx:175](../../../../apps/web/components/workflow-monitor.tsx#L175): String(view.block\_versions[...]) coerces unknown
  - [apps/web/components/approvals-panel.tsx:70-72](../../../../apps/web/components/approvals-panel.tsx#L70): approval scope tool versions interpolated as unknown in the review text
- **Evidence:** Walking `schemas` in generated.ts finds 10 object fields whose values have a schema. ApprovalScope.tools and RetentionApplied.refused have integer values. ExecutionBinding, ExecutionView and WorkflowVersionView.block\_versions, ExpertBinding.role\_bindings and RouteOption.role\_bindings have string values. ExpertConfig.role\_bindings and ModelPolicyState and ModelPolicyUpdate.role\_overrides have ModelProfileId values. All 10 generate as Record&lt;string, unknown&gt;, and no value is validated. runtime.ts also ignores minItems (4 uses) and maxItems (15 uses).
  ```
  if kind == 'object' and 'properties' not in schema:          # generate_contracts.py:46-47
      return 'Record<string, unknown>'
  } else if (schema.additionalProperties === false) {         // runtime.ts:75
  setOverrides(next.role_overrides as Record<string, string>);  // model-policy-panel.tsx:130
  ```
- **Why it matters:** The generator's docstring promises that every parse function checks at runtime, but for these fields it does not. Five casts and two String or template coercions paper over the gap. If role\_overrides values changed shape, parseModelPolicyState would accept them. The policy form would then post them back and fail with a 422 far from the cause, and the approval review text would print "[object Object]" for a tool version.
- **Recommendation:** Emit Record&lt;string, T&gt; from additionalProperties schemas and validate each extra value against that schema in checkObject. Enforce minItems and maxItems. Make `generate_contracts.py check` fail when the schema uses a keyword that runtime.ts does not enforce, with annotation keywords allow-listed. Regenerate, then delete the 5 casts and 2 coercions. Add a valid:false boundary case with a non-profile role override.
- **Rule check:** contracts.md: generated TypeScript consumes the Pydantic contract, and TypeScript types do not validate JSON. The fix changes the generator and the hand-written runtime, then regenerates generated.ts. Decision 0015's immutable approval scope snapshot is only validated more strictly; its content does not change.
- **Verification:** confirmed. openapi.json has exactly 10 schema-valued additionalProperties, 4 minItems and 15 maxItems, and runtime.ts checks additionalProperties only when it is false and has no array-bound check. All 7 cited casts and coercions reproduce. Kept high, consistent with WSHL-01, which reports the validator gap from the web-shell area.

```text
# scripts/generate_contracts.py
if kind == 'object' and 'properties' not in schema:
    extra = schema.get('additionalProperties', True)
    return f'Record<string, {typescript_type(extra)}>' if isinstance(extra, Mapping) else 'Record<string, unknown>'
ENFORCED = {...}  # keywords runtime.ts implements; `check` fails on any other
// packages/api-client/src/runtime.ts, checkObject
else if (typeof schema.additionalProperties === "object") check(schemas, schema.additionalProperties, item, `${path}.${name}`);
```

### <a id="xtyp-03"></a>XTYP-03: Persisted JSON documents have no schema shared by writer and reader

- **Severity** high · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 34
- **Where:**
  - [services/agent/src/autobots/application/runs.py:80](../../../../services/agent/src/autobots/application/runs.py#L80): append\_event takes payload: dict[str, Any]; 12 call sites in 6 files build dict literals
  - [services/agent/src/autobots/application/tool_uses.py:147-157](../../../../services/agent/src/autobots/application/tool_uses.py#L147): tool.use.started written as a dict, though ToolUseStarted exists (contracts/runs.py:88)
  - [services/agent/src/autobots/application/run_projection.py:107](../../../../services/agent/src/autobots/application/run_projection.py#L107): a payload that fails RunEvent is dropped, with nothing logged
  - [apps/web/components/run-workspace.tsx:144-150](../../../../apps/web/components/run-workspace.tsx#L144): the browser drops any event that fails parseRunEvent, whether its type is known or not
  - [services/agent/src/autobots/application/runs.py:136-153](../../../../services/agent/src/autobots/application/runs.py#L136): role-policy snapshot written as a hand-built dict
  - [services/agent/src/autobots/application/worker_inference.py:114](../../../../services/agent/src/autobots/application/worker_inference.py#L114): a snapshot without 'routes' skips the frozen wire-identity check
  - [services/agent/src/autobots/application/runs.py:119](../../../../services/agent/src/autobots/application/runs.py#L119): idempotency receipt returned as dict[str, Any] and replayed by key
- **Evidence:** The count: 12 append\_event call sites in 6 files, 11 policy\_snapshot reads outside runs.py in 5 modules (frozen\_policy and SQL JSON paths), and 11 existing\_receipt replays that read the stored receipt by key, in 8 modules (14 calls in 9 modules in all).
  ```
  async def append_event(connection: Any, run_id: UUID, payload: dict[str, Any]) -> int:  # runs.py:80
      except ValidationError:                       # run_projection.py:107-108, project_event
          return None
      for name, route in ((snapshot or {}).get("routes") or {}).items():   # worker_inference.py:114
      result: dict[str, Any] = row[1]               # runs.py:119
      return AdmissionResult(UUID(existing["run_id"]), existing["version"], existing["status"], True)
  ```
- **Why it matters:** These three durable formats are contracts between modules and across releases, but only string keys connect each writer to its reader. A misspelled key in an event dict is stored durably. It is then filtered silently by project\_event and again by known() in the browser, so the timeline loses an entry with nothing logged. Renaming "routes" in \_snapshot would make frozen\_policy skip the check that keeps an admitted run on its frozen model, on the paid path. A receipt written by an earlier release and replayed after a lost reply raises KeyError, a 500 at exactly the moment the client retries.
- **Recommendation:** Give each persisted document one versioned model that writer and reader share. Build public event payloads with their contract models, for example ToolUseStarted(...).model\_dump(mode="json"); project\_event already validates the stored payload as RunEvent, so this moves that check to the writer. Give private payloads their own models, and keep the snapshot and receipt models in a persisted module of their own, apart from the DTOs. Add a PolicySnapshot model whose legacy omissions, such as `sources` before MD-02, are explicit per version instead of `.get(...) or {}`. Add one receipt model per operation, returned by existing\_receipt(..., kind). Keep project\_event's filter, but log the type and sequence (never the content) when it drops a known type. In the browser, skip unknown types quietly and report known types that fail. Add a test that runs every append\_event producer through RunEvent, and stored-document fixtures for each snapshot version.
- **Rule check:** contracts.md: version event envelopes and immutable model-policy snapshots. python-worker.md: persist outbox events and operation receipts. model-gateway.md: freeze wire identities at admission. Stored rows are read as they are, with legacy shapes accepted explicitly, and no migration is edited. Persisted, domain (RolePolicy) and public (EffectiveRolePolicy, RunEvent) types stay separate, and project\_event remains the one mapping to the public stream.
- **Verification:** revised. Counts redone: 12 append\_event calls in 6 files, 11 policy\_snapshot reads outside runs.py in 5 modules, and 14 existing\_receipt calls of which 11 index the receipt by key, so 34 sites, not 32. project\_event drops a ValidationError with nothing logged (run\_projection.py:107-108), and frozen\_policy skips the route check when 'routes' is absent (worker\_inference.py:114). The browser change keeps Decision 0017 Q13: unknown types are still skipped. XDUP-04 reports the snapshot readers from the duplication lens.

```text
# contracts/persisted.py: persisted documents, distinct from domain types and DTOs
class FrozenRoute(BaseModel): wire_id: str; canonical_id: str
class PolicySnapshot(BaseModel): version: int; bindings: dict[ModelRole, ModelProfileId]; sources: dict[ModelRole, BindingSource] = {}; routes: dict[ModelProfileId, FrozenRoute]
class AdmissionReceipt(BaseModel): run_id: UUID; version: int; status: RunStatus
DurablePayload = RunStatusChanged | ApprovalRequested | ToolUseStarted | ... | PrivatePayload
# application/runs.py
async def append_event(connection: SqlConnection, run_id: UUID, payload: DurablePayload) -> int
async def existing_receipt[T: BaseModel](connection, scope, fingerprint, kind: type[T]) -> T | None
# application/run_projection.py: on a dropped known type, log_event("event_not_projected", type=..., sequence=...)
```

### <a id="xtyp-04"></a>XTYP-04: The SQL boundary is untyped: Any connections and positional rows

- **Severity** high · **Dimension** types · **Effort** L · **Risk** medium · **Occurrences** 225
- **Where:**
  - [services/agent/src/autobots/api/app.py:30-32](../../../../services/agent/src/autobots/api/app.py#L30): the Pool Protocol has open() and close() but no connection()
  - [services/agent/src/autobots/api/run_routes.py:66-70](../../../../services/agent/src/autobots/api/run_routes.py#L66): \_pool(request) -&gt; Any, copied in 10 route modules
  - [services/agent/src/autobots/application/runs.py:316](../../../../services/agent/src/autobots/application/runs.py#L316): record\_transition(connection: Any, ..., previous: str, following: str, ...)
  - [services/agent/src/autobots/application/run_projection.py:519-520](../../../../services/agent/src/autobots/application/run_projection.py#L519): 16 unnamed columns mapped by index; tasks\_complete is row[10] and tasks\_total is row[9]
  - [services/agent/src/autobots/application/approvals.py:68](../../../../services/agent/src/autobots/application/approvals.py#L68): fetchone() indexed without a None check; 42 such sites in src
  - [services/agent/src/autobots/application/goal_loop.py:554](../../../../services/agent/src/autobots/application/goal_loop.py#L554): run status read back as a str
  - [services/agent/src/autobots/persistence/rows.py:8](../../../../services/agent/src/autobots/persistence/rows.py#L8): RunRow, the only row type in the service
  - [services/agent/src/autobots/application/run_projection.py:120](../../../../services/agent/src/autobots/application/run_projection.py#L120): RunRow's one consumer needs # type: ignore[arg-type] to build it
- **Evidence:** `grep -rn 'connection: Any' services/agent/src` finds 225 annotations in 42 files, which are 221 of ruff's 398 ANN401 hits. 339 lines in application/ call connection.execute on them. 178 lines in 41 application, api and operations files read rows by position, 42 sites index fetchone() directly, and persistence/rows.py holds one TypedDict.
  ```
  class Pool(Protocol):                       # api/app.py:30-32
      async def open(self) -> None: ...
      async def close(self) -> None: ...
  def _pool(request: Request) -> Any:         # run_routes.py:66, one of 10 copies
                  tasks_complete=int(row[10]),  # run_projection.py:519-520
                  tasks_total=int(row[9]),
  ```
- **Why it matters:** mypy strict passes the service while checking none of its SQL reads. Adding a column to \_LIST\_SELECT shifts 16 positional reads without an error. fetchone() on a missing row raises TypeError, which becomes a 500. Statuses come back as str and feed the arg-type suppressions in the finding on state vocabularies. Reviewers must count SELECT columns to check a mapping. Generated row types for the public schema already exist (packages/db-types), but only in TypeScript, and nothing consumes them.
- **Recommendation:** Type the boundary in three steps. (1) Define one narrow SqlConnection and SqlCursor Protocol in application, with no psycopg import, whose fetchone() returns `tuple[Any, ...] | None`. Add a `one()` helper that raises a typed not-found. Replace the 10 `_pool` copies with one typed dependency, and add connection() to the Pool Protocol. (2) Alias the columns of multi-column SELECTs and read them through per-query TypedDict rows in persistence/rows.py with psycopg's dict\_row or class\_row. Map each row explicitly, the way contracts/adapters.py maps RunRow. (3) Ratchet ruff ANN401 with per-file ignores for today's files, starting with api (16 hits) and domain (5).
- **Rule check:** python-worker.md and DH-06: keep application types separate from persistence and DTOs, and avoid broad Any and untyped dictionaries. Rows stay in persistence/rows.py and are mapped explicitly. SQL migrations keep owning the schema, and none is edited. Leases and fences are untouched.
- **Verification:** confirmed. 225 `connection: Any` in 42 files; a ruff ANN401 rerun gives 398 hits, 221 on parameters named connection, 16 in api/ and 5 in domain/. 339 connection.execute lines in application/, 178 positional row reads in 41 files, 42 `(await cursor.fetchone())[n]` sites and 10 \_pool copies; persistence/rows.py holds the one TypedDict. \_LIST\_SELECT has 16 columns read by index (run\_projection.py:510-525).

```text
# application/sql.py
class SqlCursor(Protocol):
    async def fetchone(self) -> tuple[Any, ...] | None: ...
    async def fetchall(self) -> list[tuple[Any, ...]]: ...
class SqlConnection(Protocol):
    async def execute(self, query: str, params: Sequence[object] | Mapping[str, object] = ...) -> SqlCursor: ...
    def transaction(self) -> AbstractAsyncContextManager[object]: ...
async def one(connection: SqlConnection, query: str, params: ...) -> tuple[Any, ...]  # raises NotFound, never None[0]
# persistence/rows.py: RunListRow(TypedDict), ApprovalListRow(TypedDict), ... read via dict_row, mapped like run_from_row
# api/dependencies.py: DbPool = Annotated[ConnectionPool, Depends(database_pool)]
```

### <a id="xtyp-14"></a>XTYP-14: A contract mismatch on a read looks like an outage

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 25
- **Where:**
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): an HTTP status failure is also thrown as ContractError
  - [apps/web/components/workflow-monitor.tsx:50-57](../../../../apps/web/components/workflow-monitor.tsx#L50): parseExecutionView failure becomes "reconnecting" and polling continues
  - [apps/web/components/home-activity.tsx:79](../../../../apps/web/components/home-activity.tsx#L79): parse inside a catch-all that sets failed
  - [apps/web/components/model-policy-panel.tsx:147](../../../../apps/web/components/model-policy-panel.tsx#L147): parse inside a catch-all that sets failed
  - [apps/web/components/tool-catalog.tsx:170](../../../../apps/web/components/tool-catalog.tsx#L170): parse failure becomes the unavailable state
  - [apps/web/components/run-workspace.tsx:194](../../../../apps/web/components/run-workspace.tsx#L194): refresh() lets a ContractError escape as an unhandled rejection
  - [apps/web/lib/service-status.ts:46](../../../../apps/web/lib/service-status.ts#L46): any failure becomes unavailable
- **Evidence:** In the 25 component files that call generated parsers, the parse runs inside catch-all handlers (89 `.catch(() =>` in components). These map any failure to the screen's unavailable or reconnecting state; this was checked in run-list, home-activity, model-policy-panel, workflow-monitor and tool-catalog. No web file references ContractError.
  ```
  const next = await reply.json().then(parseExecutionView).catch(() => null);  // workflow-monitor.tsx:50-53
  if (next === null) { setState("reconnecting"); }                           // :56-57
  throw new ContractError(path, `request failed with status ${response.status}`);  // runtime.ts:169
  ```
- **Why it matters:** The parsers detect drift, and the screens throw the detection away. The workflow monitor polls as "reconnecting" forever, and lists show their unavailable state. Nothing reaches the console, and runtime.ts names a 503 a ContractError. So neither a developer nor a browser test can tell drift from downtime.
- **Recommendation:** Split ApiError from ContractError in runtime.ts, as in the write-path finding. Give screens one helper that returns ready, unavailable or out\_of\_date. It logs a ContractError's schema and path (never values) with console.error, and the screen shows a distinct "out of date with the API" state. Start from tool-catalog.tsx's useLoaded.
- **Rule check:** nextjs.md requires explicit error, empty and loading states. service-status.ts keeps details on the server, and the browser log carries only a schema name and path, no response values.
- **Verification:** revised. Raised to high: the parsers detect drift and each screen checked discards it (catch-alls at home-activity.tsx:84, model-policy-panel.tsx:150, tool-catalog.tsx:172 and workflow-monitor.tsx:53), which is the rubric's 'hides contract drift at a trust boundary'; XERR-03 reports the same root at high. 25 component files call generated parsers, not 23; components hold 89 `.catch(() =>` handlers, and no web file references ContractError. Risk set to medium, since each screen's failure state changes and the contract test that pins ContractError for a failed status (contract.test.ts:33-36) changes with it. Added the target-shape sketch a high finding needs.

```text
// packages/api-client/src/runtime.ts
export class ApiError extends Error { status: number; code: string }   // a non-2xx reply, parsed as ErrorResponse
export class ContractError extends Error { path: string }               // a shape mismatch only
// apps/web/lib/load.ts (useLoaded moved here from tool-catalog.tsx)
export type Loaded<T> = { kind: "loading" } | { kind: "ready"; value: T } | { kind: "unavailable" } | { kind: "out_of_date" };
export function useLoaded<T>(path: string, parse: (value: unknown) => T): Loaded<T>;
// a ContractError sets out_of_date and logs console.error(schema, path), never the values
// run-workspace.tsx refresh() and workflow-monitor.tsx poll() use the same mapping instead of catch-alls
```

### <a id="xtyp-05"></a>XTYP-05: State vocabularies travel as plain str and are bridged with suppressions

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/application/runs.py:70](../../../../services/agent/src/autobots/application/runs.py#L70): AdmissionResult.status: str; TransitionResult at :311 is the same
  - [services/agent/src/autobots/api/run_routes.py:275](../../../../services/agent/src/autobots/api/run_routes.py#L275): status=result.status  # type: ignore[arg-type]; again at :328
  - [services/agent/src/autobots/application/provider_settings.py:168-170](../../../../services/agent/src/autobots/application/provider_settings.py#L168): source, auth\_status and catalog\_status suppressed, though CredentialSource, AuthStatus and CatalogStatus exist
  - [services/agent/src/autobots/application/operations.py:81](../../../../services/agent/src/autobots/application/operations.py#L81): state: str  # ok, degraded or unavailable
  - [services/agent/src/autobots/api/operation_routes.py:172](../../../../services/agent/src/autobots/api/operation_routes.py#L172): that state needs an arg-type suppression at the DTO
  - [services/agent/src/autobots/contracts/tools.py:263](../../../../services/agent/src/autobots/contracts/tools.py#L263): ToolGroupName re-declares domain ToolGroup; 4 more aliases follow, plus an inline cost\_class Literal
  - [services/agent/src/autobots/contracts/workflows.py:233](../../../../services/agent/src/autobots/contracts/workflows.py#L233): ExecutionView.run\_status: str although RunStatus exists
  - [services/agent/src/autobots/application/run_projection.py:386](../../../../services/agent/src/autobots/application/run_projection.py#L386): terminal states re-typed as strings
- **Evidence:** 12 of the 18 `type: ignore` in services/agent/src are [arg-type] on a str passed into a Literal or Enum DTO field: remote\_files 1, run\_routes 2, search\_routes 1, settings\_routes 1, operation\_routes 2, provider\_settings 4 and tool\_catalog 1. Two cast() calls do the same (api/routes.py:61, application/tool\_catalog.py:217). 23 contract fields named status, state, outcome, kind, role or profile are str (a grep over contracts/), for example ApprovalView.status, ModelCallView.status, role and profile, and ToolAttemptView.status. Six domain StrEnums are re-declared as Literals in contracts/tools.py. They are equal today, but no test ties them, while RunStatus and ModelProfileId are reused directly. The workflow domain keeps its states as bare strings (domain/workflow\_execution.py:12). The TERMINAL set from domain/runs.py:22 is re-typed in 6 places in application/, 3 of them inside SQL text.
  ```
  class AdmissionResult:        # application/runs.py:67-71
      status: str
          status=result.status,  # type: ignore[arg-type]    api/run_routes.py:275
      state: str  # ok, degraded or unavailable             application/operations.py:81
      "finished": ("succeeded", "failed", "cancelled"),     application/run_projection.py:386
  ```
- **Why it matters:** mypy cannot see a misspelled or new state anywhere between the row and the DTO. The lax VIEW config coerces at response time, so a bad value becomes a 500 internal\_error instead of a type error. The str-typed public fields generate TypeScript `string`, which is why the web keys its label maps by string. If a tool group is added to the domain enum but not to ToolGroupName, building ToolDescriptor raises, and the whole catalog request fails, with no test to catch it first.
- **Recommendation:** Annotate application results and locals with the vocabularies that already exist: RunStatus, AuthStatus, CredentialSource, CatalogStatus, SearchKind and Literal['input', 'output']. Convert once where the row is read, as run\_from\_row does with RunStatus(row["status"]). Then delete the 12 suppressions and 2 casts. Give the 23 public state fields Literal or Enum types, and regenerate. For the six re-declared vocabularies, either reuse the StrEnums, as the contracts already do for RunStatus, or add a test that set(get\_args(alias)) equals the enum's values. Pass list(TERMINAL) as a SQL parameter instead of quoting states in query text.
- **Rule check:** DH-06 asks for explicit enums and unions and forbids a second state enum for the UI. contracts.md says canonical states and guards are shared. Only types change, not values, and the contract change regenerates the client. Reusing a domain StrEnum in a DTO follows the existing RunStatus precedent: it shares a vocabulary and does not merge types.
- **Verification:** revised. All 18 src suppressions were listed: 13 are arg-type, and 12 of them pass a str into a Literal or Enum field (the 13th, run\_projection.py:120, passes a dict into RunRow). The casts at api/routes.py:61 and tool\_catalog.py:217 reproduce. Five Literal aliases and the inline cost\_class Literal restate six domain StrEnums, and no test ties them. TERMINAL is re-typed in 6 application places, 3 inside SQL. Revised: the str-typed state fields number 23, not 25. XDUP-09 and XERR-08 report related vocabulary drift.

### <a id="xtyp-06"></a>XTYP-06: Web label maps are keyed by string and duplicated; the generated enum types go unused

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 28
- **Where:**
  - [apps/web/components/run-list.tsx:16](../../../../apps/web/components/run-list.tsx#L16): STATUS\_TEXT: Record&lt;string, string&gt;, ten run states
  - [apps/web/components/run-workspace.tsx:49](../../../../apps/web/components/run-workspace.tsx#L49): STATUS\_LABEL: the same ten entries
  - [apps/web/components/run-list.tsx:75](../../../../apps/web/components/run-list.tsx#L75): PROFILE\_NAMES; the same map at experts-panel.tsx:295
  - [apps/web/components/tool-catalog.tsx:45](../../../../apps/web/components/tool-catalog.tsx#L45): PROVIDERS, used with `?? tool.provider` fallbacks
  - [apps/web/components/run-controls.tsx:16](../../../../apps/web/components/run-controls.tsx#L16): TERMINAL set; again at workflow-monitor.tsx:13
  - [apps/web/components/run-list.tsx:68](../../../../apps/web/components/run-list.tsx#L68): type Group re-declares the API's RunListGroup
  - [apps/web/components/model-policy-panel.tsx:24](../../../../apps/web/components/model-policy-panel.tsx#L24): SOURCE\_LABEL keyed by BindingSource; ROLE\_SOURCE at run-workspace.tsx:83
- **Evidence:** There are 28 `const X: Record<string, ...>` maps in 12 component files. Most are keyed by contract vocabularies: run status, profile, binding source, provider, operation class, availability, tool-use outcome and condition name. generated.ts exports RunStatus, ModelProfileId, BindingSource and ModelRole, and grep finds no web file that imports any of them.
  ```
  export const STATUS_TEXT: Record<string, string> = {   // run-list.tsx:16
    queued: "Queued", running: "Running", ...
  const STATUS_LABEL: Record<string, string> = {          // run-workspace.tsx:49
    queued: "Queued", running: "Running", ...
  const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);  // run-controls.tsx:16
  ```
- **Why it matters:** A new state, profile or provider compiles everywhere and then falls through to a raw code or to nothing, as in `PROVIDERS[tool.provider] ?? tool.provider`. The same vocabulary is edited in two or three copies, and the web's terminal set can drift from TERMINAL in domain/runs.py.
- **Recommendation:** Key every vocabulary map by its generated type so that tsc checks exhaustiveness: `const STATUS_LABEL = {...} satisfies Record<RunStatus, string>`. Where the contract inlines a union, use indexed access, such as `Record<ToolDescriptor["provider"], string>`. Move the shared run-status words and tones, profile names and terminal set into one module in apps/web/lib. Fields that are str in the contract need the Python change first. The run list's Group has no generated type, because the generator emits no query parameters; keyof RunGroupCounts gives the same four names.
- **Rule check:** DH-06 forbids inventing a second state enum for the UI, and nextjs.md requires generated API types. Display words stay in UI modules; they are only keyed by the generated types and are not merged with DTOs.
- **Verification:** revised. 28 `const X: Record<string, ...>` maps in 12 component files. generated.ts exports RunStatus, ModelProfileId, BindingSource and ModelRole, and no web file imports them. STATUS\_TEXT (run-list.tsx:16) and STATUS\_LABEL (run-workspace.tsx:49) hold the same ten entries, and PROFILE\_NAMES is copied verbatim. Revised: RunListGroup exists only in Python, since generate\_contracts.py emits path parameters only, so the recommendation names keyof RunGroupCounts for Group. XWEB-08 and XDUP-10 cover the screen-level copies.

```text
// apps/web/lib/run-vocabulary.ts
import type { ModelProfileId, RunStatus } from "@autobots/api-client";
export const RUN_STATUS_LABEL = { queued: "Queued", ... } satisfies Record<RunStatus, string>;
export const TERMINAL: ReadonlySet<RunStatus> = new Set(["succeeded", "failed", "cancelled"]);
export const PROFILE_NAME = { openrouter_terra: "Terra", ... } satisfies Record<ModelProfileId, string>;
```

### <a id="xtyp-07"></a>XTYP-07: Event-stream frames are a contract that nothing declares

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/api/event_routes.py:226](../../../../services/agent/src/autobots/api/event_routes.py#L226): stream route excluded from the schema
  - [services/agent/src/autobots/api/event_routes.py:208](../../../../services/agent/src/autobots/api/event_routes.py#L208): cursor frame is hand-written JSON
  - [services/agent/src/autobots/api/event_routes.py:201](../../../../services/agent/src/autobots/api/event_routes.py#L201): gap frame is hand-written JSON
  - [apps/web/components/run-workspace.tsx:224](../../../../apps/web/components/run-workspace.tsx#L224): cursor frame cast to { cursor: number }
  - [apps/web/components/run-workspace.tsx:207](../../../../apps/web/components/run-workspace.tsx#L207): message.data as string; again at :214
  - [apps/web/components/run-workspace.tsx:259](../../../../apps/web/components/run-workspace.tsx#L259): event page cast to { events?: unknown[] } before a partial parse
- **Evidence:** The run and live frames carry a RunEvent parsed with parseRunEvent. The cursor, gap and end frames are matched by event name on both sides and have no model. grep finds no test that mentions a cursor frame. There are 5 assertions in the listener and page reader.
  ```
  @router.get("/runs/{run_id}/events/stream", include_in_schema=False)   # event_routes.py:226
      yield f"event: cursor\ndata: {json.dumps({'cursor': cursor})}\n\n"  # event_routes.py:208
  source.addEventListener("cursor", (message) => {                       // run-workspace.tsx:221-225
    cursor = Math.max(cursor,
      (JSON.parse(message.data as string) as { cursor: number }).cursor);
  ```
- **Why it matters:** A cursor frame without a numeric cursor makes the client's cursor NaN. start() then requests /events?after=NaN, the API refuses it with 422 because Cursor is an int of at least 0, and retry() keeps the page "Reconnecting" indefinitely. Renaming an event on either side breaks the stream silently.
- **Recommendation:** Declare StreamCursor and StreamGap models, and the frame names as a Literal, in contracts. Add them to PUBLIC\_MODELS in contracts/export.py so they are generated, and build the frames from them in event\_routes.py. On the web, move the EventSource wiring into one lib module that parses each frame with its generated parser and accepts only a safe-integer cursor. The stream route itself can stay out of the OpenAPI paths.
- **Rule check:** contracts.md requires versioned event envelopes, and nextjs.md requires handling reconnects and deduplication. The BFF stream stays a pass-through, and a browser disconnect still cancels nothing.
- **Verification:** confirmed. The cursor (208), gap (201) and end (210) frames are hand-written, and the route is include\_in\_schema=False. The 5 assertions are at run-workspace.tsx:207, 214, 224 (two) and 259. No test checks a frame's shape; stream-result.spec.ts:112 exercises a reconnect end to end. PUBLIC\_MODELS exists at contracts/export.py:14, so the frames can be generated as recommended.

```text
# contracts/runs.py
StreamFrame = Literal["run", "live", "cursor", "gap", "end"]
class StreamCursor(BaseModel): cursor: Sequence
class StreamGap(BaseModel): after: int
// apps/web/lib/run-stream.ts
export function openRunStream(base: string, after: number, on: { event(e: RunEvent): void; cursor(n: number): void; gap(): void; end(): void }): () => void
```

### <a id="xtyp-08"></a>XTYP-08: Open dictionaries in public contracts are validated by hand and re-read by string keys

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 12
- **Where:**
  - [services/agent/src/autobots/contracts/routines.py:25](../../../../services/agent/src/autobots/contracts/routines.py#L25): RoutineConfig.trigger: dict[str, Any]
  - [services/agent/src/autobots/domain/routines.py:17](../../../../services/agent/src/autobots/domain/routines.py#L17): validate\_trigger checks keys by hand
  - [services/agent/src/autobots/domain/routines.py:49](../../../../services/agent/src/autobots/domain/routines.py#L49): occurrences() indexes trigger["kind"] and trigger["minutes"]
  - [services/agent/src/autobots/contracts/workflows.py:19](../../../../services/agent/src/autobots/contracts/workflows.py#L19): WorkflowNode.config: dict[str, Any]
  - [services/agent/src/autobots/domain/workflows.py:104](../../../../services/agent/src/autobots/domain/workflows.py#L104): \_config\_errors checks each block's keys
  - [services/agent/src/autobots/application/workflow_runner.py:171](../../../../services/agent/src/autobots/application/workflow_runner.py#L171): runner re-reads config["operation"], ["max\_items"], ["path"] and ["expert\_id"]
  - [services/agent/src/autobots/application/workflow_overview.py:89](../../../../services/agent/src/autobots/application/workflow_overview.py#L89): overview re-reads config expert\_id
  - [services/agent/src/autobots/application/workflows.py:310](../../../../services/agent/src/autobots/application/workflows.py#L310): publisher re-reads node["config"]["expert\_id"]
- **Evidence:** Contracts declare 11 open dict fields. Most are open by design (JSON schemas, tool inputs and outputs, workflow inputs); RoutineConfig.trigger and WorkflowNode.config are the 2 whose shape is closed and checked by hand. Outside the validator, 10 raw reads of node config sit in 3 application files: 6 in workflow\_runner, 3 in workflow\_overview and 1 in workflows.
  ```
  class RoutineConfig(BaseModel):     # contracts/routines.py:21-25
      target: RoutineTarget
      trigger: dict[str, Any]
      block, config = node["block"], node.get("config", {})   # workflow_runner.py:171
          if len(items) > config["max_items"]:               # workflow_runner.py:187
  ```
- **Why it matters:** The generated client sees Record&lt;string, unknown&gt; for both fields, so the workflow editor and the cronjob tool get no shape, and extra trigger keys are accepted. Each block's keys are checked in \_config\_errors and then re-read by string in the runner, overview and publisher. Renaming a key therefore passes validation and fails with KeyError while a workflow runs.
- **Recommendation:** Parse once into typed domain values. validate\_trigger returns an IntervalTrigger | DailyTrigger dataclass that occurrences() consumes. validate\_graph returns typed per-block configs (TransformConfig, ConditionConfig, ForeachConfig, ArtifactConfig, AgentConfig), which the runner, overview and publisher read instead of raw keys. Keep the node-level error codes. If the routine trigger becomes a discriminated union in the contract, map its validation errors to the same codes so the 422 responses do not change.
- **Rule check:** contracts.md: the workflow IR is versioned (ir\_version 1 and 2) and remains the stored format. DH-06: avoid untyped dictionaries. The typed configs are domain types, kept apart from the IR contract and from the web's editable drafts.
- **Verification:** revised. The 10 raw node-config reads outside the validator reproduce (workflow\_runner 6, workflow\_overview 3, workflows 1), and validate\_trigger ignores unknown keys. Revised: the contracts hold 11 open dict fields, not 2; the finding concerns the 2 with a closed shape. PDOM-02 reports the routine configuration's two definitions from the py-domain area.

### <a id="xtyp-09"></a>XTYP-09: External provider replies are read as Any and coerced field by field

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 33
- **Where:**
  - [services/agent/src/autobots/adapters/tavily.py:47](../../../../services/agent/src/autobots/adapters/tavily.py#L47): call() returns the raw reply as Any
  - [services/agent/src/autobots/adapters/tavily.py:72](../../../../services/agent/src/autobots/adapters/tavily.py#L72): str(item.get("title", "")) turns null into "None"
  - [services/agent/src/autobots/adapters/github_reads.py:53](../../../../services/agent/src/autobots/adapters/github_reads.py#L53): \_checked() -&gt; Any
  - [services/agent/src/autobots/adapters/github_pulls.py:84](../../../../services/agent/src/autobots/adapters/github_pulls.py#L84): reply.json()["object"]["sha"] raises KeyError on another shape
  - [services/agent/src/autobots/adapters/browser_executor.py:77](../../../../services/agent/src/autobots/adapters/browser_executor.py#L77): reply.json()["webSocketDebuggerUrl"]
  - [services/agent/src/autobots/adapters/market_data.py:139](../../../../services/agent/src/autobots/adapters/market_data.py#L139): the good pattern: explicit shape check mapped to provider\_reply\_malformed
  - [services/agent/src/autobots/application/tool_gateway.py:422](../../../../services/agent/src/autobots/application/tool_gateway.py#L422): any other exception becomes a generic tool\_failed
- **Evidence:** 17 `.json()` reads in adapters, application and operations return Any, and 33 `str(x.get(...))` coercions sit in 7 adapter files.
  ```
  async def call(context: ToolContext, path: str, body: dict[str, Any]) -> Any:   # tavily.py:47
                  title=str(item.get("title", "")),                                 # tavily.py:72
          return str(reply.json()["object"]["sha"])                                  # github_pulls.py:84
          if not isinstance(body, list) or len(body) < 2 or not isinstance(body[1], list):  # market_data.py:139
  ```
- **Why it matters:** Provider JSON is untrusted input. A null title becomes the string "None" in what the model reads, and a missing URL becomes "". A reply of the wrong shape raises AttributeError or KeyError, which the gateway turns into a generic tool\_failed instead of the provider\_reply\_malformed code that market\_data.py already uses.
- **Recommendation:** Give each provider a small reply model next to its adapter: Pydantic, extra="ignore", with explicit optional fields. Validate `reply.json()` once and map ValidationError to provider\_reply\_malformed, treating market\_data.py's explicit shape check as the minimum. Return typed values from `call` and `_checked`.
- **Rule check:** DH-06: validate data at trust boundaries. Decision 0017's URL guard and the tool output contracts stay as they are. The reply models are adapter types, kept apart from the tool output contracts.
- **Verification:** confirmed. 17 `.json()` reads in adapters, application and operations, and 33 `str(x.get(...))` coercions in 7 adapter files. A wrong-shaped reply also costs calls: ToolGateway.\_read (tool\_gateway.py:410-433) treats the AttributeError or KeyError as a generic failure and retries it up to tool.retries.

### <a id="xtyp-10"></a>XTYP-10: Public timestamps come in three forms, and only one is checked for UTC

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 14
- **Where:**
  - [services/agent/src/autobots/contracts/primitives.py:28](../../../../services/agent/src/autobots/contracts/primitives.py#L28): UtcTimestamp, with the UTC pattern
  - [services/agent/src/autobots/contracts/approvals.py:69](../../../../services/agent/src/autobots/contracts/approvals.py#L69): ApprovalView.expires\_at: str; decided\_at at :81
  - [services/agent/src/autobots/api/approval_routes.py:91](../../../../services/agent/src/autobots/api/approval_routes.py#L91): .isoformat() without converting to UTC
  - [services/agent/src/autobots/application/workflows.py:70](../../../../services/agent/src/autobots/application/workflows.py#L70): .astimezone(UTC).isoformat() into WorkflowDraftView.saved\_at: str
  - [services/agent/src/autobots/contracts/settings.py:119](../../../../services/agent/src/autobots/contracts/settings.py#L119): ModelList.fetched\_at: datetime | None, with no UTC pattern
  - [services/agent/src/autobots/contracts/operations.py:71](../../../../services/agent/src/autobots/contracts/operations.py#L71): DelayedOccurrence.occurrence\_time: datetime
  - [apps/web/components/approvals-panel.tsx:489](../../../../apps/web/components/approvals-panel.tsx#L489): new Date(approval.expires\_at) on an unvalidated string
- **Evidence:** Of the 17 date-time fields in the generated schema, 13 come from UtcTimestamp and carry the UTC pattern. Four are plain datetime: ProviderStatus.validated\_at, ModelList.fetched\_at, DelayedOccurrence.occurrence\_time and RestoreRecord.at. Another 10 contract timestamps are str. Five are public (ApprovalView.expires\_at and decided\_at, WorkflowDraftView.saved\_at, WorkflowExecutionSummary.started\_at and OccurrenceView.occurrence\_time), and five are in tool outputs.
  ```
      expires_at: str                                     # contracts/approvals.py:69
                  expires_at=row["expires_at"].isoformat(),   # api/approval_routes.py:91
          saved_at=row[1].astimezone(UTC).isoformat()     # application/workflows.py:70
      fetched_at: datetime | None                         # contracts/settings.py:119
  ```
- **Why it matters:** Neither side validates the str timestamps, and plain datetime admits non-UTC offsets because its schema has no pattern. The browser formats whatever arrives, so a bad value shows as "Invalid Date" in the approval detail. UTC normalization also differs by call site.
- **Recommendation:** Use UtcTimestamp for every public timestamp and let Pydantic serialize it. Use it in tool output contracts too, or document why a string is kept. Regenerate the client, and add a non-UTC boundary case for one of the converted fields.
- **Rule check:** DH-06 requires timezone-aware UTC dates, and python-worker.md requires explicit UTC. This is a contract change that regenerates the client; generated files are not edited.
- **Verification:** confirmed. openapi.json has 17 date-time fields, 13 with the UTC pattern; the 4 without are ProviderStatus.validated\_at, ModelList.fetched\_at, DelayedOccurrence.occurrence\_time and RestoreRecord.at. The contracts hold 10 str timestamps, 5 public and 5 in tool outputs.

### <a id="xtyp-11"></a>XTYP-11: The LangChain model hooks on the paid path are typed Any

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 49
- **Where:**
  - [services/agent/src/autobots/adapters/loop_middleware.py:629](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L629): awrap\_model\_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -&gt; Any
  - [services/agent/src/autobots/adapters/loop_middleware.py:641](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L641): response.result[-1].response\_metadata on Any
  - [services/agent/src/autobots/adapters/loop_middleware.py:491](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L491): \_admitted\_call(request: Any, handler: Any) -&gt; tuple[Any, bool]
  - [services/agent/src/autobots/adapters/loop_middleware.py:479](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L479): str(response.result[-1].content)
  - [services/agent/src/autobots/adapters/loop_middleware.py:400](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L400): \_bounded(handler: Any, request: Any) -&gt; Any
  - [services/agent/src/autobots/application/worker_inference.py:169](../../../../services/agent/src/autobots/application/worker_inference.py#L169): ainvoke(messages: Any, stop: Any = None, \*\*kwargs: Any) -&gt; Any
- **Evidence:** ruff ANN401 finds 38 Any annotations in loop\_middleware.py (request 9 times, handler 5, and 6 return types) and 16 in worker\_inference.py. 5 of the 54 are SQL connection parameters, which XTYP-04 covers, so 49 are counted here. The pinned langchain 1.4.8 exports ModelRequest, ModelResponse and ModelCallResult from langchain/agents/middleware/types.py (lines 88, 273 and 315).
  ```
  async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:  # :629
      if response.result[-1].response_metadata.get("finish_reason") != "length":                    # :641
  ```
- **Why it matters:** The middleware that admits, budgets and compacts every paid model call reaches into request.override(...), response.result[-1] and response\_metadata on Any. A LangChain upgrade that renames them still type-checks and then fails during a model call. DH-06 asks for the combined dependency set to be qualified before it is frozen, and mypy cannot help with that here.
- **Recommendation:** Annotate the hooks with the library's own types, as AgentMiddleware.awrap\_model\_call declares them (types.py:598-602): request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]], returning ModelCallResult. Where the library type is too loose, define a narrow Protocol in adapters/models with a comment that names the gap, and keep the list of such exceptions in one place.
- **Rule check:** DH-06 asks for third-party typing exceptions to be narrow and documented. model-gateway.md keeps fake transports as the test path. Only types change; no call path or budget logic changes.
- **Verification:** revised. langchain 1.4.8 is pinned in uv.lock, and its types.py defines ModelRequest at 88, ModelResponse at 273 and ModelCallResult at 315. Revised: 5 of the 54 ANN401 hits are connection parameters already counted in XTYP-04, so 49 remain, and the hook's return type is ModelCallResult, as the base class declares.

### <a id="xtyp-12"></a>XTYP-12: 42% of the in-scope Python is never type-checked, though most of it is annotated

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 133
- **Where:**
  - [services/agent/pyproject.toml:52](../../../../services/agent/pyproject.toml#L52): mypy files = ["src", "tests"] only
  - [scripts/toolchain.py:212](../../../../scripts/toolchain.py#L212): the only mypy step runs in services/agent
  - [scripts/persistent_install.py:288](../../../../scripts/persistent_install.py#L288): reserve\_goal -&gt; tuple[object, dict] hides the shared spend Ledger
  - [scripts/persistent_install.py:446](../../../../scripts/persistent_install.py#L446): ledger.settle(...)  # type: ignore[attr-defined], one of 14 inert suppressions
  - [tests/db/keys_and_vars_check.py:255](../../../../tests/db/keys_and_vars_check.py#L255): calls a service API under an inert arg-type suppression
  - [tests/db/run_admission_check.py:27](../../../../tests/db/run_admission_check.py#L27): inert no-untyped-def suppression
  - [.claude/hooks/dispatch.py:96](../../../../.claude/hooks/dispatch.py#L96): bare dict parameters, which strict mode would flag
- **Evidence:** scripts/, tests/ and .claude/hooks/ have no type-check step. They hold 133 files and 25,788 lines, 42% of the in-scope Python. 81% of their functions are fully annotated by an ast count (scripts 99%, tests/db 99%, tests/harness 39%), 68 of the files import the service package (autobots.\*), and they carry 25 type: ignore comments that no checker reads.
  ```
  files = ["src", "tests"]                                                  # services/agent/pyproject.toml:52
  def reserve_goal(ledger_path: Path, limit: int) -> tuple[object, dict]:   # scripts/persistent_install.py:288
                  ledger.settle(entry, charged, 'settled')  # type: ignore[attr-defined]   # :446
  ```
- **Why it matters:** Annotations that nothing checks can be wrong. A signature change in autobots.application passes the service's mypy and surfaces only when the db profile runs the checks on Docker. In the paid install path, the shared spend ledger is typed object and called through 14 suppressed lines, so a renamed Ledger.settle would fail after the model call it settles and leave the reservation open.
- **Recommendation:** Add a second mypy step to the fast profile over scripts, tests and .claude/hooks: strict mode, a mypy\_path that covers scripts and services/agent/src, and warn\_unused\_ignores. Start from a baseline file of today's errors that may only shrink, kept by a small comparison script, since mypy has no baseline option. tests/harness, 39% annotated, will dominate that baseline. Fix the ledger first: import Ledger under TYPE\_CHECKING and return tuple[Ledger, ReservationEntry].
- **Rule check:** DH-06 and SP-017 call for mypy strict on owned modules. The new step uses the prepared environment and installs nothing, as the harness rules require. It adds a check and weakens none.
- **Verification:** revised. 133 files and 25,788 of 61,654 Python lines (42%) sit outside mypy, whose only step (toolchain.py:212) and files list (pyproject.toml:52) cover services/agent. 68 of them import autobots, and 25 type: ignore comments are inert, 14 in persistent\_install.py. Revised the title and evidence: tests/harness is only 39% annotated. Kept medium: the db profile still catches a broken service signature, though late. XTOL-01 and SCRP-04 report the wider lint, format and type gap at high.

### <a id="xtyp-13"></a>XTYP-13: Shared cross-language fixtures cover 4 of 170 schemas

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 4
- **Where:**
  - [contracts/fixtures/boundary-cases.json:1](../../../../contracts/fixtures/boundary-cases.json#L1): 29 cases: RunSummary 19, RunEvent 4, WorkflowGraph 4, ErrorResponse 2
  - [services/agent/tests/test_contracts.py:31](../../../../services/agent/tests/test_contracts.py#L31): MODELS maps the same 4 schemas
  - [packages/api-client/tests/contract.test.ts:9](../../../../packages/api-client/tests/contract.test.ts#L9): parsers maps the same 4 schemas
- **Evidence:** The generated client has 170 schemas, and the web calls 32 distinct generated parsers. Only 2 of those 32 (RunSummary and RunEvent) have shared cases.
  ```
  MODELS: dict[str, type[BaseModel]] = {   # services/agent/tests/test_contracts.py:31
      "RunSummary": RunSummary, "RunEvent": RunEvent, "ErrorResponse": ErrorResponse, "WorkflowGraph": WorkflowGraph,
  const parsers = { RunSummary: parseRunSummary, RunEvent: parseRunEvent, ErrorResponse: parseErrorResponse, WorkflowGraph: parseWorkflowGraph };  // contract.test.ts:9
  ```
- **Why it matters:** Unknown enums, private fields and type shapes are compared across the two languages only for runs and events. One shared case each would have caught the unchecked map values and the timestamp fields that skip the UTC check.
- **Recommendation:** Cover every schema the web parses: one valid case per schema, plus generated mutations (unknown enum value, extra field, wrong type, non-UTC timestamp, bad map value). Make the TypeScript test iterate the parsed schemas and fail when one has no case, so that new screens add cases.
- **Rule check:** contracts.md requires shared validation fixtures that cover both languages, unknown enums and private-field leakage.
- **Verification:** confirmed. contracts/fixtures/boundary-cases.json holds 29 cases (RunSummary 19, RunEvent 4, WorkflowGraph 4, ErrorResponse 2), the same 4 schemas both test maps name. The generated client has 170 schemas, and the web calls 32 distinct generated parsers, of which only RunSummary and RunEvent have cases.

### <a id="xtyp-15"></a>XTYP-15: Comments stand in for types, and suppressions give no reason

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 21
- **Where:**
  - [services/agent/src/autobots/application/operations.py:81](../../../../services/agent/src/autobots/application/operations.py#L81): state: str  # ok, degraded or unavailable
  - [services/agent/src/autobots/operations/route_qualification.py:239](../../../../services/agent/src/autobots/operations/route_qualification.py#L239): verdict: str  # passed, failed or unsupported
  - [services/agent/src/autobots/operations/concept_seed.py:153](../../../../services/agent/src/autobots/operations/concept_seed.py#L153): graph: Any  # Callable[[Mapping[str, UUID]], dict[str, Any]]
  - [services/agent/src/autobots/operations/logs.py:105](../../../../services/agent/src/autobots/operations/logs.py#L105): suppression with a code but no reason
  - [services/agent/src/autobots/application/browsing_loop.py:269](../../../../services/agent/src/autobots/application/browsing_loop.py#L269): attr-defined suppression with no reason
  - [services/agent/src/autobots/operations/route_qualification.py:486](../../../../services/agent/src/autobots/operations/route_qualification.py#L486): attr-defined suppression with no reason
  - [services/agent/src/autobots/operations/route_qualification.py:222](../../../../services/agent/src/autobots/operations/route_qualification.py#L222): assignment suppression with no reason; another at :232
- **Evidence:** 3 fields carry their real type in a comment. All 18 `type: ignore` comments in services/agent/src name an error code, and none says why. 12 of them go away with XTYP-05; the other 6 (2 assignment, 3 attr-defined and the RunRow arg-type at run\_projection.py:120) are the ones that need a reason.
  ```
      state: str  # ok, degraded or unavailable                     # application/operations.py:81
      verdict: str  # passed, failed or unsupported                 # operations/route_qualification.py:239
      graph: Any  # Callable[[Mapping[str, UUID]], dict[str, Any]]  # operations/concept_seed.py:153
          utils.get_env_var.cache_clear()  # type: ignore[attr-defined]  # operations/logs.py:105
  ```
- **Why it matters:** The comments carry a closed vocabulary or a callable signature that mypy never checks; operations.py's state then needs a suppression at operation\_routes.py:172. SP-017 asks for exceptions that are narrow and documented, and a code without a reason cannot be reviewed or retired.
- **Recommendation:** Turn the three comments into types: Literal aliases and a Callable alias. Require a reason on every remaining suppression, for example `# type: ignore[attr-defined]  # langsmith's cached helper is untyped`, enforced by a small harness test that rejects a bare `type: ignore[...]`.
- **Rule check:** SP-017 (docs/engineering/option-b-contract.md) says to keep exceptions narrow and documented, and DH-06 says to explain nonobvious invariants in code. Decision and story citations in comments stay.
- **Verification:** revised. The 3 comment-typed fields and the 18 reasonless suppressions reproduce. Revised to avoid overlap with XTYP-05: the run\_routes.py:275 and provider\_settings.py:168 locations, whose suppressions XTYP-05 removes, were replaced with the remaining ones at route\_qualification.py:486 and :222, and the evidence now says which 6 suppressions stay. The example reason now names langsmith, which logs.py:102 imports.

### <a id="xtyp-16"></a>XTYP-16: The lax contract config is copied into 18 places

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 18
- **Where:**
  - [services/agent/src/autobots/contracts/approvals.py:9](../../../../services/agent/src/autobots/contracts/approvals.py#L9): VIEW = ConfigDict(extra="forbid", frozen=True)
  - [services/agent/src/autobots/contracts/workflows.py:10](../../../../services/agent/src/autobots/contracts/workflows.py#L10): the same VIEW
  - [services/agent/src/autobots/contracts/run_workspace.py:12](../../../../services/agent/src/autobots/contracts/run_workspace.py#L12): the same VIEW
  - [services/agent/src/autobots/contracts/operations.py:11](../../../../services/agent/src/autobots/contracts/operations.py#L11): the same VIEW
  - [services/agent/src/autobots/contracts/run_commands.py:44](../../../../services/agent/src/autobots/contracts/run_commands.py#L44): the same config inline, under 'Not strict, since it is built from database values'
  - [services/agent/src/autobots/contracts/primitives.py:10](../../../../services/agent/src/autobots/contracts/primitives.py#L10): STRICT\_CONTRACT, defined once
  - [services/agent/src/autobots/contracts/tools.py:12](../../../../services/agent/src/autobots/contracts/tools.py#L12): TOOL\_CONTRACT, defined once, with allow\_inf\_nan=False
- **Evidence:** VIEW is defined in 9 contract modules and written inline 9 more times, configuring 113 models. STRICT\_CONTRACT (49 models) and TOOL\_CONTRACT (85 models) are each defined once.
  ```
  VIEW = ConfigDict(extra="forbid", frozen=True)                        # contracts/approvals.py:9, and 8 more modules
      model_config = ConfigDict(extra="forbid", frozen=True)            # contracts/run_commands.py:44, and 8 more
  STRICT_CONTRACT = ConfigDict(strict=True, extra="forbid", frozen=True)  # contracts/primitives.py:10
  ```
- **Why it matters:** The strictness policy for 113 response models lives in 18 copies. Changing it, for example to add the allow\_inf\_nan=False that TOOL\_CONTRACT has, means 18 edits, and a copy can drift unnoticed. The lax copies are also what lets str values reach Enum fields at runtime.
- **Recommendation:** Define VIEW once in contracts/primitives.py beside STRICT\_CONTRACT, with a comment on when each applies, and import it everywhere. Add a test that every BaseModel in contracts uses one of the named configs.
- **Rule check:** DH-06 asks for explicit coercion and strictness per field. No model's behavior changes: the existing lax and strict choices are kept and named once.
- **Verification:** confirmed. VIEW is defined in 9 contract modules and written inline 9 more times; 104 models use VIEW and 9 the inline copy (113), 49 use STRICT\_CONTRACT and 85 TOOL\_CONTRACT, the 247 that forbid extra fields. XMOD-15 notes the same copies from the boundaries lens.

### <a id="xtyp-17"></a>XTYP-17: Test doubles need suppressions because collaborators are typed as concrete classes

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 30
- **Where:**
  - [services/agent/src/autobots/application/browsing_loop.py:297](../../../../services/agent/src/autobots/application/browsing_loop.py#L297): admitted\_steps(middleware: LoopMiddleware, model: Any, ...)
  - [services/agent/tests/test_browsing_loop.py:223](../../../../services/agent/tests/test_browsing_loop.py#L223): fake middleware passed under # type: ignore[arg-type]
  - [services/agent/tests/test_final_review.py:93](../../../../services/agent/tests/test_final_review.py#L93): arg-type suppression on a fake
  - [services/agent/tests/test_browser_executor.py:100](../../../../services/agent/tests/test_browser_executor.py#L100): arg-type suppression on a fake
  - [services/agent/tests/test_workflows.py:318](../../../../services/agent/tests/test_workflows.py#L318): arg-type suppression on a fake
  - [services/agent/tests/test_code_tools.py:16](../../../../services/agent/tests/test_code_tools.py#L16): helper typed -&gt; object forces 9 attr-defined suppressions
- **Evidence:** 21 of the 44 suppressions in services/agent/tests are [arg-type] in 8 files. Most pass a fake, None or a bare route string where a concrete collaborator is declared (LoopMiddleware, ProviderContext, a stream writer, ModelRoute); test\_plans.py:41 passes deliberately invalid input. 9 [attr-defined] come from one helper typed `-> object`.
  ```
  def admitted_steps(middleware: LoopMiddleware, model: Any, route: ModelRoute) -> Step:   # browsing_loop.py:297
      step = admitted_steps(middleware, delegate, "researcher-route")  # type: ignore[arg-type]  # test_browsing_loop.py:223
  def run(**arguments: object) -> object:                                                  # test_code_tools.py:16
  ```
- **Why it matters:** Each suppression hides every argument-type error on its line. A signature change in the code under test is then not reported in the test that exercises it, and nothing checks that a fake still matches the collaborator it replaces.
- **Recommendation:** Type injected collaborators by the narrow Protocol they actually use, such as an admission port or a model step, so fakes type-check without suppressions. Return the real output type from test helpers.
- **Rule check:** DH-06 asks for narrow interfaces, and python-worker.md says default model tests are fake. The fakes stay; they just satisfy a Protocol.
- **Verification:** revised. 44 suppressions in services/agent/tests: 21 arg-type in 8 files and 9 attr-defined from the helper at test\_code\_tools.py:16 (one line below the cited 15). Revised the wording: not every arg-type passes a fake (some pass None or a route string, and test\_plans.py:41 is deliberate), and a line-level ignore hides argument errors on its line rather than all checking of the call. PTST-06 covers the same comments from the py-tests area.

### <a id="xtyp-18"></a>XTYP-18: Browser specs read API JSON through casts and local shapes

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 31
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:346](../../../../apps/web/tests/browser/approvals.spec.ts#L346): decided.approvals as { status: string }[]
  - [apps/web/tests/browser/experts.spec.ts:492](../../../../apps/web/tests/browser/experts.spec.ts#L492): catalog.tools as Tool[]
  - [apps/web/tests/browser/identity.spec.ts:120](../../../../apps/web/tests/browser/identity.spec.ts#L120): me.workspaces as { name: string }[]
  - [apps/web/tests/browser/readiness.spec.ts:58](../../../../apps/web/tests/browser/readiness.spec.ts#L58): body.services as Record&lt;string, string&gt;[]
  - [apps/web/tests/browser/search.spec.ts:30](../../../../apps/web/tests/browser/search.spec.ts#L30): body.results cast
  - [apps/web/tests/browser/settings-keys-and-vars.spec.ts:45](../../../../apps/web/tests/browser/settings-keys-and-vars.spec.ts#L45): local Item type restates the generated KeyOrVar
  - [apps/web/tests/browser/workspace-choice.spec.ts:103](../../../../apps/web/tests/browser/workspace-choice.spec.ts#L103): error body cast to { code: string }
  - [apps/web/tests/browser/release-latency.spec.ts:33](../../../../apps/web/tests/browser/release-latency.spec.ts#L33): run\_id read through a cast
- **Evidence:** 31 of the 41 browser spec files read API JSON. None imports @autobots/api-client; 18 `as {` casts and local shapes stand in for the contract.
  ```
  for (const item of decided.approvals as { status: string }[])  // approvals.spec.ts:346
  const tools = catalog.tools as Tool[];                          // experts.spec.ts:492
  const body = (await reply.json()) as { code: string };          // workspace-choice.spec.ts:103
  ```
- **Why it matters:** When the API changes shape, these tests fail with a vague assertion, or pass on undefined, instead of a ContractError that names the field. Their local shapes also drift from the contract.
- **Recommendation:** Parse API reads in specs with the generated parsers, for example parseApprovalList(await response.json()), and use generated types for fixtures. Keep casts only for the window globals that the tests install.
- **Rule check:** contracts.md: TypeScript types do not validate JSON. The browser flows stay in the db profile, as nextjs.md describes.
- **Verification:** confirmed. 41 spec files, 31 of which read API JSON; none imports @autobots/api-client, and 18 `as {` casts sit in 8 files. TWEB-04 reports the wider pattern (232 untyped reads) from the web-tests area.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|

No finding was rejected.

18 findings were kept, 9 of them revised, and 0 rejected.

## Not covered

I did not run mypy on scripts/, tests/ or .claude/hooks/, because mypy is not among the permitted commands. So the number of errors a new check would report there is unmeasured. The 398 ANN401 hits were grouped by parameter name and sampled, not opened one by one. Components and service modules were opened where a pattern led, not read in full; their single-file issues are left to the area reviews. The 56 browser-test assertions (50 type, 6 non-null) were classified from their source lines only. The NaN-cursor reconnect loop, the receipt KeyError and the skipped route check are reasoned from code, not executed. One read-only import of five contract and domain modules with the service's Python (python -I), used to confirm that the five Literal aliases match their StrEnums today, may have refreshed ignored \_\_pycache\_\_ files. git status was unchanged afterwards. PRD-Development-Harness.md was read only for DH-03 and DH-06.
