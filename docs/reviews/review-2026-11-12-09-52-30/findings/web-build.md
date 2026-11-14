# Web: workflows and Experts

The web-build area has five thin App Router pages and five client components (2,713 lines). They cover the workflow list, editor and execution monitor, and the Experts list and editor. Most boundaries are right. The pages are small Server Components that await params and mount one client island. Every successful reply except the three session starts is parsed with the generated api-client parsers, and saves and publishes carry expected versions. The monitor only reads and keeps the last known state through disconnects. The screens also take real care over accessibility and carry why-comments tied to WF-, EX- and Decision IDs. The cost is in how the client components are built. WorkflowEditor (617 lines, 11 state hooks, eight handlers), ExpertEditor (393), WorkflowsPanel (341) and ExpertsPanel (255) each write their own reads, writes, refusal parsing and messages, with no shared read or submit hook. That is where the defects are. Nine create, publish and run calls make a new Idempotency-Key on every click and never disable their buttons, so a double-click on Run this version starts two executions even though the server stores idempotency receipts. Ten reply bodies are cast with type assertions although parseErrorResponse and parseSessionView exist. Six secondary reads fail silently: into Loading text that never clears, into a missing Budget field or Blocks card, or, on the Experts page, into a Read only classification. Rules the server owns are copied into the browser and have started to drift: the offered model profiles, the WF-06 IR version, run-state tones and the terminal set, and budget choices. The editors also have no dirty state, and the workflow editor's two publish buttons publish from different sources. The most valuable changes are these. Add a useResource and useSubmit pair in lib/, starting from the useLoaded hook the tool catalog already has. Split WorkflowEditor around a draft hook, with the IR helpers in a unit-tested lib module. Create one shared module each for model-profile labels, run-state presentation, and money and time formatting. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict TypeScript and the project lint pass, and the pages are thin Server Components. But DH-06's duplicate-submit, explicit-state and no-assertion rules are missed (9 unguarded keyed writes, 15 assertions, 6 silent reads), and DS-03's radius rule at two sites. |
| modules | 3 | Rules the server owns (offered profiles, WF-06 IR version, run-state tones, budget choices) are copied into components. Shared vocabularies are imported from other screens' component files (run-list, tool-catalog). |
| size | 2 | Four functions are over 250 lines (WorkflowEditor 617, ExpertEditor 393, WorkflowsPanel 341, ExpertsPanel 255), three files are over 450 lines, and ExpertCard has complexity 27. |
| functions | 3 | Pure helpers are small and well named (withLabel, tidy, expansion, spend). Handlers mix request building, transport, parsing and five-level message ternaries (save has complexity 19). |
| structure | 3 | App Router pages are thin and uniform. Each component file bundles several components, formatting helpers and constants (some declared after use), which keeps pure logic out of reach of the unit harness. |
| approach | 2 | There is no shared read or submit hook. 8 hand-written read effects and 12 writes (9 keyed, 3 unkeyed) each re-implement state, idempotency and messages. Per-click keys defeat server dedupe. The monitor polls every second and reloads all tool uses on each poll. |
| comments | 4 | Comments mostly explain why and cite WF-, EX-, TC- and Decision IDs. One is misplaced, and the body-drain idiom is not explained here. |
| types | 3 | Successful replies are parsed with generated parsers, except the three session starts, and tsconfig is strict. But error and session bodies, role bindings and a URL parameter are cast (15 assertions), and the IR uses local DraftGraph types. |
| errors | 2 | Refusal codes get clear text. But failed secondary reads look like loading, network and auth failures read as shape errors, contract errors read as reconnecting, and sibling actions map the same code differently. |
| tests | 3 | Browser specs cover the main flows, refusals, conflicts, label IR versions and monitor reconnect. Nothing covers repeated submits or failed secondary reads, and no pure helper has a unit test. |
| maintainability | 3 | The code is readable, commented and browser-tested. But four oversized components and per-screen copies of fetch, submit, format and rule logic make every change wide and let the copies drift. |

## Strengths

