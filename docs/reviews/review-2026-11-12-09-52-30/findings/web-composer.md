# Web: composer, home and sessions

The home, composer and session screens are readable. Their comments cite PRD and decision IDs, every GET is parsed with the generated runtime parsers, and loading and failure text is usually explicit. The jobs chart, search palette and greeting show careful accessibility and hydration work. Change cost and defect risk sit in two places. GoalComposer is one 541-line function (527 counted lines, complexity 37) with 13 state hooks, two fetch effects and its submission code inline. Run admission is written separately in goal-composer and session-panel, and both differ from continue-run. Both cast their POST responses instead of parsing them, mint a new Idempotency-Key on every press with no in-flight guard, and report a lost reply as a sign-in problem (the composer) or a plain failure (the session panel), so a double click or a retry after a timeout can admit two paid runs. Elsewhere in the area: failures read as empty or signed-out states (search, the home account section, the composer's option lists); the waiting notifier stops polling for good after a 401 or 403, which a client-side sign-in does not undo, or after a reply its parser rejects; read-only views fetch in client effects data that their dynamic Server Component pages could render; and every client read hand-writes the same effect. Pure logic such as budget steps, input paths, relative time, chart layout and the waiting diff sits inside .tsx files that the repository's node:test runner cannot load. It is tested only through browser suites, or not at all. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict TypeScript, Prettier and traceable comments hold, but DH-06 is missed on the admission path (five response casts, no duplicate-submit guard), read-only views are Client Components, and one avatar hard-codes a radius against DS-03. |
| modules | 3 | Imports point at the generated client and lib, but shared run view-models (status labels, the default budget, the goal field id) live in or are copied across feature components. |
| size | 2 | Eight of the ten files have a function over 60 lines: GoalComposer 527 at complexity 37, JobsPlot 252, SessionPanel 194, SearchPalette 189, HomeActivity 165. |
| functions | 2 | Components interleave data loading, derivation, submission and rendering; the riskiest logic (refusal mapping, budget steps, bar layout, waiting diff) is inline rather than in pure functions. |
| structure | 3 | Pages are thin and each feature has one file, but logic the repo's own lib/\*.ts pattern would hold stays in client components, out of reach of unit tests. |
| approach | 3 | Hydration-safe reads, a native modal dialog and parallel server reads are sound, but read-only data is fetched client-side, each screen writes its own fetch effect, and the polling loop is fragile. |
| comments | 4 | Comments mostly explain why and cite PRD and decisions (tab order, nothing sent until Run, body draining); one composer comment is stale and one non-obvious pattern lacks its reason. |
| types | 3 | GET reads use generated parsers and the search kind map is keyed by the generated union, but admission responses are cast, request bodies are untyped against RunRequest, and status maps are keyed by string. |
| errors | 2 | Loading and failure text is usually explicit, but lost admission replies read as sign-in problems or plain failures, failures read as empty or signed out, option-list failures are swallowed, and polling stops silently. |
| tests | 3 | Browser specs cover the main flows with axe checks, but no unit test covers the area's pure logic, and double submits, lost replies, failure states and polling restarts are untested. |
| maintainability | 3 | Readable and traceable, with change cost concentrated in GoalComposer and in three diverging copies of run admission. |

## Strengths

- **Every read is parsed with the generated runtime parsers.** Each GET in the area validates its JSON before use: [apps/web/components/goal-composer.tsx:152](../../../../apps/web/components/goal-composer.tsx#L152), 157 and 185, [home-activity.tsx:79-81](../../../../apps/web/components/home-activity.tsx#L79), [jobs-chart.tsx:90](../../../../apps/web/components/jobs-chart.tsx#L90), [data-summary.tsx:27](../../../../apps/web/components/data-summary.tsx#L27), [search-palette.tsx:76](../../../../apps/web/components/search-palette.tsx#L76), [session-panel.tsx:35](../../../../apps/web/components/session-panel.tsx#L35) and [waiting-notifier.tsx:47](../../../../apps/web/components/waiting-notifier.tsx#L47). [jobs-chart.tsx:9](../../../../apps/web/components/jobs-chart.tsx#L9) and [search-palette.tsx:12](../../../../apps/web/components/search-palette.tsx#L12) derive local types from the generated ones instead of restating them.
- **Hydration-safe browser-only values.** [apps/web/components/home-greeting.tsx:26-43](../../../../apps/web/components/home-greeting.tsx#L26) reads the clock through useSyncExternalStore with a minute subscription and a null server snapshot, and line 38 says why. [goal-composer.tsx:114](../../../../apps/web/components/goal-composer.tsx#L114) restores the draft from sessionStorage the same way, and unavailable storage degrades quietly (38-44, 249-253).
- **A chart whose meaning never depends on colour.** [apps/web/components/jobs-chart.tsx:12-46](../../../../apps/web/components/jobs-chart.tsx#L12) gives each outcome a documented status token (Decision 0021 R4, 0022 D14) and textures two series. The SVG title carries the totals (186-188), the tooltip is aria-hidden (311-313), and an equivalent table follows (332-381).
- **An accessible command palette on a native modal dialog.** apps/web/components/search-palette.tsx uses showModal and returns focus to the opener (35-47, 103-106). It implements a combobox over a listbox with aria-activedescendant (139-148, 168-200), keeps focus in the input on option mousedown (183), ignores out-of-order replies (65-94), and keys its kind labels by the generated union so a new kind fails to compile (14-19).
- **Comments that state invariants and trace them.** [apps/web/components/waiting-notifier.tsx:19-22](../../../../apps/web/components/waiting-notifier.tsx#L19) says what is read and that nothing leaves the Mac. [goal-composer.tsx:46-47](../../../../apps/web/components/goal-composer.tsx#L46) and 358-359 tie the file limits and the Tab order to FI-01 and the layout. [home-activity.tsx:73](../../../../apps/web/components/home-activity.tsx#L73) explains why refused bodies are read, and [apps/web/app/page.tsx:22](../../../../apps/web/app/page.tsx#L22) says why the page is dynamic.
- **Parallel, per-request server reads on Home.** [apps/web/app/page.tsx:33-38](../../../../apps/web/app/page.tsx#L33) awaits four independent reads with Promise.all, and [page.tsx:22-23](../../../../apps/web/app/page.tsx#L22) forces dynamic rendering with its reason, so service status is never baked into a build.
- **Stable data-field hooks for tests.** Components expose data-field and data-\* attributes ([goal-composer.tsx:378](../../../../apps/web/components/goal-composer.tsx#L378), 451 and 465; [home-activity.tsx:110](../../../../apps/web/components/home-activity.tsx#L110) and 200-206; [jobs-chart.tsx:159](../../../../apps/web/components/jobs-chart.tsx#L159), 313 and 332) that the browser specs select on instead of styling classes, for example [apps/web/tests/browser/home.spec.ts:37](../../../../apps/web/tests/browser/home.spec.ts#L37).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WCMP-01](#wcmp-01) | high | errors | Run admission can start duplicate paid runs: no in-flight guard and a new Idempotency-Key on every press | M | medium |
| [WCMP-02](#wcmp-02) | high | types | Admission replies are cast instead of parsed, and request bodies are untyped | S | medium |
| [WCMP-03](#wcmp-03) | high | size | GoalComposer is a 541-line component with 13 state hooks, three effects and inline submission | M | medium |
| [WCMP-04](#wcmp-04) | medium | duplication | Run admission is implemented three times, with different refusal handling and announcements | M | medium |
| [WCMP-05](#wcmp-05) | medium | errors | Failures render as signed out, empty results or nothing | M | medium |
| [WCMP-06](#wcmp-06) | medium | errors | The waiting notifier stops polling for good after a 401 or a rejected reply | S | medium |
| [WCMP-07](#wcmp-07) | medium | approach | Read-only home, data and session views fetch in client effects data their dynamic pages could render | M | medium |
| [WCMP-08](#wcmp-08) | medium | duplication | Every client read writes its own fetch effect, and the copies already disagree | M | low |
| [WCMP-10](#wcmp-10) | medium | functions | SearchPalette puts the shortcut, dialog, debounced search, key handling and status in one function | S | low |
| [WCMP-11](#wcmp-11) | medium | tests | Pure logic lives in .tsx files the unit runner can't load, so it is untested or tested only in the browser | M | low |
| [WCMP-12](#wcmp-12) | medium | duplication | Money and relative-time formatting is copied per component and differs between screens | S | low |
| [WCMP-09](#wcmp-09) | low | size | JobsPlot mixes scale math and SVG rendering in one 252-line function | M | low |
| [WCMP-13](#wcmp-13) | low | modules | The composer copies the server's default budget and imports shared constants from other feature components | S | low |
| [WCMP-14](#wcmp-14) | low | types | Status label maps are keyed by string instead of the generated RunStatus union | S | low |
| [WCMP-15](#wcmp-15) | low | duplication | Home's hairline sections are assembled by hand four times | S | low |
| [WCMP-16](#wcmp-16) | low | standards | The Expert initial avatar is copied three times with a hard-coded radius | S | low |
| [WCMP-17](#wcmp-17) | low | naming | Near-identical names for unrelated state | S | low |
| [WCMP-18](#wcmp-18) | low | comments | A composer comment says the choices survive setup, but only the draft is stored | S | low |
| [WCMP-19](#wcmp-19) | low | standards | The coordinator's Expert choice has no group label, and Run is disabled without saying why | S | low |

### <a id="wcmp-01"></a>WCMP-01: Run admission can start duplicate paid runs: no in-flight guard and a new Idempotency-Key on every press

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/goal-composer.tsx:287-292](../../../../apps/web/components/goal-composer.tsx#L287): new key per press; the comment states that intent
  - [apps/web/components/goal-composer.tsx:257-262](../../../../apps/web/components/goal-composer.tsx#L257): startSession mints its own key per press, so a press can also create a second session
  - [apps/web/components/goal-composer.tsx:591-593](../../../../apps/web/components/goal-composer.tsx#L591): Run is not disabled while a request is in flight
  - [apps/web/components/goal-composer.tsx:335-340](../../../../apps/web/components/goal-composer.tsx#L335): a null reply or any 5xx falls through to 'error'
  - [apps/web/components/goal-composer.tsx:647](../../../../apps/web/components/goal-composer.tsx#L647): the 'error' copy tells the user to sign in
  - [apps/web/components/session-panel.tsx:51-55](../../../../apps/web/components/session-panel.tsx#L51): same per-press key
  - [apps/web/components/session-panel.tsx:190](../../../../apps/web/components/session-panel.tsx#L190): disabled only by !ready
  - [apps/web/components/continue-run.tsx:20-21](../../../../apps/web/components/continue-run.tsx#L20): the app's own policy: key kept until the outcome is known; null reply and 5xx treated as unknown at 47-51
- **Evidence:** Three POSTs set Idempotency-Key to a fresh crypto.randomUUID() inside the click handler ([goal-composer.tsx:262](../../../../apps/web/components/goal-composer.tsx#L262) and 292, [session-panel.tsx:55](../../../../apps/web/components/session-panel.tsx#L55); counted by grep in the area's files). Neither Run button tracks a pending request: [goal-composer.tsx:593](../../../../apps/web/components/goal-composer.tsx#L593) disables only on an empty draft or no budget, and [session-panel.tsx:190](../../../../apps/web/components/session-panel.tsx#L190) only on !ready. csrfFetch first GETs /api/csrf (apps/web/lib/csrf-fetch.ts), so each press spans two round trips. A null reply or a 5xx ends in outcome 'error', whose copy is 'That could not be checked. Sign in, then try again.' ([goal-composer.tsx:647](../../../../apps/web/components/goal-composer.tsx#L647)). That includes the BFF's 503 after its 30 s upstream timeout ([apps/web/lib/bff.ts:102](../../../../apps/web/lib/bff.ts#L102) and 120). continue-run.tsx does the opposite: it keeps the key until the outcome is known (20-21, 39) and treats a null reply or 5xx as unknown (47-51).
- **Why it matters:** A double click admits a second run, and so does a second press after an admission that the API committed but whose reply was lost or timed out. With an Expert, it also creates a second session. Each run reserves budget and calls models. The user is told to sign in when the real state is unknown. The app also now applies two contradictory idempotency policies to the same endpoint.
- **Recommendation:** Adopt continue-run's policy in one shared admission hook: (1) disable Run while a request is in flight; (2) keep the Idempotency-Key, and on the Expert path the created session id, until the outcome is definite; (3) keep the request body fixed while the outcome is unknown, as ContinueRun locks its model choice ([continue-run.tsx:94-97](../../../../apps/web/components/continue-run.tsx#L94)), because the API refuses a reused key with different content ([application/runs.py:117-118](../../../../services/agent/src/autobots/application/runs.py#L117)); (4) clear the key only after acceptance or a 4xx refusal; (5) show a null reply or 5xx as 'not known yet, press Run again to check', and keep the sign-in copy for 401 not_signed_in. Share the unknown-outcome rule with the command helper WRUN-03 proposes. Add browser cases that double-click Run and that drop the admission reply, each asserting one run. Write those tests first.
- **Rule check:** DH-06: 'Disable duplicate submits with server idempotency as the correctness mechanism.' The server key stays the correctness mechanism; the client stops minting a new one per press and adds the in-flight guard. No run state or scheduling moves into Next.js.
- **Verification:** revised. Confirmed the three fresh-key POSTs, the missing in-flight guard and the sign-in copy for an unknown outcome. Added step (3): the admission fingerprint covers the goal, budget, files, Expert and model ([application/runs.py:202-217](../../../../services/agent/src/autobots/application/runs.py#L202)), so a retry that sends an edited draft under the kept key is refused rather than replayed.

```tsx
// lib/run-admission.ts (JSX-free) plus one hook used by GoalComposer, SessionPanel and ContinueRun
export function useRunAdmission() {
  const key = useRef<string | null>(null);            // kept until the outcome is known (continue-run.tsx:20)
  const [state, dispatch] = useReducer(admission, { status: 'idle' });
  async function submit(body: RunRequest): Promise<void> {
    if (state.status === 'submitting') return;          // Run is also disabled while submitting
    dispatch({ type: 'submit' });
    const result = await admitRun(body, (key.current ??= crypto.randomUUID()));
    if (result.kind !== 'unknown') key.current = null;  // a null reply or 5xx keeps the key for the retry
    dispatch({ type: 'settled', result });
  }
  return { state, submit };
}
// GoalComposer also keeps the session id it created, so a retry reuses it instead of starting another session.
// While the outcome is unknown, the draft and chips stay locked, so the retry sends the same body.
```

### <a id="wcmp-02"></a>WCMP-02: Admission replies are cast instead of parsed, and request bodies are untyped

- **Severity** high · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 8
- **Where:**
  - [apps/web/components/goal-composer.tsx:273](../../../../apps/web/components/goal-composer.tsx#L273): POST /v1/sessions reply cast to { id: string }; it returns SessionView
  - [apps/web/components/goal-composer.tsx:311](../../../../apps/web/components/goal-composer.tsx#L311): 202 reply cast to { run_id: string } instead of parseRunAccepted
  - [apps/web/components/goal-composer.tsx:318-321](../../../../apps/web/components/goal-composer.tsx#L318): error body cast instead of parseErrorResponse
  - [apps/web/components/goal-composer.tsx:294-308](../../../../apps/web/components/goal-composer.tsx#L294): RunRequest body built as an untyped literal
  - [apps/web/components/session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65): same RunAccepted cast
  - [apps/web/components/session-panel.tsx:68-70](../../../../apps/web/components/session-panel.tsx#L68): same error-body cast
  - [apps/web/components/session-panel.tsx:57-62](../../../../apps/web/components/session-panel.tsx#L57): untyped body; expert_id can be undefined (49-50)
  - [packages/api-client/src/generated.ts:7693](../../../../packages/api-client/src/generated.ts#L7693): ErrorResponse and parseErrorResponse are generated, as are RunAccepted (8526), RunRequest (8673) and SessionCreate (8801)
- **Evidence:** Every GET in these two files is parsed, but the admission POSTs are not. [goal-composer.tsx:273](../../../../apps/web/components/goal-composer.tsx#L273) uses `((await reply.json()) as { id: string }).id`. [goal-composer.tsx:311](../../../../apps/web/components/goal-composer.tsx#L311) and [session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65) cast to `{ run_id: string }`. Refusals are cast to `{ code?: string; message?: string } | null` ([goal-composer.tsx:318-321](../../../../apps/web/components/goal-composer.tsx#L318), [session-panel.tsx:68-70](../../../../apps/web/components/session-panel.tsx#L68)). That makes five assertions, the ESLint consistent-type-assertions hits for these files. The three bodies go through JSON.stringify untyped, so [session-panel.tsx:60](../../../../apps/web/components/session-panel.tsx#L60) passes an expert_id typed string | null | undefined; JSON.stringify drops an undefined key, but `satisfies RunRequest` would reject it under exactOptionalPropertyTypes, since RunRequest declares `expert_id?: string | null`. The generated createWorkSession ([generated.ts:9482-9483](../../../../packages/api-client/src/generated.ts#L9482)) shows that POST /v1/sessions returns SessionView.
- **Why it matters:** This is the paid admission path. If run_id, id or code is renamed or retyped, the code still compiles and fails quietly: the success link becomes /runs/undefined, and refusals fall to the generic message. The project's ESLint config does not flag these casts, so nothing stops more of them.
- **Recommendation:** Parse with the generated functions. Use parseSessionView for the session reply and parseRunAccepted for the 202. Call parseErrorResponse inside a readError(reply) helper that returns null for other bodies, such as an HTML error page; the API itself turns every validation failure into an ErrorResponse with status 422 ([api/errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29)). Treat a ContractError on a 202 as an unknown outcome (the run may exist), not a refusal. Declare the bodies with `satisfies RunRequest` and `satisfies SessionCreate`. Consider publishing the refusal codes as an enum on ErrorResponse in Pydantic and regenerating, so the Outcome union stops mirroring them by hand. Enable @typescript-eslint/consistent-type-assertions for app code, with narrow, documented exceptions.
- **Rule check:** DH-06 and rules/nextjs.md: generated API types plus explicit response parsing at untrusted boundaries, and no blanket type assertions; rules/contracts.md: TypeScript types do not validate JSON. The fix uses existing generated parsers and hand-edits nothing generated; any new enum is added in Pydantic and regenerated.
- **Verification:** revised. The five casts match eslint.json, apps/web/eslint.config.mjs enables only the Next presets, and the generated parsers sit at the cited lines. Corrected two details: the API answers every validation failure with an ErrorResponse 422 ([api/errors.py:29-32](../../../../services/agent/src/autobots/api/errors.py#L29)), so a FastAPI HTTPValidationError body never arrives; and an undefined expert_id is dropped by JSON.stringify, so the defect is the untyped body rather than a wrong value on the wire.

```tsx
async function readError(reply: Response): Promise<ErrorResponse | null> {
  try { return parseErrorResponse(await reply.json()); } catch { return null; }  // not an ErrorResponse, e.g. an HTML error page -> null
}
const body = { goal_text: draft, ...(sessionId === null ? {} : { session_id: sessionId }) } satisfies RunRequest;
const session = parseSessionView(await reply.json());    // POST /v1/sessions returns SessionView
const accepted = parseRunAccepted(await reply.json());   // ContractError on a 202 -> 'unknown', not 'refused'
```

### <a id="wcmp-03"></a>WCMP-03: GoalComposer is a 541-line component with 13 state hooks, three effects and inline submission

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/goal-composer.tsx:113-653](../../../../apps/web/components/goal-composer.tsx#L113): one function: 527 counted lines, complexity 37, 32 statements
  - [apps/web/components/goal-composer.tsx:128-140](../../../../apps/web/components/goal-composer.tsx#L128): 13 useState hooks
  - [apps/web/components/goal-composer.tsx:143-194](../../../../apps/web/components/goal-composer.tsx#L143): two fetch effects
  - [apps/web/components/goal-composer.tsx:196-216](../../../../apps/web/components/goal-composer.tsx#L196): budget math in render; unguarded loop at 199-205
  - [apps/web/components/goal-composer.tsx:218-245](../../../../apps/web/components/goal-composer.tsx#L218): file admission
  - [apps/web/components/goal-composer.tsx:276-341](../../../../apps/web/components/goal-composer.tsx#L276): run(): 65 lines, complexity 18
  - [apps/web/components/goal-composer.tsx:601-649](../../../../apps/web/components/goal-composer.tsx#L601): outcome as a nine-way nested ternary
  - [services/agent/src/autobots/contracts/settings.py:152](../../../../services/agent/src/autobots/contracts/settings.py#L152): step_micro_usd is a plain int with no minimum
- **Evidence:** Lines 113-653 hold the whole composer. They contain 13 useState hooks (128-140) and a store read (114); effects for focus (116-127), the option lists (143-166) and the preview (169-194); budget math in render (196-216); file admission (218-245); session start and admission (256-341); and 310 lines of JSX ending in a nine-way nested ternary (607-648). outcome, runId and refusal are separate hooks updated in pairs (277-278, 312-313, 323-324), so the queued branch still has to check runId === null (640). Budget choices come from `for (value = min; value <= max; value += step)` over server values (199-205), and the contract sets no minimum on step_micro_usd.
- **Why it matters:** Every change to a chip, a refusal or the attachments lands in one 37-branch function whose states must be kept consistent by hand. The admission and option-loading defects in this area are hidden inside it. Its pure parts can't be unit-tested where they are, and a zero step from the server would hang the render.
- **Recommendation:** Split by responsibility. Give the draft, the option lists, the preview, the attachments and admission their own hooks. Make budget choices and file admission pure, JSX-free functions; budget choices should reject step &lt;= 0 and cap the count. Move the markup into four presentational children. Use useReducer only for admission, where fields must change together; the rest of the state is independent. A form library would add little, because validation is one non-empty check plus the server's refusals. Fix admission first, with its tests, because composer.spec.ts pins the current behavior.
- **Rule check:** DH-06 asks for small cohesive modules and keeps UI view models distinct. The reducer models the admission request (idle, submitting, accepted, refused, unknown), not RunStatus, so it adds no second run-state enum; the run's state stays RunAccepted.status.
- **Verification:** confirmed. Counted 13 useState hooks, the store read, three effects and the nine-way outcome chain at the cited lines; run() matches eslint.json (65 lines, complexity 18), and git log shows 14 commits on the file. The zero-step hang is defensive: the API sends a fixed US$0.25 step today ([domain/budgets.py:7](../../../../services/agent/src/autobots/domain/budgets.py#L7)), though the contract does not forbid zero.

```text
GoalComposer (layout only, about 120 lines)
  useDraft()                        sessionStorage draft (33-44, 114, 128, 141, 247-254)
  useNewRunFocus()                  NEW_RUN_PARAM effect (116-127), beside focusGoal in new-run.tsx
  useRunOptions()                   experts and models with a status (143-166)
  useRunPreview(profile, expertId)  { status, preview } (169-194)
  useAttachments()                  over lib/attachments.ts: admitFiles(), inputPath(), limits (46-100, 218-245)
  useRunAdmission()                 shared reducer: idle | submitting | accepted | refused | unknown (256-341)
  lib/budget.ts budgetChoices(range, chosen) -> { choices, budget, exhausted }, rejects step <= 0 (196-212)
  <RunOptionChips/> 375-458   <PreviewChips/> 465-508   <AttachmentField/> 510-589   <AdmissionMessage/> 601-649
```

### <a id="wcmp-04"></a>WCMP-04: Run admission is implemented three times, with different refusal handling and announcements

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/goal-composer.tsx:322-340](../../../../apps/web/components/goal-composer.tsx#L322): maps budget_\*, model_not_offered, 422 and three credential codes
  - [apps/web/components/goal-composer.tsx:601-648](../../../../apps/web/components/goal-composer.tsx#L601): copy with settings links; role=alert even for a queued run (603)
  - [apps/web/components/session-panel.tsx:71-79](../../../../apps/web/components/session-panel.tsx#L71): three cases in a nested ternary
  - [apps/web/components/session-panel.tsx:195-207](../../../../apps/web/components/session-panel.tsx#L195): role=status for success, role=alert for problems
  - [apps/web/components/continue-run.tsx:65-71](../../../../apps/web/components/continue-run.tsx#L65): shows the server's message instead
- **Evidence:** [goal-composer.tsx:322-340](../../../../apps/web/components/goal-composer.tsx#L322) maps budget_\* codes, model_not_offered, a 422 and three credential codes to nine outcomes, three of which link to settings (609-630). [session-panel.tsx:71-79](../../../../apps/web/components/session-panel.tsx#L71) handles credentials_required (without the link), model_not_offered and a 422. There, credential_invalid, credential_unavailable and budget refusals all read 'That could not be started.' [continue-run.tsx:65-71](../../../../apps/web/components/continue-run.tsx#L65) shows failure.message. The composer announces a queued run with role=alert (603); the session panel uses role=status (196).
- **Why it matters:** The same server refusal reads differently, or loses its fix-it link, depending on which screen started the run, and a new refusal code needs three edits. Each copy also carries its own casts and key policy, which is how the duplicate-submit and parsing gaps spread.
- **Recommendation:** Put the request, parsing and refusal mapping in a JSX-free lib/run-admission.ts that returns a discriminated result. Render that result with one AdmissionMessage component: role=status when accepted, role=alert for refusals, and the settings links in one place. GoalComposer, SessionPanel and ContinueRun then supply only their RunRequest body. Do this together with the duplicate-submit and parsing fixes, which need the same module.
- **Rule check:** DH-06: centralize error handling and avoid duplicated business rules. The mapping still comes from the server's codes, so no client rule is invented and admission remains a server decision.
- **Verification:** confirmed. Compared the three mappings side by side: only the composer links to settings, the session panel folds credential_invalid, credential_unavailable and budget refusals into one sentence, and the composer announces a queued run with role=alert.

```tsx
// lib/run-admission.ts
export type AdmissionResult =
  | { kind: 'accepted'; accepted: RunAccepted }
  | { kind: 'refused'; refusal: Refusal; message: string | null }  // the codes the screens map today
  | { kind: 'unknown' };                                              // null reply or 5xx
export async function admitRun(body: RunRequest, key: string): Promise<AdmissionResult>
// components/admission-message.tsx
<AdmissionMessage result={result} />  // role=status when accepted, role=alert for refusals
```

### <a id="wcmp-05"></a>WCMP-05: Failures render as signed out, empty results or nothing

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/app/page.tsx:71-80](../../../../apps/web/app/page.tsx#L71): a null session renders 'Signed out' and 'You are not signed in.'; Sign in link at 90-96
  - [apps/web/lib/service-status.ts:52-61](../../../../apps/web/lib/service-status.ts#L52): fetchSession returns null when signed out and on any API failure
  - [apps/web/components/search-palette.tsx:75-79](../../../../apps/web/components/search-palette.tsx#L75): a refused reply becomes an empty result list
  - [apps/web/components/search-palette.tsx:83-87](../../../../apps/web/components/search-palette.tsx#L83): a network failure does too
  - [apps/web/components/search-palette.tsx:211-212](../../../../apps/web/components/search-palette.tsx#L211): which then reads 'Nothing in this workspace matches.'
  - [apps/web/components/goal-composer.tsx:151-162](../../../../apps/web/components/goal-composer.tsx#L151): option-list refusals are drained and dropped, and errors are swallowed
- **Evidence:** page.tsx branches six times on session === null (42, 59, 71, 75, 79, 90). fetchSession returns null from its catch ([lib/service-status.ts:58-59](../../../../apps/web/lib/service-status.ts#L58)) when the API is unreachable, so a signed-in user with the API down sees 'Signed out', 'You are not signed in.' and a Sign in button. In search, a refused reply yields an empty list through `reply.ok ? parseSearchResults(...).results : []` ([search-palette.tsx:75-77](../../../../apps/web/components/search-palette.tsx#L75)), the catch does the same (83-87), and both show 'Nothing in this workspace matches.' (211-212). In the composer, a refused experts or models read is drained and nothing else happens, and `.catch(() => undefined)` (162) swallows network and ContractError failures. The selects then offer only their defaults, with no message.
- **Why it matters:** When the local API is down, the app tells the user to sign in, says nothing matches, or says nothing at all, which sends the user to the wrong fix. These are the states DH-06 asks to keep apart.
- **Recommendation:** Return a discriminated result from the session read (signed_out, signed_in or unavailable), and when it is unavailable, show that the account can't be checked instead of offering Sign in. Give search a failed status with its own message. Show one line under the chips when experts or models can't be read, so the user knows the lists are incomplete. The shared resource hook in the fetch-effect finding provides the failed state.
- **Rule check:** DH-06: represent loading, empty, denied, unavailable and retryable states deliberately; rules/nextjs.md: explicit error, empty and loading states. Error details stay on the server, as fetchServiceStatus already keeps them.
- **Verification:** confirmed. fetchSession's catch returns null, so an unreachable API renders 'Signed out' and a Sign in link. The Services section on the same page does show 'Python API: unavailable', which softens the contradiction but does not remove it. The search and option-list paths behave as stated.

```tsx
// lib/service-status.ts
export type SessionState =
  | { kind: 'signed_out' }
  | { kind: 'signed_in'; session: SessionSummary }
  | { kind: 'unavailable' };
// search: useSearch(query) -> { status: 'idle' | 'searching' | 'ready' | 'failed'; results }
// composer: useRunOptions() -> { status: 'loading' | 'ready' | 'failed'; experts; models }
```

### <a id="wcmp-06"></a>WCMP-06: The waiting notifier stops polling for good after a 401 or a rejected reply

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/waiting-notifier.tsx:66-69](../../../../apps/web/components/waiting-notifier.tsx#L66): a 401 or 403 returns without scheduling the next poll
  - [apps/web/app/layout.tsx:30](../../../../apps/web/app/layout.tsx#L30): mounted once in the root layout, so client navigation never remounts it
  - [apps/web/components/sign-in-form.tsx:31-32](../../../../apps/web/components/sign-in-form.tsx#L31): sign-in is router.push plus router.refresh, not a page load
  - [apps/web/components/waiting-notifier.tsx:47-49](../../../../apps/web/components/waiting-notifier.tsx#L47): bad JSON or a ContractError rejects poll(), so line 71 is never reached
  - [apps/web/components/waiting-notifier.tsx:36](../../../../apps/web/components/waiting-notifier.tsx#L36): timer is undefined while a request is in flight
  - [apps/web/components/waiting-notifier.tsx:74-78](../../../../apps/web/components/waiting-notifier.tsx#L74): so restart() during a request starts a second loop
  - [apps/web/components/waiting-notifier.tsx:71](../../../../apps/web/components/waiting-notifier.tsx#L71): fixed 4 s interval and no backoff while the API is down
- **Evidence:** poll() sets timer = undefined (36), awaits the fetch, and reschedules only at its end (71). A 401 or 403 returns first (69). The comment at 68 expects the page to reload and restart it, but sign-in navigates client-side ([sign-in-form.tsx:31-32](../../../../apps/web/components/sign-in-form.tsx#L31)), and the notifier lives in the root layout ([layout.tsx:30](../../../../apps/web/app/layout.tsx#L30)) with an effect keyed on the stable router, so nothing restarts it. parseRunList(await reply.json()) (47) is outside any try, and poll runs as `void poll()`, so a rejected reply ends the loop with an unhandled rejection. restart() cannot cancel an in-flight poll, because the timer it checks at 75 is undefined then. Toggling the setting off and on within one request therefore leaves two loops. Failures retry every 4 s indefinitely.
- **Why it matters:** With the setting on, notifications silently stop until a reload after the user signs out and back in, or opens the app on an expired session. That disables PRD-Studio SE-05. One reply the parser rejects has the same effect. The forked loop and the missing backoff are rarer and cheaper, but come from the same structure.
- **Recommendation:** Make every exit path schedule the next poll: wrap each poll in try/finally, back off after failures (doubling from 4 s up to a cap, reset on success), and either retry slowly after a 401 or 403 (for example every 60 s) or remount the notifier when the signed-in user changes. Add a generation counter that restart() increments, so a stale poll never reschedules. Extract the newly-waiting diff as a pure function with unit tests, and cover the loop with fake timers instead of the fixed five-second waits in tests/browser/settings-sections.spec.ts.
- **Rule check:** PRD-Studio SE-05: read only the app's own API and raise one notification per newly waiting run; both stay. The loop only reads, so it schedules no business work in the browser (DH-06).
- **Verification:** confirmed. Traced every exit path: a 401 or 403 returns before line 71, a parser rejection escapes `void poll()`, and restart() cannot clear a poll in flight, so a second loop starts. The effect depends only on the stable router, and sign-in is client-side, so the root-layout notifier is never restarted.

```tsx
// lib/waiting.ts (pure, unit-tested)
export function newlyWaiting(seen: ReadonlySet<string> | null, runs: readonly RunListItem[]): { fresh: RunListItem[]; seen: Set<string> }
// waiting-notifier.tsx
let generation = 0; let failures = 0;
async function tick(mine: number): Promise<void> {
  let delay = EVERY_MS;
  try { delay = await pollOnce(); failures = 0; }                 // EVERY_MS, or SIGNED_OUT_MS after 401/403
  catch { failures += 1; delay = Math.min(EVERY_MS * 2 ** failures, MAX_MS); }
  finally { if (!stopped && mine === generation) timer = setTimeout(() => void tick(mine), delay); }
}
function restart(): void { generation += 1; clearTimeout(timer); seen = null; void tick(generation); }
```

### <a id="wcmp-07"></a>WCMP-07: Read-only home, data and session views fetch in client effects data their dynamic pages could render

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/home-activity.tsx:56-90](../../../../apps/web/components/home-activity.tsx#L56): no interaction; three client reads in an effect
  - [apps/web/components/data-summary.tsx:18-39](../../../../apps/web/components/data-summary.tsx#L18): no interaction; one client read
  - [apps/web/components/session-panel.tsx:24-43](../../../../apps/web/components/session-panel.tsx#L24): the session the page could pass in
  - [apps/web/components/home-activity.tsx:68](../../../../apps/web/components/home-activity.tsx#L68): /api/v1/runs at the default limit of 100 to show five (191)
  - [apps/web/app/page.tsx:33-38](../../../../apps/web/app/page.tsx#L33): the page awaits four reads with no Suspense boundary
  - [apps/web/app/page.tsx:36](../../../../apps/web/app/page.tsx#L36): readiness is read again by the shell ([app-shell.tsx:19](../../../../apps/web/components/app-shell.tsx#L19)) with no cache()
  - [apps/web/lib/service-status.ts:33](../../../../apps/web/lib/service-status.ts#L33): the server-only member client these reads would use
- **Evidence:** HomeActivity and DataSummary have no event handlers. They are Client Components only so they can fetch in an effect, so they render 'Loading.' first and carry their own failure branches. HomeActivity also needs three non-null assertions (79-81). The generated client already has server operations for these reads: getRetentionSummary, getWorkSession and listApprovals ([packages/api-client/src/generated.ts:9386](../../../../packages/api-client/src/generated.ts#L9386), 9486 and 9294). lib/service-status.ts already builds the member clients they need. Recent runs downloads up to 100 runs to show five (68, 191), although the endpoint accepts limit. On the server, page.tsx blocks on four reads before anything streams, and fetchReadiness runs twice per render ([page.tsx:36](../../../../apps/web/app/page.tsx#L36), [app-shell.tsx:19](../../../../apps/web/components/app-shell.tsx#L19)).
- **Why it matters:** Each of these views adds a round trip through the BFF and a loading flash for data the server can read with a typed client, and each duplicates effect code. On Home, the slowest read delays the composer, which needs none of them.
- **Recommendation:** Make HomeActivity and DataSummary async Server Components. Feed them from server-only helpers beside fetchReadiness: needs-you runs, five recent runs with limit=5 and pending approvals for Home, and the retention summary for the data page. Pass SessionPanel a server-read SessionView so it keeps only the form. Move the home page's own reads into Suspense-wrapped sections so the composer streams first. Wrap fetchReadiness and fetchSession in React cache() so the shell and the page share one read per request. The generated listRuns takes no query parameters, so its helper uses requestJson plus parseRunList until the generator supports them.
- **Rule check:** DH-06: prefer Server Components, use Client Components for actual interaction, and keep workspace data out of shared caches. The reads stay per request (the session cookie makes the pages dynamic, and the reads use no-store) and go through the existing server-only member client.
- **Verification:** confirmed. HomeActivity and DataSummary have no handlers; getRetentionSummary, getWorkSession and listApprovals exist at the cited lines, and /api/v1/runs defaults to RUN_LIST_SIZE = 100 ([run_projection.py:55](../../../../services/agent/src/autobots/application/run_projection.py#L55)). The second readiness read was inferred from the two call sites, not measured.

```tsx
// app/page.tsx (Server Component)
<GoalComposer />
<Suspense fallback={<ActivityLoading />}>
  <HomeActivity />   // async: needs-you runs, five recent runs and approvals, parsed, via the member client
</Suspense>
// app/settings/data/page.tsx: <DataSummary summary={await fetchRetentionSummary()} />
// app/sessions/[id]/page.tsx: <SessionPanel session={await fetchWorkSession(id)} />  // the panel keeps only the form
// lib/service-status.ts: export const fetchReadiness = cache(async () => { ... })
```

### <a id="wcmp-08"></a>WCMP-08: Every client read writes its own fetch effect, and the copies already disagree

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 8
- **Where:**
  - [apps/web/components/goal-composer.tsx:143-166](../../../../apps/web/components/goal-composer.tsx#L143): option lists
  - [apps/web/components/goal-composer.tsx:169-194](../../../../apps/web/components/goal-composer.tsx#L169): preview
  - [apps/web/components/search-palette.tsx:65-94](../../../../apps/web/components/search-palette.tsx#L65): search
  - [apps/web/components/jobs-chart.tsx:85-102](../../../../apps/web/components/jobs-chart.tsx#L85): job counts
  - [apps/web/components/data-summary.tsx:22-39](../../../../apps/web/components/data-summary.tsx#L22): retention
  - [apps/web/components/session-panel.tsx:31-33](../../../../apps/web/components/session-panel.tsx#L31): the refused body is never read
  - [apps/web/components/home-activity.tsx:73](../../../../apps/web/components/home-activity.tsx#L73): says why a refused body must be read
  - [apps/web/components/goal-composer.tsx:147](../../../../apps/web/components/goal-composer.tsx#L147): /api/models, which the child RunDisclosure fetches again ([run-disclosure.tsx:47](../../../../apps/web/components/run-disclosure.tsx#L47))
- **Evidence:** Eight effects in this area repeat the same shape: a `let live = true`, `let active = true` or `let stopped = false` flag, a no-store fetch, parse on ok, drain on refusal, then a failed flag. They are at [goal-composer.tsx:144](../../../../apps/web/components/goal-composer.tsx#L144) and 170, [home-activity.tsx:64](../../../../apps/web/components/home-activity.tsx#L64), [jobs-chart.tsx:86](../../../../apps/web/components/jobs-chart.tsx#L86), [data-summary.tsx:23](../../../../apps/web/components/data-summary.tsx#L23), [search-palette.tsx:68](../../../../apps/web/components/search-palette.tsx#L68), [session-panel.tsx:25](../../../../apps/web/components/session-panel.tsx#L25) and [waiting-notifier.tsx:28](../../../../apps/web/components/waiting-notifier.tsx#L28). A grep for those flags finds 29 in 24 files under apps/web components, app and lib. [home-activity.tsx:73](../../../../apps/web/components/home-activity.tsx#L73) says an unread refusal keeps its connection open, yet [session-panel.tsx:31-33](../../../../apps/web/components/session-panel.tsx#L31) never reads the refused body, and every `if (!live) return` exits before reading. The composer and its RunDisclosure child each fetch /api/models on mount.
- **Why it matters:** Each copy decides liveness, body handling, error typing and the failure state again. A fix like the ones in the failure-state finding must be repeated eight times in this area and 29 times across the app, and the copies have already drifted.
- **Recommendation:** Add one hook, useApiResource(url, parse). It should abort with an AbortController on cleanup (which also releases the connection), cancel refused bodies, turn a ContractError into the failed state, and return a discriminated state. Use it for the reads that must stay client-side here: the composer's option lists and preview, search, and the jobs chart inside the client OperationsPanel. Pass the models list from GoalComposer to RunDisclosure instead of fetching it twice.
- **Rule check:** DH-06: centralize error handling; rules/nextjs.md: explicit error, empty and loading states. The hook only reads, and the generated parsers remain the validation step.
- **Verification:** confirmed. Recounted 29 liveness flags in 24 files (grep for `let live = true`, `let active = true` and `let stopped = false`); [session-panel.tsx:31-33](../../../../apps/web/components/session-panel.tsx#L31) does not read the refused body, and both the composer and RunDisclosure request /api/models.

```tsx
// lib/use-api-resource.ts
export type Resource<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'failed'; httpStatus: number | null };
export function useApiResource<T>(url: string | null, parse: (value: unknown) => T): Resource<T>
// one AbortController per url, aborted on cleanup; a refused body is cancelled; ContractError -> failed
```

### <a id="wcmp-10"></a>WCMP-10: SearchPalette puts the shortcut, dialog, debounced search, key handling and status in one function

- **Severity** medium · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/search-palette.tsx:49-63](../../../../apps/web/components/search-palette.tsx#L49): global ⌘K listener
  - [apps/web/components/search-palette.tsx:65-94](../../../../apps/web/components/search-palette.tsx#L65): debounced search, with a 150 ms literal at 89
  - [apps/web/components/search-palette.tsx:151-163](../../../../apps/web/components/search-palette.tsx#L151): arrow and Enter handling inline in JSX
  - [apps/web/components/search-palette.tsx:207-213](../../../../apps/web/components/search-palette.tsx#L207): four-way status ternary
  - [apps/web/components/search-palette.tsx:108](../../../../apps/web/components/search-palette.tsx#L108): old results stay selectable while a new term is pending (Enter at 159-161)
  - [apps/web/components/search-palette.tsx:115](../../../../apps/web/components/search-palette.tsx#L115): aria-keyshortcuts and the ⌘K label (121-126) are hard-coded
  - [apps/web/lib/shortcuts.ts:15](../../../../apps/web/lib/shortcuts.ts#L15): the Settings list repeats ⌘K by hand
- **Evidence:** SearchPalette (24-218, 189 counted lines) handles opening the dialog and returning focus (35-47, 103-106), the global shortcut (49-63), the debounced fetch (65-94), arrow wrap-around and Enter (151-163), and the status text (207-213). The shortcut is defined three times: in the key matcher (52-55), in aria-keyshortcuts and the kbd label (115, 121-126), and in the SE-07 registry entry ([lib/shortcuts.ts:14-17](../../../../apps/web/lib/shortcuts.ts#L14)). `shown` holds the current results whenever the query is non-empty (108), so while 'Searching.' is announced, Enter opens a result for the previous term.
- **Why it matters:** The keyboard behavior is correct today, but none of it can be unit-tested inline. A shortcut change needs three coordinated edits, and typing quickly then pressing Enter opens a stale result.
- **Recommendation:** Extract three pieces: a useSearch(query) hook returning { status, term, results }, with a failed status (see the failure-state finding); a pure moveActive(current, key, count) in lib/keyboard.ts; and a useShortcut(match, handler) hook shared with NewRun's ⇧⌘O. Give each SHORTCUTS entry its matcher and aria-keyshortcuts value. Let Enter act only when the results belong to the current term, and ignore keys during IME composition.
- **Rule check:** Decision 0022 D3 (⌘K opens search, and no shortcut acts in a text field) and PRD-Studio SE-07 (every shortcut in one list) stay true; the registry becomes the single source instead of a manual copy.
- **Verification:** confirmed. With the previous results still in `shown` while 'Searching.' is announced, Enter calls go(shown[active]) for the old term (108, 159-161). The ⌘K definition appears at 52-55, 115, 121-126 and [lib/shortcuts.ts:14-17](../../../../apps/web/lib/shortcuts.ts#L14).

```tsx
useShortcut(SHORTCUTS.search, open)  // matcher and aria-keyshortcuts beside the label in lib/shortcuts.ts; NewRun reuses it for ⇧⌘O
const search = useSearch(query)       // { status: 'idle' | 'searching' | 'ready' | 'failed'; term; results }, debounced, aborted on change
moveActive(current, key, count)       // pure, lib/keyboard.ts
<SearchResults search={search} active={active} />  <SearchStatus search={search} />
// SearchPalette keeps the dialog, open/close and focus return
```

### <a id="wcmp-11"></a>WCMP-11: Pure logic lives in .tsx files the unit runner can't load, so it is untested or tested only in the browser

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 10
- **Where:**
  - [apps/web/components/goal-composer.tsx:88-100](../../../../apps/web/components/goal-composer.tsx#L88): inputPath; also fileSize (68), budget steps (196-212) and refusal mapping (318-340)
  - [apps/web/components/home-activity.tsx:24-48](../../../../apps/web/components/home-activity.tsx#L24): relative and progressOrSpend
  - [apps/web/components/jobs-chart.tsx:66-70](../../../../apps/web/components/jobs-chart.tsx#L66): ticks
  - [apps/web/components/waiting-notifier.tsx:50-64](../../../../apps/web/components/waiting-notifier.tsx#L50): the newly-waiting diff, inline
  - [apps/web/components/home-greeting.tsx:7-23](../../../../apps/web/components/home-greeting.tsx#L7): greetingFor, exported but exercised only by browser page loads
  - [apps/web/tests/browser/home.spec.ts:70-84](../../../../apps/web/tests/browser/home.spec.ts#L70): one sign-in, then six page loads test the greeting's hour boundaries
  - [apps/web/lib/schema-value.ts:1-2](../../../../apps/web/lib/schema-value.ts#L1): the repo's pattern: 'Pure, so it can be tested without a browser.'
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): node --test runs two named files; tests/unit/schema-value.test.ts is not one of them
- **Evidence:** Ten pure helpers sit in client components, counted by reading the area's files: fileSize, inputPath, the budget-step loop and the refusal mapping (goal-composer); relative and progressOrSpend (home-activity); ticks and total (jobs-chart); the waiting diff (waiting-notifier); and greetingFor (home-greeting). The unit runner is `node --test` over listed .ts files ([scripts/verify.py:161-162](../../../../scripts/verify.py#L161)). It can load neither JSX nor the @/ alias, so none of these helpers can be imported. lib/schema-value.ts with tests/unit/schema-value.test.ts shows the intended shape. The greeting's boundaries are tested by one sign-in and six page loads under a fixed clock ([home.spec.ts:70-84](../../../../apps/web/tests/browser/home.spec.ts#L70)).
- **Why it matters:** Edge cases that matter have no fast test: path collisions and the 180-character cut, a zero budget step, each refusal code, the hour boundaries, a run that waits again. The only way to cover them today is the db profile with seeded users.
- **Recommendation:** Move each helper to a JSX-free lib/\*.ts module with relative imports, and add node:test files beside tests/unit/schema-value.test.ts. Have the web_unit_tests step in scripts/verify.py glob tests/unit/\*.test.ts, so a new file can't be skipped the way schema-value.test.ts is today. Keep the browser specs for the user flows.
- **Rule check:** DH-06 asks for unit tests of pure and client behavior and names Vitest. This uses the node:test runner the repo already has, so no dependency is added. Changing scripts/verify.py is a separate authorized work item.
- **Verification:** revised. The ten helpers, the two-file runner list and the unrun schema-value.test.ts are confirmed (no other script or Makefile target runs it). Corrected the greeting test: it signs in once and loads the page six times ([home.spec.ts:70-84](../../../../apps/web/tests/browser/home.spec.ts#L70)), not six sign-ins.

```text
apps/web/lib/attachments.ts    admitFiles(kept, chosen), inputPath(), MEDIA_TYPES, limits
apps/web/lib/budget.ts         budgetChoices(range, chosen)
apps/web/lib/run-admission.ts  refusal mapping
apps/web/lib/format.ts         formatUsd, formatRelative, formatBytes, greetingFor
apps/web/lib/jobs-layout.ts    ticks, layoutJobs
apps/web/lib/waiting.ts        newlyWaiting
apps/web/tests/unit/*.test.ts  node:test, picked up by a glob in scripts/verify.py
```

### <a id="wcmp-12"></a>WCMP-12: Money and relative-time formatting is copied per component and differs between screens

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 13
- **Where:**
  - [apps/web/components/goal-composer.tsx:74-76](../../../../apps/web/components/goal-composer.tsx#L74): dollars
  - [apps/web/components/home-activity.tsx:34-36](../../../../apps/web/components/home-activity.tsx#L34): dollars, identical
  - [apps/web/components/home-activity.tsx:24-32](../../../../apps/web/components/home-activity.tsx#L24): relative
  - [apps/web/components/run-list.tsx:87](../../../../apps/web/components/run-list.tsx#L87): dollars, identical (also [workflows-panel.tsx:50](../../../../apps/web/components/workflows-panel.tsx#L50))
  - [apps/web/components/run-panel.tsx:30](../../../../apps/web/components/run-panel.tsx#L30): dollars, identical
  - [apps/web/components/run-inspector.tsx:10-11](../../../../apps/web/components/run-inspector.tsx#L10): dollars without rounding
  - [apps/web/components/workflows-panel.tsx:36-47](../../../../apps/web/components/workflows-panel.tsx#L36): relative, identical to Home's
  - [apps/web/components/approvals-panel.tsx:88-97](../../../../apps/web/components/approvals-panel.tsx#L88): relative in a shorter style ('5 min ago')
- **Evidence:** The same `function dollars(micro)`, returning US$ plus `(micro / 1_000_000).toFixed(2)`, is copied in [goal-composer.tsx:74](../../../../apps/web/components/goal-composer.tsx#L74), [home-activity.tsx:34](../../../../apps/web/components/home-activity.tsx#L34), [run-list.tsx:87](../../../../apps/web/components/run-list.tsx#L87), [run-panel.tsx:30](../../../../apps/web/components/run-panel.tsx#L30) and [workflows-panel.tsx:50](../../../../apps/web/components/workflows-panel.tsx#L50). [run-inspector.tsx:10-11](../../../../apps/web/components/run-inspector.tsx#L10) prints the value unrounded. [model-policy-panel.tsx:34](../../../../apps/web/components/model-policy-panel.tsx#L34), [workflow-editor.tsx:658](../../../../apps/web/components/workflow-editor.tsx#L658), [run-workspace.tsx:803](../../../../apps/web/components/run-workspace.tsx#L803) and [run-disclosure.tsx:97](../../../../apps/web/components/run-disclosure.tsx#L97) format inline, for 10 sites in total. relative() is identical in [home-activity.tsx:24-32](../../../../apps/web/components/home-activity.tsx#L24) and [workflows-panel.tsx:36-47](../../../../apps/web/components/workflows-panel.tsx#L36), while [approvals-panel.tsx:88-97](../../../../apps/web/components/approvals-panel.tsx#L88) prints a shorter form, for 3 functions. Counted by grep under apps/web for 'function dollars', '/ 1_000_000' and 'function relative'.
- **Why it matters:** Screens disagree on how a micro-dollar amount reads (cents on Home, unrounded in the inspector, locale-formatted in model policy) and how a time reads ('5 minutes ago' on Home, '5 min ago' on Approvals). A change to money or time display touches up to ten files.
- **Recommendation:** Add lib/format.ts with formatUsd (and MICRO_USD), formatRelative and formatBytes, unit-test it, and replace the copies, starting with this area's two. Keep the '≈' estimate marker in the caller ([home-activity.tsx:45-47](../../../../apps/web/components/home-activity.tsx#L45)), so estimated and reported costs stay distinct.
- **Rule check:** DS-04: estimated and reported costs remain distinct. The formatter only formats a number; callers still decide when a value is an estimate.
- **Verification:** confirmed. grep found the five identical dollars(), the unrounded inspector copy, four inline sites and three relative() functions, as stated. WRUN-10 proposes the same lib/format.ts for the run screens.

```tsx
// lib/format.ts
export const MICRO_USD = 1_000_000;
export function formatUsd(micro: number): string         // 'US$0.07'
export function formatRelative(iso: string, now: number): string
export function formatBytes(bytes: number): string
```

### <a id="wcmp-09"></a>WCMP-09: JobsPlot mixes scale math and SVG rendering in one 252-line function

- **Severity** low · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/jobs-chart.tsx:133-385](../../../../apps/web/components/jobs-chart.tsx#L133): JobsPlot: 252 counted lines; the file is 366 counted lines
  - [apps/web/components/jobs-chart.tsx:142-151](../../../../apps/web/components/jobs-chart.tsx#L142): scale computed in render
  - [apps/web/components/jobs-chart.tsx:214](../../../../apps/web/components/jobs-chart.tsx#L214): bar x, repeated at 252
  - [apps/web/components/jobs-chart.tsx:253-271](../../../../apps/web/components/jobs-chart.tsx#L253): segments stacked by mutating base inside map
  - [apps/web/components/jobs-chart.tsx:230](../../../../apps/web/components/jobs-chart.tsx#L230): ticks(tallest) recomputed (first at 144)
  - [apps/web/components/jobs-chart.tsx:194](../../../../apps/web/components/jobs-chart.tsx#L194): fixed SVG ids (also 186, 217 and 265)
  - [apps/web/components/jobs-chart.tsx:83](../../../../apps/web/components/jobs-chart.tsx#L83): hover state owned by JobsChart but used only by JobsPlot (127)
- **Evidence:** After computing tallest, scaleTop, band, barWidth and y (142-151), JobsPlot repeats geometry inline. `LEFT + index * band + (band - barWidth) / 2` appears at 214 and 252, and `LEFT + index * band` at 258, 288, 299 and 316. ticks(tallest) runs at 144 and again at 230. Segment positions come from a `let base` mutated inside the SERIES map (253-271). Pattern and clip ids are fixed strings (jobs-${key}, jobs-bar-${index}, jobs-plot-title).
- **Why it matters:** A change to padding, gaps or label spacing touches several places in the JSX, and the stacking and tick rules can be checked only through operations-jobs.spec.ts on the db profile. The fixed ids would collide if the chart ever rendered twice on one page.
- **Recommendation:** Move the layout into a pure lib/jobs-layout.ts that returns ticks, bars and segments in plot coordinates. Unit-test it with no hours, all-zero counts and one tall hour, and render from it in small components. Keep the documented status tokens, textures and table unchanged. Prefix the SVG ids with useId(), and let JobsPlot own its hover state.
- **Rule check:** DS-03 and DS-04, with Decision 0021 R4 and Decision 0022 D14: the status tokens, textures and equivalent table stay; only where the math lives changes.
- **Verification:** revised. The repeated geometry, the second ticks() call, the mutated base and the fixed ids are where stated. Lowered from medium to low: the file has one commit (US-15.19), renders once, and operations-jobs.spec.ts covers it, so this is polish until the chart next changes.

```tsx
// lib/jobs-layout.ts (pure, node:test)
export function layoutJobs(hours: readonly JobHour[], frame: Frame): {
  ticks: { value: number; y: number }[];
  bars: { index: number; bandX: number; x: number; width: number; top: number;
          segments: { key: SeriesKey; y: number; height: number }[] }[];
  sums: Record<SeriesKey, number>;
}
// jobs-chart.tsx: JobsChart (fetch, states) -> JobsPlot (owns hover, useId() prefix)
//   -> JobsLegend 158-177, JobsBars 179-309, JobsTooltip 310-330, JobsTable 332-382
```

### <a id="wcmp-13"></a>WCMP-13: The composer copies the server's default budget and imports shared constants from other feature components

- **Severity** low · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/goal-composer.tsx:17-20](../../../../apps/web/components/goal-composer.tsx#L17): DEFAULT_BUDGET_MICRO_USD imported from [run-disclosure.tsx:20](../../../../apps/web/components/run-disclosure.tsx#L20)
  - [apps/web/components/goal-composer.tsx:209-212](../../../../apps/web/components/goal-composer.tsx#L209): used whenever no range is known
  - [apps/web/components/goal-composer.tsx:296](../../../../apps/web/components/goal-composer.tsx#L296): a budget is always sent
  - [services/agent/src/autobots/domain/budgets.py:8](../../../../services/agent/src/autobots/domain/budgets.py#L8): the server's own default
  - [apps/web/components/home-activity.tsx:13](../../../../apps/web/components/home-activity.tsx#L13): STATUS_TEXT imported from [run-list.tsx:16](../../../../apps/web/components/run-list.tsx#L16)
  - [apps/web/components/new-run.tsx:12](../../../../apps/web/components/new-run.tsx#L12): focusGoal finds the composer's textarea by the literal id 'goal' ([goal-composer.tsx:362](../../../../apps/web/components/goal-composer.tsx#L362) and 368)
- **Evidence:** While there is no preview range (still loading, or failed), budget falls back to DEFAULT_BUDGET_MICRO_USD = 1_000_000 from [run-disclosure.tsx:20](../../../../apps/web/components/run-disclosure.tsx#L20). That is a copy of D11's default, BUDGET_DEFAULT_MICRO_USD in [domain/budgets.py:8](../../../../services/agent/src/autobots/domain/budgets.py#L8), and run() always sends it as budget_micro_usd (296). SessionPanel sends no budget, so the API applies RunRequest.limit_micro_usd's own default ([contracts/run_commands.py:24](../../../../services/agent/src/autobots/contracts/run_commands.py#L24), also US$1.00) and skips require_budget's range, step and daily-cap checks. Home imports its run labels from run-list.tsx, another feature component, and [new-run.tsx:12](../../../../apps/web/components/new-run.tsx#L12) is coupled to goal-composer.tsx through the string 'goal'.
- **Why it matters:** D11's US$1.00 default is written twice in the API and twice in the client ([run-disclosure.tsx:20](../../../../apps/web/components/run-disclosure.tsx#L20), [workflow-editor.tsx:118](../../../../apps/web/components/workflow-editor.tsx#L118)), so a change must find every copy, and the two run forms already take different budget paths. Renaming the textarea id breaks ⇧⌘O without a type error.
- **Recommendation:** Import the fallback from one module (lib/runs/budget.ts) that names its source, D11. Omitting budget_micro_usd is not a drop-in fix: the API would apply the limit default and skip the daily-cap check, as it does for SessionPanel, so whether the composer may start a run while no range is known is a product decision. Move run status labels and tones to lib/runs/run-status.ts (WRUN-08). Export a GOAL_FIELD_ID beside focusGoal and use it for the composer's label and textarea.
- **Rule check:** DH-06: avoid duplicated business rules. The server stays the owner of the default budget, and the client only displays it.
- **Verification:** revised. The import, the fallback and the 'goal' coupling are as stated. Revised the recommendation: omitting the budget, as first proposed, makes the API fall back to limit_micro_usd's default ([contracts/run_commands.py:24](../../../../services/agent/src/autobots/contracts/run_commands.py#L24)) and skip require_budget ([run_routes.py:188-197](../../../../services/agent/src/autobots/api/run_routes.py#L188)). Aligned the status module with WRUN-08.

### <a id="wcmp-14"></a>WCMP-14: Status label maps are keyed by string instead of the generated RunStatus union

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/waiting-notifier.tsx:14-17](../../../../apps/web/components/waiting-notifier.tsx#L14): WAITING: Record&lt;string, string&gt;
  - [apps/web/components/waiting-notifier.tsx:55](../../../../apps/web/components/waiting-notifier.tsx#L55): ?? '' covers a lookup that the filter at 48 already guarantees
  - [apps/web/components/home-activity.tsx:201](../../../../apps/web/components/home-activity.tsx#L201): STATUS_TEXT[run.status] ?? run.status
  - [apps/web/components/run-list.tsx:16](../../../../apps/web/components/run-list.tsx#L16): STATUS_TEXT: Record&lt;string, string&gt;
  - [apps/web/components/search-palette.tsx:14-19](../../../../apps/web/components/search-palette.tsx#L14): the right shape: keyed by the generated kind union
  - [apps/web/components/goal-composer.tsx:102-111](../../../../apps/web/components/goal-composer.tsx#L102): Outcome restates server error codes by hand; ErrorResponse.code is a plain string
  - [packages/api-client/src/runtime.ts:106](../../../../packages/api-client/src/runtime.ts#L106): the parser already rejects statuses outside the enum
- **Evidence:** RunStatus is generated ([generated.ts:8691](../../../../packages/api-client/src/generated.ts#L8691)), and parseRunList rejects unknown values ([runtime.ts:106](../../../../packages/api-client/src/runtime.ts#L106)). Even so, WAITING and STATUS_TEXT accept any string key, and readers add fallbacks ([waiting-notifier.tsx:55](../../../../apps/web/components/waiting-notifier.tsx#L55), [home-activity.tsx:201](../../../../apps/web/components/home-activity.tsx#L201)). [search-palette.tsx:14](../../../../apps/web/components/search-palette.tsx#L14) shows the exhaustive form, Record&lt;Result['kind'], string&gt;. The composer's Outcome union (102-111) restates server codes because ErrorResponse.code is typed string ([generated.ts:7693-7696](../../../../packages/api-client/src/generated.ts#L7693)).
- **Why it matters:** Adding or renaming a run status compiles cleanly while a label silently disappears or falls back to the raw snake_case value.
- **Recommendation:** Type STATUS_TEXT as Record&lt;RunStatus, string&gt; and WAITING as Partial&lt;Record&lt;RunStatus, string&gt;&gt; with a type guard, then drop the fallbacks. For Outcome, see the enum suggested in the parsing finding.
- **Rule check:** DH-06: do not invent a second state enum for the UI. These maps label the generated RunStatus instead of redefining it, and the parser already handles unknown values.
- **Verification:** confirmed. Maps and fallbacks confirmed; parseRunList rejects statuses outside the enum ([runtime.ts:106](../../../../packages/api-client/src/runtime.ts#L106)), so the fallbacks guard only the type.

### <a id="wcmp-15"></a>WCMP-15: Home's hairline sections are assembled by hand four times

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/app/page.tsx:62-77](../../../../apps/web/app/page.tsx#L62): Account header
  - [apps/web/app/page.tsx:103-111](../../../../apps/web/app/page.tsx#L103): Services header
  - [apps/web/components/home-activity.tsx:113-121](../../../../apps/web/components/home-activity.tsx#L113): Needs you header
  - [apps/web/components/home-activity.tsx:176-184](../../../../apps/web/components/home-activity.tsx#L176): Recent runs header
  - [apps/web/app/page.tsx:27-30](../../../../apps/web/app/page.tsx#L27): LOWER_HEAD is the same string as HEAD in [home-activity.tsx:50](../../../../apps/web/components/home-activity.tsx#L50)
  - [apps/web/app/page.tsx:42](../../../../apps/web/app/page.tsx#L42): one of six session === null branches (42, 59, 71, 75, 79, 90)
- **Evidence:** Each section header is an icon plus a SectionLabel with className text-[12.5px], inside 'mb-2 flex items-center gap-2'. It is written twice in page.tsx and twice in home-activity.tsx, under different constant names (LOWER_HEAD and HEAD). HomePage (96 counted lines, complexity 11) tests session === null six times.
- **Why it matters:** A spacing, size or label change on Home needs four edits in two files, and repeating the same condition is what pushes HomePage over the complexity limit.
- **Recommendation:** Add a HairlineSection component (icon, heading id and text, optional badge, body, action) and an AccountSection that receives the session once. HomePage then only composes sections and falls under 60 lines and complexity 10.
- **Rule check:** Decision 0021: quiet hairline lists that end in their one action at the same height, so Tab never climbs. The component keeps that order.
- **Verification:** confirmed. Four hand-built headers with equal class strings, and the six session === null tests in HomePage, confirmed; eslint.json gives HomePage 96 lines and complexity 11.

```text
// components/ui/hairline-section.tsx
<HairlineSection icon={UserRound} labelId='account-heading' label='Account' badge={badge} action={action}>
  {children}
</HairlineSection>
// app/page.tsx: <AccountSection session={session} />  <ServicesSection status={status} readiness={readiness} />
```

### <a id="wcmp-16"></a>WCMP-16: The Expert initial avatar is copied three times with a hard-coded radius

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/session-panel.tsx:113-118](../../../../apps/web/components/session-panel.tsx#L113): rounded-[10px] at 115
  - [apps/web/components/experts-panel.tsx:344-346](../../../../apps/web/components/experts-panel.tsx#L344): same markup
  - [apps/web/components/expert-editor.tsx:229-231](../../../../apps/web/components/expert-editor.tsx#L229): same markup at size-10
  - [apps/web/app/globals.css:72](../../../../apps/web/app/globals.css#L72): --radius-lg is var(--radius): the same 10px, as a token
- **Evidence:** A span with 'bg-background grid size-9 shrink-0 place-items-center rounded-[10px] border font-serif' around name.trim().charAt(0).toUpperCase() appears in [session-panel.tsx:113-118](../../../../apps/web/components/session-panel.tsx#L113) and [experts-panel.tsx:344-346](../../../../apps/web/components/experts-panel.tsx#L344), and at size-10 in [expert-editor.tsx:229-231](../../../../apps/web/components/expert-editor.tsx#L229). [globals.css:72](../../../../apps/web/app/globals.css#L72) maps rounded-lg to var(--radius) (0.625rem).
- **Why it matters:** The avatar won't follow a change to --radius, and its three copies can drift; they already differ in size.
- **Recommendation:** Add components/ui/expert-initial.tsx (taking name and size) that uses rounded-lg, and use it in all three places.
- **Rule check:** DS-03: map the radius scale to the canonical base rather than hardcoding component-specific values.
- **Verification:** confirmed. Three avatar copies with rounded-[10px] confirmed; --radius is 0.625rem ([docs/design/luma.css:25](../../../../docs/design/luma.css#L25)), so rounded-lg renders the same today.

### <a id="wcmp-17"></a>WCMP-17: Near-identical names for unrelated state

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/goal-composer.tsx:133](../../../../apps/web/components/goal-composer.tsx#L133): refusals: attachment rejections
  - [apps/web/components/goal-composer.tsx:140](../../../../apps/web/components/goal-composer.tsx#L140): refusal: the server's budget message
  - [apps/web/components/home-activity.tsx:70](../../../../apps/web/components/home-activity.tsx#L70): replies: HTTP responses
  - [apps/web/components/home-activity.tsx:100](../../../../apps/web/components/home-activity.tsx#L100): replies: runs waiting for input, in the same function
  - [apps/web/components/goal-composer.tsx:144](../../../../apps/web/components/goal-composer.tsx#L144): active: effect liveness (also 170, [home-activity.tsx:64](../../../../apps/web/components/home-activity.tsx#L64), [session-panel.tsx:25](../../../../apps/web/components/session-panel.tsx#L25))
  - [apps/web/components/search-palette.tsx:32](../../../../apps/web/components/search-palette.tsx#L32): active: the highlighted option (also [jobs-chart.tsx:83](../../../../apps/web/components/jobs-chart.tsx#L83)); the liveness flag is called live at 68
- **Evidence:** refusals and refusal ([goal-composer.tsx:133](../../../../apps/web/components/goal-composer.tsx#L133) and 140) hold unrelated things. In one function, replies first names Responses ([home-activity.tsx:70-78](../../../../apps/web/components/home-activity.tsx#L70)) and then runs waiting for a reply (100-102, 124, 152). active means 'effect still mounted' in four effects and 'highlighted index' in two components, which name their liveness flag live instead.
- **Why it matters:** Readers must work out which meaning applies line by line, which invites mistakes such as setting the wrong refusal state.
- **Recommendation:** Rename to attachmentErrors and budgetMessage; use inputRequests (or waitingForInput) for the runs and highlighted for the index; use one liveness name until the shared fetch hook removes those flags.
- **Rule check:** none
- **Verification:** confirmed. Both double meanings confirmed at the cited lines.

### <a id="wcmp-18"></a>WCMP-18: A composer comment says the choices survive setup, but only the draft is stored

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/goal-composer.tsx:33-35](../../../../apps/web/components/goal-composer.tsx#L33): 'The draft and choice survive setup in this tab only.'
  - [apps/web/components/goal-composer.tsx:131](../../../../apps/web/components/goal-composer.tsx#L131): profile is plain state
  - [apps/web/components/goal-composer.tsx:134-135](../../../../apps/web/components/goal-composer.tsx#L134): so are expertId and chosenBudget
  - [apps/web/components/goal-composer.tsx:36](../../../../apps/web/components/goal-composer.tsx#L36): no-op subscribe with no reason given (used at 114)
  - [apps/web/components/home-greeting.tsx:38](../../../../apps/web/components/home-greeting.tsx#L38): the same pattern, with its reason
- **Evidence:** Only DRAFT_KEY is written (35, 247-254), so the model, Expert and budget choices reset when the user comes back. The no-op subscribe and the empty server snapshot (36, 114) keep the server render and hydration in agreement. [home-greeting.tsx:38](../../../../apps/web/components/home-greeting.tsx#L38) explains that pattern; the composer does not. The comment dates from the first composer (commit fff9dd4), which also stored only the draft.
- **Why it matters:** A reader looking for where the choices persist will search for code that doesn't exist, and the hydration reason for useSyncExternalStore isn't stated where it is used.
- **Recommendation:** Say that the draft survives in this tab, or persist the choices if that is intended (a product decision, not one for this review). Add one line at 36 saying the store is read only in the browser so the server render and hydration agree.
- **Rule check:** DH-06: explain nonobvious invariants in code. The fix keeps the reasoning and its traceability, and removes only a claim the code doesn't make.
- **Verification:** confirmed. Only DRAFT_KEY is written; git show fff9dd4 has the same comment over a composer that stored only the draft.

### <a id="wcmp-19"></a>WCMP-19: The coordinator's Expert choice has no group label, and Run is disabled without saying why

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/session-panel.tsx:106-132](../../../../apps/web/components/session-panel.tsx#L106): radios in list items, with no fieldset, legend or radiogroup
  - [apps/web/components/session-panel.tsx:96-97](../../../../apps/web/components/session-panel.tsx#L96): ready requires a choice
  - [apps/web/components/session-panel.tsx:190](../../../../apps/web/components/session-panel.tsx#L190): a disabled Run with no hint
  - [apps/web/components/notifications-control.tsx:52-53](../../../../apps/web/components/notifications-control.tsx#L52): fieldset and legend are already used elsewhere
- **Evidence:** For a coordinator session, each option is a radio named expert inside an li (120-132). The group's question lives only in the section heading (101-105), which labels the region, not the radio group. Until an Expert is chosen, Run is disabled (96-97, 190), and nothing on screen says why.
- **Why it matters:** Screen-reader users hear each radio without the question it answers, and the disabled Run, which Tab skips, never says that an Expert must be chosen first.
- **Recommendation:** Wrap the coordinator list in a fieldset whose legend is the section label, or use role=radiogroup with aria-labelledby='options-heading'. While nothing is chosen, link a short hint to Run with aria-describedby.
- **Rule check:** DS-04: check labels and disabled controls in both themes.
- **Verification:** revised. No fieldset or radiogroup wraps the coordinator's radios. Corrected the impact: Button renders a native disabled button, which Tab skips rather than reaches, so the missing reason is a hint problem, not a focus stop.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

The review is static. I ran no browser and no type check, because tsc is not among the allowed commands. Two claims are therefore inferred from the code, not compiled: that the three non-null assertions in [home-activity.tsx:79-81](../../../../apps/web/components/home-activity.tsx#L79) are redundant, and that typing session-panel's body against RunRequest would fail under exactOptionalPropertyTypes. I did not re-run ESLint; per-file lint messages come from the run's raw eslint.json. Some neighbouring files were read only where they touch this area: PRD-Development-Harness.md (DH-03 to DH-06), continue-run.tsx, run-disclosure.tsx, run-list.tsx, new-run.tsx, notifications-control.tsx, lib/bff.ts, lib/session.ts, lib/workspace-choice.ts, sign-in-form.tsx, parts of the home, composer and settings-sections browser specs, [scripts/verify.py:150-175](../../../../scripts/verify.py#L150), services/agent contracts/settings.py and domain/budgets.py, and selected lines of the generated API client and OpenAPI document. Their own quality belongs to other areas. The accessibility observations (radio grouping, role=alert on success) come from reading markup, not from an axe or screen-reader run. The duplicate-submit and polling defects follow from the control flow and have not been reproduced at runtime.
