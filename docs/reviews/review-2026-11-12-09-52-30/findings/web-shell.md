# Web: shell, BFF, lib and configuration

The web shell, BFF and lib are small and deliberately bounded. Every proxied operation passes one pure Host, Origin, Sec-Fetch-Site and double-submit guard, then a session check, before forward() adds the internal token and the cookie-chosen workspace. The API checks membership again (Decision 0023 E3). Server modules carry server-only, the proxy route handlers are one-liners, the exact Luma tokens are imported unedited, and every input, select and textarea goes through components/ui. The weak points are failure handling and how deeply responses are validated. The hand-written api-client validator ignores minItems, maxItems and schema-valued additionalProperties, which leaves 29 constraints in 19 generated schemas unchecked. requestJson reports HTTP failures as ContractError. Every catch in service-status.ts and bff.ts throws away its cause without logging it, so contract drift, a 401, a timeout and a missing environment variable all end up as 'Sign in', a generic 503 or a bare 500. Sign-in reports an outage as a wrong password. Each component writes its own mutation code: 20 response bodies are type-asserted and the generated parseErrorResponse is never used. They all sit on a csrfFetch that rotates the token on every write, so two overlapping writes can refuse each other. The tooling enforces less than it seems to. schema-value.test.ts never runs because verify.py names unit tests one by one. ESLint has no type-aware, assertion or size rules. packages/api-client is outside lint and format. DH-06's Vitest and React Testing Library layer is missing: US-1.3 deferred it, and no decision records node:test as its substitute. Size is not the problem in this area. I read the code behind the metric leads for guardRequest's complexity, the primitive files with several components and the test-fixture type assertion, and judged all three acceptable. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict flags (noUncheckedIndexedAccess, exactOptionalPropertyTypes), pinned versions and separate lint, typegen and typecheck steps meet DH-06 as written. ESLint has no assertion, size or type-aware rules, api-client is outside lint and format, and the Vitest/RTL layer is missing without a decision. |
| modules | 4 | Server-only modules, a pure guard and one forwarder make the boundaries clear. Alias routes, a credential module the app never calls and an incomplete primitive set blur the public surface. |
| size | 4 | The largest file is 175 lines. Four components run 63 to 75 lines, and forward() and guardRequest reach complexity 13. All modest. |
| functions | 4 | Most functions do one thing. forward() and AccountFooter each mix policy or derived state with output. |
| structure | 4 | The layout follows Next.js conventions and the DH-03 placement of apps/web and packages/api-client. Three alias routes give some endpoints two URLs. |
| approach | 3 | Server Components are the default, reads happen on the server and the SSE pass-through never owns a run. Rotating the CSRF token on every write causes a race, each component writes its own mutation code, and per-render reads are not memoized. |
| comments | 4 | Comments explain why and cite decisions and PRD IDs. Two no longer match the code, and a third gives a focus-order reason that has since changed. |
| types | 3 | Generated types are used at the server boundary. The runtime validator ignores 29 declared constraints, and 20 client sites type-assert response shapes instead of parsing them. |
| errors | 2 | Every server-side catch throws away its cause without a log. Drift and a 401 both read as signed out, and sign-in reports outages as bad credentials. |
| tests | 3 | The guard and credential tests are table-driven on shared fixtures, and boundary.spec.ts covers the BFF end to end. One unit test never runs, body limits are untested, and there is no fast layer for BFF or client logic. |
| maintainability | 3 | Readable, well-bounded code. Its main costs are failures nobody can see, a validator weaker than its contract, and mutation code repeated across screens. |

## Strengths

