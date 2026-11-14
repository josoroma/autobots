# Web: run screens

The run screens handle the hard behavior with care. The workspace loads a snapshot, replays the events after a cursor, then opens the event stream from that cursor and deduplicates by sequence. Writes use server idempotency keys and version guards. Empty states are deliberate, colors come only from semantic tokens, accessible names are in place, and Playwright covers reconnects, duplicates, gaps, a cut stream and refusals. The cost sits in one place. RunWorkspaceView is a single function of 677 lines with complexity 39. It does the data loading (snapshot, event-page replay, a second refresh path driven by a counter, and the result download), runs the EventSource with its reconnect timer, deduplicates through a Map, merges live text, derives view state during render and draws about fifteen regions. 17 commits for 16 stories have edited it. Error handling is the weakest dimension. The workspace treats every failed read as temporary: it keeps polling a denied or missing run every second, and it never leaves 'Loading' on 403, 422, 5xx or a contract error. Three components also report a lost write reply as a failure and send any retry with a new idempotency key, so an owner can record one provider charge twice. Smaller costs recur across the area: status words and tones, money and time formats, the summarizer rule and the command senders are each written more than once; contract unions are widened to string; error and admission replies are cast although generated parsers exist; run-list and run-panel import each other; and pure logic sits in .tsx files that the node:test runner cannot load. The refactor can be done in steps. First move pure lib/runs modules out with unit tests. Then add load and stream hooks with an explicit state machine that keeps snapshots in cursor order. Then split the screens into section components. This is a static review. It is not runtime evidence. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict TypeScript flags and the project lint pass, and the pages are thin Server Components, but 10 type assertions at trust boundaries, no denied state, a client-only inspector and a fresh idempotency key per press fall short of DH-06. |
| modules | 3 | Pages compose views and views compose children clearly, but run-list and run-panel import each other and other screens import vocabulary, hooks and constants from screen modules. |
| size | 2 | 9 of the 13 files have functions over 60 lines. RunWorkspaceView (677 lines, complexity 39) is the largest function in the app, and 17 commits have edited it. |
| functions | 2 | The small pure helpers are good (withDelta, wallTime, brief), but each main component mixes fetching, state machines, product rules and markup, and multi-step flows are tracked with boolean flags. |
| structure | 3 | Files are where you would expect them, but the 10 run components sit flat among the 43 files in apps/web/components, and there is no lib/runs or feature folder to receive extracted code. |
| approach | 3 | The replay-then-stream design with server idempotency and version guards is sound. It is weakened by an unordered refetch on every event, no request aborts, counters used as effect triggers and client-side fetching for a static inspector. |
| comments | 4 | Comments explain why and cite decisions and stories throughout. A few mechanics, such as blanking the events before parsing a page and draining response bodies, have no stated reason. |
| types | 3 | Generated parsers validate every successful read, but error replies, the admission reply and the stream's cursor frame are cast, and contract unions are widened to string. |
| errors | 2 | The run page retries forever on 401, 403, 404 and 422 and hangs on contract errors, and lost write replies are reported as failures. ContinueRun shows the right pattern. |
| tests | 3 | Playwright covers reconnect, deduplication, gaps, stream cuts, controls and refusals, but none of the pure stream, merge or rule logic has a unit test. |
| maintainability | 3 | Well commented and covered by browser tests, but the workspace hotspot, duplicated vocabulary and formatting, and inconsistent error states make every run story costly. |

## Strengths

