# Web: tool catalog and approvals

The tool catalog and approvals screens are careful where it matters most. Every read goes through the generated runtime parsers. A decision binds the argument hash shown on screen, and the list is re-read from the API instead of being updated optimistically. Request text is rendered as React text nodes only. The tool guide is a native modal that closes on the backdrop and Escape and returns focus. Playwright covers decisions, replay, tabs, J/K, the two-press shortcut, both request views, the modal's close paths and axe in both themes. The cost sits in two oversized client modules. approvals-panel.tsx has 773 lines, including a 308-line panel with nine useState hooks and a key handler with complexity 27. tool-catalog.tsx has 853 lines and eight components, plus pure text helpers that the Expert editor imports. Reading them in full surfaced defects where their responsibilities meet. A held ⌘↵ or Ctrl+↵ satisfies AP-04's second press, and the arm is not tied to a request. Decisions have no in-flight state, and the button and keyboard paths apply different truncation rules. The list fetch exists twice, because the project's react-hooks/set-state-in-effect rule forbids the obvious reuse, and the unguarded copy can put waiting requests under Decided. Each screen turns every load failure into one message with no retry, and that message is sometimes wrong. The recommended split fixes these without moving any decision out of the API: pure text, field and shortcut rules move to lib with node:test, one reloadable useLoaded hook serves both screens, decisions and shortcuts get their own hooks, and each detail surface gets its own file. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict TypeScript flags and the project ESLint pass and colors are semantic, but DH-06's rules on duplicate submits, deliberate states and assertions are each missed, and the tool dialog departs from DS-03's dialog surface. |
| modules | 3 | Dependencies run correctly from the generated client into the components, but pure text and a generic data hook live inside client component files, and the Expert editor imports from the catalog panel. |
| size | 2 | These are two of the five largest web files (773 and 853 lines), with functions of 308, 249, 245 and 174 lines and a key handler with complexity 27. |
| functions | 3 | The small pure formatters at the top of approvals-panel are well separated, but onKey, ToolCatalogPanel and ToolDetail each mix state, URL handling and rendering. |
| structure | 3 | The thin server pages and the flat, feature-prefixed components folder match the rest of apps/web, but four and eight components per file hide the area's shape. |
| approach | 3 | The server stays authoritative, with no optimistic updates and a native modal, but fetching is hand-rolled twice, nine useStates carry an implicit state machine, and the two-press guard accepts key repeat. |
| comments | 4 | Most comments explain why and trace to AP, TL, TG and Decision IDs; a few invariants are unstated, and two comments no longer match the code. |
| types | 3 | Generated types and runtime parsers are used at every read, but the label tables ignore the contract's unions and one error body is cast. |
| errors | 2 | Each screen collapses every failure into one state, with copy that can be wrong ('sign in', 'not in the catalog'), no retry and the cause discarded. |
| tests | 3 | Playwright covers the main flows and accessibility thoroughly, but the pure logic has no unit tests, and nothing covers held keys, races or failure states. |
| maintainability | 3 | Readable, accessible and well traced, but the two oversized modules concentrate this area's defects; the split plus shared hooks would make it a model. |

## Strengths

