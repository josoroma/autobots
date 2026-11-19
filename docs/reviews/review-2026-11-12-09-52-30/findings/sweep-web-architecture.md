# Lens: web UI architecture

The web UI is a set of thin Server Component routes over 39 client components. There are 22 pages, and only 2 of them load data on the server. Each client component fetches, writes and renders on its own. The screens agree on the lowest layer: every form control comes from components/ui/field, the Luma tokens are imported once, and almost every read response is parsed with a generated validator. Above that layer they share almost nothing. In 23 component files, data is fetched inside effects that keep their own loading and error flags. The CSRF write path appears in 29 call sites across 19 files, with hand-built headers, untyped JSON bodies and, at 19 sites, cast error bodies. Only 8 of those 19 files stop a second press while a request is in flight, and the composer, the session screen and the workflow run are not among them. Loading, error and denied states, refusal texts, run-state words and tones, and money and time formats are each written per screen, and they visibly disagree. Two well-shaped hooks already exist, useLoaded in tool-catalog and useToolUses, and ContinueRun handles an unknown outcome correctly. These show the target patterns, but they stay private to their files. There are two root causes. First, there is no shared layer: no typed browser client, no resource or submit hooks, no view-state components and no lib vocabulary. Second, the generated client drops query parameters and refusal bodies, so screens cannot use it. Building that layer first would let the ten screen functions of 260 to 677 lines split along the same seams, and it would turn most findings below into mechanical migrations. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | TypeScript is strict, lint passes and every form control comes from ui/field. DH-06's rules on duplicate submits, generated request types and Server Components are met only in part, and type sizes bypass the theme. |
| modules | 3 | The server-only lib boundary is clean. Shared vocabulary and hooks live inside feature components, which import each other sideways with one cycle, and there are no hooks or feature folders. |
| size | 2 | The ten longest functions are route screens of 260 to 677 lines, with complexity up to 39. Each one mixes data loading, writes and markup. |
| functions | 3 | The pure helpers are small and well named. The screen components interleave effects, writes and rendering, and the same write shape is repeated at 29 call sites. |
| structure | 3 | Routes are thin server pages over one client panel. The 43 feature components sit in one flat folder, recurring layout pieces are private to screens, and the run routes own their own headers. |
| approach | 2 | There is no shared data, submit or view-state layer. 23 files hand-roll fetch effects, live updates and URL state differ per screen, and only two pages load data on the server. |
| comments | 4 | Comments explain why and cite decisions. A few record manual sync duties that a shared module would remove, for example run-workspace.tsx:48 and lib/shortcuts.ts:1-2. |
| types | 3 | Read responses are parsed with generated validators. 28 request bodies, 19 error-body reads and 7 success-body reads bypass the generated types, and many label maps are keyed by string instead of the generated unions. |
| errors | 3 | Most failures are shown in words. States and announcement roles differ per screen, three loads stay on Loading after a failure, search shows an outage as no results, and refusal texts diverge. |
| tests | 3 | Playwright coverage is broad and uses data-\* hooks. Pure UI helpers sit inside client components with no unit tests, and the unit runner names two of the three test files. |
| maintainability | 3 | The screens are careful and accessible, but their per-screen plumbing turns every cross-cutting change (contracts, states, formatting) into a many-file edit. |

## Strengths