- **Successful replies are parsed with the generated contract.** These sites pass reply JSON through parse* functions from @autobots/api-client before it reaches state: expert-editor.tsx:83, 102, 160; experts-panel.tsx:40, 50, 116; workflow-editor.tsx:130, 148, 165, 187, 212, 252, 341, 388; workflow-monitor.tsx:52; workflows-panel.tsx:104, 138, 478, 496. Drift on a success path fails at the boundary. The three session starts are the exception (WBLD-03). Sources: [components/expert-editor.tsx:83](../../../../apps/web/components/expert-editor.tsx#L83), [components/experts-panel.tsx:40](../../../../apps/web/components/experts-panel.tsx#L40), [components/workflow-editor.tsx:130](../../../../apps/web/components/workflow-editor.tsx#L130), [components/workflow-monitor.tsx:52](../../../../apps/web/components/workflow-monitor.tsx#L52), [components/workflows-panel.tsx:104](../../../../apps/web/components/workflows-panel.tsx#L104).
- **Thin Server Component pages with one client island.** apps/web/app/experts/[id]/page.tsx:8-20, apps/web/app/workflows/[id]/page.tsx:8-20 and apps/web/app/workflow-executions/[id]/page.tsx:8-20 await params, export route metadata and mount one component. apps/web/app/workflows/page.tsx:16-24 wraps the panel that uses useSearchParams in Suspense, with an accessible role=status fallback. Sources: [app/experts/[id]/page.tsx:8](../../../../apps/web/app/experts/[id]/page.tsx#L8), [app/workflows/[id]/page.tsx:8](../../../../apps/web/app/workflows/[id]/page.tsx#L8), [app/workflow-executions/[id]/page.tsx:8](../../../../apps/web/app/workflow-executions/[id]/page.tsx#L8), [app/workflows/page.tsx:16](../../../../apps/web/app/workflows/page.tsx#L16).
- **Linkable list state in the URL.** workflows-panel.tsx:86-89 and 116-124 keep tab, search, selection and version in search params. The tab links use aria-current and scroll={false} (185-189), and key={chosen.id} (380-388) resets the preview when the selection changes, so the view survives reload and Back. Sources: [components/workflows-panel.tsx:86](../../../../apps/web/components/workflows-panel.tsx#L86), [components/workflows-panel.tsx:116](../../../../apps/web/components/workflows-panel.tsx#L116), [components/workflows-panel.tsx:185](../../../../apps/web/components/workflows-panel.tsx#L185), [components/workflows-panel.tsx:380](../../../../apps/web/components/workflows-panel.tsx#L380).
- **Optimistic concurrency with plain-language conflicts.** Saves and publishes send expected_version (expert-editor.tsx:143; workflow-editor.tsx:206, 301), and conflicts become clear text (expert-editor.tsx:177-178; workflow-editor.tsx:265-266). experts.spec.ts:104 and workflows.spec.ts:217 exercise this. Sources: [components/expert-editor.tsx:143](../../../../apps/web/components/expert-editor.tsx#L143), [components/workflow-editor.tsx:206](../../../../apps/web/components/workflow-editor.tsx#L206), [components/workflow-editor.tsx:265](../../../../apps/web/components/workflow-editor.tsx#L265), [tests/browser/experts.spec.ts:104](../../../../apps/web/tests/browser/experts.spec.ts#L104), [tests/browser/workflows.spec.ts:217](../../../../apps/web/tests/browser/workflows.spec.ts#L217).
- **Accessibility designed in from the start.** workflows-panel.tsx:455-467 moves focus to the preview heading and respects reduced motion when it scrolls. Lines 78-79 keep the table usable at 400% zoom, and 230-235 make the scroll region focusable. expert-editor.tsx:339-343 links each disabled tool to its reason with aria-describedby. experts-panel.tsx:373 and 380 give each button and checkbox the Expert's name. workflow-monitor.tsx:178-191 puts words beside every status dot (Decision 0021). Sources: [components/workflows-panel.tsx:455](../../../../apps/web/components/workflows-panel.tsx#L455), [components/expert-editor.tsx:339](../../../../apps/web/components/expert-editor.tsx#L339), [components/experts-panel.tsx:373](../../../../apps/web/components/experts-panel.tsx#L373), [components/workflow-monitor.tsx:178](../../../../apps/web/components/workflow-monitor.tsx#L178).
- **A read-only monitor that cleans up and survives disconnects.** workflow-monitor.tsx:26 documents that reconnecting cannot start or repeat anything. Line 61 stops polling at a terminal state, 67-70 clear the timer on unmount, and 132-134 keep the last known state while reconnecting. slice-workflows.spec.ts:132-158 drives the disconnect. Sources: [components/workflow-monitor.tsx:26](../../../../apps/web/components/workflow-monitor.tsx#L26), [components/workflow-monitor.tsx:61](../../../../apps/web/components/workflow-monitor.tsx#L61), [components/workflow-monitor.tsx:132](../../../../apps/web/components/workflow-monitor.tsx#L132), [tests/browser/slice-workflows.spec.ts:132](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L132).
- **Why-comments with traceable IDs.** workflow-editor.tsx:78-79 explains why nulls are removed (the hash stays stable). Line 89 cites WF-06, 138 cites WF-02, and 144 cites WF-05 and D11. expert-editor.tsx:114-115, 145 and 356 explain what the form keeps or drops. experts-panel.tsx:46 cites EX-02 and EX-03, and workflows-panel.tsx:81-82 cites WF-01, WF-03 and WF-04. Sources: [components/workflow-editor.tsx:78](../../../../apps/web/components/workflow-editor.tsx#L78), [components/workflow-editor.tsx:144](../../../../apps/web/components/workflow-editor.tsx#L144), [components/expert-editor.tsx:114](../../../../apps/web/components/expert-editor.tsx#L114), [components/experts-panel.tsx:46](../../../../apps/web/components/experts-panel.tsx#L46), [components/workflows-panel.tsx:81](../../../../apps/web/components/workflows-panel.tsx#L81).
- **Stable data attributes as test hooks.** data-field, data-state, data-validation and data-message attributes give the Playwright specs selectors that don't depend on wording or styling, for example expert-editor.tsx:387, workflow-editor.tsx:548 and 568, workflow-monitor.tsx:103 and workflows-panel.tsx:284. Sources: [components/expert-editor.tsx:387](../../../../apps/web/components/expert-editor.tsx#L387), [components/workflow-editor.tsx:548](../../../../apps/web/components/workflow-editor.tsx#L548), [components/workflow-monitor.tsx:103](../../../../apps/web/components/workflow-monitor.tsx#L103), [components/workflows-panel.tsx:284](../../../../apps/web/components/workflows-panel.tsx#L284).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WBLD-01](#wbld-01) | high | size | WorkflowEditor is one 617-line component that owns eight concerns | M | medium |
| [WBLD-02](#wbld-02) | high | approach | Create, publish and run calls make a new Idempotency-Key on every click and never disable their buttons | M | medium |
| [WBLD-03](#wbld-03) | medium | types | Ten reply bodies are cast although generated parsers exist for them | S | low |
| [WBLD-04](#wbld-04) | medium | errors | Six secondary reads fail silently into Loading text that never clears, or into wrong facts | M | medium |
| [WBLD-05](#wbld-05) | medium | approach | The editors have no dirty state, and the workflow editor's two publish buttons publish from different sources | M | medium |
| [WBLD-06](#wbld-06) | medium | modules | WF-06 IR rules are re-implemented in the browser, and half of the label rule exists only there | M | high |
| [WBLD-07](#wbld-07) | medium | duplication | The Expert editor hard-codes which model profiles are offered, and profile labels exist in three copies | S | medium |
| [WBLD-08](#wbld-08) | medium | approach | The execution monitor polls every second with no backoff, reloads all tool uses on each poll, and shows contract errors as reconnecting | M | medium |
| [WBLD-09](#wbld-09) | medium | duplication | The Experts and Workflows screens copy the same list and detail scaffolding, with two filter mechanisms | M | medium |
| [WBLD-10](#wbld-10) | medium | size | ExpertEditor is a 393-line component with a save handler of complexity 19 | M | medium |
| [WBLD-11](#wbld-11) | medium | size | workflows-panel.tsx holds two large components (341 and 213 lines) and the list's formatting helpers | M | low |
| [WBLD-12](#wbld-12) | medium | size | ExpertCard has complexity 27 and shares a 434-line file with a 255-line panel | S | low |
| [WBLD-13](#wbld-13) | medium | duplication | The monitor re-implements run-state labels, tones and the terminal set, and other screens import them from component files | S | low |
| [WBLD-14](#wbld-14) | medium | duplication | Budget choices and money and time formatting are copied across screens and have diverged | S | medium |
| [WBLD-15](#wbld-15) | medium | tests | Risky editor logic has no unit tests, and no test covers repeated submits or failed secondary reads | M | low |
| [WBLD-16](#wbld-16) | low | errors | Refusal codes are mapped with nested ternaries, inconsistently across sibling actions | S | low |
| [WBLD-17](#wbld-17) | low | standards | Pixel type sizes, a hard-coded radius and repeated heading and avatar class strings bypass the token scale | S | low |
| [WBLD-18](#wbld-18) | low | comments | A comment sits above the wrong declarations, and the body drains have no explanation | S | low |
| [WBLD-19](#wbld-19) | low | naming | `draft` names two different things in the workflow editor, and one action has two names | S | low |
| [WBLD-20](#wbld-20) | low | types | A URL parameter, role bindings and block versions are narrowed without checks | S | medium |

### <a id="wbld-01"></a>WBLD-01: WorkflowEditor is one 617-line component that owns eight concerns

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/workflow-editor.tsx:106-736](../../../../apps/web/components/workflow-editor.tsx#L106): Component body: 617 lines, complexity 20, 27 statements (ESLint with the review's extra rules)
  - [apps/web/components/workflow-editor.tsx:108-118](../../../../apps/web/components/workflow-editor.tsx#L108): 11 useState hooks: catalog, graph text, validation, message, version, inputs, description, budgets, budget, and so on
  - [apps/web/components/workflow-editor.tsx:120-171](../../../../apps/web/components/workflow-editor.tsx#L120): One effect loads the workflow, the run-preview budget and the block catalog
  - [apps/web/components/workflow-editor.tsx:173-396](../../../../apps/web/components/workflow-editor.tsx#L173): Eight async handlers write one shared message slot
  - [apps/web/components/workflow-editor.tsx:412-735](../../../../apps/web/components/workflow-editor.tsx#L412): Three cards and the block table, inline
- **Evidence:** The function holds:
  - 11 useState hooks (108-118);
  - one effect that fetches three unrelated resources (120-171);
  - eight async handlers at 173-396: validate, publish, draftRequest, saveDraft, publishDraft, discardDraft, saveDescription and run. Each builds a request, reads the reply and writes the same `message`;
  - about 320 lines of JSX for the graph card, the run card and the block catalog (412-735).

  The file is 739 lines. ESLint with the review's warn-only rules reports 617 lines, complexity 20 and 27 statements for this one function.
- **Why it matters:** Any change to drafts (WF-02), labels (WF-06), budgets (WF-05) or starting an execution edits the same closure, and the concerns leak into each other. For example, saving the description replaces a validation or publish message. No piece can be unit-tested or reused on its own. That is why the editor-state gaps in this review (dirty state, publish sources, duplicate submits) are hard to fix safely here.
- **Recommendation:** Split along the concerns, with workflows.spec.ts and slice-workflows.spec.ts as the safety net, and add the dirty-state cases first. The pieces:
  - a read hook for the workflow;
  - a draft hook that owns the graph text and every draft action;
  - pure IR helpers in lib/;
  - one component per card.

  Keep WorkflowEditor as a layout container of about 80 lines.
- **Rule check:** DH-06 asks for small cohesive modules and Client Components only for interaction. The split keeps publish, draft and run as API calls that the service owns, and edits no generated file.
- **Verification:** confirmed. Re-read the whole function: 11 useState hooks at 108-118, one three-read effect at 120-171, eight async handlers at 173-396 and JSX at 412-735; the ESLint figures match eslint.json.

```text
lib/workflow-ir.ts         parseGraphText, withLabel, tidy (pure, node --test)
lib/use-resource.ts        useResource(url, parse) -> {status, data, retry}
lib/use-submit.ts          pending flag + an Idempotency-Key kept until the outcome is known
workflow-editor/use-graph-draft.ts  useGraphDraft(workflow) -> {text, setText, graph, isDirty, check, validate, saveDraft, publish, publishDraft, discard, message}
workflow-editor/index.tsx  WorkflowEditor: reads the workflow, lays out the cards (~80 lines)
  <WorkflowHeading>   name, version and draft badges
  <DescriptionField>  textarea, its own save and message
  <GraphEditor>       textarea, <StepLabels>, <ValidationResult>, <DraftActions>
  <RunVersionCard>    version, inputs, budget (lib/budget.ts), RunDisclosure, run
  <BlockCatalogTable> its own read and unavailable state
```

### <a id="wbld-02"></a>WBLD-02: Create, publish and run calls make a new Idempotency-Key on every click and never disable their buttons

- **Severity** high · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 9
- **Where:**
  - [apps/web/components/workflow-editor.tsx:369-385](../../../../apps/web/components/workflow-editor.tsx#L369): run() starts an execution with a new key on every call
  - [apps/web/components/workflow-editor.tsx:675-678](../../../../apps/web/components/workflow-editor.tsx#L675): Run this version has no pending or disabled state
  - [apps/web/components/workflow-editor.tsx:197-210](../../../../apps/web/components/workflow-editor.tsx#L197): publish() uses a new key; so does the draft publish at 245
  - [apps/web/components/expert-editor.tsx:134-158](../../../../apps/web/components/expert-editor.tsx#L134): save() uses a new key; so does startSession at 187-199
  - [apps/web/components/expert-editor.tsx:434-441](../../../../apps/web/components/expert-editor.tsx#L434): Save revision and Start a session are never disabled
  - [apps/web/components/experts-panel.tsx:84-95](../../../../apps/web/components/experts-panel.tsx#L84): startRun(); create() at 104-114 and coordinate() at 131-142 do the same
  - [apps/web/components/workflows-panel.tsx:126-136](../../../../apps/web/components/workflows-panel.tsx#L126): create() uses a new key
  - [apps/web/components/continue-run.tsx:21-39](../../../../apps/web/components/continue-run.tsx#L21): The repository's safe pattern: the key stays in a ref until the outcome is known, plus a pending flag
- **Evidence:** All nine keyed POSTs build the header inside the handler with "Idempotency-Key": crypto.randomUUID(). The sites are expert-editor 140 and 193; experts-panel 89, 111 and 136; workflow-editor 203, 245 and 375; and workflows-panel 133. No trigger in these files is disabled while a request runs. The only disabled props check input: name.trim() === "", routed.size === 0, workflow.draft === null and budgets.length === 0. A lost reply (.catch(() => null)) is reported as a refusal. continue-run.tsx shows the intended shape: it writes "Idempotency-Key": (key.current ??= crypto.randomUUID()), keeps a pending flag, and treats null and 5xx as an unknown outcome.
- **Why it matters:** The API dedupes by key, through stored receipts in application/experts.py add_version and IdempotencyConflict in api/workflow_routes.py. A new key per click defeats that.
  - A double-click on Run this version, or a second press after a lost reply, starts two executions, each with its own budget.
  - Start run or Start a session opens two sessions.
  - A repeated Save revision or Publish fails the expected-version check and tells the user someone saved a newer version, after their own click.
- **Recommendation:** Add one useSubmit hook in lib/, modelled on continue-run.tsx, and use it for the nine keyed calls and the three unkeyed writes (saveDescription, draft PUT and DELETE). The hook provides:
  - a pending state that disables the trigger and changes its label;
  - where the API takes one, a key held in a ref until the outcome is known: cleared on success or a 4xx refusal, kept after a null or 5xx reply, and dropped when the request body changes, because the API refuses a reused key with different content (IdempotencyConflict, api/workflow_routes.py:82-84);
  - a typed outcome.

  Add a Playwright case that double-clicks Run this version and expects exactly one execution.
- **Rule check:** DH-06: 'Disable duplicate submits with server idempotency as the correctness mechanism.' The hook supplies both halves and leaves the server's receipts and version checks as the authority. No guard is weakened.
- **Verification:** revised. Recounted 9 keyed POSTs with grep and found no trigger disabled while pending; added that a kept key must reset when the body changes, since the server's fingerprint check refuses a reused key with new content.

```ts
// lib/use-submit.ts
type Outcome<T> = { kind: 'ok'; value: T } | { kind: 'refused'; refusal: ErrorResponse } | { kind: 'unknown' };
export function useSubmit<T>(send: (key: string) => Promise<Response>, parse: (body: unknown) => T) {
  const key = useRef<string | null>(null);
  const [pending, setPending] = useState(false);
  // submit(): key.current ??= crypto.randomUUID(); null or 5xx -> 'unknown', key kept;
  // ok -> parse, key cleared; 4xx -> readRefusal(reply), key cleared; finally setPending(false)
  return { pending, submit };
}
// <Button disabled={run.pending}>{run.pending ? 'Starting' : 'Run this version'}</Button>
```

### <a id="wbld-03"></a>WBLD-03: Ten reply bodies are cast although generated parsers exist for them

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 10
- **Where:**
  - [apps/web/components/expert-editor.tsx:168-171](../../../../apps/web/components/expert-editor.tsx#L168): Error body cast
  - [apps/web/components/expert-editor.tsx:201](../../../../apps/web/components/expert-editor.tsx#L201): Session reply cast to { id: string }
  - [apps/web/components/experts-panel.tsx:97](../../../../apps/web/components/experts-panel.tsx#L97): Session reply cast; also at 144
  - [apps/web/components/experts-panel.tsx:119-121](../../../../apps/web/components/experts-panel.tsx#L119): Error body cast
  - [apps/web/components/workflow-editor.tsx:220-223](../../../../apps/web/components/workflow-editor.tsx#L220): Error body cast; also at 254, 351 and 392
  - [apps/web/components/workflows-panel.tsx:141-143](../../../../apps/web/components/workflows-panel.tsx#L141): Error body cast
  - [packages/api-client/src/generated.ts:7698](../../../../packages/api-client/src/generated.ts#L7698): parseErrorResponse, used 0 times in apps/web
  - [packages/api-client/src/generated.ts:8840](../../../../packages/api-client/src/generated.ts#L8840): parseSessionView, the schema of the 201 reply to POST /v1/sessions
- **Evidence:** Seven refusal reads use: const failure = (await reply?.json().catch(() => null)) as { code?: string; message?: string } | null;. A grep for 'json().catch(() => null)) as' finds 20 such casts in 15 files across the repository. The three session starts read (await reply.json()) as { id: string } and put id into a URL. Every refusal from the API (api/errors.py) and the BFF (lib/bff.ts safeError) has the shape {code, message}, which parseErrorResponse validates. POST /v1/sessions returns SessionView, which parseSessionView validates. parseErrorResponse is used nowhere in apps/web, while every other successful reply in these files is parsed.
- **Why it matters:** DH-06 rules out assertions that hide contract mismatches. If either shape drifts, these paths fail quietly, with generic messages or a push to /sessions/undefined, instead of failing at the boundary like the rest of the screen. The same read-and-cast code is also repeated at each site.
- **Recommendation:** Add readRefusal(reply) in lib/. It drains the body and returns parseErrorResponse(...) or null. Use parseSessionView for session starts. Then enable @typescript-eslint/consistent-type-assertions (assertionStyle: never) for these files as a ratchet.
- **Rule check:** DH-06: explicit response parsing at untrusted boundaries and no blanket assertions. The fix uses the generated parsers and edits no generated file.
- **Verification:** confirmed. Recounted 7 refusal casts and 3 session casts in scope; grep finds 20 such casts in 15 files and no parseErrorResponse use in apps/web; every API refusal is built from ErrorResponse (api/errors.py:19-21).

```ts
// lib/refusal.ts
export async function readRefusal(reply: Response | null): Promise<ErrorResponse | null> {
  if (reply === null) return null;
  try { return parseErrorResponse(await reply.json()); } catch { return null; }
}
// session starts: router.push(`/sessions/${parseSessionView(await reply.json()).id}`)
```

### <a id="wbld-04"></a>WBLD-04: Six secondary reads fail silently into Loading text that never clears, or into wrong facts

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [apps/web/components/expert-editor.tsx:80-85](../../../../apps/web/components/expert-editor.tsx#L80): Tool catalog read: a non-ok reply is ignored and errors are swallowed
  - [apps/web/components/expert-editor.tsx:273-276](../../../../apps/web/components/expert-editor.tsx#L273): 'Loading the tool catalog.' then stays, and no tools are listed
  - [apps/web/components/experts-panel.tsx:47-53](../../../../apps/web/components/experts-panel.tsx#L47): Tool catalog read is swallowed
  - [apps/web/components/experts-panel.tsx:59-75](../../../../apps/web/components/experts-panel.tsx#L59): Without the catalog, every Expert is counted as Read only
  - [apps/web/components/experts-panel.tsx:398-409](../../../../apps/web/components/experts-panel.tsx#L398): The 'Approval on every…' note disappears with it
  - [apps/web/components/workflow-editor.tsx:145-167](../../../../apps/web/components/workflow-editor.tsx#L145): Budget-range and block-catalog reads are swallowed; the Budget field and the Blocks card never appear
  - [apps/web/components/workflows-panel.tsx:469-486](../../../../apps/web/components/workflows-panel.tsx#L469): Preview read is swallowed; 'Loading its steps.' stays (552-553)
  - [apps/web/components/workflows-panel.tsx:488-503](../../../../apps/web/components/workflows-panel.tsx#L488): Executions read is swallowed; 'Loading.' stays (608-609)
- **Evidence:** Each secondary read ignores a non-ok reply and swallows errors with `.catch(() => undefined)`, and none has a failed state. The six reads are:
  - the tool catalog in expert-editor.tsx:80-85;
  - the tool catalog in experts-panel.tsx:47-53;
  - the budget range in workflow-editor.tsx:145-161;
  - the block catalog in workflow-editor.tsx:162-167;
  - the preview in workflows-panel.tsx:469-486;
  - the recent executions in workflows-panel.tsx:488-503.

  On the Experts page, `outside` is computed with `catalog.get(tool)?.operation_class` against a Map that starts empty (59-70). Until the catalog arrives, or if it never does, every Expert counts as Read only, including Experts granted github_open_pull_request, and the approval note is hidden. When the budget read fails, run() also sends no budget (380-382), so the server applies its default limit. Only 2 of the 11 read sites in scope read a refused body (workflows-panel 479 and 497), which is the convention documented in run-disclosure.tsx:53.
- **Why it matters:** DH-06 and nextjs.md require deliberate loading, unavailable and retryable states. Here a 500 or a dropped connection looks like a load that never finishes. The Experts page presents a safety-relevant classification as known when it isn't (DS-04, state meaning).
- **Recommendation:** Promote the useLoaded hook from tool-catalog.tsx:156-181, which already aborts on cleanup, ignores stale replies and returns a typed state, into lib/ as useResource(url, parse). Extend it to return {status: 'loading'|'ready'|'unavailable', data, retry} and to read refused bodies. Render an explicit unavailable line with a Retry control for each secondary read. On the Experts page, treat the classification as unknown until the catalog is ready: disable the two class filters and show 'Checking granted tools'.
- **Rule check:** DH-06: 'Represent loading, empty, denied, unavailable and retryable states deliberately'. nextjs.md: 'explicit error/empty/loading states'. DS-04: state meaning.
- **Verification:** revised. All six reads re-read: the code shapes vary (two drain refused bodies) but none has a failed state; the recommendation now builds on the existing useLoaded hook instead of a second new one, and the omitted-budget consequence was added.

```ts
// lib/use-resource.ts, promoted from tool-catalog.tsx useLoaded
type Resource<T> = { status: 'loading' } | { status: 'ready'; data: T } | { status: 'unavailable'; retry: () => void };
export function useResource<T>(url: string | null, parse: (body: unknown) => T): Resource<T>;
// reads refused bodies, aborts on unmount or URL change, treats ContractError as unavailable
// ExpertsPanel: const catalog = useResource('/api/v1/tools', parseToolCatalog);
//   classify only when catalog.status === 'ready'; otherwise the class filters say 'Checking granted tools'
```

### <a id="wbld-05"></a>WBLD-05: The editors have no dirty state, and the workflow editor's two publish buttons publish from different sources

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 2
- **Where:**
  - [apps/web/components/workflow-editor.tsx:111](../../../../apps/web/components/workflow-editor.tsx#L111): Editor text, kept apart from the saved WF-02 draft with no comparison between them
  - [apps/web/components/workflow-editor.tsx:194-210](../../../../apps/web/components/workflow-editor.tsx#L194): Publish sends the textarea and never checks the JSON first
  - [apps/web/components/workflow-editor.tsx:293-312](../../../../apps/web/components/workflow-editor.tsx#L293): Publish draft publishes the saved server draft, whatever the textarea shows
  - [apps/web/components/workflow-editor.tsx:437-441](../../../../apps/web/components/workflow-editor.tsx#L437): 'Draft saved' shows whenever a server draft exists, even with unsaved edits
  - [apps/web/components/workflow-editor.tsx:511-546](../../../../apps/web/components/workflow-editor.tsx#L511): Publish and Publish draft sit side by side, with nothing saying what each publishes
  - [services/agent/src/autobots/application/workflows.py:220-250](../../../../services/agent/src/autobots/application/workflows.py#L220): publish_draft deletes the draft; publish_version (251) leaves it in place
  - [apps/web/components/expert-editor.tsx:434-441](../../../../apps/web/components/expert-editor.tsx#L434): Save revision is always enabled; Start a session navigates away from unsaved edits
- **Evidence:** The workflow editor holds the IR as one text string (`draft`) next to `workflow.draft` (the saved draft) and the published versions, and never compares them.
  - Publish sends graph: parsed(draft) without the parsed(...) === null check that validate() (176-179) and saveDraft() (273-277) apply. Invalid JSON therefore reaches the API as graph: null and returns the generic 'The request is not valid.'
  - Publish draft sends only expected_version, so it publishes the stored draft while the textarea may show different, unsaved edits.
  - Publishing the textarea leaves an older stored draft in place.

  The Expert editor has the same gap. Save revision is always enabled, and each save creates a new version (add_version has no no-op check). Start a session goes to a session bound to the saved version while the edits stay unsaved.
- **Why it matters:** Users can publish or start work from a different graph or configuration than the one on screen, and the badge says 'Draft saved' when the screen isn't. Every fix today has to reason about three implicit states inside a 617-line component.
- **Recommendation:** Model the editor state explicitly in the draft hook: `baseline` (the saved draft or the latest version, tidied), `text`, `isDirty = text !== baseline`, and `graph`, parsed once. Then:
  - show 'Unsaved changes' beside the badge;
  - name the two actions by source;
  - disable 'Publish saved draft' while the text is dirty;
  - run the JSON check in one place for every action;
  - warn before leaving the page or starting a session while there are unsaved changes.

  In the Expert editor, derive isDirty by comparing the draft with draftOf(expert), and disable Save when nothing has changed.
- **Rule check:** Under PRD-Studio WF-02, one saved draft is published under the expected version. The recommendation keeps both publish paths and the server checks, and only makes the browser's view of them explicit (DH-06: browser state is a view of durable state).
- **Verification:** confirmed. Traced both publish paths against publish_draft and publish_version (application/workflows.py:220-303); invalid JSON in publish() reaches the API as graph: null, and add_version has no no-op check.

```ts
type GraphDraft = {
  baseline: string;             // tidy(saved draft ?? latest version)
  text: string;                 // what the textarea shows
  isDirty: boolean;             // text !== baseline
  graph: WorkflowGraph | null;  // parsed once per text (useMemo)
};
// every action starts with: if (graph === null) return say(INVALID_JSON)
// 'Publish what is shown' | 'Publish saved draft' (disabled while isDirty); warn before leaving when dirty
// ExpertEditor: isDirty = !sameDraft(draft, draftOf(expert)); Save disabled when clean
```

### <a id="wbld-06"></a>WBLD-06: WF-06 IR rules are re-implemented in the browser, and half of the label rule exists only there

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** high · **Occurrences** 3
- **Where:**
  - [apps/web/components/workflow-editor.tsx:59-76](../../../../apps/web/components/workflow-editor.tsx#L59): Local DraftNode and DraftGraph types; parsed(text) is asserted as DraftGraph before it is checked
  - [apps/web/components/workflow-editor.tsx:78-87](../../../../apps/web/components/workflow-editor.tsx#L78): tidy() strips label: null and ir_version: null, mirroring ir_normalized
  - [apps/web/components/workflow-editor.tsx:89-104](../../../../apps/web/components/workflow-editor.tsx#L89): withLabel() bumps the graph to ir_version 2, and deletes it when no label is left
  - [apps/web/components/workflow-editor.tsx:479-486](../../../../apps/web/components/workflow-editor.tsx#L479): draftGraph(draft) is parsed twice per render, then asserted non-null with !
  - [services/agent/src/autobots/domain/workflows.py:199-211](../../../../services/agent/src/autobots/domain/workflows.py#L199): ir_normalized strips null labels and adds ir_version 2 to a labelled graph, but never returns a label-free graph to version 1
  - [packages/api-client/src/generated.ts:9167](../../../../packages/api-client/src/generated.ts#L9167): Generated WorkflowGraph and WorkflowNode (with label and ir_version), unused here
- **Evidence:** The server already canonicalizes every graph it validates, publishes or previews with ir_normalized (api/workflow_routes.py:136, application/workflows.py:58). It drops null labels and a null ir_version, and stores a labelled graph at version 2. The editor repeats this in tidy and withLabel, and adds one rule the server doesn't have: removing the last label deletes ir_version, so the graph returns to version 1 and its old hash. That half runs only when a label input changes. A user who deletes the labels in the JSON textarea keeps "ir_version": 2, and the API stores it. The editor also types the payload with hand-written DraftNode and DraftGraph types instead of the generated WorkflowGraph and WorkflowNode.
- **Why it matters:** WF-06's version rule has two owners that disagree on one case, so a graph's hash depends on which control the user edited. Changing the IR, for example to a version 3, means editing a React component as well as the domain. Each keystroke in a label field also re-serializes the whole graph text, which drops the user's own JSON formatting.
- **Recommendation:** Choose one owner. The preferred option is a story that makes ir_normalized return a label-free graph to version 1. That is a contract and hash decision, so it needs its own work item; after it, the editor only sets or deletes labels. Until then:
  - move parse, tidy and withLabel to lib/workflow-ir.ts, typed with Pick<WorkflowNode, 'id' | 'block' | 'label'> and WorkflowGraph;
  - parse once per render with useMemo;
  - unit-test both directions of the label rule.
- **Rule check:** DH-06: 'Avoid duplicated business rules'. contracts.md: version the workflow IR. nextjs.md: Next.js owns UI and BFF, not business-state transitions. The recommendation moves ownership toward the domain, edits no generated file, and leaves the hash change to an explicit story. The draft graph is the WorkflowDraftSave payload, so typing it with the generated type uses the DTO without merging it into a view model.
- **Verification:** revised. ir_normalized (domain/workflows.py:199-211) keeps an explicit ir_version 2 while withLabel deletes it; re-serialization happens on label edits, not on every keystroke, so that sentence and the nextjs.md wording were corrected. Risk stays high only for the domain story; the interim lib move is low risk.

```ts
// lib/workflow-ir.ts, until the domain owns the whole rule
type LabelNode = Pick<WorkflowNode, 'id' | 'block' | 'label'>;
export function parseGraphText(text: string): (WorkflowGraph & { nodes: LabelNode[] }) | null;
export function withLabel(graph: WorkflowGraph, nodeId: string, label: string): WorkflowGraph;
export function tidy(graph: WorkflowGraph): WorkflowGraph;
// story: domain/workflows.py ir_normalized also returns a label-free graph to version 1;
// then withLabel only sets or deletes `label`, and tidy goes once views omit nulls
```

### <a id="wbld-07"></a>WBLD-07: The Expert editor hard-codes which model profiles are offered, and profile labels exist in three copies

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/expert-editor.tsx:21-25](../../../../apps/web/components/expert-editor.tsx#L21): PROFILES: workspace setting, Terra, Sol
  - [apps/web/components/expert-editor.tsx:116-128](../../../../apps/web/components/expert-editor.tsx#L116): Kept and dropped bindings are computed against PROFILES
  - [apps/web/components/expert-editor.tsx:415-432](../../../../apps/web/components/expert-editor.tsx#L415): The 'not offered for new runs until qualified' option and the dropped-binding notice come from PROFILES
  - [apps/web/components/experts-panel.tsx:295-299](../../../../apps/web/components/experts-panel.tsx#L295): PROFILE_NAMES copy
  - [apps/web/components/run-list.tsx:75-79](../../../../apps/web/components/run-list.tsx#L75): PROFILE_NAMES copy
  - [services/agent/src/autobots/domain/models.py:72](../../../../services/agent/src/autobots/domain/models.py#L72): OFFERED_FOR_NEW_RUNS = {TERRA, SOL}, exposed as ModelAvailability.offered
  - [apps/web/components/model-policy-panel.tsx:235](../../../../apps/web/components/model-policy-panel.tsx#L235): Already builds its choices from offered, read from /api/models
- **Evidence:** PROFILES lists Terra and Sol as the offered choices. Any other saved binding is treated as not offered and removed on save. The server decides the same thing in OFFERED_FOR_NEW_RUNS (domain/models.py:72), which gained Sol on 2026-11-07 under Decision 0019 S2 and S4. It publishes the answer per profile as ModelAvailability.offered through /api/models, which run-disclosure.tsx:47 and model-policy-panel.tsx:136 already read. The labels for ModelProfileId are written out again in experts-panel.tsx and run-list.tsx.
- **Why it matters:** The next change to the offered set needs a matching edit in this component, or the editor misleads. A newly offered DeepSeek would still be labelled 'not offered' and silently dropped from other roles on save. A withdrawn profile would still be offered, and the save would only fail late with model_not_offered.
- **Recommendation:** Read /api/models in the editor, or reuse RunDisclosure's read through a shared hook. Build the executor options as model-policy-panel does: the offered profiles plus the current value, marked not offered. Compute kept and dropped from offered. Put the labels in one lib/model-profiles.ts typed Record<ModelProfileId, string>, so a new generated profile breaks the build until it has a label.
- **Rule check:** model-gateway.md: three approved profiles, with DeepSeek and Sol offered only once qualified; Decision 0019 S2. The server stays the only owner of 'offered', and no fallback or alternative provider is introduced.
- **Verification:** confirmed. PROFILES at 21-25 and the kept/dropped logic match; OFFERED_FOR_NEW_RUNS is at domain/models.py:72, expert routes call require_offered, and model-policy-panel.tsx:234-235 already builds choices from offered.

```ts
// lib/model-profiles.ts
export const PROFILE_NAMES: Record<ModelProfileId, string> = {
  openrouter_terra: 'Terra', openrouter_sol: 'Sol', openrouter_deepseek_flash: 'DeepSeek Flash',
};
// expert-editor: const models = useResource('/api/models', parseModelList);
// options = offered profiles plus the saved one marked not offered (as model-policy-panel.tsx:235)
// dropped = other roles whose profile has offered === false
```

### <a id="wbld-08"></a>WBLD-08: The execution monitor polls every second with no backoff, reloads all tool uses on each poll, and shows contract errors as reconnecting

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/workflow-monitor.tsx:12](../../../../apps/web/components/workflow-monitor.tsx#L12): POLL_MS = 1000, used by the fixed re-poll at 64 with no check of page visibility
  - [apps/web/components/workflow-monitor.tsx:44-45](../../../../apps/web/components/workflow-monitor.tsx#L44): A null or 5xx reply sets 'reconnecting' without reading the body; the next poll is still 1 s later
  - [apps/web/components/workflow-monitor.tsx:50-56](../../../../apps/web/components/workflow-monitor.tsx#L50): A parse failure (ContractError) also shows as 'reconnecting', indefinitely
  - [apps/web/components/workflow-monitor.tsx:59](../../../../apps/web/components/workflow-monitor.tsx#L59): loads is incremented on every successful poll, whether or not anything changed
  - [apps/web/components/workflow-monitor.tsx:199-203](../../../../apps/web/components/workflow-monitor.tsx#L199): version={loads} drives useToolUses
  - [apps/web/components/tool-uses.tsx:110-145](../../../../apps/web/components/tool-uses.tsx#L110): Each version change re-reads every tool-use page
  - [apps/web/components/run-workspace.tsx:204](../../../../apps/web/components/run-workspace.tsx#L204): The run screen follows the same run with an EventSource, a cursor and reconnect
  - [apps/web/tests/browser/slice-workflows.spec.ts:152-166](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L152): Pins that an unexpected reply reads as reconnecting and that polling recovers to live
- **Evidence:** load() (38-65) polls again every POLL_MS = 1000 until the run reaches a terminal state, with no backoff and no visibility check. A null or 5xx reply sets 'reconnecting' without reading the body. A reply that fails parseExecutionView is also shown as 'reconnecting'. slice-workflows.spec.ts:152-166 pins that on purpose: an HTML reply must read as reconnecting, and polling must then recover to live. Nothing tells a ContractError (valid JSON in the wrong shape) apart from a network blip, though. Every successful poll increments loads, and version={loads} makes useToolUses re-read every tool-use page, 200 at a time. run-workspace.tsx:170-204 follows a run with an EventSource, a cursor and a reconnect delay.
- **Why it matters:** While an execution runs, each open monitor, hidden tabs included, sends at least two requests about once a second and downloads the whole tool-use history again, which keeps growing with the run. During an outage it keeps polling every second and leaves refused bodies unread, against the documented drain convention (run-disclosure.tsx:53). After an API or bundle mismatch it shows 'Reconnecting' indefinitely, with nothing that suggests a reload.
- **Recommendation:** Move polling into a useExecution hook:
  - back off while reconnecting;
  - pause while the page is hidden;
  - read refused bodies;
  - bump the tool-use revision only when the snapshot changed.

  Keep polling after any unexpected reply, as slice-workflows.spec.ts:152-166 requires. A ContractError may add a note that the page may be out of date, with a reload link, while polling continues. Alternatively, refetch on the bound run's event stream, as the run screen does. Split the JSX into per-card components while moving it.
- **Rule check:** nextjs.md: 'handle reconnect/deduplication and explicit error/empty/loading states. Browser disconnect does not cancel a run.' The monitor stays read-only, as its documented invariant at line 26 requires, and the tested keep-polling behaviour is preserved.
- **Verification:** revised. Polling rate, the loads counter and useToolUses' full re-read are confirmed; treating a bad body as reconnecting is pinned by slice-workflows.spec.ts:152-166, so the recommendation now keeps polling and only adds an out-of-date hint for a ContractError.

```ts
// lib/use-execution.ts
export function useExecution(id: string): {
  view: ExecutionView | null;
  connection: 'live' | 'reconnecting' | 'unavailable';
  outdated: boolean; // the last reply failed parseExecutionView; polling continues
  revision: number;  // bumps only when the snapshot changed; drives useToolUses
};
// 1 s while live, doubling to 15 s while reconnecting, paused while document.hidden
// 5xx -> body read, back off; any bad body keeps polling (slice-workflows.spec.ts:152-166)
// or refetch on /api/v1/runs/{run_id}/events/stream events, as run-workspace.tsx:204 does
// WorkflowMonitor -> <BindingCard>, <InstancesTable>, <NodeToolUses revision>, <EmissionsList>
```

### <a id="wbld-09"></a>WBLD-09: The Experts and Workflows screens copy the same list and detail scaffolding, with two filter mechanisms

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 15
- **Where:**
  - [apps/web/components/experts-panel.tsx:246-281](../../../../apps/web/components/experts-panel.tsx#L246): Create section; workflows-panel.tsx:389-424 differs in 4 of 36 lines
  - [apps/web/components/experts-panel.tsx:104-129](../../../../apps/web/components/experts-panel.tsx#L104): create(); workflows-panel.tsx:126-151 differs in 5 of 26 lines
  - [apps/web/components/workflows-panel.tsx:389-424](../../../../apps/web/components/workflows-panel.tsx#L389): The second create section
  - [apps/web/components/experts-panel.tsx:35-45](../../../../apps/web/components/experts-panel.tsx#L35): List read, with failed and loading text at 160-173; same as workflows-panel.tsx:98-114 and 153-166
  - [apps/web/components/experts-panel.tsx:178-211](../../../../apps/web/components/experts-panel.tsx#L178): Filter and search kept in component state, with aria-pressed buttons
  - [apps/web/components/workflows-panel.tsx:182-221](../../../../apps/web/components/workflows-panel.tsx#L182): Tab and search kept in the URL, with links and aria-current
  - [apps/web/components/expert-editor.tsx:91-112](../../../../apps/web/components/expert-editor.tsx#L91): Detail read and states (208-221); same as workflow-editor.tsx:120-143 and 398-411
  - [apps/web/components/expert-editor.tsx:187-206](../../../../apps/web/components/expert-editor.tsx#L187): Session start; copied in experts-panel.tsx:84-102 and 131-149
- **Evidence:** Running diff on the two create sections shows 4 changed lines of 36. On the two create() handlers it shows 5 of 26: the endpoint, body, parser and messages. The list reads with their failed and loading paragraphs, the empty states and the detail reads all follow one template, and the session start is written three times. That makes 15 places in seven blocks. The two toolbars differ in mechanism. Experts keeps filter and search in component state with aria-pressed buttons. Workflows keeps tab, search and selection in the URL, with links and aria-current.
- **Why it matters:** Each fix in this review (the submit guard, unavailable states, refusal parsing) has to be made in up to 15 places. The two lists also behave differently for the same task: Expert filters reset on reload and Back, while workflow tabs survive both.
- **Recommendation:** Extract the shared pieces: useResource for list and detail reads, a CreateByName component, useStartSession, a ListToolbar backed by the URL, and EmptyState and load-state primitives. Then give the Experts toolbar the same URL behaviour as Workflows.
- **Rule check:** DH-06: small cohesive modules. PRD-Studio EX-02 does not say where the Expert filters live, so moving them into the URL is a visible behaviour change that belongs in its own story rather than in this refactor.
- **Verification:** revised. Re-ran diff: the create sections differ in 4 of 36 lines and the create handlers in 5 of 26, not 6; the 15 places in seven blocks recount correctly, and the ruleCheck now flags the URL change as a story.

```text
lib/use-resource.ts             list and detail reads with loading and unavailable states
lib/use-start-session.ts        useStartSession() -> { pending, start(kind, expertIds) } with parseSessionView
components/create-by-name.tsx   <CreateByName heading inputId endpoint body={(name) => ...} parse hrefFor refusals />
components/ui/list-toolbar.tsx  <ListToolbar tabs={[{ id, label, count }]} tabParam='tab' searchParam='q' /> (URL state)
components/ui/empty-state.tsx   <EmptyState>No Experts yet.</EmptyState>
components/ui/load-state.tsx    <Loading>, <Unavailable> for list and detail pages
```

### <a id="wbld-10"></a>WBLD-10: ExpertEditor is a 393-line component with a save handler of complexity 19

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/expert-editor.tsx:70-472](../../../../apps/web/components/expert-editor.tsx#L70): Component: 393 lines, complexity 14
  - [apps/web/components/expert-editor.tsx:59-68](../../../../apps/web/components/expert-editor.tsx#L59): draftOf has complexity 13 from its default values
  - [apps/web/components/expert-editor.tsx:116-128](../../../../apps/web/components/expert-editor.tsx#L116): Role-binding reconciliation computed during render
  - [apps/web/components/expert-editor.tsx:130-185](../../../../apps/web/components/expert-editor.tsx#L130): save(): body merge, transport, cast and a five-level message ternary
  - [apps/web/components/expert-editor.tsx:279-319](../../../../apps/web/components/expert-editor.tsx#L279): Group grants inline, calling grantable() again for each group
  - [apps/web/components/expert-editor.tsx:326-383](../../../../apps/web/components/expert-editor.tsx#L326): Tool grants inline, with an onChange that updates two fields
- **Evidence:** ExpertEditor reads the catalog and the Expert, reconciles role bindings during render, and saves with save(). save() merges the body, sends it, casts the reply and maps it through a five-level message ternary, giving complexity 19. The component also starts sessions and renders:
  - group grants;
  - tool grants;
  - the expansion sentence (385-397);
  - the executor select (398-432);
  - the version list (450-469).

  The file is 475 lines.
- **Why it matters:** The grant rules (TC-06 expansion, unavailable tools, group wholeness at 356-361) and the binding rules can only be exercised through the browser. Any change to one fieldset re-renders and re-reasons about the whole form.
- **Recommendation:** Move the pure grant and draft logic to lib/, keep the container small, and give each fieldset its own component. Map refusals with a lookup table, as the error-mapping finding describes.
- **Rule check:** DH-06: small cohesive modules. The form's Draft type stays a UI model separate from ExpertConfig, as contracts.md keeps DTO and UI types distinct.
- **Verification:** confirmed. ESLint figures (393 lines and complexity 14; save 19; draftOf 13) match eslint.json; grantable() runs twice per group at 280-284, and the file is 475 lines.

```text
lib/expert-grants.ts  grantable, members, expansion, draftOf, revisionBody(expert, draft, offered) (pure, unit-tested)
expert-editor.tsx     ExpertEditor: reads, draft and isDirty, save via useSubmit (~90 lines)
  <PurposeFields>     purpose and instructions with the contract's maxLength
  <GroupGrants>       whole-group checkboxes (now 279-319)
  <ToolGrants>        per-tool checkboxes and unavailable reasons (now 326-382)
  <GrantSummary>      the expansion sentence (now 385-397)
  <ExecutorSelect>    offered profiles from /api/models and the dropped notice (now 398-432)
  <VersionHistory>    the versions list (now 450-469)
SAVE_REFUSALS: Record<string, string> replaces the five-level ternary
```

### <a id="wbld-11"></a>WBLD-11: workflows-panel.tsx holds two large components (341 and 213 lines) and the list's formatting helpers

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/workflows-panel.tsx:83-427](../../../../apps/web/components/workflows-panel.tsx#L83): WorkflowsPanel: 341 lines, complexity 11
  - [apps/web/components/workflows-panel.tsx:269-374](../../../../apps/web/components/workflows-panel.tsx#L269): The row map alone is 106 lines
  - [apps/web/components/workflows-panel.tsx:429-649](../../../../apps/web/components/workflows-panel.tsx#L429): WorkflowPreviewPanel: 213 lines, complexity 12, focus handling and two read effects
  - [apps/web/components/workflows-panel.tsx:34-74](../../../../apps/web/components/workflows-panel.tsx#L34): relative, dollars, spend, duration and stateText
- **Evidence:** WorkflowsPanel reads URL state, loads the list, builds hrefs, creates workflows, and renders the tabs, search, a seven-column table and the create form. WorkflowPreviewPanel owns focus management and two read effects, and renders the steps and recent executions. The file is 649 lines.
- **Why it matters:** The table row, the preview and the formatting helpers can't be changed, reused or tested on their own. The preview's two silent reads are hidden inside a 213-line function.
- **Recommendation:** Split into a container, a table file and a preview file. Move the helpers to lib/format.ts and share the create form with experts-panel.
- **Rule check:** DH-06: small cohesive modules. A mechanical split covered by workflow-list.spec.ts.
- **Verification:** confirmed. Function spans and complexities match eslint.json; the row map is 106 lines at 269-374, and the file is 649 lines.

```text
workflows-panel.tsx   WorkflowsPanel: URL state, list read, layout (~100 lines)
workflow-table.tsx    <WorkflowTable rows selected hrefFor> and <WorkflowRow> (now the 106-line map at 269-374)
workflow-preview.tsx  <WorkflowPreviewPanel> -> <VersionSwitch>, <PreviewSteps>, <RecentExecutions>, each with its own read state
create-by-name.tsx    shared with experts-panel
lib/format.ts         formatMicroUsd, formatRelative, formatDuration (reuse run-panel's wallTime), spendText
```

### <a id="wbld-12"></a>WBLD-12: ExpertCard has complexity 27 and shares a 434-line file with a 255-line panel

- **Severity** medium · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/experts-panel.tsx:22-284](../../../../apps/web/components/experts-panel.tsx#L22): ExpertsPanel: 255 lines, with two reads, classification and three writes
  - [apps/web/components/experts-panel.tsx:59-82](../../../../apps/web/components/experts-panel.tsx#L59): Classification, counts and filtering computed during render
  - [apps/web/components/experts-panel.tsx:286-305](../../../../apps/web/components/experts-panel.tsx#L286): Module constants placed between the two components
  - [apps/web/components/experts-panel.tsx:317-431](../../../../apps/web/components/experts-panel.tsx#L317): ExpertCard: 115 lines, complexity 27, from inline ternaries
- **Evidence:** ExpertsPanel holds the experts and catalog reads, the classification, the filtering, and three writes (startRun, create, coordinate) plus the toggle. It renders the toolbar, the grid, the coordinator bar and the create form. ExpertCard gets complexity 27 from inline ternaries for the executor label, the run count, the approval noun and the tool chips.
- **Why it matters:** The safety-relevant classification (outside versus read only) is computed inline, where no unit test can reach it. The card's branching makes small wording changes risky.
- **Recommendation:** Move the card to its own file built from small parts. Make the classification a pure function in lib/ that reports when it is unknown. Reuse the shared create form and the session-start hook.
- **Rule check:** DH-06: small cohesive modules.
- **Verification:** confirmed. ExpertCard complexity 27, the 255-line panel and the 434-line file are confirmed; the module constants sit between the components at 286-305.

```text
experts-panel.tsx      ExpertsPanel: reads, toolbar, grid, coordinator bar (~120 lines)
expert-card.tsx        <ExpertCard> -> <InitialTile>, <ExecutorLine>, <RunsLine>, <ApprovalNote>, <ToolChips>
lib/expert-classes.ts  classify(experts, catalog | null) -> { known, items, counts } (pure)
lib/model-profiles.ts  PROFILE_NAMES shared with run-list
create-by-name.tsx and lib/use-start-session.ts shared with workflows-panel and expert-editor
```

### <a id="wbld-13"></a>WBLD-13: The monitor re-implements run-state labels, tones and the terminal set, and other screens import them from component files

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/components/workflow-monitor.tsx:13](../../../../apps/web/components/workflow-monitor.tsx#L13): TERMINAL, the same set as run-controls.tsx:16
  - [apps/web/components/workflow-monitor.tsx:103-110](../../../../apps/web/components/workflow-monitor.tsx#L103): Run status and stop reason shown as raw enum text
  - [apps/web/components/workflow-monitor.tsx:235-242](../../../../apps/web/components/workflow-monitor.tsx#L235): tone() gives no tone to waiting_input or verifying
  - [apps/web/components/run-list.tsx:33-47](../../../../apps/web/components/run-list.tsx#L33): tone() for the same run states: waiting_input gets attention, verifying gets live
  - [apps/web/components/run-list.tsx:127](../../../../apps/web/components/run-list.tsx#L127): Exported StateLine, which the monitor doesn't use; STOP_TEXT at 80 is private
  - [apps/web/components/workflows-panel.tsx:17](../../../../apps/web/components/workflows-panel.tsx#L17): STATUS_TEXT imported from the run-list component file
  - [apps/web/components/expert-editor.tsx:17](../../../../apps/web/components/expert-editor.tsx#L17): AVAILABILITY and repair imported from the 853-line tool-catalog.tsx
- **Evidence:** workflow-monitor.tsx defines its own TERMINAL and its own tone(), both citing Decision 0021 R3–R4. run-list.tsx has a tone() for the same run states that differs: there, waiting_input gets the attention tone and verifying the live tone, while the monitor gives neither a tone. The monitor prints the run status as raw enum text ('waiting approval'). workflows-panel.tsx shows the same status as 'Waiting for approval', through STATUS_TEXT imported from run-list.tsx. run-list.tsx also has STOP_TEXT and an exported StateLine that the monitor doesn't use.
- **Why it matters:** The same canonical run state looks different on three screens, and the monitor misses R3's attention tone for requested input. The next change to a state or its wording has to be found in several components. Imports from one component file to another couple screens that otherwise share nothing.
- **Recommendation:** Move run-state presentation into lib/ plus one small component keyed by the canonical states: labels, stop reasons, tone, the terminal set and StateLine. Use StateLine for the monitor's run line, and keep node-instance states in their own map. Move AVAILABILITY and repair to lib/ as well.
- **Rule check:** AGENTS.md: canonical states from the Option B contract. DH-06: 'do not invent a second state enum for the UI'. Decision 0021 R3–R4. These are presentation maps only; the DTO's run_status: string is unchanged.
- **Verification:** revised. Both tone() maps and both TERMINAL sets confirmed, and Decision 0021 R3 gives requested input the attention tone the monitor omits; StateLine is at run-list.tsx:127, not 126. The AVAILABILITY move is the same as web-tools-approvals WTAP-07.

```text
lib/run-states.ts         RUN_STATE_TEXT, STOP_TEXT, runStateTone(), TERMINAL_RUN_STATES, isTerminal()
components/run-state.tsx  <StateLine status /> moved from run-list.tsx, used by the monitor's run line
lib/workflow-states.ts    INSTANCE_STATE_TEXT and instanceTone() for node instances
lib/tool-availability.ts  AVAILABILITY and repair() moved from tool-catalog.tsx
```

### <a id="wbld-14"></a>WBLD-14: Budget choices and money and time formatting are copied across screens and have diverged

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 16
- **Where:**
  - [apps/web/components/workflow-editor.tsx:150-157](../../../../apps/web/components/workflow-editor.tsx#L150): Budget-step loop, the same as goal-composer.tsx:197-206
  - [apps/web/components/workflow-editor.tsx:118](../../../../apps/web/components/workflow-editor.tsx#L118): 1_000_000 literal instead of DEFAULT_BUDGET_MICRO_USD (run-disclosure.tsx:20)
  - [apps/web/components/workflow-editor.tsx:641-679](../../../../apps/web/components/workflow-editor.tsx#L641): 'Nothing left today' next to an enabled Run this version; the budget is omitted at 380-382
  - [apps/web/components/goal-composer.tsx:593](../../../../apps/web/components/goal-composer.tsx#L593): The composer disables Run when no budget is left (207)
  - [apps/web/components/workflows-panel.tsx:34-70](../../../../apps/web/components/workflows-panel.tsx#L34): relative(), dollars(), spend() and duration()
  - [apps/web/components/experts-panel.tsx:310-315](../../../../apps/web/components/experts-panel.tsx#L310): lastRun(): a second relative-time wording, calling Date.now() during render
  - [apps/web/components/run-panel.tsx:34-42](../../../../apps/web/components/run-panel.tsx#L34): Exported wallTime(), which duration() re-implements without hours
  - [apps/web/components/workflow-editor.tsx:658](../../../../apps/web/components/workflow-editor.tsx#L658): Inline US$ formatting, one of 7 copies
- **Evidence:** The same helpers are written several times across the repository, counted with grep:
  - 2 budget-step loops;
  - 7 copies of `US$${(micro / 1_000_000).toFixed(2)}`;
  - 4 relative-time implementations: experts-panel, workflows-panel, approvals-panel.tsx:88 and home-activity.tsx:24;
  - 2 duration formatters: workflows-panel and run-panel's exported wallTime.

  That is 16 counting the literal default, 7 of them in scope. With nothing left today, the composer disables Run. The workflow editor keeps Run enabled and sends no budget, so the server applies DEFAULT_LIMIT_MICRO_USD without require_budget (api/workflow_routes.py:350-361). duration() prints 2 hours as '120m 00s', where wallTime prints '2h 00m'.
- **Why it matters:** WF-05's 'same budget choices as a goal run' is two copies that already behave differently, and nothing records whether the editor's behaviour is meant for versions without agent steps. The same timestamp reads '5 min ago' on an Expert card and '5 minutes ago' in the workflow list.
- **Recommendation:** Share lib/budget.ts and lib/format.ts between the screens. Write the rule for starting a run when nothing is left once, and take `now` from one hook instead of calling Date.now() during render.
- **Rule check:** PRD-Studio WF-05 and Decision 0022 D11. The server's require_budget remains the authority; the browser only stops duplicating its choices.
- **Verification:** confirmed. Recounted with grep: 2 budget loops, 7 US$ formatters (5 helpers, workflow-editor.tsx:658 and run-disclosure.tsx:97), 4 relative-time helpers and 2 duration helpers; the execution route skips require_budget when no budget is sent.

```ts
// lib/budget.ts
export function budgetChoices(range: BudgetRange | null): number[];  // guards step > 0
export function canStart(range: BudgetRange | null, usesModel: boolean): boolean;  // one written rule for both screens
// lib/format.ts
export function formatMicroUsd(micro: number): string;
export function formatRelative(iso: string, now: number): string;
export function formatDuration(seconds: number | null): string;  // today run-panel.tsx wallTime
```

### <a id="wbld-15"></a>WBLD-15: Risky editor logic has no unit tests, and no test covers repeated submits or failed secondary reads

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 16
- **Where:**
  - [apps/web/components/workflow-editor.tsx:51-104](../../../../apps/web/components/workflow-editor.tsx#L51): parsed, draftGraph, tidy and withLabel live in a .tsx client module
  - [apps/web/components/expert-editor.tsx:36-68](../../../../apps/web/components/expert-editor.tsx#L36): grantable, members, expansion and draftOf
  - [apps/web/components/workflows-panel.tsx:36-74](../../../../apps/web/components/workflows-panel.tsx#L36): relative, dollars, spend, duration and stateText
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): web_unit_tests runs node --test on two lib test files only
  - [apps/web/tests/browser/experts.spec.ts:528](../../../../apps/web/tests/browser/experts.spec.ts#L528): Cards and filters are tested only with a loaded catalog
  - [apps/web/tests/browser/slice-workflows.spec.ts:132-158](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L132): The only failure-injection test in this area (monitor reconnect)
- **Evidence:** Sixteen top-level helpers in this area live inside 'use client' .tsx modules, counted by reading: 4 in workflow-editor, 4 in expert-editor, 5 in workflows-panel, 2 in experts-panel and 1 in workflow-monitor. All but lastRun, which reads the clock, are pure. The unit runner (node --test, on an explicit file list in scripts/verify.py) can't import those, and apps/web/tests/unit holds only lib tests. experts.spec.ts, workflows.spec.ts and workflow-list.spec.ts contain no page.route calls, so no failed read is ever simulated. No spec double-clicks a submit. The label IR rule is covered only end to end (workflows.spec.ts:177-213).
- **Why it matters:** The two highest-risk gaps in this review, duplicate submits and silent read failures, have no regression test. Each change to the IR or grant helpers needs a full browser run to check.
- **Recommendation:** Move the helpers to lib/*.ts with node --test units, and make web_unit_tests run every tests/unit file. Add Playwright cases for:
  - a double-click on Run this version, which should start one execution;
  - a failed /api/v1/tools, which should show no Read only classification;
  - a failed preview, which should show an unavailable state.
- **Rule check:** DH-06: unit tests for relevant pure and client behaviour, and Playwright for key flows. The repository runs unit tests with node --test rather than Vitest, and the recommendation keeps that runner.
- **Verification:** revised. Recounted 16 top-level helpers in five client modules (15 pure; lastRun reads the clock), not 13; the three specs have no page.route or double-click, and web_unit_tests lists two files.

```text
apps/web/lib/workflow-ir.ts   + tests/unit/workflow-ir.test.ts   (a label adds v2, removing the last label returns to v1, tidy keeps the hash)
apps/web/lib/expert-grants.ts + tests/unit/expert-grants.test.ts (named tools first, group tools appended once)
apps/web/lib/format.ts        + tests/unit/format.test.ts        (estimated versus reported, minutes and hours)
scripts/verify.py web_unit_tests: run tests/unit/*.test.ts, not a fixed list
Playwright: double-click Run this version -> one execution; /api/v1/tools 500 -> no Read only count
```

### <a id="wbld-16"></a>WBLD-16: Refusal codes are mapped with nested ternaries, inconsistently across sibling actions

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [apps/web/components/expert-editor.tsx:172-184](../../../../apps/web/components/expert-editor.tsx#L172): Five-level ternary
  - [apps/web/components/workflow-editor.tsx:224-228](../../../../apps/web/components/workflow-editor.tsx#L224): publish(): no case for workflow_version_conflict
  - [apps/web/components/workflow-editor.tsx:261-269](../../../../apps/web/components/workflow-editor.tsx#L261): refused(): maps workflow_version_conflict for the draft actions
  - [apps/web/components/workflow-editor.tsx:186-191](../../../../apps/web/components/workflow-editor.tsx#L186): validate(): any failure reads 'That has the wrong shape for a workflow.'
  - [apps/web/components/workflow-editor.tsx:586-590](../../../../apps/web/components/workflow-editor.tsx#L586): Refusals announced with role=status
  - [apps/web/components/experts-panel.tsx:277](../../../../apps/web/components/experts-panel.tsx#L277): Refusals announced with role=alert, as in workflows-panel.tsx:420
  - [apps/web/components/expert-editor.tsx:246-265](../../../../apps/web/components/expert-editor.tsx#L246): Purpose and instructions lack the contract's maxLength
- **Evidence:** expert-editor.tsx:172-184 is a five-level ternary on failure?.code, which accounts for most of save()'s complexity of 19. Five more chains repeat the shape: experts-panel.tsx:122-128, workflows-panel.tsx:144-150 and workflow-editor.tsx:224-228, 262-268 and 354-357. Several handlers disagree:
  - publish() has no case for workflow_version_conflict, which refused() maps, so the same conflict reads differently from the two publish buttons;
  - validate() reports any failure, including a lost reply or a 401, as a shape error;
  - refusals use role=status in the editors and role=alert in the lists.

  The purpose and instructions fields omit the contract's maxLength of 1000 and 20000, so overlong text ends in the generic invalid_request message.
- **Why it matters:** Messages for the same refusal drift between buttons. Transport failures are blamed on the user's input. Assistive technology announces some refusals politely and others assertively.
- **Recommendation:** Give each screen one Record<code, text> map and a messageFor(refusal, map, fallback) helper built on readRefusal. Tell a lost reply apart from a refusal. Use role=alert for refusals and role=status for confirmations. Set maxLength from ExpertConfig.
- **Rule check:** DH-06: 'centralize error handling… expose safe typed errors'.
- **Verification:** confirmed. Six ternary chains confirmed; publish() falls back to the API's own message for workflow_version_conflict while refused() has its own text, and the generated ExpertConfig sets maxLength 1000 and 20000.

```ts
const SAVE_REFUSALS: Record<string, string> = {
  owner_required: 'Only the workspace owner can save a revision.',
  expert_version_conflict: 'Someone saved a newer version. Reload to see it.',
};
const text = refusal === null ? LOST_REPLY : (SAVE_REFUSALS[refusal.code] ?? refusal.message);
// refusals: role='alert'; confirmations: role='status'
```

### <a id="wbld-17"></a>WBLD-17: Pixel type sizes, a hard-coded radius and repeated heading and avatar class strings bypass the token scale

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 51
- **Where:**
  - [apps/web/components/expert-editor.tsx:229](../../../../apps/web/components/expert-editor.tsx#L229): rounded-[10px] initial tile, equal to rounded-lg
  - [apps/web/components/experts-panel.tsx:344](../../../../apps/web/components/experts-panel.tsx#L344): The same tile copied; also session-panel.tsx:115
  - [apps/web/components/expert-editor.tsx:235](../../../../apps/web/components/expert-editor.tsx#L235): Serif 22px heading string; 7 copies repo-wide, one already drifted (tool-catalog.tsx:621)
  - [apps/web/components/workflow-editor.tsx:426](../../../../apps/web/components/workflow-editor.tsx#L426): The same heading string, again at 598
  - [apps/web/components/workflow-editor.tsx:739](../../../../apps/web/components/workflow-editor.tsx#L739): SECTION copies SectionLabel's classes and is declared after use
  - [apps/web/components/expert-editor.tsx:475](../../../../apps/web/components/expert-editor.tsx#L475): LEGEND: the same classes plus mb-2, declared after use
  - [apps/web/components/workflows-panel.tsx:76](../../../../apps/web/components/workflows-panel.tsx#L76): TH with text-[12.5px]; 22 uses of text-[12.5px] in scope
  - [apps/web/app/globals.css:72](../../../../apps/web/app/globals.css#L72): --radius-lg: var(--radius)
- **Evidence:** The in-scope files use 47 arbitrary text sizes in 7 distinct values (212 in 39 files repo-wide) and two hard-coded radii, both rounded-[10px] on the initial tile (five repo-wide, with session-panel.tsx:115 and appearance-control.tsx:56 and 78). Three of the 47 sizes belong to copies of the serif display heading string, which has seven copies repo-wide. The initial tile repeats `grid … shrink-0 place-items-center rounded-[10px] border font-serif`, at size-10 in the editor and size-9 on the card. SECTION and LEGEND re-type the classes of SectionLabel (ui/page-header.tsx:47-69), because SectionLabel can't render a label or a legend. The total counts the 47 sizes, the 2 radii and the 2 re-typed constants, counted with grep for text-[Npx] and rounded-[.
- **Why it matters:** DS-03 asks for the radius scale mapped to the base token and for consistent typography. Today a type or radius change means editing class strings across files, and copies have already started to drift.
- **Recommendation:** Name the sizes in use as tokens in globals.css @theme. Add an InitialTile primitive next to IconTile. Add a display variant of CardTitle. Let SectionLabel render a label or a legend.
- **Rule check:** PRD-Design-System.md DS-03: 'Map the radius scale to the canonical base… Keep layout spacing and typography consistent.' The new size tokens add to the Luma tokens without changing them (DS-01).
- **Verification:** revised. Text-size counts confirmed with grep; hard-coded radii are 2 in scope and 5 repo-wide, not 1 and 3, so the evidence and the total (51) were corrected. --radius is 0.625rem, so rounded-[10px] equals rounded-lg.

```text
/* globals.css @theme: named steps for the sizes in use */
--text-meta: 12.5px; --text-row: 13.5px; --text-title: 15px; --text-display: 22px;
// components/ui/card.tsx
export function InitialTile({ name }: { name: string }) // rounded-lg, replaces three copies
// components/ui/page-header.tsx: SectionLabel as='label' | 'legend', or export SECTION_LABEL
```

### <a id="wbld-18"></a>WBLD-18: A comment sits above the wrong declarations, and the body drains have no explanation

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/experts-panel.tsx:288](../../../../apps/web/components/experts-panel.tsx#L288): Describes ExpertCard but sits above `type Filter`, 29 lines before the card
  - [apps/web/components/workflows-panel.tsx:479](../../../../apps/web/components/workflows-panel.tsx#L479): `else await reply.text();` with no reason given
  - [apps/web/components/workflows-panel.tsx:497](../../../../apps/web/components/workflows-panel.tsx#L497): The same drain, also unexplained
  - [apps/web/components/run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53): Where the reason is written
- **Evidence:** experts-panel.tsx:288 reads 'One Expert as a card: what its latest version says, from the list already loaded.', but it sits above type Filter, FILTERS, PROFILE_NAMES and APPROVAL_NOUN; ExpertCard starts at 317. workflows-panel.tsx ends two refused reads with `else await reply.text();` and no comment. run-disclosure.tsx:53, model-policy-panel.tsx:142 and home-activity.tsx:73 explain the same line: 'Read, or an unread refusal holds its connection open for as long as the page lives.'
- **Why it matters:** A reader can't tell why the drains exist, so they look removable, and the other nine reads in this area skip them. The card comment describes the wrong declarations.
- **Recommendation:** Move the card comment to line 317. State the drain rule once where it is enforced, in the shared read hook, instead of at each call. Until then, copy the one-line reason to both drains.
- **Rule check:** DH-06: 'Explain nonobvious invariants in code'. The citations of stories and decisions stay.
- **Verification:** confirmed. The comment at 288 describes ExpertCard (317); the two drains lack the reason that run-disclosure.tsx:53, model-policy-panel.tsx:142 and home-activity.tsx:73 give.

### <a id="wbld-19"></a>WBLD-19: `draft` names two different things in the workflow editor, and one action has two names

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/workflow-editor.tsx:111](../../../../apps/web/components/workflow-editor.tsx#L111): `draft`: the textarea text, which publish() sends
  - [apps/web/components/workflow-editor.tsx:139](../../../../apps/web/components/workflow-editor.tsx#L139): `loaded.draft`: the saved WF-02 draft that saveDraft, publishDraft and discardDraft act on
  - [apps/web/components/workflows-panel.tsx:172](../../../../apps/web/components/workflows-panel.tsx#L172): `shown`: the filtered rows
  - [apps/web/components/workflows-panel.tsx:442](../../../../apps/web/components/workflows-panel.tsx#L442): `shown`: the previewed version, in the same file
  - [apps/web/components/experts-panel.tsx:84](../../../../apps/web/components/experts-panel.tsx#L84): `startRun` posts a session, behind the 'Start run' button (372)
  - [apps/web/components/expert-editor.tsx:187](../../../../apps/web/components/expert-editor.tsx#L187): The same POST is `startSession`, behind 'Start a session' (440)
- **Evidence:** In workflow-editor.tsx, the local `draft` holds what the textarea shows, while `workflow.draft` (139, 437, 531) is the stored draft. The handler names (saveDraft, publishDraft, discardDraft) refer to the stored one, and publish() sends the local one. workflows-panel.tsx reuses `shown` for two meanings. The session start has two function names and two button labels. `routed` (experts-panel.tsx:28) holds the coordinator picks.
- **Why it matters:** The `draft` collision sits exactly where the two publish paths are easiest to confuse. One action with two function names suggests two different behaviours.
- **Recommendation:** Rename the text to graphText; keep workflow.draft, which is the contract's name. Rename `shown` to visibleWorkflows and previewVersion, `routed` to coordinatorPicks, and both session handlers to startDirectSession. Keep the two button labels: PRD-Studio EX-01 names the card's 'Start run', which experts.spec.ts:578 checks.
- **Rule check:** DH-06: readable names. EX-01 fixes the card's 'Start run' label, so only identifiers change.
- **Verification:** revised. Names and sites confirmed; the original advice to use one button label would change EX-01's 'Start run' on the card, so the recommendation now renames identifiers only.

### <a id="wbld-20"></a>WBLD-20: A URL parameter, role bindings and block versions are narrowed without checks

- **Severity** low · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 4
- **Where:**
  - [apps/web/components/workflows-panel.tsx:87](../../../../apps/web/components/workflows-panel.tsx#L87): params.get('tab') asserted as Tab | null
  - [apps/web/components/workflows-panel.tsx:167-171](../../../../apps/web/components/workflows-panel.tsx#L167): An unknown tab falls through to the Drafts rule
  - [apps/web/components/expert-editor.tsx:116-119](../../../../apps/web/components/expert-editor.tsx#L116): role_bindings cast to Record<string, string>
  - [apps/web/components/experts-panel.tsx:331-332](../../../../apps/web/components/experts-panel.tsx#L331): The same cast
  - [apps/web/components/workflow-monitor.tsx:175](../../../../apps/web/components/workflow-monitor.tsx#L175): String(view.block_versions[node_id]) renders 'undefined' for a missing node
  - [packages/api-client/src/runtime.ts:64-79](../../../../packages/api-client/src/runtime.ts#L64): checkObject ignores schema-valued additionalProperties
  - [scripts/generate_contracts.py:46-47](../../../../scripts/generate_contracts.py#L46): An object without properties becomes Record<string, unknown>
- **Evidence:** Four values are narrowed without a check:
  - `const tab = (params.get('tab') as Tab | null) ?? 'all';` accepts any string. inTab then sends an unknown value to the Drafts branch, and no tab has aria-current.
  - Two sites cast role_bindings to Record<string, string>. The generator emits Record<string, unknown> for an object without properties, and runtime.ts never checks map values, so the ModelProfileId values are neither typed nor validated.
  - The monitor stringifies an unknown map lookup, so a missing key prints 'undefined'.
- **Why it matters:** Each narrowing hides a shape the code then trusts. A hand-edited URL shows the wrong rows, and a binding that isn't a string would be rendered as text or sent back on save.
- **Recommendation:** Add isTab() and fall back to 'all'. Read the executor through a typed accessor that calls parseModelProfileId inside try/catch. Render a dash for a missing block version. Fix the root cause in the generator and runtime.ts: emit Record<string, ModelProfileId> and check map values. Never edit generated.ts by hand.
- **Rule check:** DH-06: 'No blanket type assertions'. Ground rule: generated files are regenerated, not edited, so the type gap is fixed in scripts/generate_contracts.py and runtime.ts.
- **Verification:** revised. All four narrowings confirmed, with the generator rule at generate_contracts.py:46-47 and checkObject at runtime.ts:64-79; risk raised to medium because the root-cause fix changes generated types and runtime validation for every client.

## Rejected during verification

No finding was rejected. All 20 were kept, 10 of them revised.

## Not covered

This was a static reading; no browser session was run. The duplicate-submit, silent-failure and polling-load scenarios are traced from the code, not observed. The claim that unread refusals hold connections open is the repository's own documented rationale (run-disclosure.tsx:53), not something measured here.

Several sources were read only in part:
- Browser specs (experts.spec.ts, workflows.spec.ts, workflow-list.spec.ts, slice-workflows.spec.ts): checked by test titles and grep for route injection, ir_version and double clicks.
- Server files (api/workflow_routes.py, api/errors.py, application/workflows.py, application/experts.py, domain/workflows.py, domain/models.py): read only at the cited lines, to confirm behaviour the web code depends on.
- Sibling web components (run-list, run-disclosure, continue-run, goal-composer, tool-uses, run-workspace, model-policy-panel, ui/card, ui/page-header), the relevant PRD-Development-Harness.md sections (DH-03, DH-06) and the metrics file: read only in part.

Not checked: whether workflow node progress emits run events, which decides whether the monitor can follow the run event stream as run-workspace.tsx does.

Left to the web-architecture lens: whether screens should load first-paint data in Server Components or read it in the browser through the BFF, which is a cross-cutting decision.

ESLint was not re-run. The in-scope rule hits come from .checks/reviews/review-2026-11-12-09-52-30/eslint.json.