- **Runtime contract parsing on every read.** approvals-panel.tsx:143 and 168 use parseApprovalList. tool-catalog.tsx:192, 582-585 and 780-783 parse through useLoaded with parseToolCatalog, parseToolVersions and parseToolGrants. These are backed by parseWith in packages/api-client/src/runtime.ts:142-149, which rejects unknown enum values and missing fields. Sources: [components/approvals-panel.tsx:143](../../../../apps/web/components/approvals-panel.tsx#L143), [components/tool-catalog.tsx:192](../../../../apps/web/components/tool-catalog.tsx#L192), [components/tool-catalog.tsx:582](../../../../apps/web/components/tool-catalog.tsx#L582), [packages/api-client/src/runtime.ts:142](../../../../packages/api-client/src/runtime.ts#L142).
- **A typed, abortable load hook worth promoting.** tool-catalog.tsx:156-181 useLoaded returns a discriminated union (loading, unavailable, ready). It aborts on cleanup, ignores stale replies and turns parse errors into a visible state. It is the best fetch shape in the area, and 24 hand-rolled 'let active = true' effects elsewhere in apps/web/components could share it. Sources: [components/tool-catalog.tsx:156](../../../../apps/web/components/tool-catalog.tsx#L156).
- **Server-authoritative decisions with no optimistic state.** approvals-panel.tsx:195-206 posts through csrfFetch with an Idempotency-Key and binds the decision to approval.argument_hash. Lines 24-33 turn the API's refusal codes into plain words, and line 223 re-reads the list after the reply instead of editing it locally, as DH-06 asks ('browser state is a view of durable state'). Sources: [components/approvals-panel.tsx:195](../../../../apps/web/components/approvals-panel.tsx#L195), [components/approvals-panel.tsx:24](../../../../apps/web/components/approvals-panel.tsx#L24), [components/approvals-panel.tsx:223](../../../../apps/web/components/approvals-panel.tsx#L223).
- **Untrusted request content rendered safely and faithfully.** approvals-panel.tsx:700-742 Markdown and inline build only React text nodes, and neither file uses dangerouslySetInnerHTML. At 686-698, parsedFields withholds the Fields view when JSON would reorder integer-like keys, which keeps AP-03's 'never reorders' promise. Sources: [components/approvals-panel.tsx:700](../../../../apps/web/components/approvals-panel.tsx#L700), [components/approvals-panel.tsx:686](../../../../apps/web/components/approvals-panel.tsx#L686).
- **Accessibility engineered in.** tool-catalog.tsx:439-481 opens a native modal dialog with showModal, a form method='dialog' Close button and backdrop detection, and 422-429 returns focus. approvals-panel.tsx:391-395 uses a roving-tabindex list with aria-current, 362-368 a polite live announcement for the two-press shortcut, and 744-773 sr-only colons in dt/dd pairs. Axe checks assert this in tools.spec.ts:246-263 (both themes) and approvals.spec.ts:399-402. Sources: [components/tool-catalog.tsx:439](../../../../apps/web/components/tool-catalog.tsx#L439), [components/approvals-panel.tsx:391](../../../../apps/web/components/approvals-panel.tsx#L391), [components/approvals-panel.tsx:362](../../../../apps/web/components/approvals-panel.tsx#L362), [tests/browser/tools.spec.ts:246](../../../../apps/web/tests/browser/tools.spec.ts#L246), [tests/browser/approvals.spec.ts:399](../../../../apps/web/tests/browser/approvals.spec.ts#L399).
- **Schema rendering driven by server-flattened fields.** tool-catalog.tsx:483-579 renders the API's FieldDescriptor rows (path, type, required, constraints, public) as a captioned table with column and row scopes inside a focusable, named scroll region, instead of walking JSON Schema in the browser. Lines 739-751 keep the raw schema behind a disclosure, and 831-853 copies exactly the shown version's input schema (TL-03). Sources: [components/tool-catalog.tsx:483](../../../../apps/web/components/tool-catalog.tsx#L483), [components/tool-catalog.tsx:739](../../../../apps/web/components/tool-catalog.tsx#L739), [components/tool-catalog.tsx:831](../../../../apps/web/components/tool-catalog.tsx#L831).
- **Exhaustive table typing where it is used.** tool-catalog.tsx:117-121 declares APPROVAL_TEXT as Record<ToolDescriptor['approval'], string>, so tsc fails if the contract adds an approval mode. This is the pattern to spread to the other label tables. Sources: [components/tool-catalog.tsx:117](../../../../apps/web/components/tool-catalog.tsx#L117).
- **Comments that explain why and trace to requirements.** approvals-panel.tsx:115-116 (AP-01 to AP-04), 232 (arrows only inside the list), 686 (integer-like keys) and 700 (text nodes only). tool-catalog.tsx:43 (state in words), 116 (Decision 0026 C9), 437-438 (G2/G3 native dialog), 458 (backdrop click) and 501 (axe scrollable-region rule). Sources: [components/approvals-panel.tsx:115](../../../../apps/web/components/approvals-panel.tsx#L115), [components/approvals-panel.tsx:686](../../../../apps/web/components/approvals-panel.tsx#L686), [components/tool-catalog.tsx:43](../../../../apps/web/components/tool-catalog.tsx#L43), [components/tool-catalog.tsx:437](../../../../apps/web/components/tool-catalog.tsx#L437).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WTAP-01](#wtap-01) | high | size | approvals-panel.tsx packs data loading, decisions, a shortcut state machine and two large views into one module | M | medium |
| [WTAP-02](#wtap-02) | high | approach | The two-press shortcut accepts a held key, Alt chords, and an arm that is not tied to a request | S | medium |
| [WTAP-03](#wtap-03) | medium | standards | Decisions have no in-flight state, and the button and keyboard paths follow different rules | S | medium |
| [WTAP-04](#wtap-04) | medium | duplication | The approval list fetch exists twice, and the unguarded copy can show waiting requests under Decided | S | medium |
| [WTAP-05](#wtap-05) | medium | errors | Every load failure becomes one message with no retry, and some messages are wrong | M | medium |
| [WTAP-07](#wtap-07) | medium | modules | Pure tool text is exported from a client component and imported by the Expert editor | S | low |
| [WTAP-08](#wtap-08) | medium | size | tool-catalog.tsx has a 249-line panel and a 174-line detail among eight components | M | low |
| [WTAP-09](#wtap-09) | medium | tests | Pure logic has no unit tests, and the riskiest interactions are untested | M | low |
| [WTAP-06](#wtap-06) | low | types | Label tables are typed Record<string, …> although the contract gives exact unions | S | low |
| [WTAP-10](#wtap-10) | low | duplication | Relative time is formatted four ways, and the approvals countdown freezes | S | low |
| [WTAP-11](#wtap-11) | low | duplication | The segmented 'tabs with counts' control is copied in three screens | S | low |
| [WTAP-12](#wtap-12) | low | standards | The tool modal uses page colors where DS-03 maps dialogs to popover, and each dialog hand-rolls its chrome | S | low |
| [WTAP-13](#wtap-13) | low | standards | The modal's accessible name and focus return rest on fixed IDs and a DOM query | S | low |
| [WTAP-15](#wtap-15) | low | approach | The search box is uncontrolled while the other filters follow the URL | S | low |
| [WTAP-16](#wtap-16) | low | naming | Names that hide what they return, or collide | S | low |
| [WTAP-17](#wtap-17) | low | naming | Typography is set with 44 one-off pixel sizes | S | low |
| [WTAP-18](#wtap-18) | low | types | The decision error body is cast instead of parsed | S | low |
| [WTAP-19](#wtap-19) | low | comments | Invariants the code relies on are unstated, and two comments no longer match the code | S | low |

### <a id="wtap-01"></a>WTAP-01: approvals-panel.tsx packs data loading, decisions, a shortcut state machine and two large views into one module

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/approvals-panel.tsx:117-434](../../../../apps/web/components/approvals-panel.tsx#L117): ApprovalsPanel: 308 lines, complexity 11; fetches, decides, handles keys and renders tabs and list
  - [apps/web/components/approvals-panel.tsx:123-134](../../../../apps/web/components/approvals-panel.tsx#L123): nine useState hooks carrying one implicit state machine
  - [apps/web/components/approvals-panel.tsx:228-298](../../../../apps/web/components/approvals-panel.tsx#L228): keyboard machine and disarm timer inside the panel
  - [apps/web/components/approvals-panel.tsx:436-684](../../../../apps/web/components/approvals-panel.tsx#L436): ApprovalDetail: 245 lines, complexity 13: facts, exact request, diffs, alert, decision bar
  - [apps/web/components/approvals-panel.tsx:47-113](../../../../apps/web/components/approvals-panel.tsx#L47): five pure formatters that node:test cannot import from a 'use client' TSX module
  - [apps/web/components/approvals-panel.tsx:686-742](../../../../apps/web/components/approvals-panel.tsx#L686): Fields parser and a self-contained markdown renderer
  - [apps/web/components/approvals-panel.tsx:746-773](../../../../apps/web/components/approvals-panel.tsx#L746): Fact component
- **Evidence:** Reading confirms the ESLint leads. ApprovalsPanel declares nine useState hooks (123-134), fetches the list (136-187), sends decisions (192-226), runs the two-press shortcut machine (228-298) and renders the tabs, messages and list (317-433). ApprovalDetail adds 245 more lines. The file also holds five formatters, parsedFields, Markdown and inline, and Fact: 4 components and 735 counted lines (max-lines rule).
- **Why it matters:** Every change to the approval gate edits one 300-line closure. The defects found in this area sit exactly where these responsibilities meet: a held key confirms a decision, a reload can land under the wrong tab, and the button and keyboard paths apply different guards. None of the pure logic can reach the node:test suite.
- **Recommendation:** Split by responsibility without changing behavior, keeping every data-* hook and visible string so approvals.spec.ts passes unchanged. First, move the formatters, parsedFields and the shortcut rule to lib, with node:test cases. Then extract a reloadable useLoaded, useApprovalDecision and useApprovalShortcuts. Finally, move ApprovalDetail and its parts, and the markdown renderer, to their own files. ApprovalsPanel ends up holding tab and selection state plus composition.
- **Rule check:** DH-06 'small cohesive modules'. Every decision stays in the API, so no business transition moves into Next.js, and AP-04's two-press confirmation and the hash binding are kept.
- **Verification:** confirmed. Nine useState hooks, the 308- and 245-line functions, four components and 735 counted lines confirmed against the code and eslint.json.

```text
lib/approval-text.ts      requesterText, scopeText, policyText, decidedText, OUTCOME, DECISION_MESSAGES
lib/approval-fields.ts    parsedFields (AP-03 no-reorder rule)
lib/approval-shortcut.ts  chord(event), press(arm, input): pure two-press machine
lib/use-loaded.ts         useLoaded(path, parse) -> { state, reload }
components/approvals-panel.tsx  ApprovalsPanel: tab + selection + composition
  useApprovalDecision(reload)  { pending, message, decide }
  useApprovalShortcuts(...)    keydown via useEffectEvent, subscribed once
  ApprovalTabs, ApprovalList   segmented control with counts; roving-tabindex list
components/approval-detail.tsx ApprovalFacts, ExactRequest(RequestFields | RequestJson), ReviewDiffs, DecisionBar
components/markdown-text.tsx   MarkdownText, looksLikeMarkdown (text nodes only)
```

### <a id="wtap-02"></a>WTAP-02: The two-press shortcut accepts a held key, Alt chords, and an arm that is not tied to a request

- **Severity** high · **Dimension** approach · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/approvals-panel.tsx:229-283](../../../../apps/web/components/approvals-panel.tsx#L229): onKey, complexity 27: navigation, focus moves and decision arming in one function; line 231 routes any meta, ctrl or alt chord to decisions
  - [apps/web/components/approvals-panel.tsx:269-279](../../../../apps/web/components/approvals-panel.tsx#L269): the second-press check never reads event.repeat
  - [apps/web/components/approvals-panel.tsx:129-132](../../../../apps/web/components/approvals-panel.tsx#L129): arm is { decision, until } with no approval id
  - [apps/web/components/approvals-panel.tsx:146-150](../../../../apps/web/components/approvals-panel.tsx#L146): list reload changes the selection without clearing the arm (again at 172)
  - [apps/web/components/approvals-panel.tsx:427](../../../../apps/web/components/approvals-panel.tsx#L427): button path decides without clearing the arm
  - [apps/web/lib/shortcuts.ts:32](../../../../apps/web/lib/shortcuts.ts#L32): documents ⌘ or Ctrl, not Alt
  - [apps/web/components/search-palette.tsx:52-53](../../../../apps/web/components/search-palette.tsx#L52): peer handler requires meta or ctrl and excludes alt
  - [apps/web/tests/browser/approvals.spec.ts:407-455](../../../../apps/web/tests/browser/approvals.spec.ts#L407): presses each chord discretely; no held key or Alt case
- **Evidence:**

  ```tsx
  if (
    armed !== null &&
    armed.decision === decision &&
    Date.now() <= armed.until
  ) {
    setArmed(null);
    setAnnouncement("");
    void decide(current, decision);
  ```

  Nothing reads event.repeat (grep finds no use in apps/web/components or lib). Line 231 sends any chord with meta, ctrl or alt to the decision branch, so ⌥↵ and ⌥⌫ act too. The arm holds no request id. Example: arm ⌘↵ on request A, click Reject on A, and once the list reloads (selection moves to B) a single ⌘↵ within 2 s approves B.
- **Why it matters:** AP-04 requires a second press within 2 s. Holding ⌘↵ or Ctrl+↵ past the OS key-repeat delay fires a repeated keydown that counts as the second press, so one long press decides. The stale-arm path decides a request other than the one announced. The server still binds the decision to the hash shown, but the screen's confirmation step is bypassed.
- **Recommendation:** Make the rule a pure function in lib/approval-shortcut.ts. Inputs: current arm, decision, approval id, now, repeat and truncated. Outputs: next arm, decision to send or none, and announcement. Cover repeat, Alt, approval change, expiry and truncation with node:test. Call it from useApprovalShortcuts, which subscribes once through React 19's useEffectEvent; react 19.3.1 is installed, and a stdin probe of this shape passes the project ESLint. The hook ignores event.repeat, requires (metaKey || ctrlKey) && !altKey, stores the approval id in the arm and clears the arm when the selection or pending state changes. Keep J/K/arrow navigation as its own small function. Add a browser case: hold Meta, call keyboard.down('Enter') twice (Playwright sends the second with repeat set), and expect no decision.
- **Rule check:** PRD-Studio AP-04 (PRD-Studio.md:99), and ground rule 2 against weakening an approval: this change tightens the confirmation. typing() still gates every shortcut, and the server's hash binding is untouched.
- **Verification:** confirmed. No use of event.repeat exists in apps/web; line 231 routes Alt chords to decisions and the arm carries no id; a fresh ESLint stdin probe of the useEffectEvent hook passes. The held-key path is reasoned from the code, not observed.

```ts
// lib/approval-shortcut.ts (pure, node:test)
type Decision = "approve" | "reject";
export type Arm = { decision: Decision; approvalId: string; until: number } | null;
export function chord(e: KeyLike): Decision | "next" | "previous" | null; // repeat or Alt -> null
export function press(arm: Arm, p: { decision: Decision; approvalId: string; now: number; truncated: boolean }):
  { arm: Arm; send: Decision | null; announce: string };
// components: useApprovalShortcuts({ approvals, selectedId, enabled, onSelect, onDecide }) -> { announcement }
```

### <a id="wtap-03"></a>WTAP-03: Decisions have no in-flight state, and the button and keyboard paths follow different rules

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/approvals-panel.tsx:192-226](../../../../apps/web/components/approvals-panel.tsx#L192): decide: no pending flag; new Idempotency-Key per call (201); lost reply reported as a failure (220)
  - [apps/web/components/approvals-panel.tsx:664-675](../../../../apps/web/components/approvals-panel.tsx#L664): Approve and Reject never disabled; Approve stays live on truncated requests
  - [apps/web/components/approvals-panel.tsx:265-268](../../../../apps/web/components/approvals-panel.tsx#L265): keyboard path refuses truncated approvals before sending
  - [apps/web/components/run-controls.tsx:60](../../../../apps/web/components/run-controls.tsx#L60): peer: busy state disables submit (142, 188)
  - [apps/web/components/continue-run.tsx:47-48](../../../../apps/web/components/continue-run.tsx#L47): peer: lost reply or 5xx is an unknown outcome, not a failure
  - [services/agent/src/autobots/application/approvals.py:278-281](../../../../services/agent/src/autobots/application/approvals.py#L278): server replays a same-decision repeat
- **Evidence:** decide() sets no pending flag. Approve and Reject stay enabled across the CSRF fetch, the POST and the reload, and each click mints a new Idempotency-Key (201). The keyboard path refuses to approve a truncated request before sending (265-268). The Approve button sends it and waits for the server's approval_too_large refusal. A null reply (lost connection) shows 'That decision couldn't be saved.' (220), although the API may have committed.
- **Why it matters:** DH-06 asks for duplicate submits to be disabled, with server idempotency as the correctness mechanism; only the server half exists here. Double clicks send duplicate POSTs and race two reloads. The truncation rule has two homes with different behavior. A lost reply asserts a failure that the reloaded list may contradict. No optimistic update is made, which is correct and should stay.
- **Recommendation:** Extract useApprovalDecision(reload) returning { pending, message, decide }. Set pending before the request and clear it in finally; disable both buttons while pending, and have the shortcut hook ignore presses while pending. Give the truncation rule one home: either derive canApprove once from the server's arguments_truncated flag and use it for both the button and the shortcut, or drop the client check from both and rely on the refusal. For reply === null or status >= 500, say the outcome is not known yet and let the reloaded list show it, as continue-run.tsx does.
- **Rule check:** DH-06 'Disable duplicate submits with server idempotency as the correctness mechanism' and 'avoid duplicated business rules'. The API's hash binding and refusal codes stay authoritative, and no state transition moves into Next.js.
- **Verification:** confirmed. The buttons at 664-675 never disable, the keyboard refuses truncated approvals at 265-268 while the button sends, and the server replays a same-decision repeat at approvals.py:278-281.

### <a id="wtap-04"></a>WTAP-04: The approval list fetch exists twice, and the unguarded copy can show waiting requests under Decided

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [apps/web/components/approvals-panel.tsx:136-156](../../../../apps/web/components/approvals-panel.tsx#L136): load(): no stale-reply guard; parse errors escape
  - [apps/web/components/approvals-panel.tsx:158-187](../../../../apps/web/components/approvals-panel.tsx#L158): effect copy: guarded, but a separate implementation
  - [apps/web/components/approvals-panel.tsx:170-171](../../../../apps/web/components/approvals-panel.tsx#L170): setCounts called twice
  - [apps/web/components/approvals-panel.tsx:223](../../../../apps/web/components/approvals-panel.tsx#L223): decide reloads the tab captured at click time
  - [apps/web/components/approvals-panel.tsx:337](../../../../apps/web/components/approvals-panel.tsx#L337): comment promises a stale list from the other tab is never shown
  - [apps/web/components/operations-panel.tsx:165-200](../../../../apps/web/components/operations-panel.tsx#L165): same load plus inline-effect pair in another area
- **Evidence:**

  ```tsx
  const parsed = parseApprovalList(await reply.json());
  setList(parsed);
  setCounts(parsed.counts);
  setCounts(parsed.counts);
  ```

  load() and the effect repeat the same URL choice, parse and selection fallback. load() has no active flag or abort and parses outside any catch, so a ContractError rejects decide() unhandled, while the effect turns the same error into the failed state. The copy exists because the project's react-hooks/set-state-in-effect rule (eslint-plugin-react-hooks 7.1.1) rejects an effect that calls load(); a stdin ESLint probe confirmed the error.
- **Why it matters:** Switching to Decided while a decision is in flight lets load('waiting') finish after the Decided fetch and replace the list. That contradicts the invariant stated at line 337, and the waiting requests then render with Decided labels. The two copies have already drifted (duplicate setCounts, different error handling).
- **Recommendation:** Keep one guarded fetch path and reload through it. A shared useLoaded(path, parse) keeps a reload counter in the effect's dependencies, aborts on cleanup and returns { state, reload }; decide() calls reload() instead of fetching. A stdin probe of this shape passes the project ESLint. Make the selection fallback (keep the current id if still listed, else the first) a pure function called from one place.
- **Rule check:** The project ESLint react-hooks/set-state-in-effect rule still holds, since setState stays inside the async callbacks. DH-06 'Browser state is a view of durable state'.
- **Verification:** confirmed. A fresh ESLint stdin probe reproduces react-hooks/set-state-in-effect for an effect that calls load(), and a reload-counter hook passes; the duplicate setCounts is at 170-171 and operations-panel.tsx:165-200 has the same pair.

```ts
// lib/use-loaded.ts
export type Load<T> = { kind: "loading" } | { kind: "failed"; reason: FailReason } | { kind: "ready"; value: T };
export function useLoaded<T>(path: string, parse: (v: unknown) => T): { state: Load<T>; reload: () => void };
//   effect deps [path, parse, version]; AbortController; setState only inside the async callbacks
// approvals: const { state, reload } = useLoaded(approvalsPath(tab), parseApprovalList);
```

### <a id="wtap-05"></a>WTAP-05: Every load failure becomes one message with no retry, and some messages are wrong

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [apps/web/components/approvals-panel.tsx:300-309](../../../../apps/web/components/approvals-panel.tsx#L300): 'Sign in, then try again.' for any failure; tabs hidden; no retry
  - [apps/web/components/approvals-panel.tsx:179-183](../../../../apps/web/components/approvals-panel.tsx#L179): status and error discarded into a boolean
  - [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156): useLoaded keeps only { kind: 'unavailable' } for status, network and ContractError
  - [apps/web/components/tool-catalog.tsx:202-209](../../../../apps/web/components/tool-catalog.tsx#L202): 'Check that the local service is running' also for 401 and 403
  - [apps/web/components/tool-catalog.tsx:587-593](../../../../apps/web/components/tool-catalog.tsx#L587): 'That tool isn't in the catalog.' also for 401, 403 and 503
  - [apps/web/components/tool-catalog.tsx:603](../../../../apps/web/components/tool-catalog.tsx#L603): a tool with no versions renders nothing
  - [apps/web/lib/bff.ts:53-57](../../../../apps/web/lib/bff.ts#L53): BFF already returns 403 and 401 (and 503 at 120)
  - [apps/web/components/operations-panel.tsx:171](../../../../apps/web/components/operations-panel.tsx#L171): peer screen words 403 separately
- **Evidence:** Neither file reads the reply status. The BFF distinguishes refusals (403), not_signed_in (401) and service_unavailable (503), and operations-panel.tsx and run-inspector.tsx word them separately. Here, Approvals says 'Sign in, then try again.' for every failure and replaces its tabs. The catalog blames the local service for auth failures. The detail page says a tool is not in the catalog when the session expired or the API is down. None of the four states offers a retry.
- **Why it matters:** DH-06 requires loading, empty, denied, unavailable and retryable states to be represented deliberately. A stopped API tells a signed-in owner to sign in, an expired session says the tool doesn't exist, and contract drift looks like an outage with no trace. If the reload fails right after a successful decision, the sign-in message replaces the confirmation, and only a full page reload recovers.
- **Recommendation:** Give the shared load hook a typed failure reason: signed_out for 401, denied for 403, not_found for 404, unavailable for 5xx or network errors, and invalid for a ContractError. Render one shared failure component with reason-specific copy and a Retry button bound to reload(). Keep the approvals tabs visible on failure. Log a ContractError's path to the console in development, since it carries no secret. Render an explicit empty state for a tool with no versions.
- **Rule check:** DH-06 'Represent loading, empty, denied, unavailable and retryable states deliberately' and 'preserve causes in private logs and expose safe typed errors'. The user-facing copy reveals no server detail.
- **Verification:** confirmed. Neither file reads reply.status; the BFF returns 401, 403 and 503 with distinct codes (bff.ts:53-57, 120); a failed reload after a decision leaves only the sign-in text, since the tabs are not rendered.

### <a id="wtap-07"></a>WTAP-07: Pure tool text is exported from a client component and imported by the Expert editor

- **Severity** medium · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/tool-catalog.tsx:67-114](../../../../apps/web/components/tool-catalog.tsx#L67): AVAILABILITY, keySource and repair exported from a 'use client' panel module
  - [apps/web/components/expert-editor.tsx:17](../../../../apps/web/components/expert-editor.tsx#L17): imports AVAILABILITY and repair from @/components/tool-catalog
  - [apps/web/components/expert-editor.tsx:330](../../../../apps/web/components/expert-editor.tsx#L330): calls repair
  - [apps/web/components/tool-catalog.tsx:386-389](../../../../apps/web/components/tool-catalog.tsx#L386): row re-derives the key source inline instead of calling keySource
  - [apps/web/components/tool-catalog.tsx:80](../../../../apps/web/components/tool-catalog.tsx#L80): keySource exported with no outside caller (used only at 710)
- **Evidence:** tool-catalog.tsx exports its label table and two text functions from a module that also imports next/navigation and lucide icons. expert-editor.tsx:17 reads 'import { AVAILABILITY, repair } from "@/components/tool-catalog";'. repair() holds five branches of TS-03 repair wording and has no unit test.
- **Why it matters:** A web-build screen now depends on the web-tools panel file for text rules, so restructuring the catalog can break the Expert editor. The PK-05 and TS-03 wording can only be checked through Playwright on a disposable stack.
- **Recommendation:** Move the label tables, keySource, repair (renamed repairText) and the row summary text to lib/tool-text.ts, with no React and no 'use client'. Import it from both components, unexport anything with no outside caller, and add node:test cases for each repair branch.
- **Rule check:** DH-06 'explicit ownership, narrow interfaces'. lib/ already holds pure helpers tested with node:test (apps/web/tests/unit).
- **Verification:** confirmed. grep finds expert-editor.tsx as the only importer of these exports and no outside caller of keySource; the same move appears in web-build WBLD-13.

### <a id="wtap-08"></a>WTAP-08: tool-catalog.tsx has a 249-line panel and a 174-line detail among eight components

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/tool-catalog.tsx:183-435](../../../../apps/web/components/tool-catalog.tsx#L183): ToolCatalogPanel: URL state, filtering, toolbar, grouped list and dialog wiring
  - [apps/web/components/tool-catalog.tsx:194-239](../../../../apps/web/components/tool-catalog.tsx#L194): three URLSearchParams helpers; choose redeclares query at 198
  - [apps/web/components/tool-catalog.tsx:318-348](../../../../apps/web/components/tool-catalog.tsx#L318): the same group filter computed three times (319, 321, 347-348)
  - [apps/web/components/tool-catalog.tsx:349-412](../../../../apps/web/components/tool-catalog.tsx#L349): row callback: 64 lines, complexity 12
  - [apps/web/components/tool-catalog.tsx:581-754](../../../../apps/web/components/tool-catalog.tsx#L581): ToolDetail: 174 lines, complexity 18
  - [apps/web/components/tool-catalog.tsx:483-579](../../../../apps/web/components/tool-catalog.tsx#L483): FieldTable: 96 lines; takes the whole tool and filters by direction itself (490)
  - [apps/web/components/tool-catalog.tsx:516-532](../../../../apps/web/components/tool-catalog.tsx#L516): five identical header cells; constraint text formatted inline at 559-567
  - [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156): generic data hook kept inside the file
- **Evidence:** Reading confirms the leads: the group callback runs 97 lines and the row callback 64, and there are eight components in 853 lines. The panel interleaves URL state, filtering (218-227), the toolbar and the grouped list. It filters shown by group three times instead of reusing inGroup. The TS-01 row wording is assembled inline (372-390). FieldTable receives the whole ToolDescriptor but needs only its fields and title, repeats <th scope='col' className='pr-3 pb-2 font-medium'> five times and builds constraint text inline as `${key} ${JSON.stringify(value)}`. Its table semantics are good and should stay: caption, column and row scopes, and a focusable, named scroll region (501-507).
- **Why it matters:** Adding a filter, a row fact or a detail field means editing a 250-line function that mixes URL, filter and markup logic. The row wording and the constraint wording cannot be tested on their own, and changing a field column means editing several places.
- **Recommendation:** Split following the repository's flat feature-prefix convention (as the run-*.tsx files do): move pure parts to lib first, then give each surface its own file. Group once with a Map and pass each group's tools down. Give FieldTable a { title, caption, fields } signature with a COLUMNS constant and a FieldRow, let ToolDetail split fields by direction once, and move constraintText to lib/tool-text.ts with tests. Behavior and data-* hooks, data-fields and data-field-path included, stay as they are, so tools.spec.ts covers the move.
- **Rule check:** DH-06 'small cohesive modules'. DH-03 prescribes no component folders, so the split keeps the flat layout.
- **Verification:** revised. Spans and complexities match eslint.json; WTAP-14 (FieldTable's whole-tool parameter, repeated header cells and inline constraint text) was merged here, because this split already moves FieldTable and constraintText.

```text
lib/tool-text.ts     label tables by union, keySource, repairText, toolSummary(tool): string[], constraintText
lib/tool-filters.ts  readFilters(params), withParam(params, name, value | null), filterTools, groupTools
lib/use-loaded.ts    useLoaded(path, parse) -> { state, reload }
components/tool-catalog.tsx  ToolCatalogPanel (~60 lines): useCatalogFilters + useLoaded + layout
  CatalogToolbar, ToolGroupSection, ToolRow
components/tool-dialog.tsx   ToolDialog (native dialog, focus return)
components/tool-detail.tsx   ToolDetail -> ToolHeader, ToolGuide, ToolFacts, ToolIdentity, GrantableTo, RawSchema
components/tool-fields.tsx   FieldTable({ title, caption, fields }) with COLUMNS, FieldRow({ field })
components/tool-grants.tsx   Grants, CopySchema
```

### <a id="wtap-09"></a>WTAP-09: Pure logic has no unit tests, and the riskiest interactions are untested

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/approvals-panel.tsx:47-113](../../../../apps/web/components/approvals-panel.tsx#L47): requesterText, scopeText, policyText, relative, decidedText
  - [apps/web/components/approvals-panel.tsx:687-742](../../../../apps/web/components/approvals-panel.tsx#L687): parsedFields (AP-03 order rule), Markdown and inline
  - [apps/web/components/tool-catalog.tsx:80-114](../../../../apps/web/components/tool-catalog.tsx#L80): keySource and repair, shared with expert-editor
  - [apps/web/tests/browser/approvals.spec.ts:407-455](../../../../apps/web/tests/browser/approvals.spec.ts#L407): no held chord, Alt chord, tab switch mid-decision or failure state
  - [apps/web/tests/browser/tools.spec.ts:223-239](../../../../apps/web/tests/browser/tools.spec.ts#L223): close paths covered; filtered deep link not covered
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): web_unit_tests lists files one by one and already omits schema-value.test.ts
  - [apps/web/tests/unit/schema-value.test.ts:1](../../../../apps/web/tests/unit/schema-value.test.ts#L1): the node:test pattern against lib/ to follow
- **Evidence:** apps/web/tests/unit holds three node:test files, all for lib modules. None covers the ten pure functions here. The browser suites are strong: decisions and replay, tabs, J/K, two-press, typing guard, Fields/JSON with axe, modal close paths, focus return and Copy schema. But they run only in the db profile, and none holds a chord, switches tabs during a decision, returns a 503 or deep-links a filtered-out tool.
- **Why it matters:** The rules most likely to regress here are checked only by slow end-to-end runs: the two-press machine, AP-03's no-reorder rule, text-only markdown and the repair wording. The held-key and stale-reload defects in this area passed those runs.
- **Recommendation:** Once the pure code has moved to lib, add node:test files for approval-shortcut (repeat, Alt, approval change, expiry, truncation), approval-text and relative-time boundaries, parsedFields (integer-like keys, arrays, truncation), markdown inline splitting and the tool-text repair branches. Register each file in the web_unit_tests step, or switch that step to a glob, which would also pick up schema-value.test.ts. Add browser cases for a held chord, a tab switch during a decision and a BFF 503.
- **Rule check:** DH-06 names Vitest and React Testing Library for pure and client behavior. The repository's current runner is node:test against lib, so this adds no dependency; adopting Vitest would be a separate tooling decision.
- **Verification:** confirmed. Three unit files exist and web_unit_tests runs two of them, and nothing else runs schema-value.test.ts; approvals.spec.ts and tools.spec.ts contain no route injection or held key.

### <a id="wtap-06"></a>WTAP-06: Label tables are typed Record<string, …> although the contract gives exact unions

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/components/tool-catalog.tsx:45-74](../../../../apps/web/components/tool-catalog.tsx#L45): PROVIDERS, CLASSES, COSTS, AVAILABILITY and AVAILABILITY_FILTERS typed by string
  - [apps/web/components/tool-catalog.tsx:124-138](../../../../apps/web/components/tool-catalog.tsx#L124): GROUP_ICONS keyed by string; '?? Wrench' at 322 and 607
  - [apps/web/components/tool-catalog.tsx:117-121](../../../../apps/web/components/tool-catalog.tsx#L117): APPROVAL_TEXT already uses the exhaustive form
  - [apps/web/components/tool-catalog.tsx:377-385](../../../../apps/web/components/tool-catalog.tsx#L377): three raw-value fallbacks in one row
  - [apps/web/components/tool-catalog.tsx:705-707](../../../../apps/web/components/tool-catalog.tsx#L705): two more in the detail
  - [apps/web/components/expert-editor.tsx:376](../../../../apps/web/components/expert-editor.tsx#L376): same fallback in the Expert editor
  - [apps/web/components/approvals-panel.tsx:24-33](../../../../apps/web/components/approvals-panel.tsx#L24): MESSAGES by string forces '?? ""' at 266
  - [packages/api-client/src/generated.ts:8896-8919](../../../../packages/api-client/src/generated.ts#L8896): ToolDescriptor declares each of these fields as a union
- **Evidence:** ToolDescriptor declares provider, operation_class, cost_class, availability and group as literal unions, and the generated runtime schema rejects any other value. Yet six tables in tool-catalog.tsx are keyed by string. Counted by grep, there are 12 lookups (11 here and 1 in expert-editor.tsx), and 11 of them carry a '?? tool.x' or '?? Wrench' fallback that cannot run after parsing.
- **Why it matters:** When the Pydantic contract gains a provider, class, cost class or group, tsc stays green and the screen shows the raw snake_case id; nothing points at the table to update.
- **Recommendation:** Type each table by its union, for example const PROVIDERS: Record<ToolDescriptor['provider'], string> and const AVAILABILITY_FILTERS: readonly ToolDescriptor['availability'][]. Then delete the fallbacks, so tsc fails at the table when the contract adds a value. Declare MESSAGES as const satisfies Record<string, string>. ApprovalView.status and operation_class are plain strings in the contract (generated.ts:7457, 7467). Narrowing them to Literals in the Pydantic DTO and regenerating would let OUTCOME become exhaustive too.
- **Rule check:** Contracts rule: Pydantic owns the contract, generated TypeScript consumes it, and unknown enums fail at runtime; this adds the compile-time half. No generated file is edited by hand.
- **Verification:** revised. Recounted 12 lookups, 11 with a fallback that parsing makes unreachable; downgraded from medium to low because nothing is wrong today and the fallbacks degrade gracefully to the raw id.

### <a id="wtap-10"></a>WTAP-10: Relative time is formatted four ways, and the approvals countdown freezes

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/approvals-panel.tsx:88-98](../../../../apps/web/components/approvals-panel.tsx#L88): hand-rolled 'in 5 min' / '5 min ago'
  - [apps/web/components/home-activity.tsx:24](../../../../apps/web/components/home-activity.tsx#L24): Intl.RelativeTimeFormat copy
  - [apps/web/components/workflows-panel.tsx:36](../../../../apps/web/components/workflows-panel.tsx#L36): identical Intl copy
  - [apps/web/components/experts-panel.tsx:310](../../../../apps/web/components/experts-panel.tsx#L310): 'min ago', 'h ago', then a date
  - [apps/web/components/approvals-panel.tsx:134](../../../../apps/web/components/approvals-panel.tsx#L134): now changes only on reload (155, 178)
- **Evidence:** There are four helpers, counted by grep for relative-time functions. Approvals reads 'in 5 min' where Home reads 'in 5 minutes'. In approvals, Math.round turns an expiry 20 s in the past into -0, which `minutes >= 0` reads as 'in 0 min'. now only advances when the list reloads, so 'Expires in 3 min' stays on screen as time passes.
- **Why it matters:** The same kind of time reads differently on Home and in Approvals, and a request can show a future expiry after it has expired. The next fix will land in one copy only.
- **Recommendation:** Add lib/relative-time.ts based on Intl.RelativeTimeFormat, as two copies already are, with node:test boundary cases. Add a small useNow(intervalMs) hook for screens that show countdowns, then replace the four helpers.
- **Rule check:** none
- **Verification:** revised. Four helpers confirmed, and Math.round(-1/3) is -0, which passes minutes >= 0; experts-panel's lastRun starts at line 310, not 309. web-build WBLD-14 counts the same helpers.

### <a id="wtap-11"></a>WTAP-11: The segmented 'tabs with counts' control is copied in three screens

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/approvals-panel.tsx:319-352](../../../../apps/web/components/approvals-panel.tsx#L319): Waiting/Decided toggle
  - [apps/web/components/run-list.tsx:236-251](../../../../apps/web/components/run-list.tsx#L236): same classes
  - [apps/web/components/experts-panel.tsx:186-198](../../../../apps/web/components/experts-panel.tsx#L186): same classes
  - [apps/web/components/approvals-panel.tsx:516-537](../../../../apps/web/components/approvals-panel.tsx#L516): Fields/JSON: a fourth, slightly different variant
- **Evidence:** Three screens repeat verbatim the button class 'text-foreground/80 inline-flex h-7 items-center gap-1.5 rounded-md border border-transparent px-3 text-[13px]' and the selected state 'bg-background text-foreground border-border font-medium dark:bg-accent': approvals-panel.tsx:344, run-list.tsx:243 and experts-panel.tsx:192 (grep for the class string).
- **Why it matters:** A focus or token change under DS-03 or DS-04 has to be made three or four times, and the copies already differ in data attributes and container markup.
- **Recommendation:** Add components/ui/segmented-control.tsx. It takes items (id, label, optional count), a value, onChange and an aria-label, renders aria-pressed buttons with the shared classes and passes data-* attributes through. Adopt it in the three screens and for the Fields/JSON toggle.
- **Rule check:** DS-03 shared semantic tokens across the UI. The primitive keeps the aria-pressed semantics and the data-tab hooks the browser tests use.
- **Verification:** confirmed. grep finds both class strings at exactly the three cited lines (approvals-panel.tsx:344 and 346, run-list.tsx:243 and 245, experts-panel.tsx:192 and 194).

### <a id="wtap-12"></a>WTAP-12: The tool modal uses page colors where DS-03 maps dialogs to popover, and each dialog hand-rolls its chrome

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/tool-catalog.tsx:461](../../../../apps/web/components/tool-catalog.tsx#L461): bg-background text-foreground … backdrop:bg-black/60
  - [apps/web/components/search-palette.tsx:132](../../../../apps/web/components/search-palette.tsx#L132): bg-popover text-popover-foreground … backdrop:bg-black/50
  - [apps/web/components/about-services.tsx:22](../../../../apps/web/components/about-services.tsx#L22): bg-popover text-popover-foreground … backdrop:bg-black/50
  - [PRD-Design-System.md:65](../../../../PRD-Design-System.md#L65): menus, selects and dialogs use popover and popover-foreground
- **Evidence:** The tool modal is the only dialog on the page surface, with a darker backdrop. No comment explains the difference. The cards inside use bg-card, which has the same value as popover in both themes (docs/design/luma.css:4-7 and 39-42), so a popover-surfaced dialog would hide their edges; that may be the reason.
- **Why it matters:** The modal's surface and backdrop differ from the other two dialogs and from DS-03, and a fourth dialog will copy one of the three variants.
- **Recommendation:** Add a shared native-dialog primitive, components/ui/dialog.tsx: showModal on mount, backdrop click, a form method='dialog' close, the popover surface and one backdrop class. Use it for all three dialogs. If the tool modal keeps the page surface so its cards stand out, say so in a comment and record it as a documented design-system exception rather than a per-screen override, then check both themes as DS-05 requires.
- **Rule check:** DS-03 (dialogs use popover and popover-foreground; no per-screen theme overrides). The primitive keeps Decision 0026 G3's native dialog and the browser's focus trap.
- **Verification:** revised. Surfaces and backdrops confirmed at the three dialogs; card and popover share one value in both themes, not only in dark mode, so the evidence was corrected.

### <a id="wtap-13"></a>WTAP-13: The modal's accessible name and focus return rest on fixed IDs and a DOM query

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/tool-catalog.tsx:455](../../../../apps/web/components/tool-catalog.tsx#L455): aria-labelledby='tool-heading'
  - [apps/web/components/tool-catalog.tsx:619-621](../../../../apps/web/components/tool-catalog.tsx#L619): the heading exists only after ToolDetail loads
  - [apps/web/components/tool-catalog.tsx:424-428](../../../../apps/web/components/tool-catalog.tsx#L424): focus return; the promised first-link fallback is not implemented
  - [apps/web/components/tool-catalog.tsx:492](../../../../apps/web/components/tool-catalog.tsx#L492): fixed input-heading and output-heading ids
  - [apps/web/components/tool-catalog.tsx:692](../../../../apps/web/components/tool-catalog.tsx#L692): fixed tool-version id
  - [apps/web/tests/browser/tools.spec.ts:223-239](../../../../apps/web/tests/browser/tools.spec.ts#L223): no filtered deep-link case
- **Evidence:**

  ```tsx
  // Back to the link that opened it, or the list's first link for a deep link.
  const opener = document.querySelector<HTMLAnchorElement>(
    `[data-tool="${CSS.escape(selected)}"] a`,
  );
  opener?.focus();
  ```

  While ToolDetail shows 'Loading this tool.' or its failure text, no element has id tool-heading, so the dialog has no accessible name. Fixed ids tie ToolDialog to ToolDetail's markup. For a deep link whose tool is filtered out (for example ?group=files&tool=calculate), the query finds nothing and focus falls to the document.
- **Why it matters:** Decision 0026 G3 says the dialog is labelled by the tool's title, but screen readers meet an unnamed dialog while it loads. TG-02's focus return fails silently in the filtered case, and the comment misleads the next maintainer.
- **Recommendation:** Create the ids with useId() in ToolDialog and pass the heading id down to ToolDetail, using aria-label={toolId} until the title loads. Implement a real fallback chain: the tool's link, else the first tool link, else the search field. Update the comment to match, and add a browser case for a filtered deep link.
- **Rule check:** PRD-Tool-Catalog TG-02 (focus returns to the tool's link), Decision 0026 G3 (labelled by the tool's title), and DS-04 labels and focus.
- **Verification:** confirmed. aria-labelledby targets a heading rendered only after the tool loads, and the first-link fallback promised at 424 is absent; the filtered deep-link case is reasoned, not observed.

### <a id="wtap-15"></a>WTAP-15: The search box is uncontrolled while the other filters follow the URL

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/tool-catalog.tsx:251-257](../../../../apps/web/components/tool-catalog.tsx#L251): defaultValue read once; router.replace on every keystroke
  - [apps/web/components/tool-catalog.tsx:263](../../../../apps/web/components/tool-catalog.tsx#L263): selects take value from the URL (also 278, 293)
  - [apps/web/components/sidebar-nav.tsx:45](../../../../apps/web/components/sidebar-nav.tsx#L45): Tools link to /tools
- **Evidence:** The input uses defaultValue={params.get('q') ?? ''}, which is read only on mount. Following the sidebar's Tools link from /tools?q=calc keeps the panel mounted, because no template.tsx remounts it. The filter clears, but the box still shows 'calc'.
- **Why it matters:** The visible query and the applied filter can disagree, breaking the promise that the URL holds the filter state.
- **Recommendation:** In a useCatalogFilters hook, keep a local draft for q that resets when the URL's q changes from outside, and write it back to the URL, debounced if needed. Add a browser case: type a query, follow the Tools link, and expect an empty box and the full list.
- **Rule check:** PRD-Tool-Catalog TS-01 (filters live in the URL) and PRD-Studio TL-01 (the text filter).
- **Verification:** confirmed. defaultValue is read once while the three selects follow the URL, and no template.tsx exists under apps/web/app; the same uncontrolled search exists in workflows-panel.tsx:212. Reasoned from the code, not observed.

### <a id="wtap-16"></a>WTAP-16: Names that hide what they return, or collide

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/tool-catalog.tsx:93](../../../../apps/web/components/tool-catalog.tsx#L93): repair() returns a sentence or null
  - [apps/web/components/expert-editor.tsx:330](../../../../apps/web/components/expert-editor.tsx#L330): const fix = repair(tool)
  - [apps/web/components/approvals-panel.tsx:746](../../../../apps/web/components/approvals-panel.tsx#L746): Fact { label, colon, data-* }
  - [apps/web/components/tool-catalog.tsx:756](../../../../apps/web/components/tool-catalog.tsx#L756): a different Fact { icon, term }
  - [apps/web/components/tool-catalog.tsx:198](../../../../apps/web/components/tool-catalog.tsx#L198): query redeclared inside choose(), shadowing line 190
  - [apps/web/components/approvals-panel.tsx:88](../../../../apps/web/components/approvals-panel.tsx#L88): relative
- **Evidence:** repair(tool) reads as an action but returns text, and it is exported to another screen. Two components named Fact both render a dt/dd pair, with different props. choose() shadows the filter query with the serialized params.
- **Why it matters:** Readers have to open each definition to know what it returns. Once the parts move to shared files, the two Fact components become an import clash.
- **Recommendation:** Rename while splitting: repairText, setFilter (with a local name that doesn't shadow) and relativeTime. For Fact, either create one ui/description-item.tsx with an optional icon, or name them ApprovalFact and ToolFact.
- **Rule check:** DH-06 'readable names'.
- **Verification:** confirmed. All four naming issues confirmed at the cited lines; the repairText rename is the same one WTAP-07 makes and should land with it.

### <a id="wtap-17"></a>WTAP-17: Typography is set with 44 one-off pixel sizes

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 44
- **Where:**
  - [apps/web/components/approvals-panel.tsx:344](../../../../apps/web/components/approvals-panel.tsx#L344): text-[13px]
  - [apps/web/components/approvals-panel.tsx:365](../../../../apps/web/components/approvals-panel.tsx#L365): text-[12.5px]
  - [apps/web/components/approvals-panel.tsx:452](../../../../apps/web/components/approvals-panel.tsx#L452): text-[22px]
  - [apps/web/components/tool-catalog.tsx:373](../../../../apps/web/components/tool-catalog.tsx#L373): text-[11.5px]
  - [apps/web/components/tool-catalog.tsx:621](../../../../apps/web/components/tool-catalog.tsx#L621): text-[22px] tracking-[-0.015em]
  - [apps/web/components/tool-catalog.tsx:682](../../../../apps/web/components/tool-catalog.tsx#L682): text-[12px]
  - [apps/web/app/globals.css:31](../../../../apps/web/app/globals.css#L31): @theme defines fonts but no text sizes
- **Evidence:** grep -oE 'text-\[[0-9.]+px\]' counts 21 in approvals-panel.tsx and 23 in tool-catalog.tsx, and 212 across apps/web components and app. They use seven sizes: 11.5, 12, 12.5, 13, 13.5, 15 and 22 px.
- **Why it matters:** The type scale exists only as repeated literals. DS-03 asks for consistent typography, and changing one step means editing hundreds of sites by hand.
- **Recommendation:** Define the steps once as --text-* tokens in the @theme block of globals.css, for example meta 12.5px, body-sm 13px, body 13.5px and title 22px, and use the generated utilities. Migrate files as they are split, and add a lint or grep ratchet against new text-[Npx] uses.
- **Rule check:** DS-03 'Keep layout spacing and typography consistent'. This adds size tokens only and leaves the Luma color tokens in docs/design/luma.css untouched.
- **Verification:** confirmed. grep counts 21 and 23 arbitrary sizes in the seven stated values, and 212 in 39 files repo-wide; the globals.css @theme block (31-77) defines no text sizes.

### <a id="wtap-18"></a>WTAP-18: The decision error body is cast instead of parsed

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/approvals-panel.tsx:216-221](../../../../apps/web/components/approvals-panel.tsx#L216): blanket assertion on an untrusted reply
  - [packages/api-client/src/generated.ts:7693-7700](../../../../packages/api-client/src/generated.ts#L7693): ErrorResponse and parseErrorResponse, unused in apps/web
- **Evidence:**

  ```tsx
  const failure = (await reply?.json().catch(() => null)) as {
    code?: string;
  } | null;
  setMessage(
    MESSAGES[failure?.code ?? ""] ?? "That decision couldn't be saved.",
  );
  ```

  grep finds the same `{ code?: string }` shape 15 times in 11 component files, this one included: 14 casts and one return type (workflow-editor.tsx:236).
- **Why it matters:** DH-06 forbids blanket assertions at untrusted boundaries. The fallback keeps this instance harmless today, but the cast hides any change to the error envelope and is copied across the app.
- **Recommendation:** Add lib/error-code.ts with errorCode(reply: Response | null): Promise<string | null>, which parses with parseErrorResponse inside try/catch. Use it here; the other copies can follow.
- **Rule check:** DH-06 'explicit response parsing at untrusted boundaries … No blanket type assertions'. It consumes the generated client without editing it.
- **Verification:** revised. The cast at 216-221 is confirmed; of the 15 grep hits for the shape, one is a return type rather than a cast, so the count is now stated as 14 casts plus one return type.

### <a id="wtap-19"></a>WTAP-19: Invariants the code relies on are unstated, and two comments no longer match the code

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [apps/web/components/tool-catalog.tsx:602](../../../../apps/web/components/tool-catalog.tsx#L602): versions.at(-1) taken as the newest
  - [services/agent/src/autobots/application/tool_catalog.py:261](../../../../services/agent/src/autobots/application/tool_catalog.py#L261): order comes from sorted(..., key=(tool_id, version))
  - [services/agent/src/autobots/contracts/tools.py:381](../../../../services/agent/src/autobots/contracts/tools.py#L381): ToolVersions.versions states no order
  - [apps/web/components/tool-catalog.tsx:74](../../../../apps/web/components/tool-catalog.tsx#L74): three of four availability values, reason not given
  - [apps/web/components/tool-catalog.tsx:179](../../../../apps/web/components/tool-catalog.tsx#L179): parse in effect deps: an inline parser would refetch on every render
  - [apps/web/components/approvals-panel.tsx:125](../../../../apps/web/components/approvals-panel.tsx#L125): counts kept apart from list without saying why
  - [apps/web/components/approvals-panel.tsx:473](../../../../apps/web/components/approvals-panel.tsx#L473): repeats the NOT_RECORDED text instead of the constant at 35
- **Evidence:** ToolDetail depends on the server's sort for 'newest', and nothing documents that order. AVAILABILITY_FILTERS omits not_qualified without a comment. useLoaded would loop on an inline parser, and nothing tells callers to pass a module-level function. The comments at approvals-panel.tsx:337 (no stale list) and tool-catalog.tsx:424 (first-link fallback) describe behavior the code does not have.
- **Why it matters:** A server-side reorder, a caller passing an inline parser, or a well-meant cleanup of the filter list would break the screen silently. Comments that disagree with the code mislead the next change.
- **Recommendation:** Pick the newest version by maximum version number, or document the order in the Pydantic field description so it reaches the generated contract. Add one-line why-comments for the filter list, the separate counts state and useLoaded's stable-parse requirement, or read parse through useEffectEvent. Use NOT_RECORDED at line 473, and fix the two comments together with the code changes they describe.
- **Rule check:** DH-06 'Explain nonobvious invariants in code; avoid comments that restate syntax'. A change to the Pydantic description reaches TypeScript only by regeneration.
- **Verification:** confirmed. versions.at(-1) relies on the sort at tool_catalog.py:261 and ToolVersions declares no order; line 473 repeats NOT_RECORDED's exact text.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| WTAP-14 | FieldTable takes a whole tool and repeats its column markup | merged into [WTAP-08](#wtap-08) |

## Not covered

This was a static review. Ground rules ruled out running the app, a browser suite or tsc. Three claims are therefore reasoned from the code and standard browser and App Router behavior, not observed: a held ⌘↵ or Ctrl+↵ counting as the second press, the tab switch during an in-flight decision, and the stale search box after following the sidebar link. ESLint ran only on stdin probes, writing no files, to check the recommended hook shapes (a reload counter, and useEffectEvent) against the project config, and to confirm that react-hooks/set-state-in-effect rejects an effect that calls load(). Several files were read only in part: PRD-Development-Harness.md (DH-03 to DH-06), metrics.md, the PRD-Studio and PRD-Tool-Catalog sections for AP, TL, TS and TG, and decision 0026. The peer files cited for comparison or counts were read only around those lines: run-controls, continue-run, operations-panel, run-inspector, search-palette, new-run, home-activity, workflows-panel, experts-panel, run-list, expert-editor, about-services, sidebar-nav, lib/bff.ts, the two browser specs, scripts/verify.py and the Python approval and tool routes. Requirement coverage was not judged. TS-01 lists side effects per tool row, but `side_effects` is rendered nowhere in apps/web (grep), which acceptance owners may want to check. No comparison with an earlier review was made.
