# Web: operations and settings

The operations and settings family is careful where it matters most and is well covered end to end. Secret fields are uncontrolled and cleared before sending, every success body goes through a generated runtime parser, settings writes carry expected_version, every control comes from components/ui/field.tsx (the harness check passes), and browser suites check refusals, stale writes and that no key leaks. The cost is in how each panel is built: each one hand-rolls its own view-state machine. Three panels write their initial read twice, because react-hooks/set-state-in-effect forbids calling load() from the effect. The save flow exists in five copies that have drifted. Failure bodies are cast instead of parsed with the generated parseErrorResponse, which apps/web never uses. Busy is cleared before the success body is parsed, so a parse error escapes as an unhandled rejection. There are three different conflict strategies, and the retention save reports one validation rule for every failure. Its days() parser turns "1,000" into 1 and "3O" into 3, ahead of a timed worker pass that deletes run content. Loading, unavailable and denied states look and announce differently, blur their causes and offer no retry. The measured leads hold: OperationsPanel (377 lines, complexity 28) and ModelPolicyPanel (350) need splitting, and ProviderSettingsPanel (222) less urgently. The small private subcomponents behind the no-multi-comp hits are fine. Pure formatting sits in client components with no fast tests. Operations keys its lookup tables by string although the contract has unions. role_overrides is cast over a runtime gap. Appearance preferences are defined both in the control and in the root layout's before-paint script. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict TS, the shared field controls (harness check passes) and semantic tokens are followed. Arbitrary pixel type sizes, eight copied token literals, four untitled pages and unassociated help text fall short of DH-06 and DS-03. |
| modules | 3 | Dependencies point the right way (generated client, small lib helpers). But each panel embeds its own read, send and state machinery, and the appearance preference table is split between the control and the root layout. |
| size | 2 | OperationsPanel (377 lines, complexity 28), ModelPolicyPanel (350) and ProviderSettingsPanel (222) each hold a whole screen. Three of the five component files exceed 300 lines. |
| functions | 3 | Small pure helpers exist (perMillion, sameForm, sourceLabel, schemaValue). But the panels mix fetching, mutation, draft state, formatting and layout, and the provider mutate reports one outcome for every action. |
| structure | 3 | Pages are thin Server Components under a settings layout. But feature components sit flat among 43 files, a page link lives inside a panel, and the settings section layout is copied page by page. |
| approach | 3 | One consistent path (BFF, generated parsers, CSRF, expected_version), but implemented as a hand-written state machine per panel. The lint-forced duplicate read and client-only initial reads add cost. |
| comments | 4 | Comments explain why and cite decisions and PRD IDs. A few are cryptic ('Its name holds the database's') or slightly wrong ('Numbers only' above values that include text). |
| types | 3 | Success bodies use the generated parsers, and two panels use exhaustive union-keyed maps. But four failure bodies and three role_overrides values are cast, operations keys its maps by string, and preferences are string-typed. |
| errors | 2 | A misparse can silently shorten retention, and success-path parse errors escape as unhandled rejections. Failures are cast and sometimes misreported. Unavailable, denied and signed-out states blur together, with no retry. |
| tests | 3 | Browser suites cover flows, refusals, stale versions and secret leakage well, but they need the db profile. The pure helpers in these panels have no fast tests, and the one precedent, schema-value.test.ts, runs in no verify profile (WSHL-08). |
| maintainability | 3 | The code behaves carefully and is well tested end to end. But changing save or error behavior means editing five drifting copies, and the two largest panels need splitting first. |

## Strengths

- **Secrets never enter React state or props.** The OpenRouter key and tool secrets are read from an uncontrolled field through FormData, and the form is reset before the request (apps/web/components/provider-settings-panel.tsx:221-232, apps/web/components/keys-and-vars-panel.tsx:65-72). The fields use type=password, autoComplete=off and data-1p-ignore (provider-settings-panel.tsx:313-322), and a secret's value is never rendered (keys-and-vars-panel.tsx:88-95). Browser suites check that the field is cleared and that page content, responses and logs never contain the key (apps/web/tests/browser/settings.spec.ts:107,117,125,408; settings-keys-and-vars.spec.ts:161,184). Sources: [apps/web/components/provider-settings-panel.tsx:221](../../../../apps/web/components/provider-settings-panel.tsx#L221), [apps/web/components/keys-and-vars-panel.tsx:65](../../../../apps/web/components/keys-and-vars-panel.tsx#L65), [apps/web/components/provider-settings-panel.tsx:313](../../../../apps/web/components/provider-settings-panel.tsx#L313), [apps/web/components/keys-and-vars-panel.tsx:88](../../../../apps/web/components/keys-and-vars-panel.tsx#L88), [apps/web/tests/browser/settings.spec.ts:107](../../../../apps/web/tests/browser/settings.spec.ts#L107), [apps/web/tests/browser/settings-keys-and-vars.spec.ts:161](../../../../apps/web/tests/browser/settings-keys-and-vars.spec.ts#L161).
- **Generated runtime parsers on every success body, no-store reads.** parseLocalStatus, parseModelList, parseModelPolicyState, parseProviderStatus and parseKeysAndVars validate each success body instead of casting it (operations-panel.tsx:176,194; model-policy-panel.tsx:147-148,175,202; provider-settings-panel.tsx:166,179,210; keys-and-vars-panel.tsx:173,186,217). Every read sends cache: "no-store". Sources: [apps/web/components/operations-panel.tsx:176](../../../../apps/web/components/operations-panel.tsx#L176), [apps/web/components/model-policy-panel.tsx:147](../../../../apps/web/components/model-policy-panel.tsx#L147), [apps/web/components/provider-settings-panel.tsx:166](../../../../apps/web/components/provider-settings-panel.tsx#L166), [apps/web/components/keys-and-vars-panel.tsx:173](../../../../apps/web/components/keys-and-vars-panel.tsx#L173).
- **Exhaustive label maps keyed by generated unions.** provider-settings-panel.tsx:19-63 declares Record&lt;ProviderStatus["auth_status"], string&gt; and similar maps. keys-and-vars-panel.tsx:18-35 keys TITLES and USES by KeyOrVar["name"]. account/page.tsx:10 maps the role union. A new enum value then fails type checking. This is the model for operations-panel. Sources: [apps/web/components/provider-settings-panel.tsx:19](../../../../apps/web/components/provider-settings-panel.tsx#L19), [apps/web/components/keys-and-vars-panel.tsx:18](../../../../apps/web/components/keys-and-vars-panel.tsx#L18), [apps/web/app/settings/account/page.tsx:10](../../../../apps/web/app/settings/account/page.tsx#L10).
- **Shared form controls with explicit labels.** Every input, select and radio comes from apps/web/components/ui/field.tsx (operations-panel.tsx:506,515; model-policy-panel.tsx:356,400; provider-settings-panel.tsx:313; keys-and-vars-panel.tsx:107,117; appearance-control.tsx:163,185,194,220,244). Each is labelled through htmlFor or a wrapping label. tests/harness/test_shared_form_controls.py was run during this review: 2 tests passed. Sources: [apps/web/components/operations-panel.tsx:506](../../../../apps/web/components/operations-panel.tsx#L506), [apps/web/components/model-policy-panel.tsx:356](../../../../apps/web/components/model-policy-panel.tsx#L356), [apps/web/components/keys-and-vars-panel.tsx:107](../../../../apps/web/components/keys-and-vars-panel.tsx#L107), [apps/web/components/appearance-control.tsx:163](../../../../apps/web/components/appearance-control.tsx#L163), [tests/harness/test_shared_form_controls.py:13](../../../../tests/harness/test_shared_form_controls.py#L13).
- **Optimistic concurrency and honest saved state.** Every settings write sends expected_version (model-policy-panel.tsx:167,198; provider-settings-panel.tsx:230,358; keys-and-vars-panel.tsx:247,250) with a specific stale_version message (model-policy-panel.tsx:184-186,213-215). RoleEffect describes only the saved policy (72-116). A saved choice that is no longer offered stays visible and is flagged (232-252, 329-345), so the browser stays a view of durable state. Sources: [apps/web/components/model-policy-panel.tsx:167](../../../../apps/web/components/model-policy-panel.tsx#L167), [apps/web/components/provider-settings-panel.tsx:230](../../../../apps/web/components/provider-settings-panel.tsx#L230), [apps/web/components/keys-and-vars-panel.tsx:247](../../../../apps/web/components/keys-and-vars-panel.tsx#L247), [apps/web/components/model-policy-panel.tsx:184](../../../../apps/web/components/model-policy-panel.tsx#L184), [apps/web/components/model-policy-panel.tsx:232](../../../../apps/web/components/model-policy-panel.tsx#L232).
- **Comments that explain why, with traceable IDs.** Examples: 'Cleared before the request, so the key never waits in the form, in any outcome.' (provider-settings-panel.tsx:226). 'Read, or an unread refusal holds its connection open...' (model-policy-panel.tsx:142). 'A refused save keeps what was typed' (operations-panel.tsx:223). The hydration note at appearance-control.tsx:141. The file header at keys-and-vars-panel.tsx:16-17 cites Decisions 0024 and 0025 and PK-04 to PK-08. Sources: [apps/web/components/provider-settings-panel.tsx:226](../../../../apps/web/components/provider-settings-panel.tsx#L226), [apps/web/components/model-policy-panel.tsx:142](../../../../apps/web/components/model-policy-panel.tsx#L142), [apps/web/components/operations-panel.tsx:223](../../../../apps/web/components/operations-panel.tsx#L223), [apps/web/components/appearance-control.tsx:141](../../../../apps/web/components/appearance-control.tsx#L141), [apps/web/components/keys-and-vars-panel.tsx:16](../../../../apps/web/components/keys-and-vars-panel.tsx#L16).
- **Thin server pages and a hydration-safe appearance control.** Most pages are 11 to 28-line Server Components that put the client boundary at the interactive panel (apps/web/app/operations/page.tsx, settings/models/page.tsx, settings/keys-and-vars/page.tsx). settings/layout.tsx:5-6 records the tab-order reasoning. appearance-control.tsx:98-124 handles unreadable or unwritable storage, and 141-148 gates checked state on mount without suppressing warnings, as DS-02 asks. Sources: [apps/web/app/operations/page.tsx:8](../../../../apps/web/app/operations/page.tsx#L8), [apps/web/app/settings/models/page.tsx:5](../../../../apps/web/app/settings/models/page.tsx#L5), [apps/web/app/settings/layout.tsx:5](../../../../apps/web/app/settings/layout.tsx#L5), [apps/web/components/appearance-control.tsx:98](../../../../apps/web/components/appearance-control.tsx#L98).
- **Meaning carried by words, indicators decorative.** Status dots and icons are aria-hidden and only repeat the text (operations-panel.tsx:79,91,242-256,310-316, with an sr-only separator at 309; provider-settings-panel.tsx:51,70-80). This follows DS-03: never infer state from color alone. Sources: [apps/web/components/operations-panel.tsx:79](../../../../apps/web/components/operations-panel.tsx#L79), [apps/web/components/operations-panel.tsx:309](../../../../apps/web/components/operations-panel.tsx#L309), [apps/web/components/provider-settings-panel.tsx:51](../../../../apps/web/components/provider-settings-panel.tsx#L51).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WSYS-01](#wsys-01) | high | errors | Retention day fields misparse typos before a destructive retention pass | S | medium |
| [WSYS-02](#wsys-02) | medium | errors | Five save flows hand-roll request, parsing and messages, and they have drifted | M | medium |
| [WSYS-03](#wsys-03) | medium | duplication | Three panels write their initial read twice, because the effect may not call load() | S | low |
| [WSYS-04](#wsys-04) | medium | errors | Loading, unavailable and denied states differ by panel, blur causes and cannot be retried | M | low |
| [WSYS-05](#wsys-05) | medium | size | OperationsPanel is one 377-line function mixing reads, a retention form and eight sections | M | medium |
| [WSYS-06](#wsys-06) | medium | size | ModelPolicyPanel is 350 lines with draft logic, catalog cards and form rows inline | M | medium |
| [WSYS-07](#wsys-07) | medium | size | ProviderSettingsPanel mixes the credential flow, status bar and a page link in 222 lines | S | low |
| [WSYS-08](#wsys-08) | medium | types | role_overrides casts hide that its values are never checked at runtime | S | medium |
| [WSYS-10](#wsys-10) | medium | tests | Display formatting and draft logic sit in client components with no fast tests | S | low |
| [WSYS-12](#wsys-12) | medium | standards | Help text and errors are not tied to their controls; field.tsx offers bare controls only | M | low |
| [WSYS-09](#wsys-09) | low | types | Operations lookup tables are keyed by string although the contract gives unions | S | low |
| [WSYS-11](#wsys-11) | low | modules | Appearance preferences are defined twice: in the control and in the before-paint script | S | medium |
| [WSYS-13](#wsys-13) | low | functions | The provider panel says 'Saved.' after Validate and Disconnect | S | low |
| [WSYS-14](#wsys-14) | low | size | ItemCard branches on specific item names, and one busy flag relabels every card | S | low |
| [WSYS-15](#wsys-15) | low | duplication | The settings section layout is copied by hand, with drifting grids | S | low |
| [WSYS-16](#wsys-16) | low | duplication | Route qualification and status dots are drawn twice, with different words and sizes | S | low |
| [WSYS-17](#wsys-17) | low | standards | Four settings pages have no document title | S | low |
| [WSYS-18](#wsys-18) | low | duplication | UI copy restates server rules that can change without it | S | low |
| [WSYS-19](#wsys-19) | low | standards | The theme preview copies eight Luma values outside the single-definition check | S | low |
| [WSYS-20](#wsys-20) | low | naming | Font sizes are arbitrary pixel values instead of a named scale | M | low |

### <a id="wsys-01"></a>WSYS-01: Retention day fields misparse typos before a destructive retention pass

- **Severity** high · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/operations-panel.tsx:153-156](../../../../apps/web/components/operations-panel.tsx#L153): days() keeps leading digits and maps any other text to null
  - [apps/web/components/operations-panel.tsx:208-222](../../../../apps/web/components/operations-panel.tsx#L208): save() sends the parsed values unchecked and reports Saved on any 2xx
  - [apps/web/components/operations-panel.tsx:504-521](../../../../apps/web/components/operations-panel.tsx#L504): free-text inputs: inputMode=numeric only, no validation or error association
  - [services/agent/src/autobots/operations/worker.py:216-219](../../../../services/agent/src/autobots/operations/worker.py#L216): the worker applies every declared window on a timer
  - [services/agent/src/autobots/contracts/operations.py:39-40](../../../../services/agent/src/autobots/contracts/operations.py#L39): the server accepts any whole number from 1 to 36500, so it cannot see the misparse
- **Evidence:** Running the same body in node gives "1,000" -&gt; 1, "3O" -&gt; 3, "2e3" -&gt; 2, "7.9" -&gt; 7 and "abc" -&gt; null (keep everything). save() puts these values into the PUT body (213-216) and, on a 2xx, shows "Saved. Nothing is removed until the next retention pass."

  ```ts
  function days(value: string): number | null {
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  ```

- **Why it matters:** A 1,000-day window typed with a thousands separator is stored as one day. The worker's next timed pass (apply_all) then removes the checkpoints, working files and artifact bytes of every run that finished more than a day ago. The loss is irreversible and is reported as a success; the only hint is the refreshed field showing 1. A mistyped value can also silently clear a window.
- **Recommendation:** Parse each field strictly in a pure helper: empty means keep everything, and otherwise only whole digits are accepted. Then validate the draft with the generated parseRetentionSettings, which already checks the contract's 1 to 36500 bounds, instead of copying the bounds. On a bad value, send nothing, set aria-invalid on that input and point aria-describedby at an inline message. Leave the cross-field rule to the server. Because the API hides validation details ('The request is not valid.'), show today's rule sentence only for code invalid_request, and show the server's message for other refusals. Cover the inputs above with node:test cases.
- **Rule check:** DH-06: validate data at trust boundaries and build accessible forms. The server's RetentionSettings validation stays the authority, including the cross-field rule. The client checks only format and reuses the generated range, so no retention rule moves into Next.js.
- **Verification:** confirmed. Re-ran days() in node ('1,000' gives 1, '3O' 3, '2e3' 2, '7.9' 7, 'abc' null); apply_retention purges every finished run older than run_days on the worker's timed pass (retention.py:92-158, worker.py:217-219), and the contract accepts any whole number from 1 to 36500.

```ts
// lib/retention.ts (pure, tests/unit/retention.test.ts)
export function parseDays(text: string): number | null | "invalid" {
  const value = text.trim();
  if (value === "") return null; // empty keeps everything
  return /^\d+$/.test(value) ? Number(value) : "invalid";
}
// components/operations/retention-form.tsx
// const run = parseDays(runText), keys = parseDays(keysText);
// if either is "invalid": aria-invalid + aria-describedby "Whole days, such as 30."; send nothing
// parseRetentionSettings({ run_days: run, receipt_days: keys }) // range from the contract
// sendJson(PUT); invalid_request -> the rule sentence; other codes -> the server's message
```

### <a id="wsys-02"></a>WSYS-02: Five save flows hand-roll request, parsing and messages, and they have drifted

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [apps/web/components/provider-settings-panel.tsx:192-219](../../../../apps/web/components/provider-settings-panel.tsx#L192): busy is cleared at 208, before the parse at 210; the failure body is cast at 213
  - [apps/web/components/keys-and-vars-panel.tsx:203-226](../../../../apps/web/components/keys-and-vars-panel.tsx#L203): the same mutate, differing only in path, parser and success text
  - [apps/web/components/model-policy-panel.tsx:158-188](../../../../apps/web/components/model-policy-panel.tsx#L158): save: cast at 179; stale_version asks for a page reload
  - [apps/web/components/model-policy-panel.tsx:191-217](../../../../apps/web/components/model-policy-panel.tsx#L191): resetAll: a near-copy of save
  - [apps/web/components/operations-panel.tsx:208-225](../../../../apps/web/components/operations-panel.tsx#L208): no catch around csrfFetch, no busy state, and one fixed rule sentence for any failure
  - [apps/web/components/operations-panel.tsx:286-289](../../../../apps/web/components/operations-panel.tsx#L286): Check again has no busy state either
  - [apps/web/components/account-form.tsx:18-45](../../../../apps/web/components/account-form.tsx#L18): the family's one try/catch/finally save, a local precedent
  - [packages/api-client/src/generated.ts:7693-7700](../../../../packages/api-client/src/generated.ts#L7693): ErrorResponse and parseErrorResponse are generated; apps/web never uses them
- **Evidence:** provider-settings-panel.tsx:208-213. Diffing provider mutate against keys mutate, and policy save against resetAll, leaves only path, body, parser and wording. Bad JSON or a ContractError on a 2xx escapes the void-called handler as an unhandled rejection, with busy already false and no message. Failure bodies are cast at provider:213, keys:220 and policy:179 and 208. git grep counts 19 such casts of failure bodies in 15 component files (20 with the success body cast at continue-run.tsx:53), and 0 uses of parseErrorResponse in apps/web.

  ```tsx
      setBusy(false);
      if (reply?.ok === true) {
        setStatus(parseProviderStatus(await reply.json()));
        setMessage("Saved.");
      } else {
        const failure = (await reply?.json().catch(() => null)) as {
  ```

- **Why it matters:** Changing how a save reports failure, conflict or progress means five edits to copies that already disagree. The policy panel asks for a page reload on stale_version (184-186), while provider and keys refetch after any failure (217, 224). Retention shows a validation rule for a 401, 403 or 503 (218-221) and leaves a network failure unhandled. An error body that drifts from {code, message} is trusted through a cast and rendered.
- **Recommendation:** Add one non-throwing sendJson helper, built once in apps/web/lib and shared with the web-shell forms (WSHL-06 proposes the same helper; agree one outcome shape). It wraps csrfFetch, parses 2xx bodies with the generated parser and refusals with parseErrorResponse, and returns a discriminated outcome. Add a small useMutation hook that owns busy (cleared in finally) and a typed notice, with per-call wording for success, stale_version and fallback. Panels then keep only path, body, parser and words. Give Save retention and Check again the same busy state. Keep the strings the browser suites pin (settings.spec.ts:83, 87, 142 and 219, models.spec.ts:189, settings-keys-and-vars.spec.ts:160 and 206, operations.spec.ts:51), or update them in the same change.
- **Rule check:** DH-06: centralize error handling, parse responses explicitly at untrusted boundaries, avoid blanket type assertions, and disable duplicate submits while expected_version stays the correctness mechanism. This consumes the generated parseErrorResponse; generated.ts is not edited.
- **Verification:** revised. Flows, the busy-before-parse order and the casts confirmed (19 failure-body casts in 15 files, no parseErrorResponse use). Lowered to medium: success bodies are parsed, and the unhandled paths need a contract-violating 2xx or an unreachable Next server, as XDUP-07 and WSHL-06 rate the same pattern.

```ts
// lib/send-json.ts
export type Outcome<T> =
  | { kind: "ok"; value: T }
  | { kind: "refused"; status: number; failure: ErrorResponse | null } // parseErrorResponse
  | { kind: "unreadable" } // a 2xx whose body failed the contract: say so, suggest a reload
  | { kind: "unreachable" }; // network or CSRF token fetch failed
export async function sendJson<T>(path: string, method: "PUT" | "POST" | "DELETE",
    body: unknown, parse: (value: unknown) => T): Promise<Outcome<T>> { /* never throws */ }
// lib/use-mutation.ts
// const { busy, notice, run } = useMutation();
// run(() => sendJson(url, "PUT", draft, parseKeysAndVars),
//     { success: "Saved.", stale: "...", fallback: "That did not work. Nothing changed." }, setItems);
// notice: { tone: "success" | "error"; text }, busy cleared in finally
```

### <a id="wsys-03"></a>WSYS-03: Three panels write their initial read twice, because the effect may not call load()

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/components/operations-panel.tsx:165-206](../../../../apps/web/components/operations-panel.tsx#L165): load and the mount effect; only load handles a null reply and clears failed
  - [apps/web/components/provider-settings-panel.tsx:161-190](../../../../apps/web/components/provider-settings-panel.tsx#L161): load and the mount effect
  - [apps/web/components/keys-and-vars-panel.tsx:168-197](../../../../apps/web/components/keys-and-vars-panel.tsx#L168): load and the mount effect
  - [apps/web/components/model-policy-panel.tsx:141-145](../../../../apps/web/components/model-policy-panel.tsx#L141): drains refused bodies, because 'an unread refusal holds its connection open'
  - [apps/web/components/operations-panel.tsx:189-192](../../../../apps/web/components/operations-panel.tsx#L189): refusals left unread here, as in provider 180-181 and keys 187-188
  - [apps/web/app/settings/account/page.tsx:14](../../../../apps/web/app/settings/account/page.tsx#L14): the one settings page that reads on the server and passes initial data
  - [packages/api-client/src/runtime.ts:168-170](../../../../packages/api-client/src/runtime.ts#L168): requestJson puts the HTTP status only inside its message
- **Evidence:** I replaced keys-and-vars-panel's effect with useEffect(() =&gt; { void load(); }, [load]) and linted it from stdin, with no file written. It fails react-hooks/set-state-in-effect (eslint-plugin-react-hooks 7.1.1), so each panel inlines a second fetch-and-parse. The copies drift. load lets a parse error escape from void load() (operations 176 and 286) or await load() (provider 217, keys 224), while the effect's .catch turns the same error into the unavailable state. The policy panel drains refused bodies for a stated reason that the other three ignore. git grep for `const load = useCallback` finds 4 components that pair a load callback with an inline mount fetch: these 3 and approvals-panel.tsx.
- **Why it matters:** Every change to how a panel reads (error codes, retry, draining refusals) has to be made twice per panel, and the two copies already react differently to the same failure.
- **Recommendation:** Give each resource one module-level reader that never throws and returns a discriminated result (value, signed_out, denied, unavailable). Apply it from the effect's .then and from refresh. The same probe rewritten this way, with readKeysAndVars and an apply callback, lints clean (exit 0). Keep one shape across screens: tool-catalog.tsx:156-181 already has a typed useLoaded that WTAP-01 proposes promoting to lib with a reload, so extend it with these problem kinds rather than adding a third shape. Longer term, the Server Component pages could read initial data on the server with the generated getLocalStatus, getModelPolicy, getModelProviders, getKeysAndVars and getModels, as AccountPage reads its session, leaving the client panels for interaction. That first needs requestJson to expose the HTTP status as a field (WSHL-03) and service-status' module-private memberClient to be exported.
- **Rule check:** This keeps react-hooks/set-state-in-effect on rather than weakening lint. DH-06 prefers Server Components for the longer-term option. Reads stay per request and no-store, and by contract none of these bodies carries a secret.
- **Verification:** revised. Both stdin lint probes reproduced (calling load() fails react-hooks/set-state-in-effect; the module-level reader exits 0). Count corrected from 5 to 4 components; memberClient is module-private, so the server-read option needs it exported.

```tsx
async function readKeysAndVars(): Promise<Read<KeysAndVars>> { /* fetch, drain refusals, parse; never throws */ }
const apply = useCallback((result: Read<KeysAndVars>) => { /* setItems or setProblem */ }, []);
useEffect(() => {
  let active = true;
  void readKeysAndVars().then((result) => { if (active) apply(result); });
  return () => { active = false; };
}, [apply]);
const reload = useCallback(async () => apply(await readKeysAndVars()), [apply]);
```

### <a id="wsys-04"></a>WSYS-04: Loading, unavailable and denied states differ by panel, blur causes and cannot be retried

- **Severity** medium · **Dimension** errors · **Effort** M · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/components/operations-panel.tsx:227-228](../../../../apps/web/components/operations-panel.tsx#L227): bare alert paragraph; loading has role=status
  - [apps/web/components/model-policy-panel.tsx:219-231](../../../../apps/web/components/model-policy-panel.tsx#L219): Card alert; 'Loading models.' has no role
  - [apps/web/components/provider-settings-panel.tsx:234-246](../../../../apps/web/components/provider-settings-panel.tsx#L234): Card alert; 'Loading settings.' has no role
  - [apps/web/components/keys-and-vars-panel.tsx:228-240](../../../../apps/web/components/keys-and-vars-panel.tsx#L228): Card alert; 'Loading settings.' has no role
  - [apps/web/app/settings/account/page.tsx:18-24](../../../../apps/web/app/settings/account/page.tsx#L18): a null session shows 'Sign in', also when the API is down
  - [apps/web/lib/service-status.ts:51-61](../../../../apps/web/lib/service-status.ts#L51): fetchSession returns null both when signed out and on any failure
  - [apps/web/lib/bff.ts:53-57](../../../../apps/web/lib/bff.ts#L53): typed refusal and not_signed_in codes (and service_unavailable at 120) that the panels never read
  - [apps/web/components/model-policy-panel.tsx:463-472](../../../../apps/web/components/model-policy-panel.tsx#L463): one message string: a refusal reads and announces like a success
- **Evidence:** Three panels show '&lt;X&gt; unavailable. Sign in, and check that the local API is running.' for any non-OK or network failure; only operations tells a 403 apart. Loading reads 'Loading…' with role=status in one panel, and 'Loading models.' or 'Loading settings.' without a role in the others. No failed state offers a retry, and operations' Check again button unmounts with the data when a refresh fails. /settings/models stacks two loading lines or two unavailable cards. Outcome notices (policy 463-472, provider 291-295, keys 262-266, operations 527-531) render success and refusal alike: role=status, plain text, no destructive tone or icon.
- **Why it matters:** Users cannot tell signed out, denied and unreachable apart, and must reload the page to recover. A signed-in user whose API is down is told to sign in. Each new panel copies one of four variants.
- **Recommendation:** Add components/ui/panel-state.tsx. It covers loading (role=status) and the signed_out, denied and unavailable problems (role=alert in a Card, with an icon and an optional Retry). Feed it from the shared reader's result, which maps the BFF codes. Make the outcome notice a {tone, text} pair, and render refusals with role=alert, the destructive tone and an icon. settings.spec.ts:83, 87 and 142 find provider refusals by role=status, so update them in the same change. On the account page, call fetchServiceStatus() beside fetchSession(), as the home page does (app/page.tsx:33-38).
- **Rule check:** DH-06: represent loading, empty, denied, unavailable and retryable states deliberately. DS-03: errors use the destructive tone plus an explicit label or icon. Keep the hooks the browser tests pin (data-state=policy-unavailable and the 403 sentence).
- **Verification:** revised. Variants, the unmounting Check again and the null-session Sign in confirmed. Added that settings.spec.ts:83, 87 and 142 read refusals by role=status and must move with the role change.

```tsx
// components/ui/panel-state.tsx
type Problem = "signed_out" | "denied" | "unavailable";
export function PanelLoading({ what }: { what: string }) { /* <p role="status">Loading {what}.</p> */ }
export function PanelProblem({ problem, what, onRetry }: {
  problem: Problem; what: string; onRetry?: () => void;
}) { /* Card + CircleAlert + role="alert" + wording per problem + Retry */ }
export function Notice({ tone, text }: { tone: "success" | "error"; text: string }) { /* status or alert */ }
```

### <a id="wsys-05"></a>WSYS-05: OperationsPanel is one 377-line function mixing reads, a retention form and eight sections

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/operations-panel.tsx:158-539](../../../../apps/web/components/operations-panel.tsx#L158): 377 lines, complexity 28 (ESLint)
  - [apps/web/components/operations-panel.tsx:179-180](../../../../apps/web/components/operations-panel.tsx#L179): a status refresh overwrites the unsaved retention draft
  - [apps/web/components/operations-panel.tsx:333-397](../../../../apps/web/components/operations-panel.tsx#L333): five fact rows of one shape, with nested ternaries
  - [apps/web/components/operations-panel.tsx:491-534](../../../../apps/web/components/operations-panel.tsx#L491): the retention form inside the status view
- **Evidence:** One component holds the read and refresh, the retention draft (runDays, receiptDays, message), the verdict, the checks grid, five facts, the jobs chart, delayed schedules, restores, route qualification and retention. Because the draft and the status share one component, Check again runs load(), which resets both retention fields from the server (179-180) and discards typing that was not saved.
- **Why it matters:** Every edit lands in a 380-line render with complexity 28, and the draft reset above is the kind of defect this coupling produces.
- **Recommendation:** Split along the sections that already exist, give the retention form its own draft state, and move formatting into lib (see the types and tests findings). Move the data-field hooks and wording unchanged.
- **Rule check:** DH-06: small cohesive modules. A behavior-preserving split: the roles, wording and data-\* hooks that the operations browser suites read move unchanged. Decision 0021 R1's presentation-only scope applied to that decision's own change only, per its Amended note.
- **Verification:** revised. 377 lines and complexity 28 (eslint.json) and the draft reset at 179-180 confirmed. Rule check corrected: Decision 0021's Amended note limits R1 to its own change, so the hooks stay because the browser suites read them.

```text
components/operations/
  operations-panel.tsx          compose; owns useLocalStatus()
  use-local-status.ts           shared reader, refresh, busy, view state
  readiness-verdict.tsx         sentence, counts, Check again (233-290)
  condition-grid.tsx            ConditionTile per check, from a CHECKS table (291-332)
  operation-facts.tsx           FactRow x5: tracing, backup, OpenRouter, network, jobs (333-397)
  history-lists.tsx             DelayedSchedules and RestoreHistory (400-455)
  route-qualification-list.tsx  (460-490), sharing qualificationText with the provider panel
  retention-form.tsx            own draft, parseDays, sendJson, busy, notice (491-534)
```

### <a id="wsys-06"></a>WSYS-06: ModelPolicyPanel is 350 lines with draft logic, catalog cards and form rows inline

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/components/model-policy-panel.tsx:118-475](../../../../apps/web/components/model-policy-panel.tsx#L118): 350 lines; the file is 475
  - [apps/web/components/model-policy-panel.tsx:233-252](../../../../apps/web/components/model-policy-panel.tsx#L233): six derived values computed in render
  - [apps/web/components/model-policy-panel.tsx:262-318](../../../../apps/web/components/model-policy-panel.tsx#L262): approved-model card markup
  - [apps/web/components/model-policy-panel.tsx:403-411](../../../../apps/web/components/model-policy-panel.tsx#L403): inline override onChange that copies and deletes keys
  - [apps/web/components/model-policy-panel.tsx:62](../../../../apps/web/components/model-policy-panel.tsx#L62): SUMMARIZER is declared between helpers, apart from EXECUTOR at 21
- **Evidence:** The component holds the paired read and two near-identical requests. It also holds the draft (defaultProfile, overrides, and dirty through sameForm) and six derived values. On top of that sit the approved-model cards with prices and capabilities, the not-offered alert, the workspace-default row, one override row per role with an inline onChange, and the action bar.
- **Why it matters:** Policy rules can only be checked through the db-profile browser suite: what counts as dirty, which choices are offered, and whether a saved choice is no longer offered. Any change to one section means reading and re-testing the whole function.
- **Recommendation:** Extract the pure policy logic into lib/model-policy.ts with unit tests, and split the view into cards, form rows and actions.
- **Rule check:** DH-06: small cohesive modules. The roles, wording and data-\* hooks that models.spec.ts reads move unchanged. The panel keeps describing only the saved policy (its own comment at 72) and sends expected_version unchanged.
- **Verification:** revised. 350 counted lines, the six derived values and the inline onChange confirmed. Rule check corrected as in WSYS-05: the hooks stay because models.spec.ts reads them, not because of Decision 0021 R1.

```text
components/settings/model-policy/
  model-policy-panel.tsx   paired read, compose
  approved-model-card.tsx  label, availability, prices, capabilities (262-318)
  role-effect.tsx          the existing RoleEffect (73-116)
  policy-form.tsx          WorkspaceDefaultRow, RoleOverrideRow per role, PolicyActions (346-462)
  use-policy-draft.ts      defaultProfile, overrides, setOverride(role, profile | null), dirty, adopt
lib/model-policy.ts        roleOverrides, sameForm, choices, followingCount, savedChoiceNotOffered,
                           perMillion, fetchedAt (pure, node:test)
```

### <a id="wsys-07"></a>WSYS-07: ProviderSettingsPanel mixes the credential flow, status bar and a page link in 222 lines

- **Severity** medium · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/provider-settings-panel.tsx:155-382](../../../../apps/web/components/provider-settings-panel.tsx#L155): 222 lines, complexity 11
  - [apps/web/components/provider-settings-panel.tsx:86-153](../../../../apps/web/components/provider-settings-panel.tsx#L86): RouteQualifications, 68 lines; four identical dt/dd grid rows at 114-146
  - [apps/web/components/provider-settings-panel.tsx:377-379](../../../../apps/web/components/provider-settings-panel.tsx#L377): page navigation owned by the panel
  - [apps/web/app/settings/models/page.tsx:9-10](../../../../apps/web/app/settings/models/page.tsx#L9): so the link renders between the two panels
- **Evidence:** One function holds the read, refresh and mutate, plus saveKey with its reset-before-send rule. It also holds the four-cell connection bar, the key form, Validate and Disconnect, two explanatory notes, the qualification cards and a 'Return to your draft' link. On /settings/models that link sits above the model policy section.
- **Why it matters:** The security-relevant part (the uncontrolled key field, cleared before the request) is buried among layout, so a reviewer of a credential change has to read the whole screen.
- **Recommendation:** Once the shared reader and sendJson land, split the view so the key form stands alone, and move the link to the page.
- **Rule check:** nextjs.md and DH-06: credentials stay out of props and state. The split keeps the FormData read and form.reset() before the request, and the wording and hooks that settings.spec.ts reads.
- **Verification:** revised. 222 lines, complexity 11 and the 68-line RouteQualifications confirmed. Rule check corrected: wording and hooks stay because settings.spec.ts reads them; Decision 0021 R1 bound only its own change.

```text
components/settings/provider/
  provider-settings-panel.tsx  read + compose (about 60 lines once reads and sends are shared)
  connection-bar.tsx           Source, Authentication, Catalog, Stored version cells (250-289)
  key-form.tsx                 uncontrolled password field, reset before send (302-333)
  key-actions.tsx              Validate and Disconnect, each with its own success text (335-373)
  route-qualifications.tsx     RouteCard + FactRow for the dt/dd rows (86-153)
app/settings/models/page.tsx   owns the Return to your draft link
```

### <a id="wsys-08"></a>WSYS-08: role_overrides casts hide that its values are never checked at runtime

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/components/model-policy-panel.tsx:55](../../../../apps/web/components/model-policy-panel.tsx#L55): as Record&lt;string, string&gt;
  - [apps/web/components/model-policy-panel.tsx:130](../../../../apps/web/components/model-policy-panel.tsx#L130): as Record&lt;string, string&gt;
  - [apps/web/components/model-policy-panel.tsx:250-252](../../../../apps/web/components/model-policy-panel.tsx#L250): profile cast to the ModelProfileId union
  - [packages/api-client/src/runtime.ts:71-78](../../../../packages/api-client/src/runtime.ts#L71): only additionalProperties === false is enforced; a schema-valued one is skipped
  - [packages/api-client/src/generated.ts:2808-2811](../../../../packages/api-client/src/generated.ts#L2808): the schema says each value is a ModelProfileId
  - [packages/api-client/src/generated.ts:8125](../../../../packages/api-client/src/generated.ts#L8125): the generated type is Record&lt;string, unknown&gt;
- **Evidence:** parseModelPolicyState passes role_overrides through checkObject. That function validates named properties and rejects extras only when additionalProperties is false, so the $ref to ModelProfileId on each value is never applied. The generator emits Record&lt;string, unknown&gt; for any object without properties (scripts/generate_contracts.py:46-47).

  ```tsx
  const saved = state.role_overrides as Record<string, string>;   // 55
  setOverrides(next.role_overrides as Record<string, string>);   // 130
  notOffered.has(profile as (typeof listed)[number]["profile"])  // 251
  ```

- **Why it matters:** A drifted override (a renamed profile, or a number) is accepted by the parser and then trusted by three casts. The form would show it as a selected value with no matching option, and sameForm would compare it as a string.
- **Recommendation:** Narrow once, in lib/model-policy.ts. roleOverrides(state) checks each key against the roles bound in state.policy.bindings and each value with the generated parseModelProfileId, and returns Partial&lt;Record&lt;ModelRole, ModelProfileId&gt;&gt;. An unknown role or profile throws ContractError, so the panel shows its unavailable state. It never drops or displays the value, because Save sends the whole map and would then delete the server's override. Use it in sameForm, adopt and the not-offered check. The root fix belongs to the api-client runtime and generator (WSHL-01): check schema-valued additionalProperties and emit typed records, then regenerate. Do not edit generated.ts.
- **Rule check:** contracts.md: generated TypeScript consumes the Pydantic/OpenAPI contract, and TypeScript types do not validate JSON. Ground rule: generated files are regenerated, never hand-edited. DH-06: no blanket type assertions.
- **Verification:** revised. Casts at 55, 130 and 251, checkObject's skip (runtime.ts:71-78) and the generator rule confirmed. Recommendation revised: an unknown role or profile must fail like a contract error, since silently dropping it would make the next Save delete the server's override.

```ts
import { ContractError } from "@autobots/api-client/runtime";
export function roleOverrides(state: ModelPolicyState): Partial<Record<ModelRole, ModelProfileId>> {
  const roles = new Map<string, ModelRole>(state.policy.bindings.map((b) => [b.role, b.role]));
  const out: Partial<Record<ModelRole, ModelProfileId>> = {};
  for (const [role, profile] of Object.entries(state.role_overrides)) {
    const bound = roles.get(role);
    if (bound === undefined) throw new ContractError(`role_overrides.${role}`, "not a bound role");
    out[bound] = parseModelProfileId(profile); // throws ContractError on drift, never drops it
  }
  return out;
}
```

### <a id="wsys-10"></a>WSYS-10: Display formatting and draft logic sit in client components with no fast tests

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 9
- **Where:**
  - [apps/web/components/operations-panel.tsx:105-156](../../../../apps/web/components/operations-panel.tsx#L105): count, gb, valueFor and days
  - [apps/web/components/operations-panel.tsx:349](../../../../apps/web/components/operations-panel.tsx#L349): '1 hours ago.' for one hour
  - [apps/web/components/operations-panel.tsx:143](../../../../apps/web/components/operations-panel.tsx#L143): queue counts printed raw, while storage uses Intl at 135
  - [apps/web/components/operations-panel.tsx:276-278](../../../../apps/web/components/operations-panel.tsx#L276): the worker plural written again, as at 147
  - [apps/web/components/operations-panel.tsx:420](../../../../apps/web/components/operations-panel.tsx#L420): dates as raw ISO strings, while the policy panel uses locale medium (44-47)
  - [apps/web/components/model-policy-panel.tsx:32-61](../../../../apps/web/components/model-policy-panel.tsx#L32): perMillion, fetchedAt, sameForm
  - [apps/web/components/keys-and-vars-panel.tsx:37-49](../../../../apps/web/components/keys-and-vars-panel.tsx#L37): sourceLabel
  - [apps/web/lib/schema-value.ts:1-9](../../../../apps/web/lib/schema-value.ts#L1): the precedent: 'Pure, so it can be tested without a browser', with tests/unit/schema-value.test.ts
- **Evidence:** Nine pure helpers are module-private in client components: valueFor, gb, days, perMillion, fetchedAt, sameForm, sourceLabel, and appearance's read and apply. apps/web/tests/unit holds three files, and only schema-value.test.ts covers this area; otherwise the helpers are checked only by Playwright suites in the db profile on a disposable stack. Formatting has already drifted. Plurals are hand-written twice and missing once ('1 hours ago.'). Counts use Intl in one branch and not the next. Dates appear as ISO strings here and as locale text in the policy panel.
- **Why it matters:** A wording, rounding or parsing change needs the slowest profile to check, and defects such as days() and the hour plural go unseen until someone reads the screen.
- **Recommendation:** Move the helpers into lib/ beside schema-value.ts (operations-format.ts, retention.ts, model-policy.ts, and appearance read/apply with injected storage), keep them free of '@/' aliases and other imports that node --test cannot resolve, export them, and add node:test files under apps/web/tests/unit. Register each new file in verify.py's web_unit_tests step, or land WSHL-08's folder discovery first: that step names two files today, so even schema-value.test.ts runs in no profile. Share one plural helper (or Intl.PluralRules) and one count and date formatter across the family. Name parsers and formatters for what they do (parseDays, formatGigabytes, integerFormat).
- **Rule check:** DH-06 asks for unit tests of pure and client behavior. Follow the repository's node:test precedent in apps/web/tests/unit rather than adding a runner, which would be a separate tooling decision. AGENTS.md: a test that no profile runs is not evidence.
- **Verification:** revised. Helpers, the '1 hours ago.' plural and the format drift confirmed. Revised: verify.py:161-162 names its unit files, so schema-value.test.ts runs in no profile, and new tests need that list or WSHL-08's discovery.

### <a id="wsys-12"></a>WSYS-12: Help text and errors are not tied to their controls; field.tsx offers bare controls only

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 6
- **Where:**
  - [apps/web/components/provider-settings-panel.tsx:306-332](../../../../apps/web/components/provider-settings-panel.tsx#L306): the disclosure under the key field has no aria-describedby
  - [apps/web/components/keys-and-vars-panel.tsx:98-140](../../../../apps/web/components/keys-and-vars-panel.tsx#L98): label and control assembled by hand in each card
  - [apps/web/components/operations-panel.tsx:497-531](../../../../apps/web/components/operations-panel.tsx#L497): retention rules and the outcome are not associated with the inputs
  - [apps/web/components/model-policy-panel.tsx:383-397](../../../../apps/web/components/model-policy-panel.tsx#L383): saved source and model are shown beside the select, not as its description
  - [apps/web/components/ui/field.tsx:13-67](../../../../apps/web/components/ui/field.tsx#L13): Input, Textarea, Select and Choice; no Field with description and error
  - [tests/harness/test_shared_form_controls.py:9-19](../../../../tests/harness/test_shared_form_controls.py#L9): the check stops at raw elements
- **Evidence:** git grep finds no aria-describedby and no aria-invalid in the 14 files; across apps/web source there are 2 aria-describedby and no aria-invalid. The provider panel's disclosure is a sibling paragraph (328-332): the key goes to this Mac's server and is checked against OpenRouter's key metadata. The retention rule appears only after a failed save, in a status line away from the inputs.
- **Why it matters:** A screen-reader user tabbing into the key field or a retention field hears neither the disclosure nor the error that applies to it. Each panel also re-assembles label, control and help with its own spacing.
- **Recommendation:** Add a Field part to components/ui/field.tsx that takes id, label, description and error, wires htmlFor, aria-describedby and aria-invalid, and renders the shared control as its child. Use it in these five forms. Optionally, extend test_shared_form_controls.py to flag a described control outside Field.
- **Rule check:** DH-06: accessible forms; DS-04: labels and disabled states. This builds on the shared controls that the US-11.11 harness check requires.
- **Verification:** confirmed. Recounted: no aria-describedby or aria-invalid in the 14 files, and 2 aria-describedby with no aria-invalid across app, components and lib; the harness check matches raw elements only. WSHL-12's Label fits the same field.tsx change.

### <a id="wsys-09"></a>WSYS-09: Operations lookup tables are keyed by string although the contract gives unions

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/operations-panel.tsx:68-96](../../../../apps/web/components/operations-panel.tsx#L68): LABELS, ICONS and DOTS declared as Record&lt;string, ...&gt;
  - [apps/web/components/operations-panel.tsx:121-151](../../../../apps/web/components/operations-panel.tsx#L121): valueFor(name: string): a switch with a default; hold falls through
  - [apps/web/components/operations-panel.tsx:296](../../../../apps/web/components/operations-panel.tsx#L296): ICONS needs a fallback to Activity
  - [apps/web/components/operations-panel.tsx:308](../../../../apps/web/components/operations-panel.tsx#L308): LABELS has no fallback, so a missing entry renders an unnamed tile
  - [apps/web/components/operations-panel.tsx:321-327](../../../../apps/web/components/operations-panel.tsx#L321): valueFor runs twice per tile
  - [apps/web/components/provider-settings-panel.tsx:19-63](../../../../apps/web/components/provider-settings-panel.tsx#L19): exhaustive maps keyed by generated unions, the family's model
  - [packages/api-client/src/generated.ts:8168-8172](../../../../packages/api-client/src/generated.ts#L8168): OperationCondition name and state are literal unions
- **Evidence:** The provider panel, by contrast, declares Record&lt;ProviderStatus["auth_status"], string&gt; and similar maps, so a new enum value fails type checking.

  ```ts
  const LABELS: Record<string, string> = { database: "Database", ... };
  const ICONS: Record<string, LucideIcon> = { ... };
  const DOTS: Record<string, string> = { ok: ..., degraded: ..., unavailable: ... };
  function valueFor(name: string, values: Values): string | null { switch (name) { ... default: return null; } }
  ```

- **Why it matters:** When the contract gains a ninth check or renames a state and the client is regenerated, this still compiles, then renders a tile with no name or a default icon. At runtime parseLocalStatus already refuses unknown values. valueFor, at complexity 17, hides which checks have values.
- **Recommendation:** Key the tables by OperationCondition['name'] and ['state'], and replace the switch with one CHECKS table {label, icon, value(values)}, so the compiler demands an entry per check. Keep CONDITIONS and HOLD_TEXT keyed by string, because code is a free string in the contract. Compute the value once per tile.
- **Rule check:** DH-06 and nextjs.md: strict TypeScript over generated API types. The CHECKS table is a UI view mapping, kept separate from the DTO.
- **Verification:** revised. Tables, switch and double call confirmed. Lowered to low, as WTAP-06 and WCMP-14: parseLocalStatus already rejects an unknown name or state (runtime.ts:106), so the gap is compile-time completeness only.

```ts
type CheckName = OperationCondition["name"];
const CHECKS: Record<CheckName, { label: string; icon: LucideIcon;
    value: (v: OperationValues) => string | null }> = {
  database: { label: "Database", icon: Database, value: databaseValue },
  hold: { label: "Hold", icon: Pause, value: () => null },
  // one entry per name
};
const DOTS: Record<OperationCondition["state"], string> = { /* ok, degraded, unavailable */ };
```

### <a id="wsys-11"></a>WSYS-11: Appearance preferences are defined twice: in the control and in the before-paint script

- **Severity** low · **Dimension** modules · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [apps/web/components/appearance-control.tsx:84-124](../../../../apps/web/components/appearance-control.tsx#L84): Preference, DEFAULTS, ATTRIBUTE_VALUE, plus read and apply on autobots.&lt;name&gt;
  - [apps/web/app/layout.tsx:17](../../../../apps/web/app/layout.tsx#L17): BEFORE_PAINT repeats the four keys and values as literals
  - [apps/web/app/globals.css:19](../../../../apps/web/app/globals.css#L19): with 23 and 111: CSS keyed by the same attribute values
  - [apps/web/components/run-workspace.tsx:120](../../../../apps/web/components/run-workspace.tsx#L120): reads dataset.stream
  - [apps/web/components/appearance-control.tsx:126-139](../../../../apps/web/components/appearance-control.tsx#L126): usePreference returns string and (value: string) =&gt; void
  - [apps/web/components/appearance-control.tsx:210-256](../../../../apps/web/components/appearance-control.tsx#L210): density and motion: the same radio group twice
  - [apps/web/components/notifications-control.tsx:12](../../../../apps/web/components/notifications-control.tsx#L12): the same noop subscribe and mounted gate as appearance-control.tsx:8 and 144-148
- **Evidence:** The key prefix, the names and the non-default values live in both files. The values are typed string, so setDensity("compat") compiles.

  ```text
  layout.tsx:17: ...if(s.getItem("autobots.serif")==="off")d.dataset.serif="off";if(s.getItem("autobots.density")==="compact")d.dataset.density="compact";...
  appearance-control.tsx:91-96: const ATTRIBUTE_VALUE: Record<Preference, string> = { serif: "off", density: "compact", motion: "reduce", stream: "off" };
  ```

- **Why it matters:** Adding or renaming a preference value in one file breaks the restore before paint, and only the db-profile suites catch it: appearance.spec.ts:422-490 for serif, density and motion, and stream-result.spec.ts:124-134 for stream.
- **Recommendation:** Create one shared module, the lib/preferences.ts that WSHL-11 also proposes, with one typed PREFERENCES table, the storage key, and read/apply. Build BEFORE_PAINT from it in layout.tsx and use it in the control. Type the values per preference. Extract a PreferenceRadioGroup for the density and motion fieldsets and one useMounted() hook for the two mounted gates; AppearanceControl then drops well under its current 115 lines.
- **Rule check:** DS-02: a dedicated nonsecret appearance key, applied before paint. Keys, values and before-paint behavior stay as they are. DH-06 keeps theme preference separate from credentials and agent state.
- **Verification:** revised. Duplicated keys and values, string-typed setters and the repeated mounted gate confirmed. Lowered to low, as XDUP-19: db-profile suites restore all four keys through the script. One change with WSHL-11.

```ts
// lib/preferences.ts, imported by app/layout.tsx and the control (one module with WSHL-11)
export const PREFERENCES = {
  serif: { fallback: "on", attribute: "off" },
  density: { fallback: "comfortable", attribute: "compact" },
  motion: { fallback: "system", attribute: "reduce" },
  stream: { fallback: "on", attribute: "off" },
} as const;
export type Preference = keyof typeof PREFERENCES;
export type PreferenceValue<P extends Preference> = (typeof PREFERENCES)[P]["fallback" | "attribute"];
export function beforePaintScript(): string { /* theme guard + one statement per entry */ }
// components/ui/preference-radio-group.tsx and lib/use-mounted.ts
```

### <a id="wsys-13"></a>WSYS-13: The provider panel says 'Saved.' after Validate and Disconnect

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/provider-settings-panel.tsx:209-211](../../../../apps/web/components/provider-settings-panel.tsx#L209): mutate has one success message
  - [apps/web/components/provider-settings-panel.tsx:340-345](../../../../apps/web/components/provider-settings-panel.tsx#L340): Validate
  - [apps/web/components/provider-settings-panel.tsx:353-361](../../../../apps/web/components/provider-settings-panel.tsx#L353): Disconnect
  - [apps/web/tests/browser/settings.spec.ts:218-219](../../../../apps/web/tests/browser/settings.spec.ts#L218): pins 'Saved.' after Validate
- **Evidence:** mutate(path, method, body?) ends every 2xx with setMessage("Saved."). Validate and Disconnect both call it, so a successful validation or removal is announced as a save, and settings.spec.ts:219 asserts that text.
- **Why it matters:** Users are told something was saved when nothing was written (Validate) or when a key was removed (Disconnect). The keys panel already distinguishes Saved from Removed (218).
- **Recommendation:** Pass the success wording per action through the shared mutation helper (for example 'The key validated.' and 'Disconnected.'), and update the test in the same change.
- **Rule check:** none
- **Verification:** confirmed. mutate's single 'Saved.' (211), Validate (340-345), Disconnect (353-361) and settings.spec.ts:219 asserting 'Saved.' after Validate confirmed.

### <a id="wsys-14"></a>WSYS-14: ItemCard branches on specific item names, and one busy flag relabels every card

- **Severity** low · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/keys-and-vars-panel.tsx:51-160](../../../../apps/web/components/keys-and-vars-panel.tsx#L51): 109 lines, complexity 15
  - [apps/web/components/keys-and-vars-panel.tsx:99-103](../../../../apps/web/components/keys-and-vars-panel.tsx#L99): nested ternary for the label
  - [apps/web/components/keys-and-vars-panel.tsx:106](../../../../apps/web/components/keys-and-vars-panel.tsx#L106): browser_executor gets a Select
  - [apps/web/components/keys-and-vars-panel.tsx:126](../../../../apps/web/components/keys-and-vars-panel.tsx#L126): github_repository gets a placeholder
  - [apps/web/components/keys-and-vars-panel.tsx:138](../../../../apps/web/components/keys-and-vars-panel.tsx#L138): every card reads 'Saving' while any one of them saves
  - [apps/web/components/keys-and-vars-panel.tsx:162-281](../../../../apps/web/components/keys-and-vars-panel.tsx#L162): KeysAndVarsPanel, 115 lines, mostly the duplicated read and mutate
- **Evidence:** The generic card switches its control on item.name === "browser_executor" and its placeholder on item.name === "github_repository". It picks its label through a nested ternary and receives the panel-wide busy flag, so all five Save buttons say 'Saving' during one request.
- **Why it matters:** Each new key or var with a different control adds another name check to a card already at complexity 15.
- **Recommendation:** Describe each item's field in a table keyed by Name, split the card, and track which item is pending.
- **Rule check:** Keeps the secret field's reset-before-send rule (65-72), and a secret's value is still never rendered (88-95).
- **Verification:** confirmed. 109 lines and complexity 15 (eslint.json), both name checks and the panel-wide busy flag confirmed.

```ts
const FIELDS: Record<Name, { control: "toggle" } | { control: "text"; placeholder?: string }> = {
  tavily: { control: "text" }, jina: { control: "text" }, github_token: { control: "text" },
  github_repository: { control: "text", placeholder: "owner/name" },
  browser_executor: { control: "toggle" },
};
// ItemCard = ItemSummary (title, uses, source, value) + ItemForm (label from kind and source,
// control from FIELDS) + RemoveSaved. The panel keeps pending: Name | null instead of busy.
```

### <a id="wsys-15"></a>WSYS-15: The settings section layout is copied by hand, with drifting grids

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/app/settings/page.tsx:10-24](../../../../apps/web/app/settings/page.tsx#L10): minmax(0,240px) column, gap-7, 12.5px description
  - [apps/web/app/settings/notifications/page.tsx:12-25](../../../../apps/web/app/settings/notifications/page.tsx#L12): the same block
  - [apps/web/app/settings/account/page.tsx:27-42](../../../../apps/web/app/settings/account/page.tsx#L27): 260px column, gap-4, 13px description
  - [apps/web/app/settings/account/page.tsx:43-66](../../../../apps/web/app/settings/account/page.tsx#L43): a second copy on the same page
- **Evidence:** settings/page.tsx:12 and notifications/page.tsx:14 use md:grid-cols-[minmax(0,240px)_minmax(0,1fr)] md:gap-7, while account/page.tsx:29 and 45 use md:grid-cols-[260px_1fr] with gap-4. settings/page.tsx:4 cites Decision 0021: 'one settings section, a label column on the left and its control on the right'.
- **Why it matters:** The label column is 240px on two pages and 260px on a third, and each new settings page copies one of the variants. The copies are also why AccountPage crosses the 60-line lead (62 lines).
- **Recommendation:** Add a SettingsSection component (id, title, description, children) that implements the Decision 0021 layout once, and use it on these pages.
- **Rule check:** The layout that the comment at settings/page.tsx:4 describes for Decision 0021's Studio look; the component encodes it once. Settling on 240px or 260px changes one page, so check it in both themes (DS-05).
- **Verification:** revised. Grids confirmed (240px with md:gap-7 at settings/page.tsx:12 and notifications/page.tsx:14; 260px with gap-4 at account/page.tsx:29 and 45). Rule check corrected: Decision 0021 adopts the Studio look but does not itself state this layout.

```tsx
export function SettingsSection({ id, title, description, children }: {
  id: string; title: string; description?: ReactNode; children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={SECTION_GRID}>
      <div className="space-y-1"><h2 id={id} className="text-sm font-semibold">{title}</h2>{description}</div>
      {children}
    </section>
  );
}
```

### <a id="wsys-16"></a>WSYS-16: Route qualification and status dots are drawn twice, with different words and sizes

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/components/operations-panel.tsx:467-487](../../../../apps/web/components/operations-panel.tsx#L467): 'Tested &lt;date&gt;, with limits.' or 'Not qualified.'
  - [apps/web/components/provider-settings-panel.tsx:39-49](../../../../apps/web/components/provider-settings-panel.tsx#L39): 'Qualified, with the limits below' or 'Not qualified'
  - [apps/web/components/operations-panel.tsx:92-96](../../../../apps/web/components/operations-panel.tsx#L92): DOTS, size-1.5, used at 310-316
  - [apps/web/components/provider-settings-panel.tsx:51-80](../../../../apps/web/components/provider-settings-panel.tsx#L51): StatusDot, size-[7px], a ring for idle
  - [apps/web/components/ui/badge.tsx:41-43](../../../../apps/web/components/ui/badge.tsx#L41): a third dot inside Badge
- **Evidence:** Both panels render RouteQualification[] (operations from LocalStatus.route_qualifications, the provider panel from ProviderStatus.qualification), each with its own status wording. Each also draws its own decorative dot with its own tone map and size, next to the dot that Badge already offers.
- **Why it matters:** The same qualification reads differently on two screens, and a change to dot tone or size has three places to go.
- **Recommendation:** Share one qualificationText(route) and one StatusDot primitive with a tone prop in components/ui, used by both panels and by Badge.
- **Rule check:** DS-03 and Decision 0021 R4: the words carry the meaning and the dot only repeats it; both stay.
- **Verification:** confirmed. Both wordings and the three dots (operations size-1.5, provider size-[7px] with an idle ring, Badge's size-1.5) confirmed.

### <a id="wsys-17"></a>WSYS-17: Four settings pages have no document title

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [apps/web/app/settings/page.tsx:6](../../../../apps/web/app/settings/page.tsx#L6): no metadata
  - [apps/web/app/settings/account/page.tsx:13](../../../../apps/web/app/settings/account/page.tsx#L13): no metadata
  - [apps/web/app/settings/keys-and-vars/page.tsx:4](../../../../apps/web/app/settings/keys-and-vars/page.tsx#L4): no metadata
  - [apps/web/app/settings/models/page.tsx:5](../../../../apps/web/app/settings/models/page.tsx#L5): no metadata
  - [apps/web/app/settings/data/page.tsx:6](../../../../apps/web/app/settings/data/page.tsx#L6): sibling pages export metadata
  - [apps/web/app/layout.tsx:9-11](../../../../apps/web/app/layout.tsx#L9): root title 'Autobots', no template
- **Evidence:** Settings, Account, Keys & vars and Models export no metadata, while Data, Keyboard, Notifications and Operations do. The root layout sets the title 'Autobots' with no template, so all four of those tabs read 'Autobots'.
- **Why it matters:** Tabs, history and screen readers cannot tell these pages apart (WCAG 2.4.2), and the convention is inconsistent within one section.
- **Recommendation:** Export metadata with a title from each page, and give the root layout a title template such as '%s · Autobots' (the web-shell area owns that file).
- **Rule check:** none
- **Verification:** confirmed. Four pages lack metadata while Data, Keyboard, Notifications and Operations export it; the root title has no template, and no browser spec asserts a title.

### <a id="wsys-18"></a>WSYS-18: UI copy restates server rules that can change without it

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [apps/web/components/model-policy-panel.tsx:361-363](../../../../apps/web/components/model-policy-panel.tsx#L361): 'Built-in default (Sol for researcher, Terra otherwise)'
  - [services/agent/src/autobots/domain/models.py:102-105](../../../../services/agent/src/autobots/domain/models.py#L102): Sol for researcher only once Sol is offered
  - [apps/web/components/keys-and-vars-panel.tsx:27-35](../../../../apps/web/components/keys-and-vars-panel.tsx#L27): tool names per key
  - [services/agent/src/autobots/adapters/tavily.py:219](../../../../services/agent/src/autobots/adapters/tavily.py#L219): the tool titles are defined in the adapters
- **Evidence:** The option label hardcodes the built-in default rule but drops its condition: builtin_default returns Sol for researcher only while Sol is offered (models.py:103-105). USES repeats the Tavily and Jina tool titles that the adapters define.
- **Why it matters:** If Sol stops being offered or a tool is renamed, these screens describe something the server no longer does, and nothing fails.
- **Recommendation:** Derive the text from API data, or word it without restating the rule ('Built-in default for each role'). The bindings already carry each role's resolved model, and a built-in default per role could be added to ModelPolicyState. For USES, prefer catalog data where the API exposes it.
- **Rule check:** DH-06: avoid duplicated business rules. model-gateway.md: researcher defaults to Sol once Sol is offered; the rule stays on the server.
- **Verification:** confirmed. builtin_default gives Sol only while Sol is offered (models.py:102-105); Sol is offered today (models.py:72), so the label is right now and would drift silently.

### <a id="wsys-19"></a>WSYS-19: The theme preview copies eight Luma values outside the single-definition check

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [apps/web/components/appearance-control.tsx:13-26](../../../../apps/web/components/appearance-control.tsx#L13): eight oklch() literals
  - [apps/web/tests/browser/appearance.spec.ts:173-182](../../../../apps/web/tests/browser/appearance.spec.ts#L173): checks only globals.css for oklch(
  - [docs/design/luma.css:37](../../../../docs/design/luma.css#L37): the values match today (lines 2, 17, 26, 28, 37, 47, 60, 62)
- **Evidence:** PREVIEWS hardcodes bg-[oklch(0.145_0_0)] and seven more, with a comment explaining that a light preview cannot inherit :root inside a dark page. These are the only oklch() literals in apps/web source (two dialog backdrops use Tailwind's bg-black), and the single-definition test only asserts that globals.css has none.
- **Why it matters:** The risk is low today because Decision 0021 R2 freezes luma.css, but nothing fails if the copy and the canonical file ever diverge.
- **Recommendation:** Extend the single-definition test to compare each PREVIEWS swatch with tokens(':root') and tokens('.dark'). Alternatively, draw the dark half inside an element with the .dark class using semantic utilities, so only the light half needs literals.
- **Rule check:** DS-01: a single maintained token definition, consumed deterministically. Decision 0021 R2 and R3 keep luma.css the only palette.
- **Verification:** revised. Values match luma.css lines 2, 17, 26, 28, 37, 47, 60 and 62, and the test reads only globals.css. Wording narrowed to oklch() literals, since two dialog backdrops use bg-black.

### <a id="wsys-20"></a>WSYS-20: Font sizes are arbitrary pixel values instead of a named scale

- **Severity** low · **Dimension** naming · **Effort** M · **Risk** low · **Occurrences** 39
- **Where:**
  - [apps/web/components/operations-panel.tsx:103](../../../../apps/web/components/operations-panel.tsx#L103): text-[13px]
  - [apps/web/components/operations-panel.tsx:260](../../../../apps/web/components/operations-panel.tsx#L260): text-[21px]
  - [apps/web/components/operations-panel.tsx:318](../../../../apps/web/components/operations-panel.tsx#L318): text-[12.5px]
  - [apps/web/components/model-policy-panel.tsx:83](../../../../apps/web/components/model-policy-panel.tsx#L83): text-[13.5px]
  - [apps/web/components/model-policy-panel.tsx:307](../../../../apps/web/components/model-policy-panel.tsx#L307): text-[11.5px]
  - [apps/web/components/provider-settings-panel.tsx:97](../../../../apps/web/components/provider-settings-panel.tsx#L97): text-[12.5px]
  - [apps/web/components/keys-and-vars-panel.tsx:83](../../../../apps/web/components/keys-and-vars-panel.tsx#L83): text-[12.5px]
  - [apps/web/app/settings/account/page.tsx:35](../../../../apps/web/app/settings/account/page.tsx#L35): text-[13px]
- **Evidence:** git grep -o 'text-\\[[0-9.]\*px\\]' finds 39 in the 14 files, with 7 sizes: 12.5px x17, 13px x13, 13.5px x4, 12px x2, and one each of 11.5px, 15px and 21px. Across apps/web/app and components it finds 212, with 13 sizes.
- **Why it matters:** Choosing between 12.5px, 13px and 13.5px is a guess on every new line, and the Studio scale cannot be adjusted in one place.
- **Recommendation:** Name the sizes the Studio screens use as @theme font-size tokens in globals.css (for example meta, row and row-strong), and replace literals as files are touched. Add a harness grep that ratchets the count down.
- **Rule check:** DS-03: consistent typography. Font-size tokens leave luma.css and the no-color-literal rule untouched (Decision 0021 R2 to R4).
- **Verification:** confirmed. Recounted with git grep -ohE: 39 in the 14 files (7 sizes) and 212 in 39 files across app and components (13 sizes). WSHL-13 owns the shared scale.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

This was a static review only. No browser suite, typecheck, build or app run was performed, so the unhandled rejections and the connection-hold rationale come from reading the code, not from observation. The only commands run were two ESLint probes on stdin against a modified keys-and-vars panel (no file written) and the read-only harness check tests/harness/test_shared_form_controls.py; scripts/verify.py was not run. The PRD-Studio requirement texts (OP, MD, SE, PK) were not read, so cited IDs were judged for clarity, not conformance. Some context files were read only in part: PRD-Development-Harness.md (DH-03 to DH-06), metrics.md (sections 1 to 3, 7 and 8), apps/web/lib/bff.ts (lines 1-140), the openings of apps/web/app/page.tsx, data-summary.tsx and notifications-control.tsx, Decision 0021, and the generated types and Python contracts behind these screens. Components that the settings pages render from other areas (settings-nav, sign-out-button, data-summary, notifications-control, jobs-chart) were not reviewed. Contrast, focus and both themes (DS-04, DS-05) need rendered checks and were not assessed.