- **A pure, table-tested request guard.** apps/web/lib/request-guard.ts:33-67 has no framework dependency and compares tokens in constant time (22-31). apps/web/tests/unit/request-guard.test.ts:31-76 tests it against forged hosts, DNS rebinding through localhost, cross-site and same-site fetches, and missing, empty and mismatched tokens. Sources: [apps/web/lib/request-guard.ts:33](../../../../apps/web/lib/request-guard.ts#L33), [apps/web/lib/request-guard.ts:22](../../../../apps/web/lib/request-guard.ts#L22), [apps/web/tests/unit/request-guard.test.ts:31](../../../../apps/web/tests/unit/request-guard.test.ts#L31).
- **Server-only boundaries held in code, not convention.** import "server-only" is line 1 of apps/web/lib/bff.ts, session.ts, server-config.ts, service-status.ts and workspace-choice.ts. Configuration is read on each call (server-config.ts:11). The internal token goes onto a fresh Headers object, so a client-sent Authorization or X-Autobots-Internal never gets through (bff.ts:59-62, 80-89). The Supabase client stays on the server behind an HttpOnly, SameSite=Strict cookie (session.ts:10-21), and accessToken says outright that nothing trusts the token's contents (session.ts:37). Sources: [apps/web/lib/bff.ts:1](../../../../apps/web/lib/bff.ts#L1), [apps/web/lib/server-config.ts:11](../../../../apps/web/lib/server-config.ts#L11), [apps/web/lib/bff.ts:59](../../../../apps/web/lib/bff.ts#L59), [apps/web/lib/session.ts:10](../../../../apps/web/lib/session.ts#L10), [apps/web/lib/session.ts:37](../../../../apps/web/lib/session.ts#L37).
- **One path for every proxied operation.** Every proxy route calls forward() or streamFrom(). Their authorized() runs the guard, then the session check, then attaches the chosen workspace (apps/web/lib/bff.ts:37-69). The stream route validates its cursor and encodes the run id (apps/web/app/api/v1/runs/[id]/events/stream/route.ts:12-17). Only the stream's reader is tied to the browser, so a disconnect never cancels a run (bff.ts:128-131). Sources: [apps/web/lib/bff.ts:37](../../../../apps/web/lib/bff.ts#L37), [apps/web/app/api/v1/runs/[id]/events/stream/route.ts:12](../../../../apps/web/app/api/v1/runs/[id]/events/stream/route.ts#L12), [apps/web/lib/bff.ts:128](../../../../apps/web/lib/bff.ts#L128).
- **Exact tokens, consumed rather than copied.** apps/web/app/globals.css:2-5 imports docs/design/luma.css unedited plus the one documented extension. Lines 31-77 map every color, including the chart and sidebar tokens, and the radius scale to Tailwind (DS-01, DS-03). Dark is the server fallback, and hydration suppression is limited to the root element (apps/web/app/layout.tsx:19-23). Invalid saved themes are removed before paint (layout.tsx:13-17). Sources: [apps/web/app/globals.css:2](../../../../apps/web/app/globals.css#L2), [apps/web/app/globals.css:31](../../../../apps/web/app/globals.css#L31), [apps/web/app/layout.tsx:19](../../../../apps/web/app/layout.tsx#L19), [apps/web/app/layout.tsx:13](../../../../apps/web/app/layout.tsx#L13).
- **Form controls fully centralized.** apps/web/components/ui/field.tsx provides Input, Textarea, Select and Choice with data-slot markers, and keeps Decision 0023 E1's border in one constant (field.tsx:10-11). git grep finds no raw &lt;input&gt;, &lt;select&gt; or &lt;textarea&gt; in app/ or components/ outside components/ui. Sources: [apps/web/components/ui/field.tsx:10](../../../../apps/web/components/ui/field.tsx#L10), [tests/harness/test_shared_form_controls.py:13](../../../../tests/harness/test_shared_form_controls.py#L13).
- **State never carried by color alone.** SidebarNav marks the current page with aria-current, fill and weight (apps/web/components/sidebar-nav.tsx:69, 95-99) and gives the pending count screen-reader words (120). Badge and readiness put the meaning in words (badge.tsx:6, readiness.tsx:15). ServiceStatusBadge keeps "Python API: available" whole for assistive technology (service-status-badge.tsx:6-7). The shell opens with a skip link (app-shell.tsx:25-30). Sources: [apps/web/components/sidebar-nav.tsx:95](../../../../apps/web/components/sidebar-nav.tsx#L95), [apps/web/components/sidebar-nav.tsx:120](../../../../apps/web/components/sidebar-nav.tsx#L120), [apps/web/components/ui/badge.tsx:6](../../../../apps/web/components/ui/badge.tsx#L6), [apps/web/components/readiness.tsx:15](../../../../apps/web/components/readiness.tsx#L15), [apps/web/components/service-status-badge.tsx:6](../../../../apps/web/components/service-status-badge.tsx#L6), [apps/web/components/app-shell.tsx:25](../../../../apps/web/components/app-shell.tsx#L25).
- **Cross-language fixtures instead of parallel test data.** apps/web/tests/unit/credential-precedence.test.ts:9-23 and packages/api-client/tests/contract.test.ts:8-20 read the same contracts/fixtures files as the Python tests (services/agent/tests/test_contracts.py:30). contract.test.ts:22-25 pins that a cast cannot stand in for validation. Sources: [apps/web/tests/unit/credential-precedence.test.ts:9](../../../../apps/web/tests/unit/credential-precedence.test.ts#L9), [packages/api-client/tests/contract.test.ts:8](../../../../packages/api-client/tests/contract.test.ts#L8), [services/agent/tests/test_contracts.py:30](../../../../services/agent/tests/test_contracts.py#L30), [packages/api-client/tests/contract.test.ts:22](../../../../packages/api-client/tests/contract.test.ts#L22).
- **Promise handling already clean.** Event handlers mark fire-and-forget calls with void (apps/web/components/account-form.tsx:49, workspace-chooser.tsx:48). A read-only ESLint run on this area with type-aware no-floating-promises and no-misused-promises found no violation in production code, so those rules can be enforced at no cost. Sources: [apps/web/components/account-form.tsx:49](../../../../apps/web/components/account-form.tsx#L49), [apps/web/components/workspace-chooser.tsx:48](../../../../apps/web/components/workspace-chooser.tsx#L48).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WSHL-01](#wshl-01) | high | types | The contract validator ignores array bounds, map value schemas and unknown keywords | S | high |
| [WSHL-02](#wshl-02) | high | errors | Server reads and the BFF throw away every failure cause, so drift, 401s and timeouts read as signed out or a generic 503 | M | medium |
| [WSHL-03](#wshl-03) | medium | errors | requestJson reports HTTP failures as ContractError and drops the API's typed error | S | medium |
| [WSHL-04](#wshl-04) | medium | approach | csrfFetch mints a new double-submit token for every write, so overlapping writes can refuse each other | S | high |
| [WSHL-05](#wshl-05) | medium | duplication | Three route files rebuild the same guard input, error envelope, cookie policy and JSON body read | S | medium |
| [WSHL-06](#wshl-06) | medium | duplication | Each component writes its own mutation code: 20 type-asserted response bodies and no shared helper | M | medium |
| [WSHL-07](#wshl-07) | medium | errors | Sign-in reports an unavailable service as a wrong password, and sign-out fails silently | S | medium |
| [WSHL-08](#wshl-08) | medium | tests | schema-value.test.ts never runs, because verify.py names unit tests one by one | S | low |
| [WSHL-09](#wshl-09) | medium | standards | Lint and format enforce only the Next.js presets, and packages/api-client is outside both | M | low |
| [WSHL-10](#wshl-10) | medium | standards | DH-06's Vitest and Testing Library layer is missing without a recorded decision, and BFF policy has no fast test | M | low |
| [WSHL-12](#wshl-12) | medium | modules | The primitive set stops short: no Label or Dialog, Card is fixed to &lt;section&gt;, Separator is unused | M | medium |
| [WSHL-13](#wshl-13) | medium | naming | Font sizes and some radii are pixel literals, not tokens | M | medium |
| [WSHL-20](#wshl-20) | medium | errors | Missing server configuration becomes empty strings and fails far from its cause | S | medium |
| [WSHL-11](#wshl-11) | low | duplication | Browser preferences are defined in several places, one of them a hand-minified script | S | medium |
| [WSHL-14](#wshl-14) | low | approach | Each render repeats the same session and readiness reads | S | low |
| [WSHL-15](#wshl-15) | low | functions | forward() mixes header policy, body limits, relay and error mapping, and hides one route's limit behind a path string | S | medium |
| [WSHL-16](#wshl-16) | low | structure | Alias routes duplicate the v1 catch-all, and the settings alias drops the query string | S | low |
| [WSHL-17](#wshl-17) | low | comments | Three comments mislead: an orphaned contrast note, an outdated focus-order reason and an incomplete workspace rule | S | low |
| [WSHL-18](#wshl-18) | low | size | AccountFooter and SidebarNav mix derived state and markup | S | low |
| [WSHL-19](#wshl-19) | low | functions | Readiness maps each state three times through nested ternaries, with two different tones for unknown | S | low |
| [WSHL-21](#wshl-21) | low | modules | credential-precedence.ts has no caller in the app | S | low |

### <a id="wshl-01"></a>WSHL-01: The contract validator ignores array bounds, map value schemas and unknown keywords

- **Severity** high · **Dimension** types · **Effort** S · **Risk** high · **Occurrences** 29
- **Where:**
  - [packages/api-client/src/runtime.ts:125-130](../../../../packages/api-client/src/runtime.ts#L125): The array branch checks items only. minItems and maxItems are never read.
  - [packages/api-client/src/runtime.ts:71-78](../../../../packages/api-client/src/runtime.ts#L71): Extra properties are checked only when additionalProperties is false. A schema value is skipped.
  - [packages/api-client/src/runtime.ts:19](../../../../packages/api-client/src/runtime.ts#L19): The index signature admits any keyword, and the switch default (137-138) accepts an unknown type.
  - [packages/api-client/src/generated.ts:2808-2810](../../../../packages/api-client/src/generated.ts#L2808): ModelPolicyState.role_overrides values must be a ModelProfileId. This is never checked.
  - [packages/api-client/src/generated.ts:6906](../../../../packages/api-client/src/generated.ts#L6906): WorkflowGraph.nodes has maxItems 200. This is never checked.
  - [apps/web/components/model-policy-panel.tsx:148](../../../../apps/web/components/model-policy-panel.tsx#L148): A consumer that trusts the parsed role overrides
  - [packages/api-client/tests/contract.test.ts:8-20](../../../../packages/api-client/tests/contract.test.ts#L8): The shared fixtures cover four models and no array bound or map value.
- **Evidence:** runtime.ts handles $ref, anyOf, const, enum, type, format, pattern, minimum and maximum, minLength and maxLength, items, properties, required and additionalProperties: false. It handles nothing else. A read-only python3.12 -I walk of `schemas` in generated.ts finds 15 maxItems, 4 minItems and 10 schema-valued additionalProperties: 29 constraints in 19 schemas. They include ModelPolicyState.role_overrides, ExpertConfig.role_bindings and tools (max 20), JobsChart.hours (1 to 25), and WorkflowGraph.nodes and links. The shared boundary fixture (29 cases, four models) exercises none of them.

  ```ts
  case "array":
    if (!Array.isArray(value)) throw new ContractError(path, "not an array");
    value.forEach((item, index) => {
      if (schema.items !== undefined) check(schemas, schema.items, item, `${path}[${index}]`);
    });
    return;
  ```

- **Why it matters:** Generated parse functions are the only runtime check at the TypeScript trust boundary. Even so, parseModelPolicyState accepts a role override that names an unapproved profile, parseJobsChart accepts an empty or 26-hour chart, and parseWorkflowGraph accepts 201 nodes. The TypeScript side validates less than Pydantic. If Pydantic starts emitting a keyword this runtime ignores (oneOf with a discriminator for a tagged union, for example), every value would pass silently. That is the drift the shared fixtures exist to catch.
- **Recommendation:** Write the failing cases first. In contracts/fixtures/boundary-cases.json, which both languages read, add a WorkflowGraph with 201 nodes and a ModelPolicyState whose role_overrides names an unapproved profile, and add ModelPolicyState to both model maps. Then implement minItems, maxItems and schema-valued additionalProperties in runtime.ts. Add a contract test that walks every schema position in `schemas` and fails on any keyword the runtime does not implement. Allow annotations (title, description, default, examples) explicitly. Leave generated.ts to the generator.
- **Rule check:** contracts.md: shared validation fixtures cover both languages, and TypeScript types do not validate JSON. The fix lives in the hand-written runtime.ts, its test and the shared fixtures. generated.ts is regenerated, never edited.
- **Verification:** confirmed. Re-walked `schemas` in generated.ts: 15 maxItems, 4 minItems and 10 schema-valued additionalProperties, 29 constraints in 19 of 170 schemas, and no other unimplemented keyword today. The shared cases cover four models and none of these constraints.

```ts
// packages/api-client/src/runtime.ts
export const KEYWORDS = new Set(["$ref", "anyOf", "const", "enum", "type", "format", "pattern", "minimum",
  "maximum", "minLength", "maxLength", "items", "minItems", "maxItems", "properties", "required",
  "additionalProperties"]);
export const ANNOTATIONS = new Set(["title", "description", "default", "examples"]);
function checkArray(schemas: Schemas, schema: Schema, value: unknown[], path: string): void; // bounds, then items
// checkObject: typeof schema.additionalProperties === "object" -> check(schemas, it, item, `${path}.${name}`)
// tests/contract.test.ts: walk properties, items, anyOf and additionalProperties of every entry in `schemas`;
//   a key outside KEYWORDS and ANNOTATIONS fails the test, so a new Pydantic keyword cannot pass silently
```

### <a id="wshl-02"></a>WSHL-02: Server reads and the BFF throw away every failure cause, so drift, 401s and timeouts read as signed out or a generic 503

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [apps/web/lib/service-status.ts:52-61](../../../../apps/web/lib/service-status.ts#L52): fetchSession turns any error, including ContractError, into null.
  - [apps/web/lib/service-status.ts:64-85](../../../../apps/web/lib/service-status.ts#L64): Readiness and pending approvals use the same catch-all null.
  - [apps/web/lib/bff.ts:119-125](../../../../apps/web/lib/bff.ts#L119): forward() turns every failure into 503 service_unavailable without logging it.
  - [apps/web/lib/bff.ts:168-174](../../../../apps/web/lib/bff.ts#L168): streamFrom() does the same.
  - [apps/web/app/api/workspace/route.ts:40-43](../../../../apps/web/app/api/workspace/route.ts#L40): A null session, whatever caused it, is answered with 401 not_signed_in.
  - [apps/web/components/account-footer.tsx:24-36](../../../../apps/web/components/account-footer.tsx#L24): A null session renders the Sign in link.
- **Evidence:** (Reflowed.) Generated getSession throws ContractError both for a non-2xx status and for a body that fails parseSessionSummary (runtime.ts:168-170). git grep finds no console or logger call anywhere in apps/web app/, components/ or lib/.

  ```ts
  export async function fetchSession(): Promise<SessionSummary | null> {
    try {
      const token = await accessToken();
      return token === null ? null : await getSession(client({ Authorization: `Bearer ${token}` }));
    } catch {
      return null;
    }
  }
  ```

- **Why it matters:** Several unrelated failures all show a signed-in person the Sign in link: a role value this build does not know, an API on another revision, a missing AUTOBOTS_INTERNAL_TOKEN (the API answers 401), or a 3-second timeout. /api/workspace then tells them "Sign in first." The BFF reports its own 30-second timeout as "The local API is unavailable." No private log records which of these happened, so at runtime nobody can see the contract drift this layer is meant to expose. DH-06 asks for the opposite.
- **Recommendation:** Add a server-only logFailure(operation, error). It records the operation, the error class, the ContractError path, the HTTP status and whether a timeout fired. It never records bodies, headers, tokens or query strings, which keeps the promise in bff.ts:33-35. Have service-status return a discriminated result: signed_out only when there is no token or the API answers 401, and unavailable (logged) for everything else. Render Sign in only for signed_out. Answer /api/workspace with 503 when the session read is unavailable. In forward(), log the cause and map a timeout to 504 upstream_timeout. This needs requestJson to keep the HTTP status; see the requestJson finding.
- **Rule check:** DH-06: centralize error handling, preserve causes in private logs and expose safe typed errors. nextjs.md: server keys never reach props or public responses. The log therefore carries only names, codes, statuses and paths, and the browser still sees only the safe envelope.
- **Verification:** confirmed. No console or logger call exists in apps/web app, components or lib, and every cited catch discards its error; security.py:42-45 refuses an empty internal token with 401. WSHL-20 covers the configuration side of the same symptom.

```ts
// lib/server-log.ts (server-only)
export function logFailure(operation: string, error: unknown): void; // name, ContractError.path, status, timeout
// lib/service-status.ts
export type MemberRead<T> = { kind: "ok"; value: T } | { kind: "signed_out" } | { kind: "unavailable" };
async function memberRead<T>(operation: string, call: (options: ClientOptions) => Promise<T>): Promise<MemberRead<T>>;
//   no token or ApiError 401 -> signed_out; anything else -> logFailure, unavailable
// lib/bff.ts: catch (error) { logFailure(`${method} ${pathOnly(apiPath)}`, error); return timeout ? 504 : 503 }
```

### <a id="wshl-03"></a>WSHL-03: requestJson reports HTTP failures as ContractError and drops the API's typed error

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): The status survives only inside the message, and the ErrorResponse body is never read.
  - [packages/api-client/src/runtime.ts:151-155](../../../../packages/api-client/src/runtime.ts#L151): ClientOptions.fetch is typed as the full typeof fetch.
  - [apps/web/lib/service-status.ts:22-27](../../../../apps/web/lib/service-status.ts#L22): The `as typeof fetch` cast that type forces
  - [packages/api-client/tests/contract.test.ts:33-36](../../../../packages/api-client/tests/contract.test.ts#L33): This test locks in the conflation.
- **Evidence:** The file's own header says ContractError is for values crossing a trust boundary. lib/service-status.ts is the only web caller of the generated request functions, and nothing in apps/web calls parseErrorResponse.

  ```ts
  if (!response.ok) {
    throw new ContractError(path, `request failed with status ${response.status}`);
  }
  return (await response.json()) as unknown;
  ```

- **Why it matters:** Callers cannot tell 401, 403, 503 and contract drift apart without parsing a message string, which is why service-status treats them all alike. Consumers also have to cast their fetch wrapper, because the option type is wider than requestJson needs.
- **Recommendation:** For non-2xx responses, throw an ApiError that carries the status and the parsed JSON body, and keep ContractError for schema violations. Callers read the safe code with the generated parseErrorResponse(error.body). Narrow ClientOptions.fetch to `(url: string, init: RequestInit) => Promise<Response>`, which is all requestJson calls, and remove the cast in service-status.ts. Change contract.test.ts:33-36 first so it expects ApiError.
- **Rule check:** contracts.md: Pydantic/OpenAPI owns ErrorResponse, so callers parse it with the generated parser instead of a hand-written shape. runtime.ts is hand-written and generated.ts is untouched. The package keeps erasableSyntaxOnly, so the sketch declares fields rather than using parameter properties.
- **Verification:** confirmed. requestJson throws ContractError for any non-2xx (runtime.ts:168-170), contract.test.ts:33-36 pins it, and service-status.ts holds the only four web calls to generated request functions.

```ts
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, body: unknown) { super(`request failed with status ${status}`); this.name = "ApiError"; this.status = status; this.body = body; }
}
export interface ClientOptions { baseUrl: string; fetch: (url: string, init: RequestInit) => Promise<Response>; headers?: Record<string, string> }
```

### <a id="wshl-04"></a>WSHL-04: csrfFetch mints a new double-submit token for every write, so overlapping writes can refuse each other

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** high · **Occurrences** 1
- **Where:**
  - [apps/web/lib/csrf-fetch.ts:6-15](../../../../apps/web/lib/csrf-fetch.ts#L6)
  - [apps/web/app/api/csrf/route.ts:9-16](../../../../apps/web/app/api/csrf/route.ts#L9): Every GET mints a token and replaces the cookie.
  - [apps/web/lib/request-guard.ts:57-66](../../../../apps/web/lib/request-guard.ts#L57): The header must equal whichever cookie the browser sends at that moment.
- **Evidence:** 29 csrfFetch calls in 19 component files depend on this function (git grep -c).

  ```ts
  const { header, token } = (await (
    await fetch("/api/csrf", { cache: "no-store" })
  ).json()) as { header: string; token: string };
  return fetch(path, {
    ...init,
    headers: { ...init.headers, [header]: token },
  });
  ```

- **Why it matters:** Write A fetches token T1, and the cookie becomes T1. Before A is sent, write B (from another tab or a quick second action) fetches T2, and the cookie becomes T2. A then carries header T1 with cookie T2 and is refused with invalid_csrf. Callers show this as a generic failure, and sign-in shows it as a wrong password. Every write also costs an extra round trip. The token reply is type-asserted rather than checked. Spreading init.headers would drop every header if a caller passed a Headers instance or a tuple array, both of which RequestInit allows; no caller does today.
- **Recommendation:** Keep one token per browser session. /api/csrf returns the request's existing autobots.csrf value and mints a new one only when there is none, and csrfFetch caches the token in module scope. After an invalid_csrf or missing_csrf refusal, fetch a token once more and resend. The guard refuses before forwarding, so the retry cannot duplicate a write. Check reply.ok and the reply's shape, and build headers with new Headers(init.headers) before setting the token. Add a browser test with two overlapping writes.
- **Rule check:** nextjs.md: protect mutations with Host, Origin and CSRF checks. The double-submit comparison, the Origin, Host and Sec-Fetch-Site checks and the SameSite=Strict cookie stay as they are. Only the token's lifetime changes, and double-submit protection does not depend on it.
- **Verification:** revised. Every GET /api/csrf mints and sets a new cookie, and 29 csrfFetch calls in 19 files rely on it; the race is reasoned from the code, not observed. The header-spreading problem is marked latent: no caller passes a Headers instance or tuple array.

```ts
// lib/csrf-fetch.ts
let current: { header: string; token: string } | null = null;
async function token(fresh: boolean): Promise<{ header: string; token: string }>; // GET /api/csrf, checks ok and shape
export async function csrfFetch(path: string, init: RequestInit): Promise<Response>;
//   headers = new Headers(init.headers); headers.set(header, token); on 403 invalid_csrf or missing_csrf, refresh once and resend
// app/api/csrf/route.ts: reuse request.cookies.get(CSRF_COOKIE) when present, mint only when absent
```

### <a id="wshl-05"></a>WSHL-05: Three route files rebuild the same guard input, error envelope, cookie policy and JSON body read

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/lib/bff.ts:41-54](../../../../apps/web/lib/bff.ts#L41)
  - [apps/web/app/api/session/route.ts:13-31](../../../../apps/web/app/api/session/route.ts#L13): A 403 without Cache-Control: no-store
  - [apps/web/app/api/workspace/route.ts:8-34](../../../../apps/web/app/api/workspace/route.ts#L8): refused() copies safeError().
  - [apps/web/app/api/session/route.ts:38-42](../../../../apps/web/app/api/session/route.ts#L38): Body read with a type assertion
  - [apps/web/app/api/workspace/route.ts:35-36](../../../../apps/web/app/api/workspace/route.ts#L35): Body read with a type assertion
  - [apps/web/lib/session.ts:15-21](../../../../apps/web/lib/session.ts#L15): Session cookie with secure: false
  - [apps/web/app/api/csrf/route.ts:11-16](../../../../apps/web/app/api/csrf/route.ts#L11): CSRF cookie with secure: false
  - [apps/web/app/api/workspace/route.ts:51-56](../../../../apps/web/app/api/workspace/route.ts#L51): The workspace cookie derives secure from the origin.
- **Evidence:** The same six-field GuardInput literal is built in bff.ts:42-49, session/route.ts:15-22 and workspace/route.ts:22-29. The 403 helpers are safeError (bff.ts:21), refused (workspace/route.ts:8) and an inline response in session/route.ts:27-30. The inline one is the only one without Cache-Control: no-store. Cookie `secure` is false in session.ts:19 and csrf/route.ts:15, but workspace/route.ts:55 derives it from AUTOBOTS_ALLOWED_ORIGIN. Both JSON body reads assert a shape:

  ```ts
  const body: unknown = await request.json().catch(() => null);
  const chosen = (body as { workspace_id?: unknown } | null)?.workspace_id;
  ```

- **Why it matters:** A new route that does not go through the proxy has to copy the guard by hand, and the existing copies have already diverged. On an https origin only the workspace cookie would be Secure, and one refusal response lacks no-store.
- **Recommendation:** Move this shared preamble into one server-only module. refusalFor(request) builds GuardInput once and returns the 403 response or null. jsonError(status, code, message) always sets no-store. readJsonObject(request) returns a record or null, which removes both assertions. cookieOptions(config, httpOnly) serves the session, CSRF and workspace cookies. Type the refusal codes as a GuardRefusal union in request-guard.ts. Keep every check and its order; request-guard.test.ts and boundary.spec.ts already cover them.
- **Rule check:** nextjs.md: verify session and workspace on every BFF operation, and protect mutations with Host, Origin and CSRF checks. The extraction keeps each check in the same order. Decision 0023 E3's HttpOnly, SameSite=Strict workspace cookie keeps its flags.
- **Verification:** confirmed. The three GuardInput literals, the missing no-store at session/route.ts:27-30, both body assertions and the three secure settings confirmed. XDUP-12 reports the same duplication from the lens.

```ts
// lib/route-guard.ts (server-only)
export function refusalFor(request: NextRequest): NextResponse | null;
export function jsonError(status: number, code: string, message: string): NextResponse; // always no-store
export async function readJsonObject(request: NextRequest): Promise<Record<string, unknown> | null>;
export function cookieOptions(config: ServerConfig, httpOnly: boolean): { httpOnly: boolean; sameSite: "strict"; path: "/"; secure: boolean };
// lib/request-guard.ts
export type GuardRefusal = "forbidden_host" | "forbidden_origin" | "missing_csrf" | "invalid_csrf";
```

### <a id="wshl-06"></a>WSHL-06: Each component writes its own mutation code: 20 type-asserted response bodies and no shared helper

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 20
- **Where:**
  - [apps/web/lib/csrf-fetch.ts:2-16](../../../../apps/web/lib/csrf-fetch.ts#L2): The only shared piece, and it returns a raw Response.
  - [apps/web/components/account-form.tsx:23-40](../../../../apps/web/components/account-form.tsx#L23)
  - [apps/web/components/sign-in-form.tsx:21-35](../../../../apps/web/components/sign-in-form.tsx#L21)
  - [apps/web/components/workspace-chooser.tsx:22-30](../../../../apps/web/components/workspace-chooser.tsx#L22)
  - [apps/web/components/provider-settings-panel.tsx:192-206](../../../../apps/web/components/provider-settings-panel.tsx#L192): A local mutate() helper
  - [apps/web/components/keys-and-vars-panel.tsx:203](../../../../apps/web/components/keys-and-vars-panel.tsx#L203): Another local mutate() helper
  - [apps/web/components/run-controls.tsx:73](../../../../apps/web/components/run-controls.tsx#L73): A local send() helper (run-panel.tsx:84 has another)
  - [apps/web/components/approvals-panel.tsx:216-218](../../../../apps/web/components/approvals-panel.tsx#L216): Asserted error body
- **Evidence:** (account-form.tsx:33-35.) git grep finds this `(await reply.json().catch(() => null)) as` form 20 times in 15 component files. It also finds 29 csrfFetch calls in 19 files, 28 JSON Content-Type literals in components, two local mutate() helpers and two local send() helpers, and no caller of the generated parseErrorResponse.

  ```ts
  const body = (await reply.json().catch(() => null)) as {
    code?: string;
  } | null;
  ```

- **Why it matters:** DH-06 asks for explicit response parsing and no blanket assertions. Yet 20 places read error codes from unchecked shapes, and every form repeats the same busy, try, catch and message sequence. That sequence is most of why AccountForm (63 lines) and SignInForm (66 lines) exceed the 60-line metric lead.
- **Recommendation:** Add a browser-side sendJson(path, { method, body, parse, idempotencyKey }) built on csrfFetch. On success it returns the value parsed by the generated parser. On failure it returns the status and the error parsed by parseErrorResponse, or null when that body fails its contract or the network fails. Migrate this area's three forms first, and the other screens when they are next touched.
- **Rule check:** DH-06: use generated API types, parse responses explicitly at untrusted boundaries, avoid blanket type assertions, and rely on server idempotency for duplicate submits (the helper carries Idempotency-Key). contracts.md: ErrorResponse comes from the generated client.
- **Verification:** confirmed. Recounted: 20 casts of this form in 15 files (19 on failure bodies; continue-run.tsx:53 casts a success body), 29 csrfFetch calls in 19 files and 28 JSON Content-Type literals in 18 files. WSYS-02 should use this same helper.

```ts
// lib/bff-client.ts (browser)
export type Outcome<T> =
  | { ok: true; value: T }
  | { ok: false; status: number; error: ErrorResponse | null }; // status 0 for a network failure
export async function sendJson<T>(path: string, options: {
  method: "POST" | "PUT" | "PATCH" | "DELETE"; body?: unknown;
  parse: (value: unknown) => T; idempotencyKey?: string;
}): Promise<Outcome<T>>;
```

### <a id="wshl-07"></a>WSHL-07: Sign-in reports an unavailable service as a wrong password, and sign-out fails silently

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [apps/web/app/api/session/route.ts:51-55](../../../../apps/web/app/api/session/route.ts#L51)
  - [apps/web/components/sign-in-form.tsx:21-35](../../../../apps/web/components/sign-in-form.tsx#L21)
  - [apps/web/components/sign-in-form.tsx:64-72](../../../../apps/web/components/sign-in-form.tsx#L64)
  - [apps/web/components/sign-out-button.tsx:10-13](../../../../apps/web/components/sign-out-button.tsx#L10)
- **Evidence:** The form treats any reply that is not ok, and any network failure, as `failed`, and shows "That email and password did not work." That includes a 403 guard refusal and a 500. SignOutButton runs `await csrfFetch("/api/session", { method: "DELETE" }).catch(() => null); router.refresh();` without checking the reply.

  ```ts
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error !== null) {
    return NextResponse.json(REFUSED, { status: 401 });
  }
  ```

- **Why it matters:** When Supabase Auth or the network is down, people are told their credentials are wrong and may retry or reset a password for nothing. A refused sign-out leaves them signed in with no message. DH-06 asks for unavailable and retryable states to be shown deliberately.
- **Recommendation:** In the route, keep 401 sign_in_failed for credential errors, still without saying which field failed. Answer Auth transport errors and 5xx statuses with 503 service_unavailable in the BFF's envelope. In the form, show the credential message only for 401, an unavailable message for 503 or a network failure, and a prompt to reload for a 403 refusal. Show a message when sign-out fails.
- **Rule check:** DH-06: represent loading, empty, denied, unavailable and retryable states deliberately. The 401 message still does not reveal whether the email exists.
- **Verification:** confirmed. The route maps every Auth error to 401 sign_in_failed (51-55), the form shows the credential sentence for any non-ok reply or rejection, and SignOutButton ignores its reply.

### <a id="wshl-08"></a>WSHL-08: schema-value.test.ts never runs, because verify.py names unit tests one by one

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161)
  - [apps/web/tests/unit/schema-value.test.ts:6-17](../../../../apps/web/tests/unit/schema-value.test.ts#L6)
  - [apps/web/package.json:5-11](../../../../apps/web/package.json#L5): No test script
  - [packages/api-client/tsconfig.json:19-21](../../../../packages/api-client/tsconfig.json#L19): Only src/ is type-checked, not tests/.
  - [openspec/changes/archive/2026-11-08-us-16-2-schema-readiness-against-every/verification.md:22](../../../../openspec/changes/archive/2026-11-08-us-16-2-schema-readiness-against-every/verification.md#L22): Says fast passed web unit tests after this test was added
- **Evidence:** .checks/full/latest.json records exactly that argv and 33 tests (14 plus 19), none of them from schema-value.test.ts. The US-16.2 record cites this test as the evidence for a passing scenario.

  ```py
  Step('web_unit_tests', (str(Path(tools.node_dir) / 'node'), '--test', 'apps/web/tests/unit/request-guard.test.ts',
                         'apps/web/tests/unit/credential-precedence.test.ts'), root),
  ```

- **Why it matters:** Any web unit test added beyond these two passes when run by hand but is skipped by every profile. The US-16.2 evidence reads as if the profile ran it, and contributors have no package script that runs the folder.
- **Recommendation:** Add a test:unit script to apps/web/package.json that runs node --test over tests/unit/\*\*/\*.test.ts, and have the verify step call that script so new files are picked up. Propose the verify.py change to the scripts owners. Put packages/api-client/tests under a type-checked tsconfig, for example a tsconfig.test.json that api_client_typecheck includes.
- **Rule check:** AGENTS.md: skipped tests never count as passing implementation evidence. verify.py belongs to the scripts area, so this review only proposes the change.
- **Verification:** confirmed. verify.py:161-162 names two files; .checks/full/latest.json records that argv and 33 passing tests, none from schema-value.test.ts, while the US-16.2 record says fast passed web unit tests.

### <a id="wshl-09"></a>WSHL-09: Lint and format enforce only the Next.js presets, and packages/api-client is outside both

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/eslint.config.mjs:4-8](../../../../apps/web/eslint.config.mjs#L4)
  - [apps/web/package.json:6-7](../../../../apps/web/package.json#L6): lint and format:check cover apps/web only.
  - [packages/api-client/src/runtime.ts:59](../../../../packages/api-client/src/runtime.ts#L59): 125 characters. 15 lines here exceed Prettier's 80.
  - [packages/api-client/tsconfig.json:15](../../../../packages/api-client/tsconfig.json#L15): erasableSyntaxOnly is set here but not in apps/web/tsconfig.json, although web unit tests also run under Node type stripping.
  - [apps/web/tsconfig.json:2-28](../../../../apps/web/tsconfig.json#L2)
- **Evidence:** The measurement found 94 type assertions, 83 functions over 60 lines and 31 functions over complexity 10, and no rule holds any of these at their current level. I ran ESLint read-only on this area with projectService plus no-floating-promises, no-misused-promises, switch-exhaustiveness-check and no-unnecessary-type-assertion. It found no violation in production code, only node:test calls.

  ```js
  const config = [
    { ignores: [".next/**", "next-env.d.ts"] },
    ...nextCoreWebVitals,
    ...nextTypescript,
  ];
  ```

- **Why it matters:** DH-06's rules against blanket assertions and for small functions depend on review alone, and the hand-written contract validator has no lint or format gate at all. Lint runs with --max-warnings=0, so any rule added at warn level fails the check immediately, which means there is no way to ratchet today.
- **Recommendation:** Add the type-aware promise and exhaustiveness rules as errors now, since they have no production hits, and turn no-floating-promises off for tests/unit. Report size, complexity and assertion rules from a separate non-blocking ESLint run, as the measurement step did. Then record per-file baselines as overrides, then make the rules errors. Extend lint and format:check to packages/api-client, and add erasableSyntaxOnly to apps/web/tsconfig.json.
- **Rule check:** DH-06: pinned ESLint with Next.js, React and TypeScript rules, Prettier, and lint run explicitly. nextjs.md: lint separately from Next.js 16 builds. Nothing here touches next build.
- **Verification:** confirmed. Re-ran the four type-aware rules read-only on all of apps/web: no-floating-promises, no-misused-promises and switch-exhaustiveness-check have no production hit (7 hits in tests/unit), while no-unnecessary-type-assertion has 3 at home-activity.tsx:79-81 and needs a baseline.

```js
// apps/web/eslint.config.mjs, after the Next presets
{
  files: ["**/*.ts", "**/*.tsx"],
  languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
  rules: { "@typescript-eslint/no-floating-promises": "error", "@typescript-eslint/no-misused-promises": "error",
           "@typescript-eslint/switch-exhaustiveness-check": "error" },
},
{ files: ["tests/unit/**"], rules: { "@typescript-eslint/no-floating-promises": "off" } },
```

### <a id="wshl-10"></a>WSHL-10: DH-06's Vitest and Testing Library layer is missing without a recorded decision, and BFF policy has no fast test

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [PRD-Development-Harness.md:141](../../../PRD/PRD-Development-Harness.md#L141)
  - [apps/web/package.json:25-37](../../../../apps/web/package.json#L25): Playwright and axe only
  - [apps/web/lib/bff.ts:15-19](../../../../apps/web/lib/bff.ts#L15): Body limits. No test asserts 413 or request_too_large.
  - [apps/web/lib/workspace-choice.ts:24-32](../../../../apps/web/lib/workspace-choice.ts#L24): currentWorkspace has no unit test.
  - [apps/web/lib/csrf-fetch.ts:2-16](../../../../apps/web/lib/csrf-fetch.ts#L2): No test
  - [apps/web/tests/unit/request-guard.test.ts:4](../../../../apps/web/tests/unit/request-guard.test.ts#L4): Relative .ts import, because node:test cannot resolve @/ aliases or server-only
  - [openspec/changes/archive/2026-11-05-us-1-3-h0-locked-toolchains-minimal/proposal.md:28](../../../../openspec/changes/archive/2026-11-05-us-1-3-h0-locked-toolchains-minimal/proposal.md#L28): US-1.3 deferred Vitest and Testing Library to the first story with behavior to test
- **Evidence:** DH-06: "Use Vitest/React Testing Library for relevant pure/client behavior". apps/web has three node:test files covering 3 of its 13 lib modules, and no component tests. git grep for 413, request_too_large and "too large" under apps/web/tests finds nothing. The US-1.3 proposal deferred Vitest and Testing Library to the story that first had behavior to test, and no decision under docs/engineering/decisions mentions Vitest or node:test since. boundary.spec.ts covers the Host, CSRF, internal-token and unavailable cases, but runs only in the db and full profiles.
- **Why it matters:** The fast profile cannot exercise BFF policy, csrfFetch, workspace selection or any client component, so each such change waits for the browser suites. The run body limit from PRD-Tool-Catalog FI-01 is not tested at any level.
- **Recommendation:** Choose one of two paths. Either record a decision that node:test replaces Vitest for pure modules, or adopt Vitest and Testing Library with path-alias resolution under an authorized story, since that is a dependency install. Either way, keep fast-testable logic in modules with no server-only or '@/' imports, as request-guard.ts is: plain Node cannot resolve server-only from apps/web, whatever condition is passed. Then extract bff.ts's pure policy and test the body limits, header allowlists and relay first.
- **Rule check:** DH-06 names Vitest and React Testing Library, so a deviation needs a recorded decision. AGENTS.md: install dependencies only when a story requires them, pinned and recorded.
- **Verification:** revised. Line 141, the missing 413 test and the absent decision confirmed, and the US-1.3 deferral added. Revised: server-only is not resolvable by plain Node from apps/web (Next resolves it internally), so --conditions=react-server cannot load those modules.

### <a id="wshl-12"></a>WSHL-12: The primitive set stops short: no Label or Dialog, Card is fixed to &lt;section&gt;, Separator is unused

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [apps/web/components/ui/field.tsx:10-67](../../../../apps/web/components/ui/field.tsx#L10): Controls only, no Label
  - [apps/web/components/account-form.tsx:50](../../../../apps/web/components/account-form.tsx#L50): Raw label
  - [apps/web/components/sign-in-form.tsx:41](../../../../apps/web/components/sign-in-form.tsx#L41): Raw label
  - [apps/web/components/about-services.tsx:19-23](../../../../apps/web/components/about-services.tsx#L19): Dialog chrome restated
  - [apps/web/components/search-palette.tsx:128-132](../../../../apps/web/components/search-palette.tsx#L128): Dialog chrome restated
  - [apps/web/components/tool-catalog.tsx:452-461](../../../../apps/web/components/tool-catalog.tsx#L452): Background pair instead of popover, backdrop /60, and the only one that closes on an outside click
  - [apps/web/components/ui/card.tsx:6-16](../../../../apps/web/components/ui/card.tsx#L6): Always renders &lt;section&gt;
  - [apps/web/components/ui/separator.tsx:6-15](../../../../apps/web/components/ui/separator.tsx#L6): Nothing imports it
- **Evidence:** field.tsx provides Input, Textarea, Select and Choice but no Label. Screens contain 49 raw &lt;label&gt; elements in 20 files, and 12 of them restate text-sm font-medium. Three native dialogs restate their chrome. about-services.tsx:22 and search-palette.tsx:132 use the popover pair with backdrop:bg-black/50. tool-catalog.tsx:461 uses bg-background with /60, and it alone closes on an outside click. Card always renders &lt;section&gt;, so 8 bg-card surfaces copy its classes instead of using it: 3 li, 1 ul, 1 form, 1 div and 2 section. Nothing imports Separator.
- **Why it matters:** DS-03 maps dialogs to popover and popover-foreground, and one dialog already departs from that. Label styling and dialog behavior drift from screen to screen, and Card's fixed element forces copies.
- **Recommendation:** Add Label to field.tsx. Add a Dialog primitive on the native &lt;dialog&gt; with the popover pair, Escape, outside-click close and focus return, as Decision 0026 G2–G3 describe for the tool guide. Give Card an `as` prop, as SectionLabel already has. Delete Separator or start using it. Check both themes, as DS-05 requires, when screens move to the new primitives.
- **Rule check:** DS-03: menus, selects and dialogs use popover and popover-foreground, built from real accessible components. Decision 0026 G2–G3: a native dialog with the browser's focus trap, which the primitive keeps.
- **Verification:** revised. 49 raw labels in 20 files confirmed, with 12 (not 11) restating text-sm font-medium; the 8 copied bg-card surfaces, the three dialogs and the unused Separator confirmed.

```tsx
// components/ui/field.tsx
export function Label({ className, ...props }: ComponentProps<"label">); // data-slot="label", text-sm font-medium
// components/ui/dialog.tsx (native <dialog>)
export function Dialog(props: { open: boolean; onClose(): void; labelledBy: string; size?: "md" | "xl" | "3xl"; children: ReactNode });
// components/ui/card.tsx
export function Card(props: { as?: "section" | "li" | "div" | "form" } & ComponentProps<"section">);
```

### <a id="wshl-13"></a>WSHL-13: Font sizes and some radii are pixel literals, not tokens

- **Severity** medium · **Dimension** naming · **Effort** M · **Risk** medium · **Occurrences** 217
- **Where:**
  - [apps/web/app/globals.css:31-77](../../../../apps/web/app/globals.css#L31): @theme maps colors, fonts and radii, but no type scale.
  - [apps/web/components/ui/page-header.tsx:28-32](../../../../apps/web/components/ui/page-header.tsx#L28)
  - [apps/web/components/ui/button.tsx:22](../../../../apps/web/components/ui/button.tsx#L22)
  - [apps/web/app/sign-in/page.tsx:8](../../../../apps/web/app/sign-in/page.tsx#L8): Restates PageHeader's title size
  - [apps/web/components/sidebar-nav.tsx:117](../../../../apps/web/components/sidebar-nav.tsx#L117)
  - [apps/web/components/notifications-control.tsx:65](../../../../apps/web/components/notifications-control.tsx#L65)
  - [apps/web/components/appearance-control.tsx:78](../../../../apps/web/components/appearance-control.tsx#L78): rounded-[10px], which equals rounded-lg
  - [apps/web/components/experts-panel.tsx:344](../../../../apps/web/components/experts-panel.tsx#L344): rounded-[10px]
- **Evidence:** git grep counts 212 text-[Npx] classes in 39 files across app/ and components/, in 13 distinct sizes: 75 at 12.5px, 63 at 13px and 19 at 13.5px, among others. It also counts rounded-[10px] four times and rounded-[7px] once. The primitives add their own literals: PageHeader's title is text-[32px] and its description text-[14.5px], and Button's sm size is text-[13px]. The sign-in page restates the title size without using PageHeader.
- **Why it matters:** DS-03 asks for consistent typography and a radius scale mapped to the canonical base, and rounded-[10px] just restates --radius. Restyling text means editing 39 files, and new screens keep inventing sizes.
- **Recommendation:** Add role-named --text-\* tokens to the @theme block (title, lead, row, meta, badge and so on), collapsing the 13 sizes, and never reuse a --color-\* name: text-control already means the control border color. Use them in components/ui first, then replace literals as files are touched, and replace rounded-[10px] with rounded-lg. Add a grep ratchet that fails on any new text-[Npx] or rounded-[Npx] class.
- **Rule check:** DS-03: map the radius scale to the canonical base and keep typography consistent. DS-01: the color tokens and --radius stay untouched; the new names are a type scale, not a palette change.
- **Verification:** revised. Counts reproduced (212 text-[Npx] in 39 files, 13 sizes; rounded-[10px] 4, rounded-[7px] 1), and Button's size moved to line 22. Sketch revised: a Tailwind 4.3.4 compile resolved text-control to --color-control's color and dropped the size, so no size token may reuse a --color-\* name.

```css
@theme inline {
  --text-title: 2rem;        /* PageHeader and sign-in, 32px */
  --text-lead: 0.90625rem;   /* PageHeader description, 14.5px */
  --text-row: 0.8125rem;     /* small buttons and nav items, 13px; not "control": --color-control owns text-control */
  --text-meta: 0.78125rem;   /* hints and permissions, 12.5px */
  --text-badge: 0.71875rem;  /* counts, 11.5px */
}
```

### <a id="wshl-20"></a>WSHL-20: Missing server configuration becomes empty strings and fails far from its cause

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/lib/server-config.ts:12-21](../../../../apps/web/lib/server-config.ts#L12)
  - [apps/web/lib/session.ts:11-14](../../../../apps/web/lib/session.ts#L11): createServerClient throws on an empty key.
  - [apps/web/lib/bff.ts:55](../../../../apps/web/lib/bff.ts#L55): accessToken() runs outside forward()'s try.
  - [apps/web/lib/request-guard.ts:38](../../../../apps/web/lib/request-guard.ts#L38): new URL() throws on a malformed origin.
  - [apps/web/app/api/workspace/route.ts:55](../../../../apps/web/app/api/workspace/route.ts#L55): new URL() again
  - [services/agent/src/autobots/api/security.py:42-45](../../../../services/agent/src/autobots/api/security.py#L42): The API refuses an empty internal token (fails closed).
- **Evidence:** With the anon key unset, @supabase/ssr's createServerClient throws "Your project's URL and Key are required" (node_modules/@supabase/ssr/dist/main/createServerClient.js:12-13). Because accessToken() runs before forward()'s try (bff.ts:55, 76), every BFF route and the session route answer a bare 500, and service-status turns the same error into signed out. With the internal token unset, the API refuses every call, and the shell again shows Sign in. A malformed AUTOBOTS_ALLOWED_ORIGIN makes new URL() throw in guardRequest and in the workspace route.

  ```ts
  internalToken: process.env.AUTOBOTS_INTERNAL_TOKEN ?? "",
  ...
  supabaseAnonKey: process.env.AUTOBOTS_SUPABASE_ANON_KEY ?? "",
  ```

- **Why it matters:** A misconfigured local start looks like a signed-out session or a wrong password, and no log names the missing variable. Failing closed is the right outcome; what is missing is a way to tell why.
- **Recommendation:** Validate in serverConfig(): require both secrets to be non-empty and the origin to parse as an http(s) origin, and throw a ConfigurationError that names the missing variables but never their values. Catch it in forward(), streamFrom() and the session and workspace routes as 503 server_misconfigured with one log line, and have service-status report unavailable rather than signed out. Keep reading the environment on each call, so nothing is compiled into a build.
- **Rule check:** DH-06: validate data at trust boundaries and expose safe typed errors. nextjs.md: server keys never reach props or bundles, so the error names variables, never values. The API's fail-closed check stays.
- **Verification:** confirmed. Empty-string defaults, createServerClient's throw on an empty key (@supabase/ssr createServerClient.js:12-13), accessToken() before forward()'s try and both new URL() calls confirmed. WSHL-02 owns the logging half.

### <a id="wshl-11"></a>WSHL-11: Browser preferences are defined in several places, one of them a hand-minified script

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/app/layout.tsx:13-17](../../../../apps/web/app/layout.tsx#L13)
  - [apps/web/components/appearance-control.tsx:84-96](../../../../apps/web/components/appearance-control.tsx#L84): Keys and attribute values (outside this area)
  - [apps/web/components/appearance-control.tsx:71-75](../../../../apps/web/components/appearance-control.tsx#L71): The theme choices again
  - [apps/web/components/theme-provider.tsx:10-16](../../../../apps/web/components/theme-provider.tsx#L10): Theme list and storage key
  - [apps/web/components/notifications-control.tsx:12](../../../../apps/web/components/notifications-control.tsx#L12): A no-op subscribe, also in appearance-control.tsx:8 and goal-composer.tsx:36
  - [apps/web/components/notifications-control.tsx:30-34](../../../../apps/web/components/notifications-control.tsx#L30): The mounted idiom, repeated in appearance-control.tsx:144-148
- **Evidence:** appearance-control.tsx builds the same keys as `autobots.${preference}`, with the values in ATTRIBUTE_VALUE (serif off, density compact, motion reduce, stream off). The theme values appear in layout.tsx, theme-provider.tsx and appearance-control.tsx.

  ```js
  try{var s=localStorage,k="autobots.theme",v=s.getItem(k);if(v!==null&&v!=="dark"&&v!=="light"&&v!=="system")s.removeItem(k);
  ...if(s.getItem("autobots.serif")==="off")d.dataset.serif="off";if(s.getItem("autobots.density")==="compact")...
  ```

- **Why it matters:** Adding or renaming a preference means editing a minified string that no unit test executes. A mismatch shows up as a flash of the wrong presentation at first paint (DS-02), and only the browser specs would catch it.
- **Recommendation:** Define the keys and values once in a shared module, build the before-paint script from them, and run that script in a node:test against a fake localStorage and dataset. Move the hydration idiom into one useHydrated() hook. Behavior does not change.
- **Rule check:** DS-02 and Decision 0022 D2: dark by default, System only when chosen, and the preference applied before paint. The PRD-Studio SE-03 presentation keys are unchanged. This is a single definition, not new behavior.
- **Verification:** revised. Keys, values and idioms confirmed (the no-op subscribe in three files). Lowered to low, as XDUP-19: db-profile suites restore all four presentation keys through the script (appearance.spec.ts:422-490, stream-result.spec.ts:124-134). One change with WSYS-11.

```ts
// lib/preferences.ts (no React; imported by the layout, the theme provider and the Settings controls)
export const THEME_KEY = "autobots.theme";
export const THEMES = ["dark", "light", "system"] as const;
export const PRESENTATION = { serif: "off", density: "compact", motion: "reduce", stream: "off" } as const;
export function beforePaintScript(): string; // built with JSON.stringify of the constants
// lib/use-hydrated.ts
export function useHydrated(): boolean; // useSyncExternalStore(noop, () => true, () => false)
```

### <a id="wshl-14"></a>WSHL-14: Each render repeats the same session and readiness reads

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/app-shell.tsx:14-19](../../../../apps/web/components/app-shell.tsx#L14)
  - [apps/web/components/account-footer.tsx:24](../../../../apps/web/components/account-footer.tsx#L24)
  - [apps/web/app/page.tsx:33-38](../../../../apps/web/app/page.tsx#L33)
  - [apps/web/lib/service-status.ts:52-85](../../../../apps/web/lib/service-status.ts#L52)
  - [apps/web/lib/session.ts:38-42](../../../../apps/web/lib/session.ts#L38)
- **Evidence:** On Home, the shell calls fetchPendingApprovals and fetchReadiness (app-shell.tsx:15, 19), and AccountFooter calls fetchSession (account-footer.tsx:24). The page then calls fetchServiceStatus, fetchSession and fetchReadiness again (app/page.tsx:33-38). That makes six API reads, two of them duplicates, and five accessToken() calls, each of which builds a Supabase server client. Nothing is wrapped in React cache().
- **Why it matters:** Every navigation makes duplicate local requests, and two readiness reads a moment apart can disagree between the sidebar line and the page's service chips.
- **Recommendation:** Wrap accessToken, fetchSession, fetchReadiness and fetchPendingApprovals in React's cache(), which memoizes per server request only.
- **Rule check:** DH-06: prevent workspace data from leaking through shared caches. React cache() is scoped to one server request for one user, so it adds no shared cache.
- **Verification:** confirmed. Traced Home: six API reads with session and readiness read twice, and five accessToken() calls; nothing in apps/web uses React cache().

```ts
import { cache } from "react";
export const fetchSession = cache(async (): Promise<SessionSummary | null> => { /* unchanged body */ });
```

### <a id="wshl-15"></a>WSHL-15: forward() mixes header policy, body limits, relay and error mapping, and hides one route's limit behind a path string

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/lib/bff.ts:15-19](../../../../apps/web/lib/bff.ts#L15): Run-creation limit keyed on a path string
  - [apps/web/lib/bff.ts:71-126](../../../../apps/web/lib/bff.ts#L71): forward(), complexity 13
  - [apps/web/lib/bff.ts:80-89](../../../../apps/web/lib/bff.ts#L80): Request header allowlist, inline
  - [apps/web/lib/bff.ts:141-144](../../../../apps/web/lib/bff.ts#L141): A second header copy using a literal header name
  - [apps/web/lib/bff.ts:105-118](../../../../apps/web/lib/bff.ts#L105): Relay
  - [apps/web/lib/bff.ts:151-160](../../../../apps/web/lib/bff.ts#L151): The relay again
  - [apps/web/lib/bff.ts:76](../../../../apps/web/lib/bff.ts#L76): authorized() runs before the try
- **Evidence:** forward() copies request headers from an inline list, reads and limits the body, fetches with a 30-second timeout, rebuilds the response headers and maps every failure to 503. streamFrom repeats the header copy with the literal "x-autobots-workspace" and repeats the non-stream relay. authorized() runs before the try, so its exceptions escape the error envelope.

  ```ts
  function bodyLimit(method: string, apiPath: string): number {
    return method === "POST" && apiPath.split("?")[0] === "/v1/runs"
      ? RUN_BODY_BYTES
      : MAX_BODY_BYTES;
  }
  ```

- **Why it matters:** The generic forwarder carries one route's policy, the two relay copies can drift apart, and none of it can be unit-tested as written.
- **Recommendation:** Split forward() into pure helpers shared with streamFrom: copying the header allowlist, building relay headers, and reading the body against a limit. Pass the limit in from the route, with a dedicated app/api/v1/runs/route.ts for run creation. Move authorized() inside the error handling, and unit-test the helpers.
- **Rule check:** nextjs.md: the per-operation session and workspace checks and the mutation guards stay, in the same order. PRD-Tool-Catalog FI-01's 12 MiB allowance for run creation stays, now stated by the route that needs it.
- **Verification:** revised. Mixed concerns, the literal header name and authorized() before the try confirmed. The trailing-slash claim was removed: with Next's default trailingSlash, /api/v1/runs/ redirects to /api/v1/runs, so the run limit still applies.

```ts
const REQUEST_HEADERS = ["content-type", WORKSPACE_HEADER, "idempotency-key"] as const;
const RESPONSE_HEADERS = ["content-disposition", "x-content-type-options"] as const;
export function upstreamHeaders(request: NextRequest, base: Headers): Headers; // pure allowlist copy
export function relayHeaders(reply: Response): Headers;                        // no-store plus allowlist
async function readBody(request: NextRequest, limit: number): Promise<ArrayBuffer | null | "too_large">;
export async function forward(request: NextRequest, apiPath: string, limit = MAX_BODY_BYTES): Promise<NextResponse>;
// app/api/v1/runs/route.ts: POST passes RUN_BODY_BYTES; GET forwards the list with its query
```

### <a id="wshl-16"></a>WSHL-16: Alias routes duplicate the v1 catch-all, and the settings alias drops the query string

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/app/api/settings/[...path]/route.ts:11-15](../../../../apps/web/app/api/settings/[...path]/route.ts#L11): No request.nextUrl.search
  - [apps/web/app/api/v1/[...path]/route.ts:11-16](../../../../apps/web/app/api/v1/[...path]/route.ts#L11): Forwards the query
  - [apps/web/app/api/models/route.ts:5-7](../../../../apps/web/app/api/models/route.ts#L5)
  - [apps/web/app/api/runs/intent/route.ts:5-7](../../../../apps/web/app/api/runs/intent/route.ts#L5)
  - [apps/web/components/model-policy-panel.tsx:136-137](../../../../apps/web/components/model-policy-panel.tsx#L136): App callers use the aliases.
  - [apps/web/tests/browser/saved-choice.spec.ts:56](../../../../apps/web/tests/browser/saved-choice.spec.ts#L56): The only caller of /api/runs/intent, next to /api/v1/runs at line 52
- **Evidence:** (Reflowed.) /api/models and /api/runs/intent forward to /v1/models and /v1/runs/intent, which the catch-all already reaches. Components call /api/settings/\* 12 times and /api/models 3 times, and never the /api/v1 forms. No app code calls /api/runs/intent.

  ```ts
  // app/api/settings/[...path]/route.ts
  return forward(request, `/v1/settings/${path.map(encodeURIComponent).join("/")}`);
  // app/api/v1/[...path]/route.ts
  return forward(request, `/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`);
  ```

- **Why it matters:** Two URLs reach the same endpoints, a settings read with a query string would lose it silently, and the route list is longer than the surface it exposes.
- **Recommendation:** Pick one scheme. Either move the 15 call sites and the spec to /api/v1/... and delete the three aliases, or keep them as documented aliases and have the settings alias forward request.nextUrl.search the way the catch-all does.
- **Rule check:** nextjs.md: verify session and workspace on every BFF operation. Every alias already calls forward(), so consolidating them changes no check.
- **Verification:** confirmed. The settings alias omits request.nextUrl.search; components call /api/settings/ 12 times in 4 files and /api/models 3 times, and only saved-choice.spec.ts calls /api/runs/intent. XMOD-16 reports the same from the lens.

### <a id="wshl-17"></a>WSHL-17: Three comments mislead: an orphaned contrast note, an outdated focus-order reason and an incomplete workspace rule

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/app-shell.tsx:11-13](../../../../apps/web/components/app-shell.tsx#L11): Gives Decision 0021 R6's reason for Home being the first stop
  - [apps/web/components/app-shell.tsx:42](../../../../apps/web/components/app-shell.tsx#L42): New run, then Search, come right after the skip link; both are buttons
  - [apps/web/app/globals.css:102-103](../../../../apps/web/app/globals.css#L102): Describes a rule that US-16.1 removed
  - [apps/web/lib/bff.ts:63-67](../../../../apps/web/lib/bff.ts#L63): Says the chosen workspace is what gets sent
  - [apps/web/lib/bff.ts:80-89](../../../../apps/web/lib/bff.ts#L80): A client-sent header then replaces it.
- **Evidence:** app-shell.tsx:12, a 152-character line, says Home holds the goal composer, "so the first link after the skip link is Home". That is still true of links, because New run and Search are buttons, but it is Decision 0021 R6's reason for Home being the first stop, and since Decision 0022 D3 and D16 the first stops are those two buttons (line 42, new-run.tsx:17, appearance.spec.ts:301-307). globals.css:102-103 describes an --input edge whose `.control-boundary` rule was removed by US-16.1 (747bc88), so the comment now sits above the reduced-motion block. bff.ts:63 says the workspace chosen in the cookie is sent. forward() and streamFrom (141-144) then replace it with any client-sent x-autobots-workspace header, which browser specs rely on (settings.spec.ts:266). No comment says which one wins, and the header name is spelled out as a literal three times instead of using WORKSPACE_HEADER.
- **Why it matters:** Readers are given an outdated reason for the focus order and a contrast fix that no longer exists, and the workspace precedence at the BFF has to be worked out from the code.
- **Recommendation:** Rewrite app-shell.tsx:11-13 to describe the current order (skip link, New run, Search, then Home, by Decision 0022 D3 and D16), and wrap it. Delete globals.css:102-103, or point it at Decision 0023 E1's --control-border. At bff.ts:63, say that an explicit request header wins over the cookie and that the API checks membership either way, and use WORKSPACE_HEADER.
- **Rule check:** Ground rule 2 keeps the practice of citing decisions and stories in comments. These edits keep the citations and correct the text. Decision 0023 E3 is unchanged.
- **Verification:** revised. The orphaned globals.css note (rule removed in 747bc88) and the bff.ts precedence gap confirmed. The app-shell sentence is literally true, since New run and Search are buttons, so it is reworded as an outdated reason rather than a wrong fact.

### <a id="wshl-18"></a>WSHL-18: AccountFooter and SidebarNav mix derived state and markup

- **Severity** low · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/account-footer.tsx:23-97](../../../../apps/web/components/account-footer.tsx#L23): 75 lines by ESLint's count
  - [apps/web/components/account-footer.tsx:9](../../../../apps/web/components/account-footer.tsx#L9): ROLE map
  - [apps/web/app/settings/account/page.tsx:10](../../../../apps/web/app/settings/account/page.tsx#L10): The same ROLE map, copied
  - [apps/web/components/sidebar-nav.tsx:70-133](../../../../apps/web/components/sidebar-nav.tsx#L70): 64 lines
  - [apps/web/components/sidebar-nav.tsx:110-123](../../../../apps/web/components/sidebar-nav.tsx#L110): Special case for /approvals inside the generic item loop
  - [apps/web/components/sidebar-nav.tsx:62-67](../../../../apps/web/components/sidebar-nav.tsx#L62): Current link by longest prefix
  - [apps/web/components/settings-nav.tsx:35](../../../../apps/web/components/settings-nav.tsx#L35): Current link by exact match
- **Evidence:** AccountFooter fetches the session, works out the current workspace and whether to show the chooser (37-41), computes initials, and renders the sign-in prompt, the chooser and the account menu, all in one function. SidebarNav checks `href === "/approvals"` inside the generic item loop to draw the pending badge. The two navs decide the current link differently.
- **Why it matters:** The workspace-choice rule from Decision 0023 E3 and the initials logic can only be tested through the browser, and every new nav count or menu entry grows the same function.
- **Recommendation:** Move the pure parts out: workspace state, initials and the role labels go into a small module with unit tests. Split AccountFooter into SignInPrompt and AccountMenu. Give nav items an optional count key rendered by a PendingBadge, and share one isCurrent(pathname, href) between the two navs.
- **Rule check:** Decision 0023 E3: the chooser still appears for a member of several workspaces or after a stale choice. The PRD-Studio SH-01 nav order is unchanged.
- **Verification:** confirmed. AccountFooter 75 and SidebarNav 64 counted lines, the copied ROLE map, the /approvals special case and the two current-link rules confirmed.

```tsx
// lib/account.ts (pure)
export const ROLE_LABEL = { owner: "Owner", member: "Member" } as const; // also used by settings/account
export function initials(name: string): string;
export function workspaceState(session: SessionSummary, chosen: string | null): { current: Workspace | null; choosing: boolean };
// components/account-footer.tsx: session === null ? <SignInPrompt /> : <>{choosing && <WorkspaceChooser />}<AccountMenu /></>
// components/sidebar-nav.tsx: items gain `count?: "pending"`; <NavItem />, <PendingBadge />; isCurrent() shared with SettingsNav
```

### <a id="wshl-19"></a>WSHL-19: Readiness maps each state three times through nested ternaries, with two different tones for unknown

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/readiness.tsx:16-29](../../../../apps/web/components/readiness.tsx#L16)
  - [apps/web/components/readiness.tsx:44-50](../../../../apps/web/components/readiness.tsx#L44): HealthLine: bg-attention for any state that is not ready
  - [apps/web/components/readiness.tsx:63-68](../../../../apps/web/components/readiness.tsx#L63): Icon chosen by state
  - [apps/web/components/readiness.tsx:78-85](../../../../apps/web/components/readiness.tsx#L78): Tone chosen by state, muted for unknown
- **Evidence:** The same three-way test picks the icon and the tone. HealthLine colors every service that is not ready, unknown included, with bg-attention, while ServiceChips gives unknown text-muted-foreground.

  ```tsx
  return service.state === "ready"
    ? "ready"
    : service.state === "unknown"
      ? "unknown"
      : "not ready";
  ```

- **Why it matters:** A state added to the generated ServiceReadiness type compiles without touching any of these chains, and the sidebar and Home tone the same unknown service differently.
- **Recommendation:** Use one table typed Record&lt;ServiceReadiness["state"], { words; openrouterWords; icon; tone }&gt;, so a new state fails to compile until it is described, and use that table's tone in both views.
- **Rule check:** DS-03: never infer a state from color alone. The words remain what carries the meaning.
- **Verification:** confirmed. The three chains (16-29, 63-68, 78-85) and HealthLine's bg-attention for unknown (48), against ServiceChips' muted tone, confirmed.

### <a id="wshl-21"></a>WSHL-21: credential-precedence.ts has no caller in the app

- **Severity** low · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/lib/credential-precedence.ts:1-3](../../../../apps/web/lib/credential-precedence.ts#L1): The header implies server code uses it.
  - [apps/web/tests/unit/credential-precedence.test.ts:7](../../../../apps/web/tests/unit/credential-precedence.test.ts#L7): Its only importer
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161)
- **Evidence:** The header says "MP-03's source order, for server code", but git grep finds no import outside its unit test. All inference goes through the Python gateway, which resolves OPENROUTER_API_KEY itself; services/agent/tests/test_credentials.py reads the same fixture. The module reads .env files with node:fs. Unlike the other server modules it has no server-only marker, because node:test cannot load one.
- **Why it matters:** Someone reading lib/ will assume the web process resolves OpenRouter keys, and the next MP-03 change may be made here in the belief that this code is live.
- **Recommendation:** Say in its header that no application code calls it and that it is the TypeScript half of the US-3.1 parity fixture. Alternatively, move it next to its test (for example tests/unit/support/), so lib/ holds only code the app runs. Keep the shared-fixture test unless its owner decides otherwise.
- **Rule check:** MP-03 and US-3.1 (shared precedence in Python and TypeScript, driven by one fixture set): the parity test stays. model-gateway.md: OpenRouter credentials stay server-side.
- **Verification:** confirmed. Its only importers are its unit test and verify.py's step, and services/agent/tests/test_credentials.py reads the same fixture.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

This review is static. I did not start the app, the BFF, the API or the browser suites, and I did not run scripts/verify.py. I read its .checks/full/latest.json and .checks/fast/latest.json instead. I did not exercise whether Next.js 16 passes '..' segments into catch-all params. I judged that harmless, because every API router sits under /v1 with docs and OpenAPI disabled, so traversal reaches nothing the catch-all does not already expose. I did not measure the primitives' contrast or rendering in either theme. Files outside this area were read only at the cited lines, as evidence: other components, generated.ts (how its schemas and functions are consumed), scripts/verify.py, scripts/toolchain.py, services/agent/src/autobots/api/security.py, services/agent/tests/test_contracts.py, the US-16.2 openspec record and two installed Supabase packages. I read PRD-Development-Harness.md only for DH-03 and DH-06, and metrics.md only in its run, size, TypeScript, baseline, command and limitation sections. No command was refused. ESLint was run read-only with extra rules on the command line and no cache, and the git status afterwards matched the starting state.