- **Snapshot, replay, then stream, with cursor-based reconnects and deduplication by sequence.** [apps/web/components/run-workspace.tsx:242-272](../../../../apps/web/components/run-workspace.tsx#L242) loads the snapshot, replays every page after the cursor and only then opens the EventSource from that cursor. Lines 175-181 deduplicate by sequence. Lines 235-239 close the browser's own retry, because it 'would resume from a stale URL'. [apps/web/tests/browser/run-workspace.spec.ts:83-151](../../../../apps/web/tests/browser/run-workspace.spec.ts#L83) and 252-265, and [stream-result.spec.ts:101-122](../../../../apps/web/tests/browser/stream-result.spec.ts#L101), exercise dropped connections, duplicates, gaps and a cut result stream in a real browser.
- **Generated runtime parsers on every successful read.** Each successful read is parsed: parseRunWorkspace ([run-workspace.tsx:194](../../../../apps/web/components/run-workspace.tsx#L194), [run-panel.tsx:68](../../../../apps/web/components/run-panel.tsx#L68)), parseRunList ([run-list.tsx:193](../../../../apps/web/components/run-list.tsx#L193)), parseRunInspector ([run-inspector.tsx:32](../../../../apps/web/components/run-inspector.tsx#L32)), parseToolUseList after the body is typed unknown ([tool-uses.tsx:127-133](../../../../apps/web/components/tool-uses.tsx#L127)), parseModelList and parseModelPolicyState ([run-disclosure.tsx:58-59](../../../../apps/web/components/run-disclosure.tsx#L58)), and parseRunEvent for each event ([run-workspace.tsx:146](../../../../apps/web/components/run-workspace.tsx#L146)). They check JSON against the generated schemas ([packages/api-client/src/runtime.ts:142-149](../../../../packages/api-client/src/runtime.ts#L142)).
- **ContinueRun treats an unknown outcome as unknown.** [apps/web/components/continue-run.tsx:20-21](../../../../apps/web/components/continue-run.tsx#L20) keeps the Idempotency-Key in a ref until the outcome is known, and line 39 reuses it. Lines 47-51 treat a lost reply or any 5xx as 'may have started'. Lines 68-69 reset the key only after a refusal that followed no unknown attempt. This is the pattern WRUN-03 asks the other writers to adopt.
- **A reusable, abortable hook for paginated reads.** useToolUses ([apps/web/components/tool-uses.tsx:102-147](../../../../apps/web/components/tool-uses.tsx#L102)) aborts a superseded read with an AbortController and says why (line 111), loops over cursor pages, and is reused by the workflow monitor ([apps/web/components/workflow-monitor.tsx:7](../../../../apps/web/components/workflow-monitor.tsx#L7)).
- **Deliberate empty, loading and failure states.** RunList separates loading, unavailable, an empty workspace (with a link to Home) and no filter matches ([run-list.tsx:282-314](../../../../apps/web/components/run-list.tsx#L282)). RunInspectorView separates loading, unavailable and error ([run-inspector.tsx:54-63](../../../../apps/web/components/run-inspector.tsx#L54)) and gives each section its own empty sentence. ToolsUsed separates failed, loading and empty ([tool-uses.tsx:262-274](../../../../apps/web/components/tool-uses.tsx#L262)). The workspace states an empty plan, no artifacts and no role map in words ([run-workspace.tsx:531](../../../../apps/web/components/run-workspace.tsx#L531), 643, 734-736).
- **Accessible states and semantic tokens throughout.** There are no color literals in scope, and every state color sits beside words: StateLine ([run-list.tsx:136-143](../../../../apps/web/components/run-list.tsx#L136)), and the header badge is aria-hidden because the status sentence says the same ([run-workspace.tsx:364-371](../../../../apps/web/components/run-workspace.tsx#L364)). Tool outcomes are announced through a polite live region ([tool-uses.tsx:257-261](../../../../apps/web/components/tool-uses.tsx#L257)), and the tool table has a caption and scoped headers (159-199). The filter buttons use aria-pressed ([run-list.tsx:239](../../../../apps/web/components/run-list.tsx#L239)), and Details sets aria-expanded and aria-controls (366-369).
- **Comments explain why and trace to decisions and stories.** Examples: [run-workspace.tsx:117-118](../../../../apps/web/components/run-workspace.tsx#L117) (US-15.24, SE-03), 125-126 (how live pieces join the text), 143 (Decision 0017 Q13) and 236; [run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53) (why bodies are drained), 86 (the server rule it mirrors) and 99-102; [run-panel.tsx:83](../../../../apps/web/components/run-panel.tsx#L83) (why the loaded version is sent); [run-controls.tsx:17](../../../../apps/web/components/run-controls.tsx#L17) (SP-010).
- **Key types derived from generated DTOs, and thin Server Component pages.** [run-panel.tsx:15](../../../../apps/web/components/run-panel.tsx#L15) derives Task from RunWorkspace, and lines 22-26 key MARKER_TEXT by Task['marker'], so a new marker value fails the type check. The pages await Next 16's async params and set metadata ([apps/web/app/runs/[id]/page.tsx:7-13](../../../../apps/web/app/runs/[id]/page.tsx#L7)). The list page wraps its useSearchParams consumer in Suspense ([apps/web/app/runs/page.tsx:10-17](../../../../apps/web/app/runs/page.tsx#L10)).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WRUN-01](#wrun-01) | high | size | RunWorkspaceView is a 677-line, complexity-39 component that every run story edits | L | medium |
| [WRUN-02](#wrun-02) | high | errors | The run page treats every failed read as temporary: denied runs are polled every second, and 403, 422, 5xx or contract errors never leave Loading | M | medium |
| [WRUN-03](#wrun-03) | high | errors | A lost write reply is reported as a failure, and the retry is sent with a new idempotency key | M | medium |
| [WRUN-06](#wrun-06) | high | types | Write replies and stream frames are cast instead of parsed, although generated parsers exist | S | low |
| [WRUN-04](#wrun-04) | medium | approach | Every stored event refetches the whole snapshot, and an older reply can overwrite a newer one | M | medium |
| [WRUN-05](#wrun-05) | medium | size | Eight more run components exceed 60 lines by combining fetching, state and the whole render tree | M | low |
| [WRUN-07](#wrun-07) | medium | types | Contract unions are widened to string, so a new status or outcome passes the type check and renders blank | S | low |
| [WRUN-08](#wrun-08) | medium | duplication | Run status words and tones are defined twice, and STATUS_TEXT names two different things | S | low |
| [WRUN-09](#wrun-09) | medium | modules | Run screens import shared pieces from each other, including a run-list and run-panel cycle | M | low |
| [WRUN-10](#wrun-10) | medium | duplication | Money and time formatting is reimplemented per file, with diverging rules | S | low |
| [WRUN-11](#wrun-11) | medium | duplication | The summarizer-differs rule is written three times, and the copies disagree | S | low |
| [WRUN-12](#wrun-12) | medium | approach | The UI re-derives SP-010's command table, and two components each have their own copy of the command code | M | medium |
| [WRUN-13](#wrun-13) | medium | errors | Several handlers catch only network errors, so a bad body leaves buttons disabled or a list stuck | S | low |
| [WRUN-14](#wrun-14) | medium | standards | The run inspector is a Client Component only so that it can fetch in an effect | M | medium |
| [WRUN-15](#wrun-15) | medium | tests | The stream, merge and rule logic has no unit tests, and living in .tsx files keeps it out of the unit runner | M | low |
| [WRUN-16](#wrun-16) | low | approach | Effects ignore late replies instead of aborting their requests | S | low |
| [WRUN-17](#wrun-17) | low | duplication | Section shells and page headers are built by hand in each screen | S | low |
| [WRUN-18](#wrun-18) | low | naming | Magic values, and different names for the same concepts | S | low |
| [WRUN-19](#wrun-19) | low | approach | Paths are built by hand, with a mix of &lt;a&gt; and Link and inconsistent encoding | S | low |
| [WRUN-20](#wrun-20) | low | comments | Some non-obvious mechanics give no reason, and one comment documents a copy | S | low |

### <a id="wrun-01"></a>WRUN-01: RunWorkspaceView is a 677-line, complexity-39 component that every run story edits

- **Severity** high · **Dimension** size · **Effort** L · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/run-workspace.tsx:152-844](../../../../apps/web/components/run-workspace.tsx#L152): RunWorkspaceView: 8 useState hooks, 3 effects and all rendering
  - [apps/web/components/run-workspace.tsx:168-280](../../../../apps/web/components/run-workspace.tsx#L168): Stream effect: snapshot load, replay loop, EventSource listeners, reconnect timer and deduplication
  - [apps/web/components/run-workspace.tsx:283-331](../../../../apps/web/components/run-workspace.tsx#L283): Derives the published result, downloads it, and runs a second snapshot fetch path
  - [apps/web/components/run-workspace.tsx:356-843](../../../../apps/web/components/run-workspace.tsx#L356): Render tree: header, 12 Section blocks, unknown outcomes, tools and parent link
  - [apps/web/components/run-workspace.tsx:36-150](../../../../apps/web/components/run-workspace.tsx#L36): Module-level status maps and pure helpers (describe, withDelta, known)
  - [apps/web/components/run-workspace.tsx:744-748](../../../../apps/web/components/run-workspace.tsx#L744): Product rule computed inline in JSX
  - [apps/web/components/run-workspace.tsx:795-826](../../../../apps/web/components/run-workspace.tsx#L795): Money arithmetic and outstanding totals computed inline in JSX
- **Evidence:** ESLint, with the review's extra rules, measures RunWorkspaceView at 677 lines with complexity 39 (metrics.md section 7), the largest and most complex function in apps/web. The one function has six jobs. (1) Data loading: refresh() reads /workspace (183-196), a loop replays /events pages (243-272), a counter triggers a second refresh (316-331), and an effect downloads the newest published artifact (294-314). (2) Event stream and reconnects: an EventSource with run, live, cursor, gap and end listeners, a fixed 1 s retry and a closed flag (198-240, 274-279). (3) Deduplication: a Map keyed by sequence plus a 'sequence &lt;= cursor' guard (175-181, 208). (4) Live text: merged through withDelta (213-220). (5) Derived view state, computed during render: the newest published artifact, the sorted timeline, the tool-event count, the summarizer rule, outstanding totals and dollar conversions (283-293, 356-357, 430-433, 576-578, 744-748, 795-826). (6) Rendering about fifteen regions. git log shows 17 commits touching the file, for 16 stories from US-4.6 to US-15.24.
- **Why it matters:** Every run-facing story edits this one function, so diffs mix stream behavior with markup and reviewers must read both. The reconnect and deduplication state machine cannot be tested without a browser. Each live text delta (setLive, line 219) re-renders every region and sorts or filters the event map three times.
- **Recommendation:** Split it in behavior-preserving steps, keeping every data-\* hook and sentence that the Playwright specs read. (1) Move the pure helpers and view-model derivations to lib/runs/\*.ts, with node:test coverage (WRUN-15). (2) Extract useRunWorkspace, which holds the load state machine (WRUN-02) and the ordered refresh (WRUN-04), and useRunEvents, which does replay, EventSource, backoff, deduplication and live text. (3) Extract one component per region. RunWorkspaceView should end as composition under 60 lines. Run the db profile's browser suites after each step.
- **Rule check:** DH-06 asks for small cohesive modules and invariants explained in code. .claude/rules/nextjs.md requires reconnect and deduplication handling and explicit states, which the hooks keep. The split moves only browser code, so business transitions stay on the server. Decision 0021 R1 froze data-\* hooks and wording only for its own change, but the specs still read them, so they are preserved.
- **Verification:** confirmed. Re-read every cited range: eight useState hooks, three effects and the six jobs sit where stated. eslint.json gives 677 lines and complexity 39, with the stream effect alone at 104 lines, and git log --follow lists 17 commits: 16 story deliveries and the Studio redesign.

```tsx
lib/runs/run-events.ts        pure: describeEvent (exhaustive switch), mergeEvents, withDelta, parseCursorFrame,
                              splitEventPage (Decision 0017 Q13 per event), latestPublished, toolEventCount
lib/runs/workspace-view.ts    pure: toWorkspaceView(snapshot) -> { statusSentence, label, tone, stopReason, openCalls,
                              outstanding, summarizerDiffers, budgetLines, roleRows }
components/runs/workspace/use-run-workspace.ts   load state machine + coalesced refresh() that keeps cursor order
components/runs/workspace/use-run-events.ts      replay pages, EventSource, backoff, dedup -> { events, connection, gap, live }
components/runs/workspace/use-published-result.ts  downloads the newest text artifact, aborts superseded reads
components/runs/workspace/*.tsx  RunHeader, StatusSection (status, connection, ContinueRun, RunControls), VerificationSection,
  ResultSection (stored | live), GoalSection, PlanSection, UnknownOutcomesSection, AssignmentsSection, ArtifactsSection,
  TimelineSection, ExpertSection, ModelsSection, BudgetsSection, UsageSection
RunWorkspaceView: const load = useRunWorkspace(runId); const stream = useRunEvents(runId, load.refresh); return layout
```

### <a id="wrun-02"></a>WRUN-02: The run page treats every failed read as temporary: denied runs are polled every second, and 403, 422, 5xx or contract errors never leave Loading

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/run-workspace.tsx:183-196](../../../../apps/web/components/run-workspace.tsx#L183): refresh(): on 401 or 404 it sets unavailable but still returns false; any other status just returns false; the body is never read; the parse is unguarded
  - [apps/web/components/run-workspace.tsx:243-249](../../../../apps/web/components/run-workspace.tsx#L243): start(): every false result schedules another attempt
  - [apps/web/components/run-workspace.tsx:198-201](../../../../apps/web/components/run-workspace.tsx#L198): retry(): a fixed 1 s delay, no cap and no final state
  - [apps/web/components/run-workspace.tsx:344-354](../../../../apps/web/components/run-workspace.tsx#L344): Shows 'Reconnecting. Showing the last known state.' when no state exists
  - [apps/web/components/run-workspace.tsx:259-261](../../../../apps/web/components/run-workspace.tsx#L259): Replay parse is unguarded, so a throw silently ends both the loop and the stream
  - [services/agent/src/autobots/api/settings_routes.py:52-66](../../../../services/agent/src/autobots/api/settings_routes.py#L52): Run reads can return 403 'forbidden' or 'workspace_required' ('Choose a workspace.')
  - [services/agent/src/autobots/api/errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29): A malformed run id such as /runs/abc fails the UUID path parameter and returns 422
  - [apps/web/components/run-inspector.tsx:36-40](../../../../apps/web/components/run-inspector.tsx#L36): The inspector tells a 403 or 422 to 'check that the local API is running'
- **Evidence:** On 401 or 404 the page says the run is not available, but it keeps requesting /workspace every second while it stays open. On 403 (current_workspace's 'Choose a workspace.'), 422 (a malformed id) or any 5xx, unavailable stays false: the page shows 'Loading this run.', then 'Reconnecting. Showing the last known state.' indefinitely. A ContractError or invalid JSON at line 194 or 259-260 rejects start(), and 'void start()' discards the rejection. Nothing retries, no stream opens, and the page stays on Loading, or stops updating silently if the snapshot had already loaded. Refusal bodies are never read, although [run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53) says an unread refusal holds its connection open.

  ```tsx
  if (reply?.ok !== true) {
    if (reply?.status === 404 || reply?.status === 401) {
      setUnavailable(true);
    }
    return false; // start() then calls retry(): another attempt after RECONNECT_MS
  }
  setSnapshot(parseRunWorkspace(await reply.json()));
  ```

- **Why it matters:** A mistyped link, a session with several workspaces and no choice made, or contract drift between the API and the client leaves the user on an endless loading message that is also misleading, while the page sends a request every second. Drift shows up only as an unhandled rejection in the console. DH-06's denied, unavailable and retryable states are not told apart.
- **Recommendation:** Give useRunWorkspace an explicit load state machine. 401 is signed_out. 403 is denied, showing the ErrorResponse message. 404 and 422 are not_found, with no retry and no stream. 5xx and network failures are retryable, with capped exponential backoff and a visible Retry button. A ContractError or invalid JSON is invalid: stop, say that the page and the API disagree, and log the ContractError path. Drain or cancel every non-ok body. Show the reconnecting sentence only when a snapshot is on screen. Add Playwright cases for 403, 422 and a malformed body using page.route, and give RunInspectorView and RunList the same classification.
- **Rule check:** DH-06: 'Represent loading, empty, denied, unavailable and retryable states deliberately' and 'explicit response parsing at untrusted boundaries'. nextjs.md: 'explicit error/empty/loading states'. Reads stay idempotent, and no server guard changes.
- **Verification:** confirmed. Traced refresh(), start() and retry(): a 401 or 404 shows the unavailable text while the effect keeps requesting /workspace every second, and every other failure keeps data-state="loading" with the reconnecting sentence. The 403 and 422 shapes match [settings_routes.py:52-66](../../../../services/agent/src/autobots/api/settings_routes.py#L52) and [errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29). The cross-workspace spec ([run-workspace.spec.ts:267-284](../../../../apps/web/tests/browser/run-workspace.spec.ts#L267)) asserts only the text, so nothing catches the polling.

```tsx
type WorkspaceLoad =
  | { kind: 'loading' } | { kind: 'ready'; snapshot: RunWorkspace; reconnecting: boolean }
  | { kind: 'signed_out' } | { kind: 'denied'; message: string } | { kind: 'not_found' }
  | { kind: 'retrying'; attempt: number } | { kind: 'invalid'; path: string };
lib/api/read-json.ts   readJson(url, parse, signal): Promise<ReadResult<T>>
                       // classifies 401/403/404/422/5xx, drains bodies, parses ErrorResponse, catches ContractError
use-run-workspace.ts   backoff 1 s, 2 s, 4 s ... 30 s; stops on signed_out | denied | not_found | invalid
RunWorkspaceView       switch (load.kind) -> RunLoading | RunDenied | RunNotFound | RunInvalid | workspace
```

### <a id="wrun-03"></a>WRUN-03: A lost write reply is reported as a failure, and the retry is sent with a new idempotency key

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [apps/web/components/run-controls.tsx:106-130](../../../../apps/web/components/run-controls.tsx#L106): Charge reconcile: new key on every submit; a lost reply becomes a refusal; the amount stays in the field for another submit
  - [apps/web/components/run-controls.tsx:38-43](../../../../apps/web/components/run-controls.tsx#L38): refusalOf(null) gives 'That could not be done. Nothing changed.'
  - [apps/web/components/run-controls.tsx:73-88](../../../../apps/web/components/run-controls.tsx#L73): Pause, resume and cancel: new key, same message
  - [apps/web/components/run-panel.tsx:84-109](../../../../apps/web/components/run-panel.tsx#L84): Panel commands: new key, same default message
  - [apps/web/components/unknown-effects.tsx:34-61](../../../../apps/web/components/unknown-effects.tsx#L34): Effect reconcile: new key; a null reply shows 'That couldn't be recorded.'
  - [apps/web/components/unknown-effects.tsx:91-118](../../../../apps/web/components/unknown-effects.tsx#L91): Buttons stay enabled while a request is in flight
  - [services/agent/src/autobots/api/run_routes.py:446-470](../../../../services/agent/src/autobots/api/run_routes.py#L446): The server deduplicates by an Idempotency-Key receipt and charges the oldest open call
  - [apps/web/components/continue-run.tsx:20-51](../../../../apps/web/components/continue-run.tsx#L20): The right pattern: the key is kept until the outcome is known, and a 5xx counts as unknown
- **Evidence:** When the browser loses the reply (null), the owner sees 'That could not be done. Nothing changed.' When the BFF times out after 30 s, it returns 503 'The local API is unavailable.' even though the API may already have committed. Neither message says the charge may have been recorded, and the amount stays in the field. post_reconcile stores a receipt per key and applies the charge to the oldest uncertain call, so a resubmission under a new key is a new request. If two or more calls are open, the same charge is recorded against a second call. Pause, resume, cancel (in both run-controls and run-panel) and effect reconciliation show the same unproven failure. In UnknownEffects a double press sends two reconciliations, and the second one's refusal ('This was already resolved.') replaces the success note.

  ```tsx
  const reply = await csrfFetch(`${base}/model-calls/reconcile`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ charged_micro_usd: Math.round(dollars * MICRO_USD) }),
  }).catch(() => null);
  // condensed. On failure: setRefusal(await refusalOf(reply)), and refusalOf(null) says 'Nothing changed.'
  ```

- **Why it matters:** An owner who follows the screen's advice can enter one provider charge twice into the run's ledger. The UI defeats the server's idempotency receipts, which exist to prevent exactly this. The defect needs a lost reply, a retry and more than one open uncertain call, but the message invites the retry.
- **Recommendation:** Use ContinueRun's pattern everywhere, through one helper. Keep the key, and the exact body it was first sent with, until a definite 2xx or 4xx arrives. The server fingerprints the body with the key and refuses a reused key with different content, so RunControls must resend the version it read for the first press, and the charge field and the effect evidence stay locked meanwhile. Treat a null reply or a 5xx as unknown, and say 'This may have been recorded. Pressing again won't record it twice.' Disable every action button while a request is pending. Show refusals with role='alert' and the destructive icon, as RunControls does. Add a Playwright case that lets the request reach the API, aborts the reply (route.fetch, then route.abort), retries, and checks that exactly one charge was recorded.
- **Rule check:** DH-06: 'Disable duplicate submits with server idempotency as the correctness mechanism'. The change uses the server's existing receipts and expected-version guard as designed and weakens no guard. AGENTS.md's receipt requirements are not touched.
- **Verification:** revised. Four fresh-key sites confirmed ([run-controls.tsx:81](../../../../apps/web/components/run-controls.tsx#L81) and 110, [run-panel.tsx:91](../../../../apps/web/components/run-panel.tsx#L91), [unknown-effects.tsx:46](../../../../apps/web/components/unknown-effects.tsx#L46)). A second effect is possible only for the charge: pause, resume and cancel carry expected_version, and an effect must still be unknown ([reconciliation.py:88-91](../../../../services/agent/src/autobots/application/reconciliation.py#L88)), so there the harm is the unproven 'Nothing changed'. Revised the recommendation and sketch: the receipt fingerprints include the body ([application/runs.py:408-410](../../../../services/agent/src/autobots/application/runs.py#L408), [run_routes.py:450](../../../../services/agent/src/autobots/api/run_routes.py#L450)), so a retry must resend the first body, including the version RunControls read for the first press.

```tsx
lib/runs/post-idempotent.ts
  type PostOutcome<T> = { kind: 'ok'; body: T } | { kind: 'refused'; code: string; message: string } | { kind: 'unknown' };
  postIdempotent<T>(url, body, key, parse): Promise<PostOutcome<T>>  // network or 5xx -> unknown; 4xx -> parseErrorResponse
components/runs/use-idempotent-action.ts
  const pending = useRef<{ key: string; body: unknown } | null>(null);
  send = (body) => { pending.current ??= { key: crypto.randomUUID(), body };   // a retry resends the first body
                     return postIdempotent(url, pending.current.body, pending.current.key, parse); }
  on ok or refused: pending.current = null; on unknown: keep both, lock the inputs, show the 'may have been recorded' note
```

### <a id="wrun-06"></a>WRUN-06: Write replies and stream frames are cast instead of parsed, although generated parsers exist

- **Severity** high · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 10
- **Where:**
  - [apps/web/components/continue-run.tsx:53-56](../../../../apps/web/components/continue-run.tsx#L53): The admission reply is cast; parseRunAccepted is generated ([generated.ts:8534](../../../../packages/api-client/src/generated.ts#L8534))
  - [apps/web/components/continue-run.tsx:65-67](../../../../apps/web/components/continue-run.tsx#L65): Error body cast
  - [apps/web/components/run-controls.tsx:39-41](../../../../apps/web/components/run-controls.tsx#L39): Error body cast
  - [apps/web/components/run-panel.tsx:101-104](../../../../apps/web/components/run-panel.tsx#L101): Error body cast
  - [apps/web/components/unknown-effects.tsx:57-59](../../../../apps/web/components/unknown-effects.tsx#L57): Error body cast; parseErrorResponse is generated ([generated.ts:7698](../../../../packages/api-client/src/generated.ts#L7698))
  - [apps/web/components/run-workspace.tsx:221-226](../../../../apps/web/components/run-workspace.tsx#L221): The stream's cursor frame is cast, and a NaN would persist
  - [apps/web/components/run-workspace.tsx:259-267](../../../../apps/web/components/run-workspace.tsx#L259): The event page is cast to { events?: unknown[] }, and the envelope is parsed with its events blanked
  - [apps/web/components/run-workspace.tsx:143-150](../../../../apps/web/components/run-workspace.tsx#L143): known() drops any event that fails validation, not only event types the page doesn't know
- **Evidence:** If a cursor frame carries no number, cursor becomes NaN, and Math.max keeps it NaN. From then on every replay and reconnect asks for after=NaN, which the API's Cursor parameter (an int with ge=0, [event_routes.py:41](../../../../services/agent/src/autobots/api/event_routes.py#L41)) rejects, so the page loops. An admission reply without run_id produces a link to /runs/undefined ([continue-run.tsx:62](../../../../apps/web/components/continue-run.tsx#L62), 108-110). Nothing in apps/web uses parseErrorResponse or parseRunAccepted. The stream route is include_in_schema=False ([event_routes.py:226](../../../../services/agent/src/autobots/api/event_routes.py#L226)), so its frames have no generated parser. ESLint counts 10 type assertions in this area, and grep finds 20 casts of the form `json().catch(() => null)) as` across apps/web. Three of the ten are `message.data as string` on EventSource data, which is always a string; the seven that can hide drift are the cursor frame, the event page, the admission reply and four error bodies.

  ```tsx
  cursor = Math.max(
    cursor,
    (JSON.parse(message.data as string) as { cursor: number }).cursor,
  );
  ```

- **Why it matters:** A contract mismatch shows up as a wrong link, a reconnect loop that never ends, or a missing timeline row, instead of a visible, logged error.
- **Recommendation:** Parse the admission reply with parseRunAccepted. Add readErrorResponse(reply): Promise&lt;ErrorResponse | null&gt;, which wraps parseErrorResponse in try/catch. Add a pure parseCursorFrame(data): number | null that accepts only safe non-negative integers, and a pure splitEventPage(raw: unknown) that requires an events array and returns the known events plus a count of skipped ones. In known(), skip only payload types outside the generated union, and log a known type that fails validation with its ContractError path.
- **Rule check:** DH-06: 'No blanket type assertions to conceal contract mismatches' and 'explicit response parsing at untrusted boundaries'. contracts.md: TypeScript types do not validate JSON. Decision 0017 Q13 still holds, because unknown event types are still ignored. Generated files are consumed, not edited.
- **Verification:** revised. Raised from medium to high: the rubric rates hidden contract drift at a trust boundary high, the stream's frames have no schema the drift check could compare ([event_routes.py:226](../../../../services/agent/src/autobots/api/event_routes.py#L226)), and WCMP-02 rates the same admission-reply cast high. All casts and the NaN path were confirmed; the evidence now says which of the ten assertions can hide drift.

```tsx
export function parseCursorFrame(data: string): number | null {
  let value: unknown;
  try { value = JSON.parse(data); } catch { return null; }
  if (typeof value !== 'object' || value === null || !('cursor' in value)) return null;
  const cursor = value.cursor;
  return typeof cursor === 'number' && Number.isSafeInteger(cursor) && cursor >= 0 ? cursor : null;
}
```

### <a id="wrun-04"></a>WRUN-04: Every stored event refetches the whole snapshot, and an older reply can overwrite a newer one

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/run-workspace.tsx:206-211](../../../../apps/web/components/run-workspace.tsx#L206): Each run frame adds the event and starts a full /workspace fetch
  - [apps/web/components/run-workspace.tsx:227-230](../../../../apps/web/components/run-workspace.tsx#L227): Each gap frame does the same
  - [apps/web/components/run-workspace.tsx:194](../../../../apps/web/components/run-workspace.tsx#L194): Replies are applied in the order they arrive, without a check
  - [apps/web/components/run-workspace.tsx:316-331](../../../../apps/web/components/run-workspace.tsx#L316): A second refresh path, driven by a counter and not coordinated with the first
  - [packages/api-client/src/generated.ts:8729](../../../../packages/api-client/src/generated.ts#L8729): RunWorkspace.cursor exists but is never read
  - [services/agent/src/autobots/application/run_projection.py:373](../../../../services/agent/src/autobots/application/run_projection.py#L373): cursor is the run's event_sequence at read time (the column is selected at line 84)
  - [apps/web/components/run-workspace.tsx:575-579](../../../../apps/web/components/run-workspace.tsx#L575): The tool-event count is ToolsUsed's reload trigger
  - [apps/web/components/tool-uses.tsx:110-140](../../../../apps/web/components/tool-uses.tsx#L110): Each change of that count reloads every tool-use page from after=0
- **Evidence:** Stored events come in bursts (tool.use.started, tool.use.completed, run.status_changed) as consecutive run frames. Each frame starts its own GET, and each reply calls setSnapshot unconditionally. The DTO's cursor, which the projection fills from runs.event_sequence, could order the replies, but the client never reads it. read_workspace makes at least 14 database calls per refresh. ToolsUsed reloads every page whenever the tool-event count changes, and setLive re-renders the whole workspace for each live delta.
- **Why it matters:** If an earlier reply resolves last, the page shows older state. After a run's final events nothing comes later to correct it, so the header and controls can show a non-terminal status after the timeline says 'Run moved from verifying to succeeded'. Long runs also make reads proportional to their event count.
- **Recommendation:** In useRunWorkspace, allow one request in flight and at most one queued refresh. Apply a reply only when its snapshot.cursor is at least the shown cursor; an equal cursor is harmless. Send the after-action refresh through the same function. Have ToolsUsed refetch only from its first unfinished use and merge the rows by id, since the list pages by id and a started use changes when it completes; when every loaded use is finished, fetch after the last id. Let ResultSection own the live text so a delta re-renders one region, and memoize the values derived from events.
- **Rule check:** DH-06: 'Browser state is a view of durable state'. Ordering snapshots by the server's event_sequence keeps it a faithful view. The reconnect and deduplication behavior required by nextjs.md is unchanged.
- **Verification:** revised. refresh() applies every reply unconditionally (194); RunWorkspace.cursor ([generated.ts:8729](../../../../packages/api-client/src/generated.ts#L8729)) comes from runs.event_sequence ([run_projection.py:84](../../../../services/agent/src/autobots/application/run_projection.py#L84) and 373), and nothing in apps/web reads it. Revised one step: the tool-use list pages by id ([tool_uses.py:277-278](../../../../services/agent/src/autobots/application/tool_uses.py#L277)), so fetching only after the last loaded id, as first proposed, would miss a started use that later completes. The race is reasoned from the code, not reproduced.

### <a id="wrun-05"></a>WRUN-05: Eight more run components exceed 60 lines by combining fetching, state and the whole render tree

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 8
- **Where:**
  - [apps/web/components/run-list.tsx:160-425](../../../../apps/web/components/run-list.tsx#L160): RunList: 260 lines; the row arrow at 332 is 65; the file is 399 non-blank lines
  - [apps/web/components/run-inspector.tsx:18-282](../../../../apps/web/components/run-inspector.tsx#L18): RunInspectorView: 263; the model-call row arrow at 93 is 84
  - [apps/web/components/run-panel.tsx:47-283](../../../../apps/web/components/run-panel.tsx#L47): RunPanel: 228, complexity 14
  - [apps/web/components/run-disclosure.tsx:22-256](../../../../apps/web/components/run-disclosure.tsx#L22): RunDisclosure: 220, complexity 25
  - [apps/web/components/run-controls.tsx:45-219](../../../../apps/web/components/run-controls.tsx#L45): RunControls: 170; the run commands and the charge form share refusal, note and busy
  - [apps/web/components/continue-run.tsx:12-127](../../../../apps/web/components/continue-run.tsx#L12): ContinueRun: 108, with seven separate useState flags
  - [apps/web/components/unknown-effects.tsx:22-130](../../../../apps/web/components/unknown-effects.tsx#L22): UnknownEffects: 107
  - [apps/web/components/tool-uses.tsx:149-237](../../../../apps/web/components/tool-uses.tsx#L149): ToolUseTable: 89
- **Evidence:** ESLint counts these lengths without blank and comment lines (metrics.md section 7). RunControls keeps refusal, note, busy and charge (58-61) for two unrelated flows, so a charge-form refusal and a pause refusal share one alert (195-207). ContinueRun tracks open, profile, started, problem, pending, lost and already as separate flags (13-19); pending stays true after a success (52-63). RunDisclosure derives bindings with a nested ternary (73-84) and chooses between its notices with a chain of ternaries (127-163). RunInspectorView repeats `reported_micro_usd === null ? 'none' : dollars(...)` three times within one row (151-167).
- **Why it matters:** A change to one flow re-renders and re-tests its neighbors, and the rules sit in JSX ternaries that no unit test can reach.
- **Recommendation:** Split each component the next time it is touched, starting with RunList, RunDisclosure and RunControls. Keep the data-\* hooks and the wording.
- **Rule check:** DH-06 asks for small cohesive modules and Client Components only where there is interaction. The specs read the data-\* hooks and wording, and both stay.
- **Verification:** confirmed. Lengths and complexities match eslint.json; the shared alert ([run-controls.tsx:195-207](../../../../apps/web/components/run-controls.tsx#L195)), the seven ContinueRun flags, the nested ternaries and the repeated charge expression are at the cited lines.

```text
RunList         useRunList(filters) { list, state, loadMore } + RunFilters + RunRow + RunListState
RunInspector    ModelCallRow (chargeText(call) once) + ToolAttemptList + EvidenceList + CheckpointList
RunPanel        useRunWorkspace(runId) (shared with WRUN-02) + PanelPlan + PanelFacts + RunCommandButtons
RunDisclosure   resolveDisclosure({ models, policy, chosen, roleOverrides, usesModel }) in lib/runs (pure)
                + ModelChoice + DisclosureNotice + RoleList
RunControls     RunCommandButtons + ChargeReconcileForm (its own refusal, note and busy)
ContinueRun     useReducer over closed | choosing | pending | unknown | started { runId, replayed }
UnknownEffects  EffectRow + useIdempotentAction (WRUN-03); ToolUseTable -> ToolUseRow + a COLUMNS array
```

### <a id="wrun-07"></a>WRUN-07: Contract unions are widened to string, so a new status or outcome passes the type check and renders blank

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 17
- **Where:**
  - [apps/web/components/run-workspace.tsx:36-72](../../../../apps/web/components/run-workspace.tsx#L36): STATUS_TEXT, STATUS_LABEL and STATUS_TONE are keyed by string
  - [apps/web/components/run-workspace.tsx:83-88](../../../../apps/web/components/run-workspace.tsx#L83): ROLE_SOURCE is keyed by string; BindingSource is generated ([generated.ts:7533](../../../../packages/api-client/src/generated.ts#L7533))
  - [apps/web/components/run-list.tsx:16-48](../../../../apps/web/components/run-list.tsx#L16): STATUS_TEXT and tone(status: string); StateLine also takes a string (127)
  - [apps/web/components/run-list.tsx:75-79](../../../../apps/web/components/run-list.tsx#L75): PROFILE_NAMES is keyed by string; ModelProfileId is generated ([generated.ts:8144](../../../../packages/api-client/src/generated.ts#L8144))
  - [apps/web/components/run-controls.tsx:16-36](../../../../apps/web/components/run-controls.tsx#L16): TERMINAL and PAUSABLE are Set&lt;string&gt;; commandsFor takes status: string, as does the prop at line 53
  - [apps/web/components/tool-uses.tsx:22-33](../../../../apps/web/components/tool-uses.tsx#L22): OUTCOMES and OutcomeIcon take string
  - [apps/web/components/unknown-effects.tsx:9-13](../../../../apps/web/components/unknown-effects.tsx#L9): A hand-written Operation type duplicates the generated UnknownEffect; outcome is a string at line 37
  - [apps/web/components/run-workspace.tsx:89-115](../../../../apps/web/components/run-workspace.tsx#L89): describe(): an if-chain whose last branch labels any unmatched payload with a name field 'Artifact ... is missing'; tsc already rejects a new type without one
- **Evidence:** Seven lookup maps, the TERMINAL and PAUSABLE sets and six parameters use string where a generated union exists (RunStatus is at [generated.ts:8691](../../../../packages/api-client/src/generated.ts#L8691)). There is also one hand-written DTO type and one non-exhaustive dispatch. With noUncheckedIndexedAccess, each lookup returns string | undefined. A status added to the Python enum therefore type-checks, then renders an empty status sentence (392) and no header badge (363), and commandsFor offers Cancel because the new status is in neither TERMINAL nor PAUSABLE. [run-panel.tsx:22](../../../../apps/web/components/run-panel.tsx#L22) already shows the safer form, Record&lt;Task['marker'], string&gt;. A related cause belongs to another area: the generator maps ExpertBinding.role_bindings, declared in Pydantic as dict[str, str], to Record&lt;string, unknown&gt; ([scripts/generate_contracts.py:46-47](../../../../scripts/generate_contracts.py#L46)). That is why [run-disclosure.tsx:34](../../../../apps/web/components/run-disclosure.tsx#L34) and 78 and [run-workspace.tsx:723-727](../../../../apps/web/components/run-workspace.tsx#L723) handle unknown values.
- **Why it matters:** After the client is regenerated, tsc still passes while the UI silently mishandles the new value, so reviewers must find every map by hand.
- **Recommendation:** Key the maps by the generated unions: Record&lt;RunStatus, string&gt;, Record&lt;BindingSource, string&gt;, Record&lt;NonNullable&lt;ToolUseView['outcome']&gt;, string&gt; and Record&lt;ModelProfileId, string&gt;. Type the parameters with the same unions. Use UnknownEffect and EffectEvidence['outcome'] in UnknownEffects. Turn describe() into a switch on payload.type that ends in assertNever(payload). Keep a runtime fallback for values the client doesn't know, as Decision 0017 Q13 requires. Report the role_bindings mapping to the contracts owner.
- **Rule check:** DH-06: use generated API types. contracts.md: generated TypeScript consumes the API definitions. The UI view maps stay separate from the DTOs and are only keyed by DTO unions, so no types are merged.
- **Verification:** revised. Recounted: seven maps, the TERMINAL and PAUSABLE sets, six parameters, the hand-written Operation type and describe() make 17, not 15. describe() is narrower than first stated: tsc already rejects a new payload type without a name field at line 114, and parseRunEvent drops unknown types at runtime, so only a new type with a name field would be mislabeled.

### <a id="wrun-08"></a>WRUN-08: Run status words and tones are defined twice, and STATUS_TEXT names two different things

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/run-list.tsx:16-27](../../../../apps/web/components/run-list.tsx#L16): Exported STATUS_TEXT: short labels
  - [apps/web/components/run-workspace.tsx:48-60](../../../../apps/web/components/run-workspace.tsx#L48): STATUS_LABEL repeats the same ten labels, under a comment saying they must match the list
  - [apps/web/components/run-workspace.tsx:35-47](../../../../apps/web/components/run-workspace.tsx#L35): Here STATUS_TEXT means full sentences
  - [apps/web/components/run-list.tsx:29-64](../../../../apps/web/components/run-list.tsx#L29): tone(), STATE_TEXT and STATE_DOT
  - [apps/web/components/run-workspace.tsx:61-72](../../../../apps/web/components/run-workspace.tsx#L61): STATUS_TONE: a second table from status to tone
  - [apps/web/components/home-activity.tsx:13](../../../../apps/web/components/home-activity.tsx#L13): Imports STATUS_TEXT from the run list screen
  - [apps/web/components/workflows-panel.tsx:17](../../../../apps/web/components/workflows-panel.tsx#L17): Imports STATUS_TEXT from the run list screen
- **Evidence:** [run-workspace.tsx:48](../../../../apps/web/components/run-workspace.tsx#L48) says the header uses 'the header's short state words, as the run list says them', but copies the words instead of importing them. The two tone tables already disagree in their categories: the list gives queued, paused, cancelling and cancelled one neutral dot, while the header uses muted for queued, cancelling and cancelled, and outline for paused.
- **Why it matters:** Adding or renaming a state means editing two label tables and two tone tables, and nothing fails if one is missed. A reader cannot tell which STATUS_TEXT a file means.
- **Recommendation:** Create lib/runs/run-status.ts: pure, keyed by RunStatus, holding RUN_STATUS_LABEL, RUN_STATUS_SENTENCE and runTone(status). Create components/runs/run-status.tsx with StateLine and a RunStatusBadge that maps the tone to dot classes or Badge variants. Import these in run-list, run-workspace, run-panel, home-activity and workflows-panel. Keep the words, which the specs assert.
- **Rule check:** Decision 0021 R3-R4 requires state words beside every tone, and they stay. DH-06 says not to invent a second state enum for the UI; the new module is keyed by the generated RunStatus.
- **Verification:** confirmed. Both label tables, both tone tables and the comment at [run-workspace.tsx:48](../../../../apps/web/components/run-workspace.tsx#L48) confirmed. The tone categories differ only for paused, which the list leaves neutral and the header marks outline.

### <a id="wrun-09"></a>WRUN-09: Run screens import shared pieces from each other, including a run-list and run-panel cycle

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/components/run-list.tsx:8](../../../../apps/web/components/run-list.tsx#L8): Imports RunPanel
  - [apps/web/components/run-panel.tsx:8-9](../../../../apps/web/components/run-panel.tsx#L8): Imports commandsFor from run-controls and StateLine from run-list, which closes the cycle
  - [apps/web/components/home-activity.tsx:13](../../../../apps/web/components/home-activity.tsx#L13): Imports STATUS_TEXT from a screen
  - [apps/web/components/workflow-monitor.tsx:7](../../../../apps/web/components/workflow-monitor.tsx#L7): Imports ToolUseTable and useToolUses from the workspace's tools section
  - [apps/web/components/goal-composer.tsx:18-20](../../../../apps/web/components/goal-composer.tsx#L18): Imports DEFAULT_BUDGET_MICRO_USD from run-disclosure
  - [apps/web/components/goal-composer.tsx:29](../../../../apps/web/components/goal-composer.tsx#L29): Imports focusGoal and NEW_RUN_PARAM from new-run
  - [apps/web/components/new-run.tsx:11-15](../../../../apps/web/components/new-run.tsx#L11): focusGoal finds the composer through the literal id 'goal'
  - [apps/web/components/run-panel.tsx:34](../../../../apps/web/components/run-panel.tsx#L34): wallTime is exported but used only in this file
- **Evidence:** There is one import cycle and six imports between screens. All 43 component files sit flat in apps/web/components. Shared run vocabulary (STATUS_TEXT, StateLine), the command rule (commandsFor), a data hook (useToolUses), a budget default and a DOM id all live inside screen modules, so other screens depend on whole screens.
- **Why it matters:** Dependencies run sideways between screens. The cycle makes module evaluation order matter if either file gains top-level effects. The pieces extracted in WRUN-01 and WRUN-05 have no home. The 'goal' id contract breaks silently if the composer renames its input.
- **Recommendation:** Add lib/runs/ for pure logic and components/runs/ for shared run widgets. Screens import from those folders, never from each other. Move DEFAULT_BUDGET_MICRO_USD to lib/runs/budget.ts. Export a GOAL_INPUT_ID constant that both the composer input and focusGoal use. Move wallTime, with a test, to lib/runs/format.ts.
- **Rule check:** DH-03 prescribes only apps/web/ and no internal layout, so these folders are a proposal. DH-06 asks for explicit ownership, narrow interfaces and small cohesive modules.
- **Verification:** confirmed. grep confirms the cycle ([run-list.tsx:8](../../../../apps/web/components/run-list.tsx#L8) and [run-panel.tsx:9](../../../../apps/web/components/run-panel.tsx#L9)) and the six cross-screen imports; wallTime has no caller outside run-panel.tsx.

```text
apps/web/lib/runs/          run-status.ts  run-events.ts  workspace-view.ts  commands.ts  format.ts  budget.ts   (pure)
apps/web/components/runs/   run-status.tsx  run-command-buttons.tsx  section.tsx  tool-uses/ (hook + table)
apps/web/components/runs/workspace/   RunWorkspaceView, its sections and hooks
apps/web/components/runs/list/        RunList, RunRow, RunFilters, RunPanel
```

### <a id="wrun-10"></a>WRUN-10: Money and time formatting is reimplemented per file, with diverging rules

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 10
- **Where:**
  - [apps/web/components/run-list.tsx:87-89](../../../../apps/web/components/run-list.tsx#L87): dollars(): US$ with two decimals
  - [apps/web/components/run-panel.tsx:30-32](../../../../apps/web/components/run-panel.tsx#L30): An identical dollars()
  - [apps/web/components/run-inspector.tsx:10-12](../../../../apps/web/components/run-inspector.tsx#L10): The same name with exact precision, which [slice-run-details.spec.ts:222-230](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L222) pins
  - [apps/web/components/run-workspace.tsx:795-822](../../../../apps/web/components/run-workspace.tsx#L795): Budgets mixes two-decimal and exact values; Usage repeats the same three figures with '$'
  - [apps/web/components/run-disclosure.tsx:19-20](../../../../apps/web/components/run-disclosure.tsx#L19): A second MICRO_USD (and toFixed(2) at line 97)
  - [apps/web/components/run-controls.tsx:94-113](../../../../apps/web/components/run-controls.tsx#L94): Charge parsing: Number() accepts '0x10' and '1e3', and extra decimals are rounded silently (MICRO_USD at line 30)
  - [apps/web/components/run-list.tsx:93-94](../../../../apps/web/components/run-list.tsx#L93): The RN-03 'estimated' rule, repeated at [run-panel.tsx:131-134](../../../../apps/web/components/run-panel.tsx#L131)
  - [apps/web/components/run-list.tsx:393](../../../../apps/web/components/run-list.tsx#L393): Start time via toISOString; [run-panel.tsx:163](../../../../apps/web/components/run-panel.tsx#L163) shows the raw string and [tool-uses.tsx:70](../../../../apps/web/components/tool-uses.tsx#L70) a locale time
- **Evidence:** There are 10 conversions from micro-USD for display across 5 files in this area. A grep for 'function dollars', '1_000_000' and 'MICRO_USD' finds 6 dollars() functions in apps/web: 3 here, plus [workflows-panel.tsx:50](../../../../apps/web/components/workflows-panel.tsx#L50), [goal-composer.tsx:74](../../../../apps/web/components/goal-composer.tsx#L74) and [home-activity.tsx:34](../../../../apps/web/components/home-activity.tsx#L34). It also finds two MICRO_USD constants.

  ```tsx
  Spend limit: US$
  {(snapshot.run.budget.limit_micro_usd / 1_000_000).toFixed(2)}.
  Reported so far: US$
  {snapshot.run.budget.spent_micro_usd / 1_000_000}. Held as an
  ...
  {snapshot.usage.repairs} repairs. Spent $
  ```

- **Why it matters:** The same amount can read US$0.30 in the list, US$0.3 under Budgets and $0.3 under Usage. Changing the currency or precision rule means editing many files, and the ledger input accepts text no reader would call dollars.
- **Recommendation:** Put the app-wide helpers in lib/format.ts, the module WCMP-12 proposes for the same copies on Home and in the composer: formatUsd(micro, { precision: 'cents' | 'exact' }) and formatTimestamp. Put the run-specific ones in lib/runs/format.ts, pure and unit-tested: parseUsdToMicro(text), which uses a strict decimal pattern of up to six places and returns micro-USD or a reason; spendSummary({ charged, reserved, unreported, limit }) for RN-03; and wallTime. Pin the current outputs first ([run-panel.spec.ts:105-107](../../../../apps/web/tests/browser/run-panel.spec.ts#L105), [slice-run-details.spec.ts:217-230](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L217)), then replace the copies. Ask product whether Usage should repeat the Budgets figures.
- **Rule check:** DH-06 asks for exact integer monetary units. Amounts stay integer micro-USD until display, and parsing stays exact on integers.
- **Verification:** revised. Recounted 10 display conversions in five files, six dollars() copies in apps/web and two MICRO_USD constants; Number('0x10') and Number('1e3') both parse. Revised only where the helpers live, so the app-wide formatter is the one WCMP-12 proposes.

### <a id="wrun-11"></a>WRUN-11: The summarizer-differs rule is written three times, and the copies disagree

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/run-workspace.tsx:744-757](../../../../apps/web/components/run-workspace.tsx#L744): The run's frozen role map
  - [apps/web/components/run-disclosure.tsx:216-229](../../../../apps/web/components/run-disclosure.tsx#L216): The disclosure shown before a run starts
  - [apps/web/components/model-policy-panel.tsx:75-79](../../../../apps/web/components/model-policy-panel.tsx#L75): Settings: the roles that differ from the executor
  - [apps/web/components/model-policy-panel.tsx:104-111](../../../../apps/web/components/model-policy-panel.tsx#L104): Settings: the summarizer note
  - [apps/web/components/run-disclosure.tsx:17](../../../../apps/web/components/run-disclosure.tsx#L17): EXECUTOR is named here, while run-workspace uses string literals
- **Evidence:** All three state the same product fact, that a differing summarizer pauses with route_not_bound when compaction is needed, each in its own words.

  ```tsx
  // run-workspace.tsx:744-748 and run-disclosure.tsx:216-217 (condensed)
  find((binding) => binding.role === "summarizer")?.profile !== executor?.profile // no summarizer: 'differs'
  // model-policy-panel.tsx:76-79 and 108 (condensed)
  differing.some((binding) => binding.role === SUMMARIZER) // no summarizer: 'same'
  ```

- **Why it matters:** When the routing rule changes, for example when the summarizer starts to dispatch, three screens must change together. They already give different answers for a role map that has no summarizer binding.
- **Recommendation:** Add pure summarizerDiffers(bindings) and differingRoles(bindings) functions to lib/runs/model-roles.ts. Cover them with node:test cases, including the missing-binding case, and decide that case's answer explicitly. Use them in all three components.
- **Rule check:** DH-06: avoid duplicated business rules. The screens still only disclose the rule, and routing stays on the server.
- **Verification:** confirmed. Compared the three checks: with no summarizer binding, the workspace and the disclosure say it differs and the model policy panel does not.

### <a id="wrun-12"></a>WRUN-12: The UI re-derives SP-010's command table, and two components each have their own copy of the command code

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 2
- **Where:**
  - [apps/web/components/run-controls.tsx:14-36](../../../../apps/web/components/run-controls.tsx#L14): TERMINAL, PAUSABLE and commandsFor, all over status strings
  - [services/agent/src/autobots/domain/runs.py:22-42](../../../../services/agent/src/autobots/domain/runs.py#L22): The canonical transition table
  - [services/agent/src/autobots/domain/runs.py:96-130](../../../../services/agent/src/autobots/domain/runs.py#L96): COMMAND_SOURCES and next_status
  - [services/agent/src/autobots/contracts/run_workspace.py:166-167](../../../../services/agent/src/autobots/contracts/run_workspace.py#L166): can_continue: a server-derived affordance already in the DTO
  - [apps/web/components/run-controls.tsx:65-88](../../../../apps/web/components/run-controls.tsx#L65): Sends the current version, read before each press
  - [apps/web/components/run-panel.tsx:83-110](../../../../apps/web/components/run-panel.tsx#L83): Sends the loaded version (RN-04's guard)
  - [apps/web/components/run-panel.tsx:14-21](../../../../apps/web/components/run-panel.tsx#L14): The Command type and LABELS again ([run-controls.tsx:14](../../../../apps/web/components/run-controls.tsx#L14), 25-29)
  - [apps/web/components/run-panel.tsx:246-260](../../../../apps/web/components/run-panel.tsx#L246): The button row again ([run-controls.tsx:138-152](../../../../apps/web/components/run-controls.tsx#L138))
- **Evidence:** Today commandsFor matches runs.py: pause from queued, running, waiting_\* and verifying; resume from paused; nothing from cancelling or a terminal state. Nothing ties the two together. Both senders build the same POST, with Content-Type, Idempotency-Key and expected_version, and the same buttons. They differ only in which version they send, a product choice recorded in two comments ([run-controls.tsx:65](../../../../apps/web/components/run-controls.tsx#L65) and [run-panel.tsx:83](../../../../apps/web/components/run-panel.tsx#L83)).
- **Why it matters:** A change to SP-010 needs a matching UI edit that no check catches, and the version policy is easy to copy into the wrong screen.
- **Recommendation:** Now: type commandsFor with RunStatus and an exhaustive switch. Move it, the labels and the button row into lib/runs/commands.ts and components/runs/run-command-buttons.tsx, with a sendRunCommand(runId, command, expectedVersion, key) function so each caller passes the version it means; WRUN-03 supplies the key handling. Later, as its own story: add the user's allowed commands to RunWorkspace, computed by next_status (Pydantic first, then regenerate the client), and delete commandsFor, as can_continue already does for continuation.
- **Rule check:** The ground rule keeps business transitions out of Next.js, and this moves that knowledge from the UI to the server. RN-04's expected-version guard and the workspace's current-version choice both survive, as explicit arguments. The generated client is regenerated, never edited.
- **Verification:** confirmed. commandsFor agrees with can_transition and next_status today ([domain/runs.py:22-128](../../../../services/agent/src/autobots/domain/runs.py#L22)); the two senders differ only in the version they send, as their comments say.

### <a id="wrun-13"></a>WRUN-13: Several handlers catch only network errors, so a bad body leaves buttons disabled or a list stuck

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [apps/web/components/run-controls.tsx:66-71](../../../../apps/web/components/run-controls.tsx#L66): currentVersion parses without a guard
  - [apps/web/components/run-controls.tsx:73-88](../../../../apps/web/components/run-controls.tsx#L73): If it throws, setBusy(false) is skipped and every button stays disabled
  - [apps/web/components/run-controls.tsx:117-118](../../../../apps/web/components/run-controls.tsx#L117): parseReconciliationResult is unguarded, and onChanged is skipped
  - [apps/web/components/tool-uses.tsx:127-133](../../../../apps/web/components/tool-uses.tsx#L127): parseToolUseList is unguarded, so 'Loading tool uses.' can stay forever
  - [apps/web/components/run-list.tsx:210-221](../../../../apps/web/components/run-list.tsx#L210): loadMore: no catch, a silent non-ok, and a stale list merged after the filters change
  - [apps/web/components/run-workspace.tsx:294-314](../../../../apps/web/components/run-workspace.tsx#L294): A failed result download is swallowed, and the live note keeps promising the stored result
  - [apps/web/components/run-workspace.tsx:316-331](../../../../apps/web/components/run-workspace.tsx#L316): A failed after-action refresh is swallowed
- **Evidence:**

  ```tsx
  setBusy(true);
  ...
  const reply = await csrfFetch(`${base}/${command}`, {
    ...
    body: JSON.stringify({ expected_version: await currentVersion() }), // may throw before the request
  }).catch(() => null);
  setBusy(false);
  ```

- **Why it matters:** A proxy error page, invalid JSON or contract drift becomes an unhandled rejection with no message. Pause, Resume and Cancel stay disabled until a reload, the tools table never resolves, Load more does nothing visible, and a page loaded for the old filters can replace the new list.
- **Recommendation:** Wrap handler bodies in try/finally so busy flags always reset, and turn a ContractError or SyntaxError into the existing refusal or failed state. Use the shared readJson (WRUN-02) for GETs. In loadMore, use a functional setList that checks the cursor it started from, abort the request when the filters change, and show a short failure note.
- **Rule check:** DH-06: centralize error handling and expose safe typed errors. nextjs.md: explicit error, empty and loading states.
- **Verification:** confirmed. currentVersion() is awaited while csrfFetch's arguments are built, outside its .catch, so a throw skips setBusy(false). RunList's first load does catch a parse error ([run-list.tsx:200-202](../../../../apps/web/components/run-list.tsx#L200)), but loadMore has no catch; the other paths behave as stated.

### <a id="wrun-14"></a>WRUN-14: The run inspector is a Client Component only so that it can fetch in an effect

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/run-inspector.tsx:1](../../../../apps/web/components/run-inspector.tsx#L1): 'use client'
  - [apps/web/components/run-inspector.tsx:18-48](../../../../apps/web/components/run-inspector.tsx#L18): useState and useEffect exist only to fetch; there are no handlers, inputs or live updates
  - [apps/web/app/runs/[id]/inspector/page.tsx:7-13](../../../../apps/web/app/runs/[id]/inspector/page.tsx#L7): The server page only passes the id
  - [apps/web/lib/service-status.ts:33-39](../../../../apps/web/lib/service-status.ts#L33): An existing server-only member client that sends the chosen workspace
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): requestJson keeps the status only inside its error message
  - [packages/api-client/src/generated.ts:9450-9452](../../../../packages/api-client/src/generated.ts#L9450): getRunInspector
- **Evidence:** RunInspectorView renders static facts and a single Link. Its only client state is the fetch result and a hand-written status mapping (36-40), so its first paint is always 'Loading this run.'
- **Why it matters:** The inspector's render code ships to the browser, the page needs an extra client round trip and flashes a loading state, and 404 or 403 get ad hoc text instead of notFound() and the app's error boundaries. DH-06 asks for Server Components unless there is interaction.
- **Recommendation:** Render the inspector on the server. Read the API on each request with a server-only member client (cache: 'no-store', a token per request, and the chosen workspace header, as lib/service-status.ts does), and parse the reply with parseRunInspector. Call notFound() on 404 and show a denied message on 401 or 403. Because requestJson reports the status only inside its message, use fetch with the generated parser, or add a status-aware helper to the hand-written runtime.ts. Keep the data-\* hooks. Later, consider rendering the workspace's first snapshot the same way, leaving only the stream client-side.
- **Rule check:** DH-06: 'Prefer Server Components; use Client Components for actual interaction', 'Authenticate and authorize each BFF mutation/read independently' and 'Prevent workspace data from leaking through shared caches, serialized props'. A no-store read with per-request authentication satisfies these. generated.ts is not edited.
- **Verification:** confirmed. RunInspectorView holds only the fetch result and its status, with no handlers, inputs or live updates. memberClient ([service-status.ts:33-39](../../../../apps/web/lib/service-status.ts#L33)) is module-private today, so the server read needs it exported or a sibling helper beside it.

### <a id="wrun-15"></a>WRUN-15: The stream, merge and rule logic has no unit tests, and living in .tsx files keeps it out of the unit runner

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 6
- **Where:**
  - [apps/web/components/run-workspace.tsx:127-141](../../../../apps/web/components/run-workspace.tsx#L127): withDelta
  - [apps/web/components/run-workspace.tsx:89-115](../../../../apps/web/components/run-workspace.tsx#L89): describe (and known at 143-150)
  - [apps/web/components/run-controls.tsx:32-36](../../../../apps/web/components/run-controls.tsx#L32): commandsFor
  - [apps/web/components/run-list.tsx:148-158](../../../../apps/web/components/run-list.tsx#L148): stateLine (and tone at 33-48)
  - [apps/web/components/run-disclosure.tsx:69-95](../../../../apps/web/components/run-disclosure.tsx#L69): Binding resolution, refused, fromExpert and showModel
  - [apps/web/components/tool-uses.tsx:78-99](../../../../apps/web/components/tool-uses.tsx#L78): brief, result and outcome
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): web_unit_tests runs a fixed list of two files with node --test
  - [apps/web/tests/browser/run-workspace.spec.ts:83-151](../../../../apps/web/tests/browser/run-workspace.spec.ts#L83): Browser coverage of reconnects and deduplication, in the db profile only
- **Evidence:** apps/web/tests/unit holds three test files, none for the run screens. Node's type stripping, in the pinned Node 22.23.2, loads .ts but not .tsx and does not resolve the @/ alias, so helpers inside components are out of reach; lib/schema-value.ts shows a shape the runner can load. A value import from @autobots/api-client does load, because the workspace link resolves to packages/api-client/src. withDelta has an edge no test pins: a piece that overlaps the current text is appended whole. For example, 'Hello' followed by the piece 'lo world' at offset 3 becomes 'Hellolo world', marked as joined. Nothing establishes whether the server can send overlapping pieces.
- **Why it matters:** Refactoring for WRUN-01 and WRUN-05 depends on slow browser runs against disposable databases, and subtle ordering or merge rules can regress with no fast failing test.
- **Recommendation:** Move the pure logic into lib/runs/\*.ts files that use relative .ts imports and no @/ alias or JSX; they may import the generated parsers and types from @autobots/api-client. Add node:test files for withDelta (continuing, duplicate, gap, overlap and new-segment pieces), describeEvent for every payload type, splitEventPage and parseCursorFrame, commandsFor against a fixture of runs.py's table, exhaustive status labels and tones, resolveDisclosure, summarizerDiffers, formatUsd and parseUsdToMicro. Add the files to web_unit_tests, or have it discover tests/unit/\*.test.ts.
- **Rule check:** DH-06 names Vitest and React Testing Library for pure and client behavior. The project's runner today is node:test; this keeps that runner and installs nothing. Changing verify.py's list is a harness edit that needs its own work item.
- **Verification:** revised. Ran one import of @autobots/api-client from apps/web under the pinned Node 22.23.2 (the version scripts/toolchain.py selects): it loaded and parsed a status, so only .tsx and the @/ alias keep helpers out of the runner, and the recommendation no longer limits pure modules to type-only imports. The withDelta overlap case was traced by hand.

### <a id="wrun-16"></a>WRUN-16: Effects ignore late replies instead of aborting their requests

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/components/run-workspace.tsx:183-186](../../../../apps/web/components/run-workspace.tsx#L183): The stream's refresh and replay fetches (also 251-253) pass no signal
  - [apps/web/components/run-workspace.tsx:294-314](../../../../apps/web/components/run-workspace.tsx#L294): Result download
  - [apps/web/components/run-workspace.tsx:316-331](../../../../apps/web/components/run-workspace.tsx#L316): After-action refresh
  - [apps/web/components/run-list.tsx:186-208](../../../../apps/web/components/run-list.tsx#L186): List load (150 ms debounce)
  - [apps/web/components/run-panel.tsx:62-81](../../../../apps/web/components/run-panel.tsx#L62): Panel load
  - [apps/web/components/run-inspector.tsx:24-48](../../../../apps/web/components/run-inspector.tsx#L24): Inspector load
  - [apps/web/components/run-disclosure.tsx:44-67](../../../../apps/web/components/run-disclosure.tsx#L44): Model and policy reads
  - [apps/web/components/tool-uses.tsx:110-145](../../../../apps/web/components/tool-uses.tsx#L110): The one effect here that aborts
- **Evidence:** Cleanup sets active = false (or closed = true). The reply is then ignored, but the request runs to completion, and refusal bodies on these paths are drained only after it finishes. Only tool-uses.tsx in this area uses an AbortController, and in the whole of apps/web only it and tool-catalog.tsx do. [tool-uses.tsx:111-112](../../../../apps/web/components/tool-uses.tsx#L111) explains the right behavior: 'A newer read replaces this one, so this one is aborted rather than left open.'
- **Why it matters:** Fast typing in the filter, switching panels and navigating away all leave requests in flight. Combined with WRUN-02's retry loop, the waste adds up.
- **Recommendation:** Pass an AbortController signal to every effect fetch through the shared readJson helper, abort in the cleanup, and ignore AbortError.
- **Rule check:** none
- **Verification:** confirmed. grep finds an AbortController only in tool-uses.tsx and tool-catalog.tsx; the seven listed effects only flip a flag on cleanup.

### <a id="wrun-17"></a>WRUN-17: Section shells and page headers are built by hand in each screen

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/components/run-workspace.tsx:846-864](../../../../apps/web/components/run-workspace.tsx#L846): A private Section component
  - [apps/web/components/run-inspector.tsx:284-309](../../../../apps/web/components/run-inspector.tsx#L284): A second private Section, with an optional note and the same Decision 0021 comment
  - [apps/web/components/tool-uses.tsx:250-256](../../../../apps/web/components/tool-uses.tsx#L250): An inline copy of the same section markup
  - [apps/web/components/run-workspace.tsx:582-595](../../../../apps/web/components/run-workspace.tsx#L582): A bordered attention card; it shares only the heading style
  - [apps/web/components/run-workspace.tsx:360-383](../../../../apps/web/components/run-workspace.tsx#L360): A header that reimplements PageHeader's layout and title classes
  - [apps/web/components/run-inspector.tsx:70-83](../../../../apps/web/components/run-inspector.tsx#L70): A header that repeats PageHeader's title class
  - [apps/web/components/ui/page-header.tsx:6-44](../../../../apps/web/components/ui/page-header.tsx#L6): PageHeader already accepts a ReactNode title, a description and actions
- **Evidence:** Three section copies repeat 'space-y-3 border-t pt-6' and an h2 with 'text-sm font-semibold' ([run-workspace.tsx:857](../../../../apps/web/components/run-workspace.tsx#L857), [run-inspector.tsx:297](../../../../apps/web/components/run-inspector.tsx#L297), [tool-uses.tsx:252](../../../../apps/web/components/tool-uses.tsx#L252)). The workspace header repeats PageHeader's 'flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between' and 'text-[32px] leading-tight', and the inspector header repeats the title class. The unknown-outcomes card is a bordered attention panel that shares only the heading style.
- **Why it matters:** Decision 0021's hairline section and title style are maintained in five places, and a spacing or heading change will miss some copies.
- **Recommendation:** Add components/ui/section.tsx, taking an id, a title and an optional note, and use it for the three hairline sections; leave the attention card's frame as it is. Render both headers with PageHeader, passing a ReactNode title for the badge, actions for 'Inspect this run', and the inspector's goal and back link as its description.
- **Rule check:** Decision 0021's hairline sections and single header style, and DS-03's consistency, are kept.
- **Verification:** revised. Recounted with grep: three hairline shells and two hand-built headers, so 5 rather than 6. The inspector header does not repeat PageHeader's flex layout, and the attention card is not a hairline section, so both claims and the recommendation were narrowed.

### <a id="wrun-18"></a>WRUN-18: Magic values, and different names for the same concepts

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 38
- **Where:**
  - [apps/web/components/run-workspace.tsx:362](../../../../apps/web/components/run-workspace.tsx#L362): text-[32px]; this file has 15 arbitrary pixel sizes
  - [apps/web/components/run-list.tsx:132](../../../../apps/web/components/run-list.tsx#L132): text-[13px]; this file has 7
  - [apps/web/components/run-list.tsx:203](../../../../apps/web/components/run-list.tsx#L203): An unnamed 150 ms debounce
  - [apps/web/components/tool-uses.tsx:119](../../../../apps/web/components/tool-uses.tsx#L119): limit=200 written inline
  - [apps/web/components/run-workspace.tsx:745-747](../../../../apps/web/components/run-workspace.tsx#L745): Literal 'summarizer' and 'executor'; [run-disclosure.tsx:17](../../../../apps/web/components/run-disclosure.tsx#L17) names EXECUTOR
  - [apps/web/components/run-panel.tsx:54](../../../../apps/web/components/run-panel.tsx#L54): Calls the RunWorkspace DTO view; [run-workspace.tsx:153](../../../../apps/web/components/run-workspace.tsx#L153) calls it snapshot
  - [apps/web/components/run-inspector.tsx:20](../../../../apps/web/components/run-inspector.tsx#L20): Calls a load failure state; [run-panel.tsx:55](../../../../apps/web/components/run-panel.tsx#L55) calls it failed and [run-workspace.tsx:158](../../../../apps/web/components/run-workspace.tsx#L158) unavailable
  - [apps/web/components/continue-run.tsx:16](../../../../apps/web/components/continue-run.tsx#L16): Calls a refused write problem; [unknown-effects.tsx:32](../../../../apps/web/components/unknown-effects.tsx#L32) calls it message and [run-controls.tsx:58](../../../../apps/web/components/run-controls.tsx#L58) refusal
- **Evidence:** There are 38 arbitrary pixel font sizes in 8 files of this area, using 8 distinct values: 19 x 13px, 6 x 12.5px, 5 x 15px, 2 x 32px, 2 x 17px, 2 x 13.5px, 1 x 12px and 1 x 11px. apps/web has 212 in total. The @theme block in globals.css defines colors, fonts and radii, but no font sizes.
- **Why it matters:** Typography drifts from screen to screen, although DS-03 asks for consistent typography. Readers must translate between names in files that hold the same data.
- **Recommendation:** Add a named type scale, font sizes only, to the @theme block in globals.css, and use it here. Name FILTER_DEBOUNCE_MS and TOOL_USE_PAGE_SIZE. Reuse the EXECUTOR and SUMMARIZER constants. Settle on one vocabulary: snapshot, load state, refusal.
- **Rule check:** Only font-size tokens are added: the DS-01 palette is untouched and, per Decision 0021 R4, no colors are added. slice-visual.spec.ts measures contrast, focus and zoom and saves screenshots, but compares them with no baseline, so check those screenshots by eye after the change.
- **Verification:** revised. Recounted 38 pixel sizes in 8 files with the stated distribution, and 212 in apps/web; the @theme block has no font-size tokens. Corrected the rule check: [slice-visual.spec.ts:686-687](../../../../apps/web/tests/browser/slice-visual.spec.ts#L686) saves screenshots without comparing them, so it would not catch size drift.

### <a id="wrun-19"></a>WRUN-19: Paths are built by hand, with a mix of &lt;a&gt; and Link and inconsistent encoding

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/components/run-workspace.tsx:609-614](../../../../apps/web/components/run-workspace.tsx#L609): &lt;a href&gt; for the parent run, a full page load
  - [apps/web/components/run-workspace.tsx:627-630](../../../../apps/web/components/run-workspace.tsx#L627): &lt;a href&gt; for child runs
  - [apps/web/components/run-workspace.tsx:375-381](../../../../apps/web/components/run-workspace.tsx#L375): Link with an unencoded runId
  - [apps/web/components/run-list.tsx:344](../../../../apps/web/components/run-list.tsx#L344): Link with an unencoded id
  - [apps/web/components/run-panel.tsx:241](../../../../apps/web/components/run-panel.tsx#L241): Link with an encoded id
  - [apps/web/components/run-workspace.tsx:297](../../../../apps/web/components/run-workspace.tsx#L297): The download path is encoded here, but not at 659 or [run-inspector.tsx:238](../../../../apps/web/components/run-inspector.tsx#L238)
  - [apps/web/components/run-controls.tsx:62](../../../../apps/web/components/run-controls.tsx#L62): One of seven places that build /api/v1/runs/{id} (also run-workspace 173 and 320, run-panel 58, tool-uses 119, unknown-effects 41 and run-inspector 26)
- **Evidence:** Seven places build the run API path, three build the artifact download path, and two internal links use &lt;a&gt; while their neighbors use Link.
- **Why it matters:** A route change means edits in many files. Navigating to a parent or child run reloads the whole app shell instead of using the client router.
- **Recommendation:** Add lib/routes.ts with runPath, runInspectorPath, artifactDownloadPath and apiRunPath(id, ...segments), each encoding its parts. Use next/link for in-app routes, and keep &lt;a&gt; only for downloads.
- **Rule check:** none
- **Verification:** confirmed. Counted seven builders of the run API path and three download paths. Run ids are UUIDs, so the missing encoding is a consistency issue, not a live bug.

### <a id="wrun-20"></a>WRUN-20: Some non-obvious mechanics give no reason, and one comment documents a copy

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/run-workspace.tsx:259-260](../../../../apps/web/components/run-workspace.tsx#L259): The page envelope is parsed with its events blanked, with no explanation
  - [apps/web/components/run-list.tsx:196](../../../../apps/web/components/run-list.tsx#L196): A body is drained without comment (also [run-panel.tsx:71](../../../../apps/web/components/run-panel.tsx#L71) and [run-inspector.tsx:35](../../../../apps/web/components/run-inspector.tsx#L35))
  - [apps/web/components/run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53): The only stated reason for draining bodies
  - [apps/web/components/run-workspace.tsx:188-193](../../../../apps/web/components/run-workspace.tsx#L188): This refusal path does not drain
  - [apps/web/components/run-workspace.tsx:160](../../../../apps/web/components/run-workspace.tsx#L160): The refreshes counter is an effect trigger (bumped at 434 and 599), unexplained
  - [apps/web/components/run-workspace.tsx:48](../../../../apps/web/components/run-workspace.tsx#L48): The comment says the labels match the run list instead of importing them
- **Evidence:** Body draining appears three times without comment and is explained once, in another file, so a reader cannot tell whether run-workspace's undrained refusal is a bug. The `{ ...raw, events: [] }` parse applies Decision 0017 Q13 one event at a time, but nothing at the call says so.
- **Why it matters:** Readers have to reverse-engineer the intent, and may 'simplify' away required mechanics or copy the omissions.
- **Recommendation:** Move these mechanics into named helpers whose doc comments carry the reason: readJson drains bodies, and splitEventPage applies Q13 per event. Replace the counter with a direct refresh() call. Delete the copied labels and their comment (WRUN-08).
- **Rule check:** DH-06: explain non-obvious invariants in code, and avoid comments that restate syntax. Decision and story citations stay.
- **Verification:** confirmed. Draining without comment at [run-list.tsx:196](../../../../apps/web/components/run-list.tsx#L196), [run-panel.tsx:71](../../../../apps/web/components/run-panel.tsx#L71) and [run-inspector.tsx:35](../../../../apps/web/components/run-inspector.tsx#L35); in this area only [run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53) gives the reason, and the workspace's refresh() leaves its refusal unread.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

This was a static review. No browser, server or verify profile was run. The snapshot race (WRUN-04), the lost-reply double charge (WRUN-03) and the endless retry loop (WRUN-02) are reasoned from the code and the server routes, not reproduced. The claim that an unread refusal holds a connection open comes from the project's own comment ([run-disclosure.tsx:53](../../../../apps/web/components/run-disclosure.tsx#L53)), not from a measurement. ESLint was not rerun; size, complexity and assertion counts come from this run's .checks/reviews/review-2026-11-12-09-52-30/eslint.json. Files from other areas were read only in the excerpts cited: PRD-Development-Harness.md DH-03 to DH-06, metrics.md, generated.ts, run_projection.py, run_routes.py, event_routes.py, settings_routes.py, security.py, errors.py, domain/runs.py, contracts/run_workspace.py, lib/bff.ts, model-policy-panel.tsx, globals.css, scripts/verify.py, scripts/generate_contracts.py and the browser specs. The /api/v1 BFF route handlers that serve these screens belong to web-shell and were not reviewed. No command was refused.