- **Read responses are validated at the browser boundary.** 25 component files parse responses with generated parse\* functions before use, for example run-list.tsx:193, approvals-panel.tsx:143 and tool-uses.tsx:133. Unknown event types are skipped on purpose rather than cast (run-workspace.tsx:143-150). The runtime validator checks formats and ranges (packages/api-client/src/runtime.ts:37-62, 81-140). Fixtures shared with Python test it (packages/api-client/tests/contract.test.ts:8-20). Write replies are the exception (XWEB-01). Sources: [apps/web/components/run-list.tsx:193](../../../../apps/web/components/run-list.tsx#L193), [apps/web/components/approvals-panel.tsx:143](../../../../apps/web/components/approvals-panel.tsx#L143), [apps/web/components/tool-uses.tsx:133](../../../../apps/web/components/tool-uses.tsx#L133), [apps/web/components/run-workspace.tsx:143](../../../../apps/web/components/run-workspace.tsx#L143), [packages/api-client/src/runtime.ts:37](../../../../packages/api-client/src/runtime.ts#L37), [packages/api-client/tests/contract.test.ts:8](../../../../packages/api-client/tests/contract.test.ts#L8).
- **Every form control goes through one primitive set.** No raw input, select or textarea exists outside components/ui (grep over components and app). DS-03's control border, focus and dark fill are defined once, in components/ui/field.tsx:6-11 and app/globals.css:95-101. Sources: [apps/web/components/ui/field.tsx:6](../../../../apps/web/components/ui/field.tsx#L6), [apps/web/app/globals.css:95](../../../../apps/web/app/globals.css#L95).
- **One token source, imported unedited.** app/globals.css:1-5 imports docs/design/luma.css and the one documented extension, then maps the semantic tokens in @theme (globals.css:31-77). The only color literals are the theme preview swatches, and a comment explains them (appearance-control.tsx:10-26). Sources: [apps/web/app/globals.css:1](../../../../apps/web/app/globals.css#L1), [apps/web/app/globals.css:31](../../../../apps/web/app/globals.css#L31), [apps/web/components/appearance-control.tsx:10](../../../../apps/web/components/appearance-control.tsx#L10).
- **An explicit server-only boundary.** lib/bff.ts:1, lib/server-config.ts:1, lib/session.ts:1, lib/service-status.ts:1 and lib/workspace-choice.ts:1 import server-only. The same-origin guard is a pure function with a unit test (lib/request-guard.ts:33-67). When the browser disconnects, only the stream ends, never the run (lib/bff.ts:128-131). Sources: [apps/web/lib/bff.ts:1](../../../../apps/web/lib/bff.ts#L1), [apps/web/lib/request-guard.ts:33](../../../../apps/web/lib/request-guard.ts#L33), [apps/web/lib/bff.ts:128](../../../../apps/web/lib/bff.ts#L128).
- **Two well-shaped data hooks to spread.** useLoaded keeps loading, unavailable and ready as one discriminated union and aborts stale requests (tool-catalog.tsx:156-181). useToolUses pages through results, aborts, and reloads when a version changes; workflow-monitor.tsx:254 reuses it (tool-uses.tsx:101-147). Sources: [apps/web/components/tool-catalog.tsx:156](../../../../apps/web/components/tool-catalog.tsx#L156), [apps/web/components/tool-uses.tsx:101](../../../../apps/web/components/tool-uses.tsx#L101), [apps/web/components/workflow-monitor.tsx:254](../../../../apps/web/components/workflow-monitor.tsx#L254).
- **Lost replies on a paid write are handled correctly.** ContinueRun keeps its idempotency key until the outcome is known, treats a 5xx response like a lost reply, and blocks re-entry with a pending flag (continue-run.tsx:20-21, 39, 47-50, 68-69, 102). It is the model for every run-creating screen. Sources: [apps/web/components/continue-run.tsx:20](../../../../apps/web/components/continue-run.tsx#L20), [apps/web/components/continue-run.tsx:39](../../../../apps/web/components/continue-run.tsx#L39), [apps/web/components/continue-run.tsx:47](../../../../apps/web/components/continue-run.tsx#L47).
- **State is told in words, with accessible interaction models.** The words carry the state and a dot only repeats it (badge.tsx:6-7, run-list.tsx:126-146). Tool uses are announced in a live region (tool-uses.tsx:257-261). Search is a combobox with a listbox (search-palette.tsx:139-166). Approvals has a J/K and press-twice keyboard model, and every shortcut ignores text fields through lib/keyboard.ts:2-8. Sources: [apps/web/components/ui/badge.tsx:6](../../../../apps/web/components/ui/badge.tsx#L6), [apps/web/components/run-list.tsx:126](../../../../apps/web/components/run-list.tsx#L126), [apps/web/components/tool-uses.tsx:257](../../../../apps/web/components/tool-uses.tsx#L257), [apps/web/components/search-palette.tsx:139](../../../../apps/web/components/search-palette.tsx#L139), [apps/web/lib/keyboard.ts:2](../../../../apps/web/lib/keyboard.ts#L2).
- **Label maps keyed by generated unions, where adopted.** provider-settings-panel.tsx:19-49, readiness.tsx:8-13, keys-and-vars-panel.tsx:20-35, search-palette.tsx:14-19 and run-panel.tsx:22-26 key their maps by generated union types. The compiler therefore flags a state the API adds. Sources: [apps/web/components/provider-settings-panel.tsx:19](../../../../apps/web/components/provider-settings-panel.tsx#L19), [apps/web/components/readiness.tsx:8](../../../../apps/web/components/readiness.tsx#L8), [apps/web/components/keys-and-vars-panel.tsx:20](../../../../apps/web/components/keys-and-vars-panel.tsx#L20), [apps/web/components/search-palette.tsx:14](../../../../apps/web/components/search-palette.tsx#L14), [apps/web/components/run-panel.tsx:22](../../../../apps/web/components/run-panel.tsx#L22).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XWEB-01](#xweb-01) | high | types | Write requests and error bodies bypass the generated contract | M | medium |
| [XWEB-02](#xweb-02) | high | approach | No shared client data layer: 23 files hand-roll fetch-in-effect | L | medium |
| [XWEB-03](#xweb-03) | high | approach | Writes have no shared submit path, and run admission isn't guarded against a second press | M | medium |
| [XWEB-05](#xweb-05) | high | size | Screen components own data, stream protocol and markup in one function | L | medium |
| [XWEB-04](#xweb-04) | medium | duplication | Model profile names and the offered set are hardcoded in three screens | S | medium |
| [XWEB-06](#xweb-06) | medium | errors | Read view states are written per screen, and some failures never appear | M | low |
| [XWEB-07](#xweb-07) | medium | errors | Write outcomes: refusal texts and announcement roles differ per screen | M | low |
| [XWEB-08](#xweb-08) | medium | duplication | Run state vocabulary, tones and commands are defined per screen | S | low |
| [XWEB-09](#xweb-09) | medium | duplication | Money, time and duration formatting is re-implemented and disagrees | S | low |
| [XWEB-10](#xweb-10) | medium | modules | Shared vocabulary and hooks live inside feature components, imported sideways and in a cycle | M | low |
| [XWEB-11](#xweb-11) | medium | structure | Recurring layout pieces are private to screens instead of in components/ui | M | low |
| [XWEB-12](#xweb-12) | medium | standards | Type sizes and many spacings are arbitrary values outside the theme | M | low |
| [XWEB-13](#xweb-13) | medium | approach | List filters and selection live in the URL on some screens and in state on others | M | low |
| [XWEB-14](#xweb-14) | medium | approach | Only two pages load data on the server, and client writes don't refresh server-rendered shell data | M | medium |
| [XWEB-15](#xweb-15) | medium | tests | UI logic sits where unit tests can't reach it, and the unit runner lists test files by name | S | low |
| [XWEB-16](#xweb-16) | medium | approach | Screen state is spread across independent flags where one union belongs | M | medium |
| [XWEB-17](#xweb-17) | low | approach | Live updates differ per screen, and the run page refetches whole resources on every event | M | medium |
| [XWEB-18](#xweb-18) | low | duplication | Browser preferences and the shortcut list are kept in sync by comments | S | low |
| [XWEB-19](#xweb-19) | low | structure | Page title and width belong to the page on most routes but to the client screen on run routes | S | low |
| [XWEB-20](#xweb-20) | low | naming | Route components use ten suffixes, and one constant name means three things | S | low |

### <a id="xweb-01"></a>XWEB-01: Write requests and error bodies bypass the generated contract

- **Severity** high · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 54
- **Where:**
  - [apps/web/components/goal-composer.tsx:288-311](../../../../apps/web/components/goal-composer.tsx#L288): The POST /api/v1/runs body is an untyped object literal, although RunRequest exists. Line 311 casts the reply to { run_id } instead of using parseRunAccepted.
  - [apps/web/components/session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65): Casts the admission reply although parseRunAccepted exists.
  - [apps/web/components/experts-panel.tsx:97](../../../../apps/web/components/experts-panel.tsx#L97): Casts to { id } although parseSessionView exists. The same cast is at line 144, expert-editor.tsx:201 and goal-composer.tsx:273.
  - [apps/web/components/workflow-editor.tsx:220-223](../../../../apps/web/components/workflow-editor.tsx#L220): One of 19 hand-cast error bodies. parseErrorResponse has no caller in apps/web; only the api-client contract test calls it.
  - [apps/web/components/expert-editor.tsx:116-119](../../../../apps/web/components/expert-editor.tsx#L116): role_bindings is cast to Record&lt;string, string&gt; because the contract types it as Record&lt;string, unknown&gt;. model-policy-panel.tsx:55 and 130 and experts-panel.tsx:331 cast it the same way, while run-disclosure.tsx:74-79 narrows it with typeof.
  - [scripts/generate_contracts.py:60-78](../../../../scripts/generate_contracts.py#L60): Emits path parameters and a JSON body only. Query parameters, such as group, q, profile and cursor on GET /v1/runs, are dropped.
  - [packages/api-client/src/runtime.ts:157-171](../../../../packages/api-client/src/runtime.ts#L157): A failed request throws a ContractError with the status in the message and the body discarded. Per-call headers already fit ClientOptions.headers (line 154).
- **Evidence:** Counted with grep over apps/web/components: 28 bodies built with `body: JSON.stringify(`, none typed against a generated request type or with satisfies. 26 of them go to /api/v1 or /api/settings routes whose request schema is generated, such as RunRequest and SessionCreate; the other 2 go to the BFF's own /api/session and /api/workspace. There are 19 error-body casts in 15 files, and 7 success-body casts in 5 files where a generated parser exists. parseErrorResponse is never called in apps/web. Excerpt from goal-composer.tsx:294-321:

  ```tsx
  body: JSON.stringify({
    goal_text: draft,
    budget_micro_usd: budget,
    ...(profile === "" ? {} : { run_profile: profile }),
  ...
  const accepted = (await reply.json()) as { run_id: string };
  ...
  const failure = (await reply?.json().catch(() => null)) as { code?: string; message?: string } | null;
  ```

- **Why it matters:** Only half of each exchange is checked. Responses are validated, but requests and refusals are not. RunRequest forbids extra fields (services/agent/src/autobots/contracts/run_commands.py:16), so a renamed field compiles cleanly and fails as a 422 in the browser. The composer reports that 422 as 'That model or request isn't approved' (goal-composer.tsx:331-334). Because the generated functions cannot take query parameters or report a refusal, browser screens cannot use them. The server path (lib/service-status.ts) and the browser path (raw fetch) have therefore diverged.
- **Recommendation:** First, type every body with the generated request types (`const body: RunRequest = {...}` or `satisfies`). Replace the 7 success casts with parseRunAccepted and parseSessionView. Read refusals through one readRefusal(reply) helper built on parseErrorResponse, which tolerates non-JSON bodies. Then extend scripts/generate_contracts.py to emit typed query parameters, make runtime.ts throw an ApiError that carries the status and the parsed ErrorResponse, and regenerate. Idempotency-Key can already travel in a per-call ClientOptions.headers; emitting the OpenAPI header parameter as a typed argument is optional. Finally, add lib/api/browser.ts, which binds the generated functions to the /api base, with csrfFetch for writes.
- **Rule check:** DH-06: 'Use generated API types ... No blanket type assertions to conceal contract mismatches'. contracts.md: 'generated TypeScript consumes them'. The fix changes the generator and runtime.ts and then regenerates generated.ts. It never hand-edits that file (ground rule 2).
- **Verification:** revised. Every cited cast, the 28 untyped bodies and the generator's path-and-body-only emission are confirmed. Corrected the success casts to 5 files, noted that 2 bodies target BFF-owned routes, and noted that per-call headers already fit ClientOptions.headers.

```tsx
// packages/api-client/src/runtime.ts (hand-written, not generated)
export class ApiError extends Error { status: number; error: ErrorResponse | null }
// scripts/generate_contracts.py emits e.g.
export async function listRuns(options: ClientOptions, query?: { group?: string; q?: string; profile?: string; cursor?: string }): Promise<RunList>
// apps/web/lib/api/browser.ts
export const reads: ClientOptions = { baseUrl: '/api', fetch: (u, i) => fetch(u, { ...i, cache: 'no-store' }) };
export const writes: ClientOptions = { baseUrl: '/api', fetch: csrfFetch };
// screen: the per-press key rides on a per-call options object
const accepted = await admitRun({ ...writes, headers: { 'Idempotency-Key': key } }, body);
```

### <a id="xweb-02"></a>XWEB-02: No shared client data layer: 23 files hand-roll fetch-in-effect

- **Severity** high · **Dimension** approach · **Effort** L · **Risk** medium · **Occurrences** 28
- **Where:**
  - [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156): The only generic read hook, and it is private to this file.
  - [apps/web/components/approvals-panel.tsx:136-187](../../../../apps/web/components/approvals-panel.tsx#L136): load() and the initial effect are two copies of the same read. setCounts runs twice at lines 170-171.
  - [apps/web/components/operations-panel.tsx:165-206](../../../../apps/web/components/operations-panel.tsx#L165): The same load-and-effect pair.
  - [apps/web/components/provider-settings-panel.tsx:161-190](../../../../apps/web/components/provider-settings-panel.tsx#L161): The same pair. keys-and-vars-panel.tsx:168-197 repeats it again.
  - [apps/web/components/run-workspace.tsx:317-331](../../../../apps/web/components/run-workspace.tsx#L317): A refetch is triggered by a counter kept in state. run-list.tsx:167 and run-panel.tsx:60 do the same.
  - [apps/web/components/goal-composer.tsx:143-166](../../../../apps/web/components/goal-composer.tsx#L143): Fetches /api/models, and its child RunDisclosure fetches it again on the same mount (run-disclosure.tsx:44-67).
  - [apps/web/components/workflow-editor.tsx:120-171](../../../../apps/web/components/workflow-editor.tsx#L120): Three requests in one effect. Two of their failures are swallowed with .catch(() =&gt; undefined).
- **Evidence:** grep counts over apps/web/components: 28 effects guarded by `let active = true` or `let live = true` in 23 files, 45 GETs with cache: 'no-store', and 60 hand-built /api/v1 URL literals. Only 2 of the 23 files abort a stale request (tool-catalog, tool-uses), and 12 sites drain refused bodies while others don't. Excerpt from run-panel.tsx:62-77:

  ```tsx
  useEffect(() => {
    let active = true;
    fetch(`${base}/workspace`, { cache: "no-store" })
      .then(async (reply) => {
        if (!active) return;
        if (reply.ok) { setView(parseRunWorkspace(await reply.json())); setFailed(false); }
        else { await reply.text(); setFailed(true); }
      }).catch(() => { if (active) setFailed(true); });
  ```

- **Why it matters:** Each screen chooses its own flags, abort behavior, body draining and reload trigger. A fix such as aborting stale requests, showing a denied state or offering a retry has to be applied file by file. Sibling components request the same resource independently. Every new screen adds about 25 lines of plumbing, and this plumbing makes up most of the non-JSX code in the largest screens.
- **Recommendation:** Generalize useLoaded into hooks/use-resource.ts. It should return one discriminated union (loading, ready with data, denied, or unavailable) plus reload(), with an AbortController and body draining built in. Add hooks for shared reads, such as use-models and use-tool-catalog. Let identical GETs that are in flight at the same time share one request, and keep nothing after it settles, so no data outlives a sign-out (which only calls router.refresh()) or a workspace switch. This needs no new dependency. Migrate panels one at a time and keep their data-\* hooks. Pair this with the typed browser client from XWEB-01.
- **Rule check:** DH-06: 'Represent loading, empty, denied, unavailable and retryable states deliberately', 'Browser state is a view of durable state' and 'Prevent workspace data from leaking through shared caches'. nextjs.md: explicit error, empty and loading states. A read hook is a view only, and no business rule moves into Next.js.
- **Verification:** revised. Recounted 28 guarded effects in 23 files, 45 no-store GETs, 60 /api/v1 literals, abort in 2 files and 12 body drains. Narrowed the shared-read cache to in-flight sharing, because sign-out keeps the tab's memory and DH-06 forbids workspace data in shared caches.

```tsx
// hooks/use-resource.ts
export type Resource<T> = { status: 'loading' } | { status: 'ready'; data: T }
  | { status: 'denied' } | { status: 'unavailable' };
export function useResource<T>(url: string | null, parse: (v: unknown) => T): Resource<T> & { reload(): void }
// hooks/use-models.ts: shared by GoalComposer, RunDisclosure and ModelPolicyPanel; a GET in flight is shared, nothing is kept after it settles
export const useModels = () => useResource('/api/models', parseModelList);
// panel: const providers = useResource('/api/settings/model-providers', parseProviderStatus);
//        replaces load() + the duplicate effect + loadFailed
```

### <a id="xweb-03"></a>XWEB-03: Writes have no shared submit path, and run admission isn't guarded against a second press

- **Severity** high · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 29
- **Where:**
  - [apps/web/components/goal-composer.tsx:591-599](../../../../apps/web/components/goal-composer.tsx#L591): Run stays enabled while admission is in flight. run() at 276-341 keeps no pending state.
  - [apps/web/components/goal-composer.tsx:287](../../../../apps/web/components/goal-composer.tsx#L287): Comment: one key per press. This is the US-4.1 choice.
  - [apps/web/components/session-panel.tsx:190](../../../../apps/web/components/session-panel.tsx#L190): The button is disabled only by !ready. run() at 45-80 has no pending flag.
  - [apps/web/components/workflow-editor.tsx:675-678](../../../../apps/web/components/workflow-editor.tsx#L675): 'Run this version' creates an execution with a new key on each press, and the button is never disabled.
  - [apps/web/components/continue-run.tsx:17-21](../../../../apps/web/components/continue-run.tsx#L17): The model to follow: a pending flag, and a key kept until the outcome is known (lines 39, 47-50, 69, 102).
  - [apps/web/components/experts-panel.tsx:84-102](../../../../apps/web/components/experts-panel.tsx#L84): Session creation is copied four times: here, at 131-149, at expert-editor.tsx:187-206 and at goal-composer.tsx:257-274.
  - [apps/web/components/provider-settings-panel.tsx:192-219](../../../../apps/web/components/provider-settings-panel.tsx#L192): Its mutate() is copied in keys-and-vars-panel.tsx:203-226, with the same fallback text.
  - [apps/web/components/operations-panel.tsx:210-217](../../../../apps/web/components/operations-panel.tsx#L210): The only write without a catch. A network failure becomes an unhandled rejection, and no message appears.
- **Evidence:** There are 29 csrfFetch call sites in 19 files, each building its headers by hand (28 Content-Type literals, 18 crypto.randomUUID calls). A busy or pending guard exists in 8 of the 19 files: provider-settings, run-controls, sign-in-form, model-policy, run-panel, account-form, continue-run and keys-and-vars. Excerpt from goal-composer.tsx:288-293 and 591-593:

  ```tsx
  const reply = await csrfFetch("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
  ...
  <Button onClick={() => void run()} disabled={draft.trim() === "" || !budgetLeft}
  ```

- **Why it matters:** A double click on Run in the composer, Run in a session, or Run this version sends two admissions with different keys. The API admits two runs and reserves two budgets, which is a paid path. Every write rebuilds headers, keys, its catch style and its refusal reading. A fix in one place, such as the missing catch in Operations, therefore reaches none of the others. Five screens with text inputs submit from onClick buttons without a &lt;form&gt;: goal-composer, session-panel, workflow-editor, the operations retention fields and unknown-effects.
- **Recommendation:** Add hooks/use-submit.ts, which owns the following. Pending state that disables the trigger and ignores re-entry. The idempotency-key policy as an explicit option: per-press for the composer as US-4.1 chose, or until-known as ContinueRun does. Unknown-outcome handling for network failures and 5xx responses. A typed outcome union as its result. Route writes through the typed browser client, and add lib/api/sessions.ts with startSession(kind, experts) for the four copies. Wrap writes that have text inputs in a &lt;form&gt;. Start with the three run-creating screens, and add a browser test that double-clicks Run and expects one admission.
- **Rule check:** DH-06: 'Disable duplicate submits with server idempotency as the correctness mechanism'. The composer keeps one key per press, as decided in openspec/changes/archive/2026-11-05-us-4-1-atomic-run-admission-canonical/proposal.md:10. The recommendation only adds the in-flight guard.
- **Verification:** revised. Recounted 29 csrfFetch sites in 19 files, 28 Content-Type literals, 18 randomUUID calls and in-flight guards in 8 files. The three unguarded run buttons and Operations' missing catch are confirmed. Corrected the form count to five, since ContinueRun has no text input.

```tsx
// hooks/use-submit.ts
export function useSubmit<T>(send: (key: string) => Promise<T>, opts: { key: 'per-press' | 'until-known' }): {
  submit(): void;
  state: { status: 'idle' } | { status: 'pending' } | { status: 'done'; value: T }
       | { status: 'refused'; error: ApiError } | { status: 'unknown' };
}
// goal-composer: const admission = useSubmit((key) => admitRun(writes, body, { headers: { 'Idempotency-Key': key } }), { key: 'per-press' });
// <Button type='submit' disabled={admission.state.status === 'pending' || ...}>
```

### <a id="xweb-05"></a>XWEB-05: Screen components own data, stream protocol and markup in one function

- **Severity** high · **Dimension** size · **Effort** L · **Risk** medium · **Occurrences** 10
- **Where:**
  - [apps/web/components/run-workspace.tsx:152-844](../../../../apps/web/components/run-workspace.tsx#L152): 677 lines, complexity 39. Lines 152-331 are state, the EventSource protocol and refetches.
  - [apps/web/components/workflow-editor.tsx:106-736](../../../../apps/web/components/workflow-editor.tsx#L106): 617 lines. 11 states and 7 write functions come before the JSX at line 398.
  - [apps/web/components/goal-composer.tsx:113-653](../../../../apps/web/components/goal-composer.tsx#L113): 527 lines, complexity 37. Data and writes occupy 113-341.
  - [apps/web/components/expert-editor.tsx:70-472](../../../../apps/web/components/expert-editor.tsx#L70): 393 lines.
  - [apps/web/components/operations-panel.tsx:158-539](../../../../apps/web/components/operations-panel.tsx#L158): 377 lines, complexity 28.
  - [apps/web/components/model-policy-panel.tsx:118-475](../../../../apps/web/components/model-policy-panel.tsx#L118): 350 lines.
  - [apps/web/components/workflows-panel.tsx:83-427](../../../../apps/web/components/workflows-panel.tsx#L83): 341 lines.
  - [apps/web/components/approvals-panel.tsx:117-434](../../../../apps/web/components/approvals-panel.tsx#L117): 308 lines, with a keyboard handler of complexity 27 at 229.
- **Evidence:** In metrics.md section 7, the ten longest non-test functions are all route-level screens: RunWorkspaceView 677, WorkflowEditor 617, GoalComposer 527, ExpertEditor 393, OperationsPanel 377, ModelPolicyPanel 350, WorkflowsPanel 341, ApprovalsPanel 308, RunInspectorView 263 and RunList 260. 83 functions are over 60 lines. In the three largest, state, effects and writes take about 180, 290 and 230 lines before the first JSX.
- **Why it matters:** Changing any section's data or markup means editing a function of 300 to 700 lines. Most of the non-JSX code is the per-screen plumbing described in the two findings above, so every large screen has the same seams. Area reviewers can't fix this one screen at a time without first creating the shared hooks.
- **Recommendation:** Split each large screen along three seams: a data hook built on useResource or a stream hook, an actions hook built on useSubmit, and presentational section components, which can be Server Components when they are read-only. Do the splits after the hooks exist, so that each split removes code instead of moving it. Keep every data-\* hook the browser suites read.
- **Rule check:** DH-06: 'small cohesive modules'. The splits must keep the data-\* hooks and accessible names that the browser suites assert.
- **Verification:** confirmed. The ten function spans, line counts and complexities match metrics.md section 7. The lines before the first JSX are 181, 292 and 230 in the three largest screens.

```tsx
// components/runs/run-workspace/index.tsx
export function RunWorkspaceScreen({ runId }: { runId: string }) {
  const run = useRunStream(runId); // hooks/use-run-stream.ts: snapshot, timeline, connection, gap, live, result, refresh
  return <RunLayout header={<RunHeader run={run} />}
    main={<><StatusSection run={run} /><ResultSection run={run} /><PlanSection plan={run.snapshot.plan} /><TimelineSection events={run.timeline} gap={run.gap} /></>}
    aside={<><ModelsSection map={run.snapshot.role_map} /><BudgetSection run={run.snapshot} /></>} />;
}
// components/build/workflow-editor/: useWorkflowDraft(id) (load, save, publish, discard, describe), useWorkflowRun(workflow) (versions, budgetSteps, execute); GraphSection, RunVersionSection, BlocksTable
// components/home/goal-composer/: useComposerOptions() (experts, models, preview, budgetSteps), useAdmission(); OptionChips, AttachmentsField, OutcomeMessage
```

### <a id="xweb-04"></a>XWEB-04: Model profile names and the offered set are hardcoded in three screens

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/expert-editor.tsx:21-25](../../../../apps/web/components/expert-editor.tsx#L21): PROFILES lists Terra and Sol and doubles as the offered set.
  - [apps/web/components/expert-editor.tsx:116-128](../../../../apps/web/components/expert-editor.tsx#L116): Bindings outside the list are dropped on save. The UI says so at 424-432 and disables the option at 415-421.
  - [apps/web/components/run-list.tsx:75-79](../../../../apps/web/components/run-list.tsx#L75): PROFILE_NAMES maps profile IDs to names by hand.
  - [apps/web/components/experts-panel.tsx:295-299](../../../../apps/web/components/experts-panel.tsx#L295): An identical PROFILE_NAMES copy.
  - [apps/web/components/run-disclosure.tsx:87-91](../../../../apps/web/components/run-disclosure.tsx#L87): Reads `offered` from /api/models instead. goal-composer.tsx:393-395 does the same.
  - [apps/web/components/model-policy-panel.tsx:234-238](../../../../apps/web/components/model-policy-panel.tsx#L234): Also reads offered from the server.
  - [services/agent/src/autobots/domain/models.py:72](../../../../services/agent/src/autobots/domain/models.py#L72): OFFERED_FOR_NEW_RUNS, which owns the rule.
- **Evidence:** grep 'openrouter_terra' in apps/web/components finds three hardcoded copies. Only expert-editor's PROFILES encodes the offered rule. The two PROFILE_NAMES maps are display labels, which /api/models doesn't carry: it returns profile, canonical_id and offered. Excerpt from expert-editor.tsx:21-25 and 126-128:

  ```tsx
  const PROFILES = [
    { id: "", label: "Workspace setting" },
    { id: "openrouter_terra", label: "Terra" },
    { id: "openrouter_sol", label: "Sol" },
  ];
  const dropped = others
    .filter(([, profile]) => !PROFILES.some((item) => item.id === profile))
  ```

- **Why it matters:** Which models new runs may use is a server rule, and /api/models already exposes it. Qualifying Sol (commit ada547a, US-14.15) required a manual edit to this list. The next qualification will need edits in three files. Until they are made, the Expert editor labels a qualified model as not offered and drops its bindings on save, while the composer offers that same model. The maps are typed Record&lt;string, string&gt;, so the compiler doesn't catch a missing profile even though the client exports ModelProfileId.
- **Recommendation:** Read profiles from /api/models through one shared hook (useModels) in all three screens. Label them with the server's canonical_id, or keep short names in one lib map typed Record&lt;ModelProfileId, string&gt;. Derive 'not offered' from model.offered, never from a local list.
- **Rule check:** DH-06: 'Avoid ... duplicated business rules'. nextjs.md: 'Next.js owns UI/BFF, not Python business-state transitions'. The rule stays in the Python domain, and the screens only read it.
- **Verification:** revised. Confirmed the three copies, OFFERED_FOR_NEW_RUNS at models.py:72 and the manual edit in ada547a. Lowered from high to medium: only one copy encodes the rule, the editor warns before a save drops a binding, and WBLD-07 and XDUP-10 rate the same issue medium.

```tsx
// hooks/use-models.ts
export function useModels(): Resource<ModelList> & { label(p: ModelProfileId): string; offered(p: string): boolean }
// expert-editor.tsx
const models = useModels();
const dropped = others.filter(([, p]) => !models.offered(p)).map(([role]) => role);
// run-list.tsx and experts-panel.tsx: models.label(profile) replaces PROFILE_NAMES
```

### <a id="xweb-06"></a>XWEB-06: Read view states are written per screen, and some failures never appear

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** low · **Occurrences** 22
- **Where:**
  - [apps/web/components/expert-editor.tsx:273-276](../../../../apps/web/components/expert-editor.tsx#L273): Shows 'Loading the tool catalog.' indefinitely when the request fails, because lines 80-85 swallow the failure.
  - [apps/web/components/workflows-panel.tsx:552-553](../../../../apps/web/components/workflows-panel.tsx#L552): 'Loading its steps.' remains after a failed preview (472-481). Executions behave the same way at 608-609.
  - [apps/web/components/search-palette.tsx:75-79](../../../../apps/web/components/search-palette.tsx#L75): A failed search becomes an empty result, so the status line says 'Nothing in this workspace matches.' (211-212).
  - [apps/web/components/run-list.tsx:282-290](../../../../apps/web/components/run-list.tsx#L282): Load failure shown in a destructive bordered box.
  - [apps/web/components/experts-panel.tsx:160-166](../../../../apps/web/components/experts-panel.tsx#L160): The same state shown as plain text.
  - [apps/web/components/model-policy-panel.tsx:219-231](../../../../apps/web/components/model-policy-panel.tsx#L219): The same state inside a Card. The loading line has no role.
  - [apps/web/components/operations-panel.tsx:227-228](../../../../apps/web/components/operations-panel.tsx#L227): An unstyled alert and 'Loading…'. This is the only screen that names a denied (403) state (171-172).
- **Evidence:** 22 component files render their own loading and failure markup. There are 30 loading lines, 14 of them with role=status, and 9 `.catch(() => undefined)` calls in 6 files swallow secondary loads. No shared view-state component exists. Excerpt from expert-editor.tsx:80-85 and 273-276:

  ```tsx
  fetch("/api/v1/tools", { cache: "no-store" })
    .then(async (reply) => {
      if (active && reply.ok) setCatalog(parseToolCatalog(await reply.json()));
    })
    .catch(() => undefined);
  ...
  {catalog === null ? (<p className="text-muted-foreground text-sm">Loading the tool catalog.</p>) : (
  ```

- **Why it matters:** In three places a user cannot tell a load that is still running from one that failed. Search hides an outage as 'no match'. On most screens, denied cannot be told apart from unavailable. Tests can assert a view state only where the screen added data-state.
- **Recommendation:** Add components/ui/view-state.tsx with Loading, Empty, Unavailable (with an optional retry) and Denied. Each sets its role and data-state the same way and is driven by the resource hook's status. Map 401 and 403 to Denied, and network failures and 5xx to Unavailable. Never swallow a secondary load; show a muted unavailable line instead.
- **Rule check:** DH-06: 'Represent loading, empty, denied, unavailable and retryable states deliberately'. nextjs.md asks for explicit error, empty and loading states. DS-03 lists empty, loading and error states as design-system surfaces.
- **Verification:** confirmed. Confirmed the three Loading lines that never clear, search's empty result on failure, four differently styled failure states, and 403 named only by Operations. Recounted 9 swallowed loads in 6 files and about 30 loading lines in 22 files.

### <a id="xweb-07"></a>XWEB-07: Write outcomes: refusal texts and announcement roles differ per screen

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** low · **Occurrences** 11
- **Where:**
  - [apps/web/components/goal-composer.tsx:601-606](../../../../apps/web/components/goal-composer.tsx#L601): Uses role=alert for every outcome, including the success 'Your goal is queued.' (637-645).
  - [apps/web/components/workflow-editor.tsx:586-590](../../../../apps/web/components/workflow-editor.tsx#L586): One role=status slot serves seven actions, including refusals such as the one at 225-227.
  - [apps/web/components/expert-editor.tsx:444-448](../../../../apps/web/components/expert-editor.tsx#L444): Refusals are announced with role=status.
  - [apps/web/components/goal-composer.tsx:318-340](../../../../apps/web/components/goal-composer.tsx#L318): Admission refusals are mapped one way.
  - [apps/web/components/session-panel.tsx:68-79](../../../../apps/web/components/session-panel.tsx#L68): The same endpoint's refusals are mapped another way, with no credential_invalid, no budget case and no link to settings.
  - [apps/web/components/continue-run.tsx:65-71](../../../../apps/web/components/continue-run.tsx#L65): A third way: it shows the server's message.
  - [apps/web/components/run-controls.tsx:195-216](../../../../apps/web/components/run-controls.tsx#L195): The model to follow: refusals as an alert and confirmations as a status note.
- **Evidence:** There are 3 different mappings for POST /api/v1/runs refusals, and owner_required is worded in 8 places across 6 files (grep owner_required in apps/web/components). Excerpt from session-panel.tsx:71-79:

  ```tsx
  setProblem(
    failure?.code === "credentials_required"
      ? "Model-backed work needs an OpenRouter key."
      : failure?.code === "model_not_offered"
        ? "A saved model choice isn't offered for new runs until it's qualified, ..."
        : reply?.status === 422
          ? "That request isn't approved, so no run started. Your goal is kept."
          : "That could not be started.",
  ```

- **Why it matters:** The same refusal from the same endpoint reads differently on Home, in a session and on a run. Screen readers interrupt for a success on Home, but announce refusals only politely in the editors and on Operations. Every new error code has to be added in several files.
- **Recommendation:** Add lib/refusals.ts, which maps ErrorResponse.code (read with parseErrorResponse) to text and an optional action link for each context: admission, owner and version conflict. Add an Outcome component that renders refusals with role=alert and confirmations with role=status, as RunControls already does. Keep the existing wording that the browser suites read.
- **Rule check:** DH-06: 'centralize error handling ... and expose safe typed errors'.
- **Verification:** confirmed. Confirmed the three admission refusal mappings, role=alert on the composer's success, role=status for refusals in the editors and Operations, and owner_required worded at 8 sites in 6 files.

### <a id="xweb-08"></a>XWEB-08: Run state vocabulary, tones and commands are defined per screen

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/components/run-list.tsx:16-64](../../../../apps/web/components/run-list.tsx#L16): STATUS_TEXT, which is exported, plus a Tone mapping with its own text and dot classes.
  - [apps/web/components/run-workspace.tsx:36-72](../../../../apps/web/components/run-workspace.tsx#L36): STATUS_LABEL repeats run-list's words, and the comment at line 48 says so. STATUS_TONE maps the same states to Badge variants instead.
  - [apps/web/components/workflow-monitor.tsx:13](../../../../apps/web/components/workflow-monitor.tsx#L13): TERMINAL is defined again. run_status is shown as raw text at line 106, and a third tone() is at 236-242.
  - [apps/web/components/run-controls.tsx:16-36](../../../../apps/web/components/run-controls.tsx#L16): The TERMINAL and PAUSABLE sets decide which commands are offered.
  - [apps/web/components/run-panel.tsx:17-21](../../../../apps/web/components/run-panel.tsx#L17): LABELS and the command buttons at 246-260 copy run-controls.tsx:25-29 and 138-152. Their version policies are opposite: the panel sends the loaded version (83-110), while RunControls re-reads it before each press (65-71).
  - [apps/web/components/waiting-notifier.tsx:14-17](../../../../apps/web/components/waiting-notifier.tsx#L14): WAITING, another state map.
  - [apps/web/components/model-policy-panel.tsx:24-29](../../../../apps/web/components/model-policy-panel.tsx#L24): SOURCE_LABEL. run-workspace.tsx:83-88 (ROLE_SOURCE) restates the same four words in lower case, in a second map keyed by string.
- **Evidence:** 7 definitions in 7 files, all keyed by string although the client exports RunStatus and BindingSource. The contract also types ExecutionView.run_status as plain string. Excerpts:

  ```tsx
  // run-list.tsx:16
  export const STATUS_TEXT: Record<string, string> = { queued: "Queued", running: "Running", ...
  // run-workspace.tsx:48-49
  // Decision 0021: the header's short state words, as the run list says them, ...
  const STATUS_LABEL: Record<string, string> = { queued: "Queued", running: "Running", ...
  // workflow-monitor.tsx:13
  const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
  ```

- **Why it matters:** A new run status compiles everywhere but renders as raw text on some screens. The same state gets different tones on the list and on the run page. The hand-written TERMINAL and PAUSABLE sets are a second state enum that can drift from the server's transition table. The opposite version policies of RunPanel and RunControls are recorded in US-15.17's design, and each file explains only its own (run-panel.tsx:82, run-controls.tsx:64), so the copied buttons hide that the two differ.
- **Recommendation:** Add lib/run-status.ts with labels, sentences and tones typed Record&lt;RunStatus, ...&gt;, and one RunStateBadge used by the list, the panel, the run page, Home and Workflows. Have the API send the allowed commands, as it already sends can_continue (run-workspace.tsx:425), instead of commandsFor's sets. Add one RunCommandButtons component with an explicit versionPolicy prop.
- **Rule check:** DH-06: 'do not invent a second state enum for the UI'. contracts.md: canonical states are shared. Having the API expose allowed commands keeps the transitions in Python.
- **Verification:** revised. Confirmed the seven definitions, the string-typed ExecutionView.run_status and the opposite version policies (US-15.17 design.md:14). Corrected two notes: SOURCE_LABEL and ROLE_SOURCE differ only in capitalization, and each command file does state its own policy in a comment.

### <a id="xweb-09"></a>XWEB-09: Money, time and duration formatting is re-implemented and disagrees

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 17
- **Where:**
  - [apps/web/components/run-list.tsx:87-89](../../../../apps/web/components/run-list.tsx#L87): dollars() with toFixed(2). It is identical in run-panel.tsx:30, goal-composer.tsx:74, workflows-panel.tsx:50 and home-activity.tsx:34.
  - [apps/web/components/run-inspector.tsx:10-12](../../../../apps/web/components/run-inspector.tsx#L10): A dollars() of the same name without toFixed.
  - [apps/web/components/run-workspace.tsx:802-822](../../../../apps/web/components/run-workspace.tsx#L802): Inline formatting shows US$1.00, US$0.5 and $0.5 for one run's figures.
  - [apps/web/components/approvals-panel.tsx:88-98](../../../../apps/web/components/approvals-panel.tsx#L88): Relative time computed by hand.
  - [apps/web/components/workflows-panel.tsx:36-48](../../../../apps/web/components/workflows-panel.tsx#L36): Relative time with Intl. home-activity.tsx:24-32 is the same function, and experts-panel.tsx:310-315 is a third style.
  - [apps/web/components/run-panel.tsx:34-42](../../../../apps/web/components/run-panel.tsx#L34): wallTime(). workflows-panel.tsx:63-70 formats the same kind of value differently.
  - [apps/web/components/goal-composer.tsx:197-206](../../../../apps/web/components/goal-composer.tsx#L197): The budget-steps loop, copied at workflow-editor.tsx:150-157.
- **Evidence:** grep for 'function dollars', '1_000_000' and 'RelativeTimeFormat' finds 6 dollars() definitions plus inline money formatting in 3 files, 4 relative-time helpers, 2 duration helpers and 2 budget-step loops. Excerpts:

  ```tsx
  // run-list.tsx:87-89
  function dollars(micro: number): string { return `US$${(micro / 1_000_000).toFixed(2)}`; }
  // run-inspector.tsx:10-12
  function dollars(micro: number): string { return `US$${micro / 1_000_000}`; }
  // run-workspace.tsx:819-821
  {snapshot.usage.repairs} repairs. Spent ${snapshot.run.budget.spent_micro_usd / 1_000_000} of $
  ```

- **Why it matters:** The same micro-USD value reads US$0.50 on the list and US$0.5 in the inspector, and one run page shows three styles. Each copy also decides for itself how to mark an estimate (≈), which DS-04 requires to stay distinct from a reported cost.
- **Recommendation:** Add lib/format.ts with formatUsd(micro, { estimated }), formatRelative(iso, now), formatDuration(seconds) and budgetSteps(range), cover it with node:test, and replace every copy.
- **Rule check:** DS-04: 'Estimated versus reported costs ... remain distinct'. One formatter keeps the estimate marking consistent.
- **Verification:** confirmed. Recounted 6 dollars() definitions, inline money in 3 files, 4 relative-time helpers, 2 duration helpers and 2 budget-step loops. The estimate rule (reserved above zero or unreported) is also restated in run-list, run-panel, home-activity and workflows-panel.

### <a id="xweb-10"></a>XWEB-10: Shared vocabulary and hooks live inside feature components, imported sideways and in a cycle

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** low · **Occurrences** 24
- **Where:**
  - [apps/web/components/run-list.tsx:8](../../../../apps/web/components/run-list.tsx#L8): Imports RunPanel ...
  - [apps/web/components/run-panel.tsx:9](../../../../apps/web/components/run-panel.tsx#L9): ... and run-panel imports StateLine back from run-list, which makes an import cycle.
  - [apps/web/components/expert-editor.tsx:17](../../../../apps/web/components/expert-editor.tsx#L17): A Build screen imports AVAILABILITY and repair() from the 853-line tool catalog.
  - [apps/web/components/workflows-panel.tsx:17](../../../../apps/web/components/workflows-panel.tsx#L17): Imports STATUS_TEXT from run-list. home-activity.tsx:13 does the same.
  - [apps/web/components/workflow-monitor.tsx:7](../../../../apps/web/components/workflow-monitor.tsx#L7): useToolUses is exported from a component file.
  - [apps/web/components/goal-composer.tsx:17-20](../../../../apps/web/components/goal-composer.tsx#L17): Takes DEFAULT_BUDGET_MICRO_USD from run-disclosure, and focusGoal and NEW_RUN_PARAM from new-run (line 29).
  - [apps/web/app/tools/[toolId]/page.tsx:5](../../../../apps/web/app/tools/[toolId]/page.tsx#L5): A route imports its screen from another route's module. tool-catalog.tsx holds 8 components.
  - [apps/web/components.json:18](../../../../apps/web/components.json#L18): Declares a hooks alias, but no hooks folder exists.
- **Evidence:** grep for imports from '@/components/&lt;non-ui&gt;' inside apps/web/components finds 24 import edges between feature components. 7 of them carry helpers, constants or a hook rather than a component. Excerpts:

  ```tsx
  // run-list.tsx:8
  import { RunPanel } from "@/components/run-panel";
  // run-panel.tsx:8-9
  import { commandsFor } from "@/components/run-controls";
  import { StateLine } from "@/components/run-list";
  // expert-editor.tsx:17
  import { AVAILABILITY, repair } from "@/components/tool-catalog";
  ```

- **Why it matters:** Pure helpers can only be reached through 'use client' modules, so they cannot be unit-tested without pulling in JSX and the React graph. A change to a list component ripples into Home, Workflows and the Expert editor. The run-list cycle works only because both imports are used inside functions.
- **Recommendation:** Move pure vocabulary and formatting into lib/ (run-status, tool-labels, format, refusals) with no React. Put hooks in hooks/ (use-resource, use-submit, use-tool-uses, use-models, use-mounted). Group screens in feature folders (components/runs, home, build, tools, approvals, settings, shell). Add a no-restricted-imports rule that forbids importing another feature folder's internals, allowing only its public entry module, and keep server-only code out of any entry module that client components import.
- **Rule check:** DH-06: 'explicit ownership, narrow interfaces ... small cohesive modules'. DH-03 places only apps/web/ itself, so folders inside it don't conflict with it.
- **Verification:** revised. Recounted 24 feature-to-feature import edges, 7 of them carrying helpers, constants or a hook, and the run-list and run-panel cycle. Reworded the lint rule so a shared entry module can't pull server-only code into a client bundle.

### <a id="xweb-11"></a>XWEB-11: Recurring layout pieces are private to screens instead of in components/ui

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** low · **Occurrences** 26
- **Where:**
  - [apps/web/components/run-workspace.tsx:846-864](../../../../apps/web/components/run-workspace.tsx#L846): Section. run-inspector.tsx:284-309 has a second copy, and tool-uses.tsx:250-256 an inline third.
  - [apps/web/components/approvals-panel.tsx:744-773](../../../../apps/web/components/approvals-panel.tsx#L744): Fact. tool-catalog.tsx:756-776 has a different Fact with a different API.
  - [apps/web/components/experts-panel.tsx:179-200](../../../../apps/web/components/experts-panel.tsx#L179): A segmented control, copied with identical classes in run-list.tsx:230-253 and approvals-panel.tsx:319-351.
  - [apps/web/components/session-panel.tsx:164](../../../../apps/web/components/session-panel.tsx#L164): A serif card title written by hand, one of 7 copies. CardTitle is used once (goal-composer.tsx:350), and Separator is never imported.
  - [apps/web/components/tool-catalog.tsx:461](../../../../apps/web/components/tool-catalog.tsx#L461): A dialog on background tokens with a black/60 backdrop. about-services.tsx:22 and search-palette.tsx:132 use popover tokens with black/50.
  - [apps/web/app/settings/account/page.tsx:29](../../../../apps/web/app/settings/account/page.tsx#L29): A settings row with a 260px label column. The other rows use 240px (app/settings/page.tsx:12, app/settings/notifications/page.tsx:14, data-summary.tsx:58).
  - [apps/web/components/expert-editor.tsx:227-232](../../../../apps/web/components/expert-editor.tsx#L227): An initial tile, also at experts-panel.tsx:342-347 and session-panel.tsx:113-118.
- **Evidence:** Grepping each class string finds 7 recurring pieces with 26 copies in total: Section 3, Fact 2, segmented control 3, serif title 7, dialog shell 3, settings row 5 and initial tile 3. Excerpt, from run-workspace.tsx:857 and run-inspector.tsx:297:

  ```tsx
  <section aria-labelledby={id} className="space-y-3 border-t pt-6">
  <section aria-labelledby={id} className="space-y-3 border-t pt-6">
  ```

- **Why it matters:** The copies drift already: there are two settings column widths, two dialog surfaces and two backdrops. DS-03's rule that dialogs use popover tokens holds in two of three dialogs, and every screen re-decides the markup of a section heading.
- **Recommendation:** Add to components/ui: SectionBlock, Fact or FactList, SegmentedControl (aria-pressed buttons, or Links when the state is in the URL), a Dialog that wraps a native &lt;dialog&gt; with popover tokens and one backdrop, SettingsRow, a serif CardTitle variant and InitialTile. Remove Separator or adopt it.
- **Rule check:** DS-01: 'Use shadcn/ui components'. DS-03: menus, selects and dialogs use popover and popover-foreground. Decision 0021's hairline sections.
- **Verification:** confirmed. Recounted the 26 copies by class string. The bg-background dialog in tool-catalog, the two backdrops and the 260px versus 240px settings rows are confirmed.

### <a id="xweb-12"></a>XWEB-12: Type sizes and many spacings are arbitrary values outside the theme

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 212
- **Where:**
  - [apps/web/app/globals.css:22-25](../../../../apps/web/app/globals.css#L22): Compact density tightens spacing only through --spacing, yet the comment says every spacing utility derives from it.
  - [apps/web/components/provider-settings-panel.tsx:83](../../../../apps/web/components/provider-settings-panel.tsx#L83): px-[18px] is fixed, so compact density doesn't tighten it. It also appears at lines 108 and 255 and at model-policy-panel.tsx:267.
  - [apps/web/components/run-list.tsx:233](../../../../apps/web/components/run-list.tsx#L233): p-[3px] in the segmented control, which has three copies.
  - [apps/web/components/model-policy-panel.tsx:65](../../../../apps/web/components/model-policy-panel.tsx#L65): py-[7px] on every row.
  - [apps/web/components/tool-catalog.tsx:621](../../../../apps/web/components/tool-catalog.tsx#L621): text-[22px] with tracking-[-0.015em], while the other serif titles use tracking-tight.
  - [apps/web/components/run-workspace.tsx:584](../../../../apps/web/components/run-workspace.tsx#L584): The dark-only tint rule from Decision 0021 is written on the element. There are 26 dark: class overrides in 12 feature files.
- **Evidence:** grep over components and app finds 212 arbitrary font sizes in 39 files, with 13 distinct values (12.5px ×75, 13px ×63, 13.5px ×19, 15px ×16, ...). It also finds 15 arbitrary pixel paddings, margins and gaps, 5 hard-coded radii (rounded-[10px] ×4, rounded-[7px] ×1), and 26 dark: class overrides in 12 files outside components/ui. @theme defines font families but no type scale (globals.css:31-77).
- **Why it matters:** The Studio type scale exists only as repeated numbers, so changing a size means searching 39 files. The compact density setting (SE-03) skips fixed paddings, although the stylesheet's comment says otherwise. Each screen restates the light/dark contrast rule, which only INNER_BOX and Badge encode centrally.
- **Recommendation:** Define the type scale in @theme, for example --text-meta 12.5px, --text-ui 13px, --text-body 13.5px, --text-lead 15px, --text-title 22px and --text-page 32px. Express paddings as spacing steps and radii as the radius scale, and replace the arbitrary values. Encode the dark-only tints as ui variants. Add a verify check that sets a baseline for arbitrary px classes and then ratchets it down.
- **Rule check:** DS-03: 'Keep layout spacing and typography consistent' and 'Map the radius scale to the canonical base'. The DS-01 palette is untouched, since a type scale is not a color token.
- **Verification:** revised. Recounted 212 arbitrary font sizes in 39 files with 13 values, and 15 arbitrary pixel spacings. Corrected the dark: count to 26 in 12 feature files, since 8 more are inside components/ui, and added the 5 hard-coded radii that the cited DS-03 rule covers.

### <a id="xweb-13"></a>XWEB-13: List filters and selection live in the URL on some screens and in state on others

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/components/tool-catalog.tsx:184-200](../../../../apps/web/components/tool-catalog.tsx#L184): All filters and the open tool live in the URL.
  - [apps/web/components/workflows-panel.tsx:86-89](../../../../apps/web/components/workflows-panel.tsx#L86): tab, q, workflow and version live in the URL. ?tab= is cast to Tab without validation.
  - [apps/web/components/run-list.tsx:161-170](../../../../apps/web/components/run-list.tsx#L161): group, query and profile live in state. Only the selected run is in the URL.
  - [apps/web/components/approvals-panel.tsx:123-126](../../../../apps/web/components/approvals-panel.tsx#L123): The tab and the selection live in state. Only the first selection comes from ?approval=.
  - [apps/web/components/experts-panel.tsx:32-33](../../../../apps/web/components/experts-panel.tsx#L32): The filter and search live in state.
  - [apps/web/components/workflows-panel.tsx:214-218](../../../../apps/web/components/workflows-panel.tsx#L214): Search writes the URL on every keystroke, as tool-catalog.tsx:254 does, while run-list debounces by 150 ms (188-203).
- **Evidence:** Five list screens use two models. Excerpt from workflows-panel.tsx:87 and run-list.tsx:161-169:

  ```tsx
  const tab = (params.get("tab") as Tab | null) ?? "all";
  ...
  const [group, setGroup] = useState<Group>("all");
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("");
  ...
  const selected = useSearchParams().get("run");
  ```

- **Why it matters:** Reload, Back and shared links keep the filters on Tools and Workflows but reset them on Runs, Approvals and Experts. Three segmented controls repeat state handling that a URL-backed control would provide. Values read from the URL are cast without validation.
- **Recommendation:** Add hooks/use-url-state.ts with a typed parse and serialize per key, a fallback, validation against the generated unions, and a debounced replace. Record per list screen which filters belong in the URL, and keep the existing ones (?run=, ?tool=, ?workflow=).
- **Rule check:** No product rule requires list filters in the URL. RN-04 keeps the selected run there and HM-04 links to ?approval=, so moving other filters into the URL is a per-screen product choice to record, not a requirement to infer from code. Validating URL values against the generated unions follows DH-06's validation at trust boundaries.
- **Verification:** revised. Confirmed the two models, the unvalidated ?tab= cast and the per-keystroke URL writes. Replaced the empty rule check: no source requires filters in the URL.

### <a id="xweb-14"></a>XWEB-14: Only two pages load data on the server, and client writes don't refresh server-rendered shell data

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 16
- **Where:**
  - [apps/web/app/page.tsx:32-38](../../../../apps/web/app/page.tsx#L32): Reads on the server through lib/service-status.
  - [apps/web/app/settings/account/page.tsx:13-14](../../../../apps/web/app/settings/account/page.tsx#L13): The only other page that loads data on the server.
  - [apps/web/components/run-inspector.tsx:18-48](../../../../apps/web/components/run-inspector.tsx#L18): A read-only page rendered as a client fetch after hydration.
  - [apps/web/components/data-summary.tsx:18-39](../../../../apps/web/components/data-summary.tsx#L18): Read-only, and fetched on the client.
  - [apps/web/components/app-shell.tsx:14-16](../../../../apps/web/components/app-shell.tsx#L14): The shell renders the approvals badge count on the server.
  - [apps/web/components/approvals-panel.tsx:192-226](../../../../apps/web/components/approvals-panel.tsx#L192): A decision reloads only the list. Nothing refreshes the shell.
  - [apps/web/components/account-form.tsx:28-31](../../../../apps/web/components/account-form.tsx#L28): Calls router.refresh() after a write that changes shell data. sign-in-form.tsx:31-32 does too.
  - [apps/web/components/account-footer.tsx:24](../../../../apps/web/components/account-footer.tsx#L24): fetchSession runs here and again in the Home and Account pages within one request. Every server read passes AbortSignal.timeout (lib/service-status.ts:26), which opts out of Next.js fetch memoization, and nothing wraps the reads in React cache().
- **Evidence:** grep for service-status or a server fetch in apps/web/app finds 2 pages. 16 other pages load their data only in client panels that fetch inside an effect; Appearance, Notifications, Keyboard and Sign in load none. Every server read passes a timeout signal, and the installed next/dist/server/lib/dedupe-fetch.js skips memoization for a request with a signal, so Home reads the session and readiness twice per request. Excerpt from approvals-panel.tsx:209-224 and account-form.tsx:28-31:

  ```tsx
  if (reply?.ok === true) {
    setMessage(decision === "approve" ? "Approved. ..." : "Rejected. ...");
  } else { ... }
  await load(tab);
  ...
  if (reply.ok) { setMessage("Saved."); router.refresh(); return; }
  ```

- **Why it matters:** Read-only screens paint a loading line first and need client JavaScript before they show anything, and screen code repeats access logic the server helper already has. Next.js does not re-render layouts on client navigation. So after an approval, the sidebar badge keeps its old count until something refreshes the page, whereas the display name updates after an account edit. Server reads also repeat within one request.
- **Recommendation:** Turn the read-only screens into async Server Components: the run inspector, the data summary, the tool detail facts and the first page of the run list. Have them read through a server-only typed client: extend lib/service-status into lib/server-api.ts with ApiError status mapping and a per-request React cache(), never a cache shared between requests. Keep interactive leaves such as version selects, copy buttons and filters as client components. Call router.refresh() after writes that change shell-rendered data, such as approval decisions.
- **Rule check:** DH-06: 'Prefer Server Components; use Client Components for actual interaction'. nextjs.md: 'Server Components by default'. Server reads keep the BFF's checks: the per-request session, the workspace header and the server-only config (lib/service-status.ts:33-39).
- **Verification:** revised. Corrected the client-only page count to 16. Confirmed the repeated server reads in the installed Next.js 16.4.5 dedupe-fetch, which never dedupes a request carrying a signal. The stale badge follows from layout partial rendering and was not observed in a browser.

### <a id="xweb-15"></a>XWEB-15: UI logic sits where unit tests can't reach it, and the unit runner lists test files by name

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): Runs two named files, so schema-value.test.ts is never run.
  - [apps/web/tests/unit/schema-value.test.ts:1](../../../../apps/web/tests/unit/schema-value.test.ts#L1): Cited as evidence in US-16.2's verification record.
  - [apps/web/components/run-workspace.tsx:125-141](../../../../apps/web/components/run-workspace.tsx#L125): withDelta merges streamed text across reconnects and has no unit test.
  - [apps/web/components/approvals-panel.tsx:686-742](../../../../apps/web/components/approvals-panel.tsx#L686): parsedFields and the Markdown reader, which builds React nodes from model-written text.
  - [apps/web/components/goal-composer.tsx:88-100](../../../../apps/web/components/goal-composer.tsx#L88): inputPath, which resolves attachment name collisions.
  - [apps/web/components/workflow-editor.tsx:78-104](../../../../apps/web/components/workflow-editor.tsx#L78): tidy and withLabel, which decide the IR version and the graph hash.
  - [apps/web/components/tool-catalog.tsx:79-114](../../../../apps/web/components/tool-catalog.tsx#L79): keySource and repair.
  - [apps/web/components/run-controls.tsx:32-36](../../../../apps/web/components/run-controls.tsx#L32): commandsFor.
- **Evidence:** apps/web/tests/unit has 3 files, all for lib/, and the 7 helper groups above, found by reading the component files, have no unit test. Excerpt from scripts/verify.py:161-162:

  ```python
  Step('web_unit_tests', (str(Path(tools.node_dir) / 'node'), '--test', 'apps/web/tests/unit/request-guard.test.ts',
                         'apps/web/tests/unit/credential-precedence.test.ts'), root),
  ```

- **Why it matters:** Edge cases are checked only by Playwright suites that need the db profile: joining a stream partway, integer-like JSON keys, IR version bumps and path collisions. As schema-value.test.ts shows, a new unit test file silently does not run unless someone also edits verify.py.
- **Recommendation:** Move the pure helpers into lib/\*.ts with no 'use client' and no JSX, and cover them with node:test as request-guard already is. Change the web_unit_tests step to discover apps/web/tests/unit/\*.test.ts. Keep the moved modules free of runtime @/ alias imports so node --test can load them, as lib/schema-value.ts is.
- **Rule check:** DH-06 asks for unit tests of relevant pure and client behavior and names Vitest and React Testing Library. The repository runs node:test instead, a departure the tooling lens records (XTOL-10). Moving pure helpers into lib/ works under either runner and adds no dependency.
- **Verification:** revised. Confirmed that verify.py:161-162 names two of the three unit files, so schema-value.test.ts never runs although US-16.2's verification.md:22 credits the web unit tests. All seven helper groups sit in client .tsx modules. Corrected the rule check: DH-06 names Vitest, not node:test.

### <a id="xweb-16"></a>XWEB-16: Screen state is spread across independent flags where one union belongs

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [apps/web/components/continue-run.tsx:13-21](../../../../apps/web/components/continue-run.tsx#L13): Seven pieces of state for one submission: open, pending, started, already, lost, problem and the key.
  - [apps/web/components/goal-composer.tsx:128-140](../../../../apps/web/components/goal-composer.tsx#L128): 13 states. outcome, refusal and runId describe one admission result, and they are reset together at 277-278 and 313-316.
  - [apps/web/components/workflow-editor.tsx:108-118](../../../../apps/web/components/workflow-editor.tsx#L108): 11 states, with one message slot shared by seven actions.
  - [apps/web/components/run-workspace.tsx:153-166](../../../../apps/web/components/run-workspace.tsx#L153): snapshot, connection, unavailable, gap, refreshes, live and result. unavailable can coexist with a live connection.
  - [apps/web/components/approvals-panel.tsx:123-134](../../../../apps/web/components/approvals-panel.tsx#L123): 10 states, including armed, announcement and message.
  - [apps/web/components/tool-catalog.tsx:157-159](../../../../apps/web/components/tool-catalog.tsx#L157): The counterexample: one discriminated union.
- **Evidence:** Counting useState calls per file (grep -c, minus the import line): goal-composer 13, workflow-editor 11, approvals-panel 10, run-workspace 8, continue-run 7. Excerpt from continue-run.tsx:13-21:

  ```tsx
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState("");
  const [started, setStarted] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [lost, setLost] = useState(false);
  const [already, setAlready] = useState(false);
  ```

- **Why it matters:** Impossible combinations can be represented, and every handler must reset several flags in the right order. A reader has to reconstruct each state machine from its setters.
- **Recommendation:** Model each screen's request state as a discriminated union, as useLoaded already does, or with useReducer. For example, admission is idle, pending, queued(runId), refused(code, message) or unknown, and connection is loading, live, reconnecting, ended or unavailable. Have the resource and submit hooks return these unions.
- **Rule check:** DH-06: 'Browser state is a view of durable state, not a second scheduler'. The unions describe request state only.
- **Verification:** confirmed. Recounted useState per file: 13, 11, 10, 8 and 7. The combinations named in the impact can be represented in the current code.

### <a id="xweb-17"></a>XWEB-17: Live updates differ per screen, and the run page refetches whole resources on every event

- **Severity** low · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 7
- **Where:**
  - [apps/web/components/run-workspace.tsx:206-211](../../../../apps/web/components/run-workspace.tsx#L206): Every stored event triggers a full GET of /workspace.
  - [apps/web/components/run-workspace.tsx:573-580](../../../../apps/web/components/run-workspace.tsx#L573): The count of tool events becomes ToolsUsed's version ...
  - [apps/web/components/tool-uses.tsx:110-145](../../../../apps/web/components/tool-uses.tsx#L110): ... so each tool event re-reads every page of tool uses.
  - [apps/web/components/run-workspace.tsx:198-201](../../../../apps/web/components/run-workspace.tsx#L198): Reconnects after a fixed 1 s, with no backoff.
  - [apps/web/components/workflow-monitor.tsx:44-64](../../../../apps/web/components/workflow-monitor.tsx#L44): Polls every 1 s, and keeps polling through 5xx responses.
  - [apps/web/components/waiting-notifier.tsx:13](../../../../apps/web/components/waiting-notifier.tsx#L13): Polls every 4 s on every page while browser notifications are on and permitted. Otherwise it doesn't poll.
  - [apps/web/components/run-list.tsx:186-208](../../../../apps/web/components/run-list.tsx#L186): The run list never refreshes, and neither do approvals (approvals-panel.tsx:158-187) or Home (home-activity.tsx:63-90).
- **Evidence:** 7 components use 4 live-update strategies: a server event stream, 1 s polling, 4 s polling while notifications are on, and none. Excerpt from run-workspace.tsx:206-211:

  ```tsx
  source.addEventListener("run", (message) => {
    const event = known(JSON.parse(message.data as string));
    if (event === null || event.sequence <= cursor) return;
    add([event]);
    void refresh();
  });
  ```

- **Why it matters:** The run page's request count grows with run length: one workspace read per event, and tool-use reads that grow quadratically over a run. When the API stops, every open run or execution tab retries it once a second. Lists that show running work go stale while the run page is live.
- **Recommendation:** Add hooks/use-live-resource.ts that refreshes by polling or by event, with backoff and coalescing: at most one refresh in flight, plus one trailing refresh. On the run page, coalesce refreshes and request only tool uses after a cursor. Document for each screen whether it is live.
- **Rule check:** nextjs.md: 'handle reconnect/deduplication'. Reading more or less often changes no run (DH-06: browser state is a view).
- **Verification:** revised. Confirmed the workspace read per event, the reread of every tool-use page, the fixed 1 s reconnect and the monitor polling through 5xx. Corrected the notifier: it polls only while notifications are enabled and permitted.

### <a id="xweb-18"></a>XWEB-18: Browser preferences and the shortcut list are kept in sync by comments

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/app/layout.tsx:17](../../../../apps/web/app/layout.tsx#L17): The before-paint script hardcodes the five storage keys and their values.
  - [apps/web/components/appearance-control.tsx:84-124](../../../../apps/web/components/appearance-control.tsx#L84): A second definition of the same keys and values.
  - [apps/web/components/run-workspace.tsx:117-121](../../../../apps/web/components/run-workspace.tsx#L117): Reads the data-stream attribute directly.
  - [apps/web/components/appearance-control.tsx:144-148](../../../../apps/web/components/appearance-control.tsx#L144): Detects mount through useSyncExternalStore. notifications-control.tsx:30-34 copies it.
  - [apps/web/lib/shortcuts.ts:1-6](../../../../apps/web/lib/shortcuts.ts#L1): The shortcut table for Settings. Its handlers live in new-run.tsx:28-39, search-palette.tsx:50-62 and approvals-panel.tsx:228-286.
- **Evidence:** The preference keys have 2 definitions and are read in a third file, the mount check exists twice, and 3 key handlers sit outside the shortcut table. Excerpt from lib/shortcuts.ts:1-2:

  ```ts
  // PRD-Studio SE-07: every keyboard shortcut the app offers, in one place. Settings → Keyboard lists
  // these, so a shortcut added elsewhere is added here too.
  ```

- **Why it matters:** Renaming a preference or adding a shortcut needs coordinated edits that no check enforces.
- **Recommendation:** Add lib/preferences.ts, which exports the keys and allowed values and builds the before-paint script from them. Add hooks/use-mounted.ts. Export each shortcut's key test from lib/shortcuts.ts beside its Settings text, and have new-run, search-palette and approvals-panel match on it, so one table serves the list and the handlers. Three handlers don't need a registration hook.
- **Rule check:** DS-02: the storage keys and the dark default stay as specified. Only their definition is shared.
- **Verification:** revised. Confirmed the two key definitions, the direct data-stream read, the copied mount check and the three handlers outside the table. Replaced the useShortcut registration hook with shared key tests, which three handlers need, to avoid a speculative framework.

### <a id="xweb-19"></a>XWEB-19: Page title and width belong to the page on most routes but to the client screen on run routes

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/app/approvals/page.tsx:15-16](../../../../apps/web/app/approvals/page.tsx#L15): The server page renders the container and the PageHeader.
  - [apps/web/app/tools/page.tsx:11-21](../../../../apps/web/app/tools/page.tsx#L11): The same, with Suspense below the header.
  - [apps/web/components/run-list.tsx:224-228](../../../../apps/web/components/run-list.tsx#L224): The client list renders the page title and width itself.
  - [apps/web/components/run-workspace.tsx:333-372](../../../../apps/web/components/run-workspace.tsx#L333): Two heading forms: a PageHeader in the loading and unavailable states, and a custom h1 with a badge once loaded.
  - [apps/web/components/run-inspector.tsx:50-72](../../../../apps/web/components/run-inspector.tsx#L50): The same split.
  - [apps/web/components/app-shell.tsx:13](../../../../apps/web/components/app-shell.tsx#L13): States the convention: 'Pages own their width and padding inside &lt;main&gt;.'
- **Evidence:** Of the 22 pages, the 3 run routes (/runs, /runs/[id] and /runs/[id]/inspector) render only a client component, which sets the container width and builds the heading. 17 of the other 19 pages render PageHeader themselves; Home and Sign in write their own h1 by design.
- **Why it matters:** On the run screens, the heading's structure changes between states, and container widths are set in two places, against the shell's stated convention.
- **Recommendation:** Keep the PageHeader and the container in the server page for every route. Let client screens render only the body, and pass adornments such as the status badge through PageHeader's actions slot or a small client leaf.
- **Rule check:** Decision 0021: every section opens the same way (components/ui/page-header.tsx:5).
- **Verification:** revised. Confirmed the three run routes and the two heading forms in RunWorkspaceView and RunInspectorView. Corrected 'every other page': Home and Sign in use their own h1.

### <a id="xweb-20"></a>XWEB-20: Route components use ten suffixes, and one constant name means three things

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 21
- **Where:**
  - [apps/web/components/approvals-panel.tsx:117](../../../../apps/web/components/approvals-panel.tsx#L117): Route components named \*Panel; ExpertsPanel, WorkflowsPanel, ToolCatalogPanel, OperationsPanel, SessionPanel and KeysAndVarsPanel follow the same pattern.
  - [apps/web/components/run-workspace.tsx:152](../../../../apps/web/components/run-workspace.tsx#L152): \*View for two run routes. RunInspectorView is the other.
  - [apps/web/components/run-panel.tsx:47](../../../../apps/web/components/run-panel.tsx#L47): RunPanel is a side panel inside the list, not a route's component. WorkflowPreviewPanel is the same kind.
  - [apps/web/components/run-list.tsx:16](../../../../apps/web/components/run-list.tsx#L16): STATUS_TEXT holds short labels here ...
  - [apps/web/components/run-workspace.tsx:36](../../../../apps/web/components/run-workspace.tsx#L36): ... and sentences here, beside STATUS_LABEL. workflow-monitor.tsx:14 uses the same name for node states.
- **Evidence:** The 21 routes that have a client component use ten suffixes: Composer, Panel, Editor, List, View, Control, Form, Summary, Detail and Monitor. STATUS_TEXT is defined three times with three meanings.
- **Why it matters:** Nothing in a name tells a route's component apart from a sub-panel, and an import of STATUS_TEXT picks up whichever meaning the source file chose.
- **Recommendation:** Name the client component that renders a route &lt;Feature&gt;Screen, and keep Panel for side panels. Name the vocabularies by content in lib/run-status.ts: RUN_STATUS_LABEL, RUN_STATUS_SENTENCE and NODE_STATUS_LABEL.
- **Rule check:** DH-06: 'readable names'.
- **Verification:** confirmed. Confirmed ten suffixes across the 21 routes with a client component (Keyboard has none) and three meanings of STATUS_TEXT. Adopt the convention with the folder move in XWEB-10 rather than as a standalone rename.

## Rejected during verification

No finding was rejected. All 20 were kept: 7 confirmed and 13 revised. XWEB-04 was lowered from high to medium; every other severity stands.

Verification re-opened every cited location at revision d0d85d3, recounted each pattern with grep and small Python scans over apps/web, and read the installed Next.js 16.4.5 dedupe-fetch source for XWEB-14. It ran no check, started no service and changed no file outside this folder.

## Not covered

The browser specs under apps/web/tests/browser were not read in full, because they belong to the web-tests area. Only lines 295-345 of approvals.spec.ts were read, to see whether the sidebar badge is tested after a decision. playwright.config.ts, postcss.config.mjs and the two other unit tests were not read. The generated client was only searched with grep, since generated files are out of scope. From PRD-Development-Harness.md, only DH-03 and DH-06 were read. scripts/verify.py was read only at lines 150-175, scripts/generate_contracts.py only at lines 55-100, and services/agent/src/autobots/domain/models.py only at lines 60-110. PRD-Studio.md, SPECS.md and CODEBASE.md were not read beyond grep, so screen-level product rules such as HM-02 and RN-04 were judged only from code comments and archived OpenSpec records. The review is static: ESLint, tsc and the app were not run, and the counts come from grep and metrics.md. Two claims rest on Next.js behavior that was not observed: that the server-rendered approvals badge stays stale after a decision (layouts don't re-render on client navigation), and that the repeated server reads in one request are not deduplicated by fetch memoization.
