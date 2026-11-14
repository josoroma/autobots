# Lens: duplication and reuse

Duplication in Autobots is mostly visible and signposted. Comments name the code that must change together ("as the run list counts it", "see app/layout.tsx", "counted as admit counts it"). Good shared pieces exist: a provider HTTP module, an ownership-checked disposable-stack teardown, an explicit run row-to-DTO mapping, one API error shape, and a harness test that enforces shared form controls. The problem is where sharing stops. In the browser, data access is hand-written at 74 call sites in 31 components, because the generated client's runtime discards error bodies. As a result, 19 error replies are cast instead of parsed, and the paid run-admission request exists in three copies; only one of them disables duplicate submits and keeps its idempotency key after a lost reply. On the server, several rules that guard secrets, money or state have copies that have already drifted apart. The public-text redactor misses the Tavily, Jina and GitHub token families that the log redactor gained under Decision 0017. An approval's return to pending is re-implemented in the GitHub pull-request adapter with its own TTL. The frozen model-policy snapshot has one writer and eight hand-written readers. The run ledger and the "run plus descendants" scope are rewritten in SQL text, with two tree definitions that disagree when delegation is two levels deep. Terminal states, profile names, the offered model set and budget limits are restated across Python, SQL, TypeScript and scripts. Tests and scripts repeat setup heavily: 36 sign-in helpers, 41 check() helpers, 27 blocks that parse a check's output, and 15 disposable-stack lifecycles. Those copies drift too: two leak scans are narrower than the other two, and most output parsers crash instead of recording a failed case. The 8-line detector found 239 file pairs. Its largest cluster, migrations 023 and 027, is the expected forward redefinition of two functions and is not reported. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | DH-06 asks to avoid duplicated business rules and to use generated types; approval, policy, budget and state rules are copied across layers, and 19 error bodies are cast. |
| modules | 3 | Shared modules exist (provider\_http, disposable\_db, api-client runtime, contracts/adapters) but stop short: an adapter writes approval state, routes resolve admission policy, and the browser has no data-access module. |
| size | 3 | Copies swell the largest files: app\_db.py repeats its check runner 19 times, the 10k-line Playwright suite repeats signIn 36 times, and 31 components each own their fetch code. |
| functions | 3 | Reusable functions exist but stay local or unused (useLoaded in one file; parseErrorResponse, admitRun and createWorkSession unused in the browser), so the same logic is written inline again and again. |
| structure | 3 | There are no shared support modules for browser specs, tests/db checks, web formatting or route dependencies; otherwise the layout follows DH-03. |
| approach | 3 | One architecture throughout, but client data access, run-tree scoping and snapshot reading are each solved several different ways. |
| comments | 4 | Comments name each copy's partner, which made every copy easy to find, but they stand in for shared code. |
| types | 3 | Generated parsers guard most success bodies, but error bodies, run and session acceptances, the frozen policy snapshot and 25 UI label tables are cast or keyed by plain string. |
| errors | 3 | Server errors share one ErrorResponse, but the browser re-reads it per screen, and lost-reply handling for paid admission exists in one of three flows. |
| tests | 3 | Coverage is broad, but helpers are copied and drift: leak scans of different breadth, unguarded output parsing, and 36 sign-in copies. |
| maintainability | 3 | Most duplication is signposted and mechanical to extract, but several copies guard secrets, money and state, and they have already diverged. |

## Strengths

- **One shared provider HTTP module.** services/agent/src/autobots/adapters/provider\_http.py:43-83 holds one client factory (no redirects, trust\_env=False), one status-to-failure-code map and one text budget, used by tavily.py:47, jina.py:47 and market\_data.py:83 and :121. It is the model for the GitHub adapters. Sources: [services/agent/src/autobots/adapters/provider_http.py:43](../../../../services/agent/src/autobots/adapters/provider_http.py#L43), [services/agent/src/autobots/adapters/tavily.py:47](../../../../services/agent/src/autobots/adapters/tavily.py#L47), [services/agent/src/autobots/adapters/jina.py:47](../../../../services/agent/src/autobots/adapters/jina.py#L47), [services/agent/src/autobots/adapters/market_data.py:83](../../../../services/agent/src/autobots/adapters/market_data.py#L83).
- **The ownership guard lives inside the shared teardown.** scripts/disposable\_db.py:266-278: remove\_stack re-checks project identity and labels before removing anything, so all 15 copied stack lifecycles inherit the guard; Cases (disposable\_db.py:335) is the one result recorder for scripts. Sources: [scripts/disposable_db.py:266](../../../../scripts/disposable_db.py#L266), [scripts/disposable_db.py:335](../../../../scripts/disposable_db.py#L335).
- **A typed loader hook worth promoting.** apps/web/components/tool-catalog.tsx:156-181: useLoaded\<T>(path, parse) returns a loading, unavailable or ready state and aborts on unmount. It is used three times in that file and nowhere else. Sources: [apps/web/components/tool-catalog.tsx:156](../../../../apps/web/components/tool-catalog.tsx#L156).
- **Label tables keyed by generated contract types.** apps/web/components/provider-settings-panel.tsx:19-64 keys its tables by generated types, e.g. Record\<ProviderStatus["auth\_status"], string>, so a new enum value fails compilation; 25 other tables in components use Record\<string, string>. Sources: [apps/web/components/provider-settings-panel.tsx:19](../../../../apps/web/components/provider-settings-panel.tsx#L19).
- **Reuse enforced by a harness test.** tests/harness/test\_shared\_form\_controls.py:13-23 fails when any screen draws a raw input, select or textarea; it also checks that it still scans enough files and that it would catch a raw control. The same pattern can guard the new shared helpers. Sources: [tests/harness/test_shared_form_controls.py:13](../../../../tests/harness/test_shared_form_controls.py#L13).
- **Status sets passed to SQL from named constants.** services/agent/src/autobots/application/model\_admission.py:8-11 and :139 pass OUTSTANDING into SQL as `status = any(%(outstanding)s)`; remaining\_daily\_micro\_usd (:295-298) reuses it and says so. This is the model for the copied TERMINAL and ledger sets. Sources: [services/agent/src/autobots/application/model_admission.py:8](../../../../services/agent/src/autobots/application/model_admission.py#L8), [services/agent/src/autobots/application/model_admission.py:139](../../../../services/agent/src/autobots/application/model_admission.py#L139), [services/agent/src/autobots/application/model_admission.py:295](../../../../services/agent/src/autobots/application/model_admission.py#L295).
- **Explicit row, domain and DTO mapping for runs.** services/agent/src/autobots/contracts/adapters.py:8-42 maps the RunRow row type (persistence/rows.py) to the domain Run and then to RunSummary, naming each public field. api/errors.py:19-40 gives every API error a single ErrorResponse shape. Sources: [services/agent/src/autobots/contracts/adapters.py:8](../../../../services/agent/src/autobots/contracts/adapters.py#L8), [services/agent/src/autobots/api/errors.py:19](../../../../services/agent/src/autobots/api/errors.py#L19).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XDUP-01](#xdup-01) | high | duplication | Three different secret patterns, and the one for public text has fallen behind | S | medium |
| [XDUP-02](#xdup-02) | high | duplication | Approval transitions and approved-request reads are re-implemented outside approvals.py | M | high |
| [XDUP-03](#xdup-03) | high | errors | Three copies of run admission; only one is protected against duplicate paid runs | M | medium |
| [XDUP-06](#xdup-06) | high | duplication | Browser data access is hand-written in 31 components, and the generated client can't be used there | L | medium |
| [XDUP-04](#xdup-04) | medium | types | The frozen model-policy snapshot has one writer and eight hand-written readers | M | high |
| [XDUP-05](#xdup-05) | medium | duplication | Run spend and 'run plus descendants' are rewritten in SQL text, with two tree definitions that disagree | M | medium |
| [XDUP-07](#xdup-07) | medium | types | Error replies are cast at 19 sites instead of parsed with the generated parseErrorResponse | S | low |
| [XDUP-08](#xdup-08) | medium | duplication | The model policy for new work is loaded and resolved separately on each admission path | M | medium |
| [XDUP-09](#xdup-09) | medium | duplication | Canonical run-state sets are restated as literals in Python, SQL, TypeScript and scripts | M | low |
| [XDUP-10](#xdup-10) | medium | duplication | Profile names and the offered model set are kept by hand in four places, and already differ | S | low |
| [XDUP-11](#xdup-11) | medium | duplication | GitHub adapters re-implement provider HTTP, and their client and failure codes differ | M | medium |
| [XDUP-12](#xdup-12) | medium | duplication | BFF route handlers assemble the same-origin guard and their refusals separately | S | medium |
| [XDUP-13](#xdup-13) | medium | duplication | Fifteen scripts repeat the disposable-stack lifecycle and build their report envelopes by hand | M | medium |
| [XDUP-14](#xdup-14) | medium | tests | Copied check runners and case helpers in tests/db and scripts have drifted | M | low |
| [XDUP-15](#xdup-15) | medium | tests | Playwright specs copy sign-in, CSRF, key and admission helpers | M | low |
| [XDUP-17](#xdup-17) | medium | duplication | Money, duration and times are formatted by local copies that give different results | S | low |
| [XDUP-18](#xdup-18) | medium | duplication | Loading, unavailable and empty states are hand-built per screen and announced inconsistently | M | low |
| [XDUP-16](#xdup-16) | low | duplication | Budget limits and choices are restated outside domain/budgets.py | S | low |
| [XDUP-19](#xdup-19) | low | duplication | Appearance storage keys and values are written twice: in the before-paint script and in the settings control | S | low |
| [XDUP-20](#xdup-20) | low | duplication | API route modules copy pool access, dependency aliases and idempotency-conflict replies | S | low |

### <a id="xdup-01"></a>XDUP-01: Three different secret patterns, and the one for public text has fallen behind

- **Severity** high · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:59-61](../../../../services/agent/src/autobots/application/run_projection.py#L59): public\_text's pattern: only sk-, Bearer and JWT
  - [services/agent/src/autobots/operations/logs.py:12-24](../../../../services/agent/src/autobots/operations/logs.py#L12): Log redaction: adds Tavily, Jina and GitHub tokens (Decision 0017), credentialed URLs and key=value pairs
  - [scripts/evidence.py:35-40](../../../../scripts/evidence.py#L35): Evidence scanner: the provider token families plus private keys; no bearer, JWT or DB URL
  - [services/agent/src/autobots/api/approval_routes.py:86](../../../../services/agent/src/autobots/api/approval_routes.py#L86): Approval arguments shown to reviewers pass through public\_text (run goal at :100)
  - [services/agent/src/autobots/application/memory.py:87-88](../../../../services/agent/src/autobots/application/memory.py#L87): Memory titles and snippets
  - [services/agent/src/autobots/api/search_routes.py:43](../../../../services/agent/src/autobots/api/search_routes.py#L43): Search titles
- **Evidence:** run\_projection.py:59-61 matches only `sk-…`, `Bearer …` and `eyJ…` tokens. logs.py:12-24, under the comment 'Tool providers' keys, Decision 0017', also matches `tvly-`, `jina_`, `ghp_`/`gho_`…, `github_pat_`, credentialed postgres and https URLs, and `password=`-style pairs. evidence.py:35-40 carries the same comment and the same token families. I compiled both service patterns from their source and ran them on synthetic strings. public\_text left a tvly- key, a jina\_ key, a ghp\_ token, a github\_pat\_ token and a postgresql://user:pw@… URL visible; logs.redact redacted all five.
- **Why it matters:** The rule 'a key the model was shown is never displayed' (comment at run\_projection.py:58; python-worker rule on sanitized public projections) was updated in two copies when Decision 0017 added tool keys, but not in the third. Approval arguments, run goals, search titles and memory snippets shown to every workspace member can therefore display a provider token that the logs would hide. Every new key family must be added in three places.
- **Recommendation:** Keep one stdlib-only module of secret token families and credential shapes, compiled into the strictest union, and use it in both operations/logs.py and public\_text. scripts/evidence.py runs under the system interpreter, so it keeps its own copy, plus a harness test that fails when its families differ from the shared module. This only widens public\_text; never narrow any copy.
- **Rule check:** python-worker.md requires sanitized public projections; nextjs.md says server keys never reach public events; AGENTS.md keeps secrets out of evidence. The change only widens redaction to the strictest union and adds a parity test, so no guardrail is weakened.
- **Verification:** confirmed. Compiled both service patterns from source and ran them on synthetic tvly-, jina\_, ghp\_, github\_pat\_ and postgresql://user:pw@ strings: public\_text left all five visible and logs.redact redacted all five. public\_text feeds approval arguments (approval\_routes.py:86-88), run goals and task titles (:100-101), search titles (search\_routes.py:43) and memory snippets (memory.py:87-88, 105-106, 124-125).

```text
# services/agent/src/autobots/domain/secret_patterns.py  (stdlib only)
TOKEN_FAMILIES = (OPENROUTER, ANTHROPIC, TAVILY, JINA, GITHUB_CLASSIC, GITHUB_FINE_GRAINED)  # strings now in logs.py
CREDENTIAL_SHAPES = (BEARER, JWT, CREDENTIALED_URL, POSTGRES_URL, KEY_VALUE)
SECRET = re.compile('|'.join(TOKEN_FAMILIES + CREDENTIAL_SHAPES))
def redact(text: str) -> str
# operations/logs.py: redact() = identifier shortening + secret_patterns.redact
# application/run_projection.py: public_text() = secret_patterns.redact(text)[:limit]
# tests/harness: every TOKEN_FAMILIES entry has a match in scripts/evidence.py SECRET_PATTERNS
```

### <a id="xdup-02"></a>XDUP-02: Approval transitions and approved-request reads are re-implemented outside approvals.py

- **Severity** high · **Dimension** duplication · **Effort** M · **Risk** high · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/adapters/github_pulls.py:134-153](../../../../services/agent/src/autobots/adapters/github_pulls.py#L134): return\_to\_review: approved to pending, TTL hard-coded as '1 day', emits approval.requested, does not call \_enter\_wait
  - [services/agent/src/autobots/application/approvals.py:182-198](../../../../services/agent/src/autobots/application/approvals.py#L182): Canonical expired-to-pending path: TTL from ttl\_seconds, then \_enter\_wait
  - [services/agent/src/autobots/application/approvals.py:25](../../../../services/agent/src/autobots/application/approvals.py#L25): DEFAULT\_TTL\_SECONDS = 86\_400, which the adapter restates
  - [services/agent/src/autobots/adapters/github_issues.py:101-109](../../../../services/agent/src/autobots/adapters/github_issues.py#L101): Reads the approved row's resource\_target by operation\_id
  - [services/agent/src/autobots/application/tool_gateway.py:216-231](../../../../services/agent/src/autobots/application/tool_gateway.py#L216): Same query text, plus the same 'receipt not failed' rule
  - [services/agent/src/autobots/adapters/github_pulls.py:122-132](../../../../services/agent/src/autobots/adapters/github_pulls.py#L122): Reads the approved row's review\_detail by operation\_id
  - [services/agent/src/autobots/application/approvals.py:168-177](../../../../services/agent/src/autobots/application/approvals.py#L168): Second copy of 'a receipt not failed means sent or possibly sent'
- **Evidence:**
  ```
  # adapters/github_pulls.py:142-145
  "update public.approval_requests set status = 'pending', decided_by = null, "
  "decided_at = null, review_detail = %s, "
  "expires_at = clock_timestamp() + interval '1 day' "
  # application/approvals.py:185-186
  "update public.approval_requests set status = 'pending', decided_by = null, "
  "decided_at = null, expires_at = clock_timestamp() + make_interval(secs => %s) "
  ```
  github\_issues.py:102-105 and tool\_gateway.py:226-229 run the same approved-row query.
- **Why it matters:** A change to approval state, a consent boundary, now lives in an adapter with its own TTL literal and its own event payload. It already differs from the canonical path: it makes no run transition through \_enter\_wait and uses a fixed '1 day' instead of DEFAULT\_TTL\_SECONDS. Any change to what a decision records (a new decided\_\* column, a different expiry, a different event) must be found in both places. The approved-row read (three copies) and the receipt rule (two copies) are checks that Decision 0025 V7 and V8 depend on.
- **Recommendation:** Make application/approvals.py the only code that writes or reads approval rows by operation: a return\_to\_pending function used by both the expiry path and the pull request's base\_moved path, an approved\_request reader, and a predicate for the receipt rule. github\_pulls keeps its GitHub reads and the receipt's reconciled\_at update. Decide explicitly, with a test, whether base\_moved should also enter the wait immediately.
- **Rule check:** python-worker.md: use canonical transitions, and approvals bind the actual normalized effect; DH-06: avoid duplicated business rules; Decision 0025 V7 and V8 are cited in the code. Centralizing keeps every check and fence in place; whether base\_moved enters the wait becomes an explicit, tested decision.
- **Verification:** confirmed. Re-read both transitions, the three approved-row reads (github\_issues.py:102-105, github\_pulls.py:123-126, tool\_gateway.py:226-229) and the two receipt rules (approvals.py:169-177, tool\_gateway.py:220-225). The pull-request path raises base\_moved right after returning the request to pending (github\_pulls.py:194-199), so the run enters the wait only if the call is tried again. XMOD-02 covers the same code from the boundaries side.

```text
# application/approvals.py
@dataclass(frozen=True)
class ApprovedRequest: approval_id: UUID; run_id: UUID; resource_target: str | None; review_detail: dict | None
async def approved_request(connection, operation_id: str) -> ApprovedRequest | None
async def return_to_pending(connection, *, operation_id: str, tool_id: str, review_detail: dict | None = None,
                            ttl_seconds: int = DEFAULT_TTL_SECONDS) -> UUID | None   # one UPDATE plus the approval.requested event
def receipt_may_have_sent(status: str | None) -> bool      # used by approval_gate and _target_unchanged
# adapters/github_pulls.py return_to_review: receipts update, then approvals.return_to_pending(...)
# adapters/github_issues.py and tool_gateway.py: approved_request(...).resource_target
```

### <a id="xdup-03"></a>XDUP-03: Three copies of run admission; only one is protected against duplicate paid runs

- **Severity** high · **Dimension** errors · **Effort** M · **Risk** medium · **Occurrences** 7
- **Where:**
  - [apps/web/components/goal-composer.tsx:287-341](../../../../apps/web/components/goal-composer.tsx#L287): New key on every press; a lost reply or a 503 becomes a plain error
  - [apps/web/components/goal-composer.tsx:591-593](../../../../apps/web/components/goal-composer.tsx#L591): The Run button stays enabled while the request is in flight
  - [apps/web/components/session-panel.tsx:45-79](../../../../apps/web/components/session-panel.tsx#L45): Same POST /v1/runs, new key, no pending state, its own refusal wording
  - [apps/web/components/continue-run.tsx:21-79](../../../../apps/web/components/continue-run.tsx#L21): Keeps the key across a lost reply or 5xx, and a pending state disables the button
  - [apps/web/lib/bff.ts:102](../../../../apps/web/lib/bff.ts#L102): 30 s upstream timeout, then 503, which can follow an admission that already committed
  - [apps/web/components/goal-composer.tsx:257-274](../../../../apps/web/components/goal-composer.tsx#L257): startSession; copied again at experts-panel.tsx:85 and :132 and expert-editor.tsx:189, each casting { id: string }
- **Evidence:**
  ```
  // continue-run.tsx:39, 47-48
  "Idempotency-Key": (key.current ??= crypto.randomUUID()),
  // A 5xx can come after the API committed, so it proves no more than a lost reply.
  if (reply === null || reply.status >= 500) {
  // goal-composer.tsx:287, 292, 593
  // One key per press, so a retried request admits one run and each new press is a new intent.
  "Idempotency-Key": crypto.randomUUID(),
  disabled={draft.trim() === "" || !budgetLeft}
  ```
- **Why it matters:** Run admission is a paid path. In the composer and the session panel (whose button at session-panel.tsx:190 is gated only by `ready`), a double click starts two billed runs. So does a retry after a lost reply, or after the BFF's 503 that follows a slow admission which already committed. continue-run, the third copy of the same request, handles both cases. The copies also word the same refusal codes differently, and the session start is cast rather than parsed four times.
- **Recommendation:** Extract one admission client (startRun and startSession, built on the generated admitRun and createWorkSession) and one submit hook that holds the idempotency key until a definite answer and exposes a pending state. Use continue-run's rule: a success or a 4xx refusal clears the key; a lost reply or a 5xx keeps it. Map admission refusal codes to wording in one table, and use all of this from the composer, the session panel and continue-run.
- **Rule check:** DH-06: disable duplicate submits, with server idempotency as the correctness mechanism; AGENTS.md paid-call boundaries. Server idempotency remains the mechanism; the UI only stops minting a new key when the outcome is unknown.
- **Verification:** revised. Re-read all three admissions: only continue-run.tsx keeps its key (line 39) and disables while pending; the composer's Run button (591-593) and the session panel's (190) stay enabled in flight, and bff.ts:102 times out at 30 s. Corrected the session-start line numbers (experts-panel.tsx:85 and :132, expert-editor.tsx:189).

```text
// apps/web/lib/use-idempotent-submit.ts
export function useIdempotentSubmit<T>(send: (key: string) => Promise<T>) {
  // key kept until success or a 4xx refusal; a null reply or 5xx marks the outcome unknown and the retry reuses the key
  return { submit, pending, outcome };   // pending disables the button
}
// apps/web/lib/runs.ts
export const startRun = (key: string, body: RunRequest) => admitRun(browserClient(key), body);
export const startSession = (key: string, body: SessionCreate) => createWorkSession(browserClient(key), body);
export const ADMISSION_REFUSALS: Partial<Record<string, string>>   // one wording per refusal code
```

### <a id="xdup-06"></a>XDUP-06: Browser data access is hand-written in 31 components, and the generated client can't be used there

- **Severity** high · **Dimension** duplication · **Effort** L · **Risk** medium · **Occurrences** 74
- **Where:**
  - [packages/api-client/src/runtime.ts:157-172](../../../../packages/api-client/src/runtime.ts#L157): requestJson throws only the status, so the ErrorResponse body is lost
  - [apps/web/components/tool-catalog.tsx:156-181](../../../../apps/web/components/tool-catalog.tsx#L156): useLoaded\<T>(path, parse): the one reusable loader, local to this file
  - [apps/web/components/experts-panel.tsx:36-56](../../../../apps/web/components/experts-panel.tsx#L36): Loader that never reads a failed body
  - [apps/web/components/provider-settings-panel.tsx:161-190](../../../../apps/web/components/provider-settings-panel.tsx#L161): Same GET written twice in one file: load() and an effect
  - [apps/web/components/model-policy-panel.tsx:142](../../../../apps/web/components/model-policy-panel.tsx#L142): Drain rule stated as a comment; repeated at home-activity.tsx:73 and run-disclosure.tsx:53
  - [apps/web/components/keys-and-vars-panel.tsx:181-196](../../../../apps/web/components/keys-and-vars-panel.tsx#L181): Another copy of the loader
  - [apps/web/lib/csrf-fetch.ts:2-16](../../../../apps/web/lib/csrf-fetch.ts#L2): The only shared piece: fetches a CSRF token, then the request
- **Evidence:** There are 45 fetch( and 29 csrfFetch( calls in 31 component files, 29 effects with hand-rolled active, live or stopped flags in 24 files, and 16 places that drain a failed body with `.text()`.
  ```
  // experts-panel.tsx:36-44
  let active = true;
  fetch("/api/v1/experts", { cache: "no-store" })
    .then(async (reply) => {
      if (!active) return;
      if (reply.ok) setExperts(parseExpertList(await reply.json()).experts);
      else setFailed(true);
    })
  ```
- **Why it matters:** Every screen re-decides cancellation, caching, parsing, failure reading and idempotency headers. The 'read an unread refusal' rule is applied in 16 places and skipped elsewhere. The browser uses none of the 78 generated request functions (the server uses 4), because runtime.requestJson discards the error body that screens need for code-specific messages. Changing a cross-cutting behavior such as timeouts, CSRF or error parsing means editing about 30 files.
- **Recommendation:** Make the generated client usable in the browser: have runtime.requestJson throw a typed ApiFailure that carries the status and the error body, and accept per-call headers (or build ClientOptions per call). Add apps/web/lib/api.ts with browser ClientOptions (base URL '/api', CSRF-aware fetch, no-store, failed bodies drained), and move useLoaded from tool-catalog.tsx into lib as the one loader hook. Migrate screens as they are touched, and add a harness test like test\_shared\_form\_controls.py that forbids new raw fetch( calls in components.
- **Rule check:** nextjs.md and DH-06: generated API types plus runtime parsing at untrusted boundaries, with explicit loading and unavailable states. runtime.ts is hand-written and in scope; generated.ts is only regenerated. Next.js stays a UI and BFF, and no business state moves into the browser.
- **Verification:** revised. Recounted with git grep: 45 fetch( and 29 csrfFetch( calls in 31 component files, and 29 cancellation flags in 24 files. Failed-body drains are 16, not 14 (18 `.text()` calls, two of which read a file or a reply's content). The cited loaders and runtime.ts:157-172 match.

```text
// packages/api-client/src/runtime.ts (hand-written runtime; generated.ts is regenerated, never edited)
export class ApiFailure extends Error { constructor(readonly status: number, readonly body: unknown) }
// requestJson(options, method, path, body?) throws ApiFailure(status, await response.json().catch(() => null))
// apps/web/lib/api.ts
export function browserClient(idempotencyKey?: string): ClientOptions   // baseUrl '/api', CSRF fetch, no-store
export function failureOf(error: unknown): ErrorResponse | null           // parseErrorResponse on ApiFailure.body
// apps/web/lib/use-loaded.ts (moved from tool-catalog.tsx:156)
export function useLoaded<T>(load: (c: ClientOptions) => Promise<T>, deps: unknown[]): Loaded<T>
```

### <a id="xdup-04"></a>XDUP-04: The frozen model-policy snapshot has one writer and eight hand-written readers

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** high · **Occurrences** 9
- **Where:**
  - [services/agent/src/autobots/application/runs.py:136-154](../../../../services/agent/src/autobots/application/runs.py#L136): Writer: version, bindings, sources (added later: 'Older snapshots have none'), routes
  - [services/agent/src/autobots/application/worker_inference.py:107-123](../../../../services/agent/src/autobots/application/worker_inference.py#L107): frozen\_policy(): the only validating reader
  - [services/agent/src/autobots/application/goal_loop.py:580-599](../../../../services/agent/src/autobots/application/goal_loop.py#L580): Two raw readers via snapshot.get('bindings'): no validation and no routes check
  - [services/agent/src/autobots/operations/browse_trial.py:197-203](../../../../services/agent/src/autobots/operations/browse_trial.py#L197): Raw read of snapshot['bindings'], then frozen\_policy at :204
  - [services/agent/src/autobots/application/run_projection.py:251](../../../../services/agent/src/autobots/application/run_projection.py#L251): SQL JSON path policy\_snapshot -> 'bindings'
  - [services/agent/src/autobots/application/run_projection.py:280-291](../../../../services/agent/src/autobots/application/run_projection.py#L280): Raw Python read of routes, sources and bindings
  - [services/agent/src/autobots/application/run_projection.py:428](../../../../services/agent/src/autobots/application/run_projection.py#L428): jsonb\_each\_text over bindings; again at :445
  - [services/agent/src/autobots/application/run_projection.py:585-586](../../../../services/agent/src/autobots/application/run_projection.py#L585): Inspector reads routes by hand
- **Evidence:**
  ```
  # goal_loop.py:592-598
  async def _route_is_bound(connection: Any, lease: Lease, config: LoopConfig) -> bool:
      ..."select policy_snapshot from public.runs where id = %s"...
      snapshot = (await cursor.fetchone())[0]
      bound: str | None = snapshot.get("bindings", {}).get(config.route.role)
  # worker_inference.py:107-109
  def frozen_policy(snapshot: Mapping[str, Any] | None) -> RolePolicy:
      bindings = (snapshot or {}).get("bindings") or {}
  ```
  Outside frozen\_policy, the snapshot is read by hand at 8 sites: goal\_loop.py:586 and :598, browse\_trial.py:202, and run\_projection.py:251, :281-291, :428, :445 and :586.
- **Why it matters:** The snapshot is the immutable record of which models a run may use; the model-gateway rule says role policy is frozen at admission. Its JSON shape is implicit: the writer and the validating reader live in different modules. goal\_loop's two readers decide routing from raw dict access with neither validation nor the routes check, and browse\_trial asserts on the raw dict before it validates. The shape has already changed once (sources) without a format version, because `version` holds ROLE\_POLICY\_VERSION. A further change must be mirrored in Python dict access and in SQL JSON paths, none of which a type checks.
- **Recommendation:** Define the snapshot's stored shape once, beside the other row shapes, with encode and decode functions that accept every historical shape. Route all Python readers through decode, via a read\_frozen\_policy(connection, run\_id) helper. Keep run\_projection's SQL JSON paths, but name the key once and add a test that encode writes it. Add an explicit format version at the next shape change.
- **Rule check:** contracts.md: version immutable model-policy snapshots; model-gateway.md: freeze role policy at admission. Row, domain (RolePolicy) and DTO types stay distinct, with an explicit mapping between them; stored snapshots are not rewritten.
- **Verification:** revised. Reader list corrected: run\_projection.py:585-586 also reads routes by hand, and browse\_trial validates through frozen\_policy right after its raw check, so two readers (goal\_loop's) bypass validation, not three. Severity lowered from high to medium: every reader agrees with the writer today and tolerates the older shape, so the cost lands at the next shape change, which the recommendation itself ties to the format version; risk stays high because it is durable state.

```text
# services/agent/src/autobots/persistence/policy_snapshot.py   (row JSON shape, not a DTO)
class StoredPolicy(TypedDict): version: int; bindings: dict[str, str]; sources: NotRequired[dict[str, str]]; routes: dict[str, StoredRoute]
BINDINGS_KEY = 'bindings'                         # also used by run_projection's SQL paths
def encode(policy: RolePolicy) -> str              # moved from runs._snapshot
def decode(raw: Mapping[str, Any] | None) -> RolePolicy   # from frozen_policy, without the role check
async def read_frozen_policy(connection, run_id: UUID) -> RolePolicy
# worker_inference.frozen_policy = decode + the executor-role check; goal_loop and browse_trial call decode
```

### <a id="xdup-05"></a>XDUP-05: Run spend and 'run plus descendants' are rewritten in SQL text, with two tree definitions that disagree

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 20
- **Where:**
  - [services/agent/src/autobots/application/run_projection.py:77-86](../../../../services/agent/src/autobots/application/run_projection.py#L77): \_SELECT\_RUN: spent and reserved
  - [services/agent/src/autobots/application/run_projection.py:446-454](../../../../services/agent/src/autobots/application/run_projection.py#L446): Run list: spent, reserved, unreported
  - [services/agent/src/autobots/application/workflow_overview.py:17-31](../../../../services/agent/src/autobots/application/workflow_overview.py#L17): Third copy: 'as the run list counts it (RN-01)'
  - [services/agent/src/autobots/application/model_admission.py:11](../../../../services/agent/src/autobots/application/model_admission.py#L11): OUTSTANDING, the status set the SQL copies restate as text
  - [services/agent/src/autobots/application/recovery.py:40-56](../../../../services/agent/src/autobots/application/recovery.py#L40): outstanding(): counts calls by run\_id or root\_run\_id, but effects by recursive subtree
  - [services/agent/src/autobots/application/reconciliation.py:36](../../../../services/agent/src/autobots/application/reconciliation.py#L36): Recursive subtree CTE; repeated at :47 and :78
  - [services/agent/src/autobots/application/run_usage.py:30](../../../../services/agent/src/autobots/application/run_usage.py#L30): child\_levels = 2, so grandchild runs exist
  - [scripts/qualify_mac_sleep.py:43-47](../../../../scripts/qualify_mac_sleep.py#L43): Fourth ledger copy, scoped by root\_run\_id only
- **Evidence:** There are 4 copies of the ledger SQL, 4 of the subtree CTE, and 12 lines using the `run_id = X or root_run_id = X` scope (grep).
  ```
  # recovery.py:44 and :50-53
  "from app_private.model_invocations where (run_id = %s or root_run_id = %s) "
  "with recursive tree as (select id from public.runs where id = %s union all "
  "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
  "select count(*) from app_private.tool_receipts "
  "where run_id in (select id from tree) and status = 'unknown'",
  ```
- **Why it matters:** Children inherit the top root (assignments.py:79 and :134), so for a depth-1 child X with its own child, `run_id = X or root_run_id = X` matches only X's own calls while the recursive CTE matches X's whole subtree, and outstanding() mixes the two for verification (verification.py:43) and resume gating (assignments.py:285). Whether a mid-level run can then pass verification with a grandchild's uncertain call still open is not established: each level checks its direct child when resuming, and the top root counts every descendant through root\_run\_id. The ledger's status set also appears as SQL text in four places beside the OUTSTANDING constant that admission uses, so a new invocation status would change enforcement but not the figures screens show.
- **Recommendation:** Name each scope once and choose deliberately: one subtree helper (a Python SQL fragment, or a SQL function added by a forward migration) and one ledger helper. Build the ledger columns from model\_admission.OUTSTANDING passed as a parameter, as admission already does. Then decide, with a disposable-database test using depth-2 delegation, which scope outstanding() should count calls in.
- **Rule check:** The Option B contract owns recovery guarantees; python-worker.md: reconcile unknown outcomes before retry; database.md: never edit applied migrations, so any SQL function comes in a forward migration. The extraction is read-only; changing the scope is a separate, tested behavior change.
- **Verification:** revised. Counts reproduced with git grep: 4 ledger copies (run\_projection.py:79-83 and :446-450, workflow\_overview.py:21-25, qualify\_mac\_sleep.py:45-48), 4 subtree CTEs and 12 scope lines. Severity lowered from high to medium: the two scopes do disagree at depth 2, but the effect on verification is inferred and partly covered by the per-level resume check, and the recommendation already asks for the deciding test.

```text
# services/agent/src/autobots/application/run_scope.py
SUBTREE = ('with recursive tree as (select id from public.runs where id = %(run)s union all '
           'select r.id from public.runs r join tree t on r.parent_run_id = t.id)')
def ledger_columns(alias: str = 'r') -> str     # spent, reserved, unreported, using status = any(%(outstanding)s)
LEDGER_PARAMS = {'outstanding': list(OUTSTANDING)}
# run_projection and workflow_overview: f'select ..., {ledger_columns("r")} from ...'
# recovery and reconciliation: SUBTREE, with one stated rule for calls versus effects
# optional forward migration: create function app_private.run_subtree(p_run uuid) returns setof uuid
```

### <a id="xdup-07"></a>XDUP-07: Error replies are cast at 19 sites instead of parsed with the generated parseErrorResponse

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 27
- **Where:**
  - [apps/web/components/workflow-editor.tsx:220](../../../../apps/web/components/workflow-editor.tsx#L220): Four casts in this file: :220, :254, :351, :392
  - [apps/web/components/model-policy-panel.tsx:179-182](../../../../apps/web/components/model-policy-panel.tsx#L179): Also :208
  - [apps/web/components/run-controls.tsx:38-43](../../../../apps/web/components/run-controls.tsx#L38): refusalOf reads only message
  - [apps/web/components/experts-panel.tsx:119-128](../../../../apps/web/components/experts-panel.tsx#L119): Maps code to local wording
  - [apps/web/components/session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65): Success body cast as { run\_id: string }; parseRunAccepted is unused
  - [services/agent/src/autobots/api/errors.py:19-21](../../../../services/agent/src/autobots/api/errors.py#L19): Every API error body is ErrorResponse
  - [packages/api-client/src/generated.ts:7698](../../../../packages/api-client/src/generated.ts#L7698): parseErrorResponse is generated but never imported by the web app
- **Evidence:** There are 19 error-body casts in 15 files and 8 success-body casts in 6 files (grep for `.json()...) as {`).
  ```
  // model-policy-panel.tsx:179-182
  const failure = (await reply?.json().catch(() => null)) as {
    code?: string;
    message?: string;
  } | null;
  ```
- **Why it matters:** The API's error contract is centralized and has a generated parser, but the browser reads it through 19 hand-written shapes. A contract change still compiles everywhere and silently falls back to generic wording. DH-06 forbids blanket assertions at untrusted boundaries.
- **Recommendation:** Replace the casts with a single failureOf(reply) helper that runs parseErrorResponse and returns null on a mismatch, and replace the success casts with parseRunAccepted and parseSessionView. This is a quick first step, before the data-access refactor.
- **Rule check:** DH-06 and nextjs.md: generated types plus runtime parsing at untrusted boundaries, and no blanket type assertions. It uses the existing generated parsers without editing generated.ts.
- **Verification:** confirmed. Reproduced with grep for ') as {': 19 error-body casts in 15 files and 8 success-body casts in 6 files. parseErrorResponse (generated.ts:7698), parseRunAccepted (:8534) and parseSessionView (:8840) exist, and createWorkSession returns SessionView, so every cast has a generated parser.

### <a id="xdup-08"></a>XDUP-08: The model policy for new work is loaded and resolved separately on each admission path

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:202-246](../../../../services/agent/src/autobots/api/run_routes.py#L202): Run admission in a route: policy row, Expert bindings, run\_profile, require\_offered
  - [services/agent/src/autobots/api/run_routes.py:121-150](../../../../services/agent/src/autobots/api/run_routes.py#L121): Preview 'as admission would see them now', a second copy
  - [services/agent/src/autobots/api/improvement_routes.py:100-114](../../../../services/agent/src/autobots/api/improvement_routes.py#L100): Replay admission in a route
  - [services/agent/src/autobots/application/workflows.py:362-376](../../../../services/agent/src/autobots/application/workflows.py#L362): Workflow execution
  - [services/agent/src/autobots/application/routines.py:354-367](../../../../services/agent/src/autobots/application/routines.py#L354): Routine runs
  - [services/agent/src/autobots/application/workflow_overview.py:119-139](../../../../services/agent/src/autobots/application/workflow_overview.py#L119): Per-step preview
  - [services/agent/src/autobots/api/settings_routes.py:393-402](../../../../services/agent/src/autobots/api/settings_routes.py#L393): Settings view
- **Evidence:**
  ```
  # routines.py:354-363
  cursor = await connection.execute(
      "select default_profile, role_overrides from app_private.model_policies "
      "where workspace_id = %s", (workspace_id,))
  policy_row = await cursor.fetchone()
  policy = resolve_role_policy(
      run_role_overrides={r: p.value for r, p in expert.role_bindings.items()},
      workspace_default=policy_row[0] if policy_row else None,
  ```
- **Why it matters:** What a new run freezes is decided on four admission paths, two of them inside API route handlers, each with its own SQL and refusal mapping, and three previews promise to show 'what admission would see'. A new input to resolution, such as another override source, must be threaded through every copy, or previews and admission paths will freeze different policies for the same inputs.
- **Recommendation:** Add one application function that loads the workspace policy, resolves it for new work, and optionally requires the profiles to be offered, taking Expert bindings and run\_profile as arguments. Call it from every admission path and preview, and keep the mapping from refusals to HTTP errors in the routes.
- **Rule check:** model-gateway.md: freeze role policy at admission; DH-06: keep domain decisions independent of HTTP. This moves the decision out of the routes and adds no profile, default or fallback.
- **Verification:** confirmed. All seven sites re-read: four admission paths (post\_run, replay, workflow execution, routine) and three views (run preview, workflow step preview, run intent check). XMOD-05 covers the same reads from the boundaries side.

```text
# application/model_policy.py
async def policy_for_new_work(connection, workspace_id: UUID, *, expert_bindings: Mapping[str, str] | None = None,
                              run_profile: str | None = None, require_offer: bool = True) -> RolePolicy
```

### <a id="xdup-09"></a>XDUP-09: Canonical run-state sets are restated as literals in Python, SQL, TypeScript and scripts

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): TERMINAL, the canonical set
  - [services/agent/src/autobots/application/runs.py:346](../../../../services/agent/src/autobots/application/runs.py#L346): SQL text in a module that imports TERMINAL (:13)
  - [services/agent/src/autobots/application/retention.py:107](../../../../services/agent/src/autobots/application/retention.py#L107): SQL text
  - [services/agent/src/autobots/application/routines.py:306](../../../../services/agent/src/autobots/application/routines.py#L306): SQL text
  - [services/agent/src/autobots/application/run_projection.py:383-387](../../../../services/agent/src/autobots/application/run_projection.py#L383): GROUPS as string tuples; another literal at :339
  - [services/agent/src/autobots/application/workflows.py:492](../../../../services/agent/src/autobots/application/workflows.py#L492): Python literal set
  - [apps/web/components/run-controls.tsx:16-36](../../../../apps/web/components/run-controls.tsx#L16): TERMINAL, PAUSABLE and commandsFor restate the guards in domain/runs.py; Command type and LABELS are copied in run-panel.tsx:14-21
  - [apps/web/components/workflow-monitor.tsx:13](../../../../apps/web/components/workflow-monitor.tsx#L13): Second UI TERMINAL; script copies at qualify\_mac\_sleep.py:42, persistent\_install.py:45 and qualify\_release.py:45
- **Evidence:** The terminal set is restated 11 times (6 in Python, 2 in TypeScript, 3 in scripts); the web never imports the generated RunStatus type.
  ```
  # application/runs.py:345-346
  "select id, version from public.runs where parent_run_id = %s "
  "and status not in ('succeeded', 'failed', 'cancelled', 'cancelling')",
  // apps/web/components/run-controls.tsx:16
  const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
  ```
- **Why it matters:** Terminal states are a shared canonical rule: terminal runs cannot resume. A new terminal or waiting state would change domain/runs.py but leave retention, routine overlap checks, child cancellation, the run-list groups and the UI controls on the old set. Nothing would fail to compile, because the UI tables (25 Record\<string, string> in components) are keyed by string rather than by the generated RunStatus.
- **Recommendation:** In Python, pass TERMINAL, and group sets built from RunStatus, as SQL parameters, as model\_admission does with OUTSTANDING. In the web, keep one lib/run-status.ts keyed by the generated RunStatus (using `satisfies Record<RunStatus, ...>`) for labels, tones, the terminal set and the commands offered, or have the API return a terminal flag and the allowed commands. Follow provider-settings-panel.tsx's typed tables.
- **Rule check:** contracts.md: canonical states and guards are shared; DH-06: do not invent a second state enum for the UI. It uses generated types, and no state transition moves into Next.js.
- **Verification:** revised. Recounted with git grep for the three-state literal: 6 Python sites, 2 TypeScript sites and 3 script copies, not 1 (persistent\_install.py:45 and qualify\_release.py:45, the latter named FINAL, besides qualify\_mac\_sleep.py:42).

### <a id="xdup-10"></a>XDUP-10: Profile names and the offered model set are kept by hand in four places, and already differ

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:104-108](../../../../services/agent/src/autobots/api/run_routes.py#L104): PROFILE\_LABELS: 'DeepSeek'
  - [apps/web/components/run-list.tsx:75-79](../../../../apps/web/components/run-list.tsx#L75): PROFILE\_NAMES: 'DeepSeek Flash'
  - [apps/web/components/experts-panel.tsx:295-299](../../../../apps/web/components/experts-panel.tsx#L295): Copy of PROFILE\_NAMES
  - [apps/web/components/goal-composer.tsx:484](../../../../apps/web/components/goal-composer.tsx#L484): Shows the API's label for the same profile
  - [apps/web/components/expert-editor.tsx:21-25](../../../../apps/web/components/expert-editor.tsx#L21): Hard-coded offered list: Terra and Sol
  - [services/agent/src/autobots/domain/models.py:72](../../../../services/agent/src/autobots/domain/models.py#L72): OFFERED\_FOR\_NEW\_RUNS, the server's set
  - [apps/web/components/run-disclosure.tsx:118](../../../../apps/web/components/run-disclosure.tsx#L118): Reads ModelAvailability.offered, as goal-composer.tsx:394 does
- **Evidence:**
  ```
  # api/run_routes.py:104-105
  PROFILE_LABELS = {
      ModelProfileId.DEEPSEEK_FLASH: "DeepSeek",
  // apps/web/components/run-list.tsx:75-78
  const PROFILE_NAMES: Record<string, string> = {
    openrouter_deepseek_flash: "DeepSeek Flash",
  // apps/web/components/expert-editor.tsx:21-24
  const PROFILES = [{ id: "", label: "Workspace setting" }, { id: "openrouter_terra", label: "Terra" }, { id: "openrouter_sol", label: "Sol" }];
  ```
- **Why it matters:** The same profile is called 'DeepSeek' in the composer's preview but 'DeepSeek Flash' in the run list and on the Experts page. The Expert editor's choice list duplicates OFFERED\_FOR\_NEW\_RUNS, which changes by decision (0013, 0019). When a profile is qualified or withdrawn, three screens follow the API and the editor does not; the server still refuses, so it fails safe, but the editor offers the wrong choices.
- **Recommendation:** Add a display label to ModelAvailability, served from one Python table next to PROFILES in domain/models.py, and regenerate the client. Have every screen use /v1/models for both label and offered status, and delete the TypeScript tables and the hard-coded list.
- **Rule check:** model-gateway.md: exactly three approved profiles, offered by decision; contracts.md: Pydantic/OpenAPI owns the public definition and TypeScript is generated. No new profile or default is introduced.
- **Verification:** confirmed. Labels and lists confirmed; ModelAvailability (contracts/settings.py:97-110) has no label field today. The editor's list equals OFFERED\_FOR\_NEW\_RUNS now, so that copy is drift risk; the 'DeepSeek' versus 'DeepSeek Flash' mismatch is current. The web-build area reports the editor copy as WBLD-07.

### <a id="xdup-11"></a>XDUP-11: GitHub adapters re-implement provider HTTP, and their client and failure codes differ

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 8
- **Where:**
  - [services/agent/src/autobots/adapters/provider_http.py:43-69](../../../../services/agent/src/autobots/adapters/provider_http.py#L43): provider\_client (no redirects, trust\_env=False) and failure\_for
  - [services/agent/src/autobots/adapters/tavily.py:47-61](../../../../services/agent/src/autobots/adapters/tavily.py#L47): call(): request, then provider\_unavailable, failure\_for or provider\_reply\_malformed
  - [services/agent/src/autobots/adapters/jina.py:47-63](../../../../services/agent/src/autobots/adapters/jina.py#L47): Same block
  - [services/agent/src/autobots/adapters/market_data.py:121-138](../../../../services/agent/src/autobots/adapters/market_data.py#L121): Same block again; also at :83-100
  - [services/agent/src/autobots/adapters/github_issues.py:127-138](../../../../services/agent/src/autobots/adapters/github_issues.py#L127): Own client; trust\_env is not disabled
  - [services/agent/src/autobots/adapters/github_issues.py:45](../../../../services/agent/src/autobots/adapters/github_issues.py#L45): \_REFUSED; the sets at github\_pulls.py:45 and github\_reads.py:40 differ
  - [services/agent/src/autobots/adapters/github_pulls.py:48](../../../../services/agent/src/autobots/adapters/github_pulls.py#L48): UnclearReply defined again (also github\_issues.py:55)
  - [services/agent/src/autobots/adapters/github_reads.py:53-71](../../../../services/agent/src/autobots/adapters/github_reads.py#L53): 429 becomes github\_refused\_429; transport errors become destination\_unreachable
- **Evidence:**
  ```
  # provider_http.py:51-57
  return httpx.AsyncClient(base_url=base_url, headers=dict(headers), transport=transport,
                           timeout=seconds, follow_redirects=False, trust_env=False)
  # github_issues.py:128-137
  return httpx.AsyncClient(base_url=API_URL, transport=transport, timeout=_REQUEST_SECONDS,
                           follow_redirects=False, headers={"Authorization": f"Bearer {token}", ...})
  ```
  Refused sets: issues {400,401,403,404,410,422,429}, pulls adds 409, reads lacks 400.
- **Why it matters:** The token-bearing GitHub client honors HTTP(S)\_PROXY, ALL\_PROXY and SSL\_CERT\_\* settings from the worker's environment (httpx 0.28.1 defaults to trust\_env=True), while every other provider client sets trust\_env=False. The same 429 reaches the model as rate\_limited from Tavily but as github\_refused\_429 from GitHub. The two write sets decide which replies count as 'nothing was created' rather than an unknown outcome, and they differ on 409 (pull requests only) with no comment saying why; the read set also lacks 400 but only picks the failure code.
- **Recommendation:** Move the request-and-map block into provider\_http as a request\_json(client, method, path, credential=...) helper, build github\_client through provider\_client, and keep one UnclearReply. Give the refused-status tables a single home, with a comment per write class stating which statuses prove there was no effect.
- **Rule check:** DH-06: centralize error handling; python-worker.md: reconcile unknown outcomes before retry. The GitHub distinction between a refused write and an unclear one is kept, and made explicit instead of copied.
- **Verification:** revised. Confirmed that github\_client (github\_issues.py:127-138) omits trust\_env=False and that the three refused sets differ as stated. Dropped the .netrc claim: httpx 0.28.1 (uv.lock) takes proxies and SSL settings from the environment, and netrc only through an explicit NetRCAuth. Clarified that only the issue and pull-request sets decide 'nothing was created'.

### <a id="xdup-12"></a>XDUP-12: BFF route handlers assemble the same-origin guard and their refusals separately

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [apps/web/lib/bff.ts:21-51](../../../../apps/web/lib/bff.ts#L21): safeError and the guard input
  - [apps/web/app/api/session/route.ts:13-31](../../../../apps/web/app/api/session/route.ts#L13): guard(): refusal without Cache-Control: no-store
  - [apps/web/app/api/workspace/route.ts:8-31](../../../../apps/web/app/api/workspace/route.ts#L8): refused() is identical to safeError; third guard input
  - [apps/web/app/api/workspace/route.ts:55](../../../../apps/web/app/api/workspace/route.ts#L55): Cookie secure flag computed from the origin
  - [apps/web/app/api/csrf/route.ts:15](../../../../apps/web/app/api/csrf/route.ts#L15): secure: false, as in lib/session.ts:19
  - [apps/web/lib/bff.ts:82](../../../../apps/web/lib/bff.ts#L82): Header literal duplicates WORKSPACE\_HEADER; again at :141-143
  - [apps/web/lib/service-status.ts:28](../../../../apps/web/lib/service-status.ts#L28): Internal-token header built again (bff.ts:61)
- **Evidence:**
  ```
  // app/api/session/route.ts:25-30
  return refusal === null
    ? null
    : NextResponse.json(
        { code: refusal, message: "This request was refused." },
        { status: 403 },
      );
  ```
  lib/bff.ts:26-28 and workspace/route.ts:9-11 both add { headers: { "Cache-Control": "no-store" } }.
- **Why it matters:** The CSRF and origin check itself is pure and tested, but what it is fed and how refusals are answered are copied. One copy already omits no-store, and the three cookies disagree on `secure` for the same origin. A new guard input, such as another header, would have to be added in three handlers.
- **Recommendation:** Export from lib/bff.ts (server-only) a guardOf(request), a refusal(status, code, message) and one cookieOptions(config, { httpOnly }); use them in the session and workspace handlers. Use WORKSPACE\_HEADER everywhere, and share one internal-headers helper with service-status.ts.
- **Rule check:** nextjs.md: protect mutations with Host, Origin and CSRF checks, and verify session and workspace per BFF operation. The guard logic and its unit tests are unchanged; only input assembly and responses are shared.
- **Verification:** confirmed. session/route.ts:25-30 refuses without no-store; workspace/route.ts:8-13 duplicates safeError; the secure flags differ (workspace/route.ts:55 from the origin, csrf/route.ts:15 and lib/session.ts:19 always false); bff.ts:82 and :141-143 spell the workspace header as a literal; service-status.ts:28 rebuilds the internal-token header.

### <a id="xdup-13"></a>XDUP-13: Fifteen scripts repeat the disposable-stack lifecycle and build their report envelopes by hand

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 15
- **Where:**
  - [scripts/qualify_browse_goal.py:44-107](../../../../scripts/qualify_browse_goal.py#L44): Near-copy of qualify\_browser\_executor.py:44-105 (36 shared 8-line windows)
  - [scripts/app_db.py:643-660](../../../../scripts/app_db.py#L643): Setup block, repeated at qualify\_identity.py:414 and qualify\_operations.py:136
  - [scripts/disposable_db.py:266-278](../../../../scripts/disposable_db.py#L266): remove\_stack re-checks ownership, so the guard itself is shared
  - [scripts/qualify_browser_executor.py:99](../../../../scripts/qualify_browser_executor.py#L99): One of the hand-written schema\_version envelopes
  - [services/agent/src/autobots/adapters/browser_executor.py:463-500](../../../../services/agent/src/autobots/adapters/browser_executor.py#L463): The service reads that report: path, status, case ids, fingerprint
  - [tests/db/browser_executor_check.py:49](../../../../tests/db/browser_executor_check.py#L49): Its check() calls emit the 20 case ids that REQUIRED\_CASES repeats as free text
  - [scripts/live_goal.py:198](../../../../scripts/live_goal.py#L198): Paid guard exits 2; persistent\_install.py:794 exits 1; route\_qualification.py:681 exits 0 with not\_sent
- **Evidence:** grep: remove\_stack and other\_resources(project) are called in 15 scripts, require\_identity appears in 16 and PROJECT\_PREFIX naming in 17; 25 distinct 'autobots.\*/vN' report schema identifiers appear in 23 scripts, and 'not\_established' in 19.
  ```
  # qualify_browse_goal.py:50-56 (same in 14 others)
  project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
  gateway_port = free_port()
  db_port = free_port([gateway_port])
  target = Target(project, db_port, gateway_port)
  stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
  ```
- **Why it matters:** Cleanup ownership is safe, because remove\_stack checks identity and labels. Everything around it is copied: starting the stack, migrating, seeding the workspace, comparing other Docker resources, and the evidence envelope that AGENTS.md requires. One report is also a runtime contract: browsing counts as qualified only if the service finds 20 case ids that live as free text in another file, so rewording a case silently disables browsing (it fails closed). A paid refusal exits 2, 1 or 0 depending on the script.
- **Recommendation:** In app\_db.py, add a disposable\_app\_stack(root, services=...) context manager that yields the stack and records the other-resources check, and a write\_report(...) used by every qualifier. Give the executor's case ids one tuple imported by both the check and the adapter, or add a schema test. Add one paid-guard helper with a single exit code; route\_qualification's no-flag plan preview can stay a separate, documented dry run.
- **Rule check:** infrastructure.md: distinct disposable projects and ownership guards come before cleanup, and these stay inside remove\_stack; AGENTS.md: completion evidence and paid-call boundaries. No guard leaves the shared primitive, and the paid guard stays mandatory.
- **Verification:** revised. remove\_stack and other\_resources are called in 15 scripts, and the browse-goal and executor qualifiers share 36 windows in the detector output. The envelope count is restated from git grep (25 schema identifiers in 23 scripts), and the title no longer fixes a number of formats. Risk raised from low to medium: the qualifiers are themselves the disposable tests, so reshaping 15 lifecycles changes ports, ordering and before-and-after resource checks.

```text
# scripts/app_db.py
@contextmanager
def disposable_app_stack(root, *, services=('db',), seed_workspace=True) -> Iterator[DisposableRun]:
    # name, ports, Target, AppStack, passwords, require_identity, render and images, before = other_resources
    # up --wait, bootstrap, migrate, seed; finally remove_stack and the 'other Docker resources are untouched' case
def write_report(root, path, schema, cases, *, target_class, not_established, started_at, **extra) -> bool
```

### <a id="xdup-14"></a>XDUP-14: Copied check runners and case helpers in tests/db and scripts have drifted

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 27
- **Where:**
  - [scripts/app_db.py:361-373](../../../../scripts/app_db.py#L361): Run a tests/db check, parse its last line, translate the cases: 19 copies in this file
  - [scripts/app_db.py:506-514](../../../../scripts/app_db.py#L506): Variant that skips parsing only when a failed run printed nothing
  - [scripts/qualify_browse_goal.py:74-84](../../../../scripts/qualify_browse_goal.py#L74): One of the 8 copies that also handle empty output after exit 0
  - [tests/db/admission_check.py:25](../../../../tests/db/admission_check.py#L25): Local check(): one of 41, with six truncation variants (none, 300, 400, 600, 700, 900)
  - [tests/db/provider_key_check.py:91-102](../../../../tests/db/provider_key_check.py#L91): Whole-database secret scan, identical to tool\_use\_check.py:64
  - [tests/db/connector_check.py:178-180](../../../../tests/db/connector_check.py#L178): Narrower three-table secret scan; also pull\_request\_check.py:215
  - [services/agent/tests/test_github_issues.py:40](../../../../services/agent/tests/test_github_issues.py#L40): FakeGithub, defined again at test\_github\_reads.py:23, connector\_check.py:39 and keys\_and\_vars\_check.py:64
- **Evidence:** There are 27 sites in 7 scripts that parse a check's cases from its last output line, and 18 copies of the runtime URL literal.
  ```
  # app_db.py:364-371
  result = subprocess.run([str(root / 'services/agent/.venv/bin/python'), str(root / 'tests/db/admission_check.py'), WORKSPACE_A],
                          env={**tool_env(), 'AUTOBOTS_DATABASE_URL': url, ...},
                          capture_output=True, text=True, timeout=120, check=False)
  if result.returncode:
      cases.check('the admission check ran', 'exit 0', f'exit {result.returncode}: {result.stderr.strip()[-400:]}', False)
      return
  for case in json.loads(result.stdout.strip().splitlines()[-1])['cases']:
  ```
- **Why it matters:** 19 of the 27 parse sites (all in app\_db.py) take splitlines()[-1] without first checking that a check which exited 0 printed anything, so empty output crashes the qualifier with a traceback instead of recording a failed case; the 8 sites in the other qualifiers guard it. The two case-record shapes ('passed' versus 'status') must be translated at every call. The 'no durable copy of a secret' assertion is a whole-database scan in two checks but a three-table scan in the two GitHub connector checks, which therefore never look at tool\_uses, run\_files or checkpoints.
- **Recommendation:** Add tests/db/support.py with the check recorder, the database scan, the runtime URL and the connection, plus a run\_check(stack, root, script, \*args, timeout, extra\_env) helper in app\_db.py that records empty output as a failure. Use the whole-database scan in the connector checks, which only widens them, and move FakeGithub into a shared test-support module.
- **Rule check:** AGENTS.md: synthetic fixtures on disposable targets, and skipped checks never count as passing; database.md: verify actual roles. Widening the narrow leak scans strengthens the assertion, and nothing is skipped.
- **Verification:** revised. Recounted: 27 case parsers (json.loads(...splitlines()[-1])['cases']), of which the 8 outside app\_db.py check for empty output first, so 19 are unguarded, not 23. The check() helpers truncate in six ways, not four. The 18 runtime URL literals, four FakeGithub classes and the run-scoped three-table scans in connector\_check.py:178-180 and pull\_request\_check.py:215-216 match.

### <a id="xdup-15"></a>XDUP-15: Playwright specs copy sign-in, CSRF, key and admission helpers

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 36
- **Where:**
  - [apps/web/tests/browser/slice-controls.spec.ts:10-60](../../../../apps/web/tests/browser/slice-controls.spec.ts#L10): signIn, write, ensureKey and admit in one spec
  - [apps/web/tests/browser/slice-inspector.spec.ts:12-49](../../../../apps/web/tests/browser/slice-inspector.spec.ts#L12): The same helpers again, plus a hard-coded model id
  - [apps/web/tests/browser/approvals.spec.ts:23](../../../../apps/web/tests/browser/approvals.spec.ts#L23): signIn copy; write at :43
  - [apps/web/tests/browser/slice.spec.ts:7](../../../../apps/web/tests/browser/slice.spec.ts#L7): Variant that also arranges a key
  - [apps/web/tests/browser/identity.spec.ts:12](../../../../apps/web/tests/browser/identity.spec.ts#L12): Variant without the signed-in assertion
  - [apps/web/playwright.config.ts:4-24](../../../../apps/web/playwright.config.ts#L4): No fixtures, globalSetup or storageState
- **Evidence:** signIn is defined in 36 of the 41 specs (38 definitions), write in 15, ensureKey in 5 and admit in 3; process.env is read on 263 lines across all 41 specs; the Terra model ids are hard-coded in 6 specs and the arranged key in 11. All signIn bodies are the same flow, differing only in which constants they read.
  ```
  // slice-controls.spec.ts:15-19
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  ```
- **Why it matters:** A change to the sign-in form's labels, the CSRF header contract or the signed-in text breaks 36 files at once. The hard-coded Terra model ids duplicate domain/models.py and will fail at the next route change.
- **Recommendation:** Add apps/web/tests/browser/support/ with a typed test.extend fixture for each role (owner A, owner B, member, ops) built from one env reader, a csrfHeaders(page, key) helper, ensureKey and admit. Read model ids from /api/models instead of literals, and consider storageState per role.
- **Rule check:** DH-06: Playwright for key browser flows, including keyboard use and accessible labels. Specs still exercise the real sign-in flow; nothing is skipped.
- **Verification:** revised. Recounted with grep over apps/web/tests/browser: signIn defined in 36 specs (38 definitions), write 15 (not 14), env reads on 263 lines in 41 specs (not 242 in 40), Terra ids in 6 specs (not 5) and the arranged key 'sk-or-valid-arranged-first' in 11 (not 10). The sign-in bodies at slice-controls.spec.ts:15-19 and slice-inspector.spec.ts:14-24 match.

### <a id="xdup-17"></a>XDUP-17: Money, duration and times are formatted by local copies that give different results

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 16
- **Where:**
  - [apps/web/components/run-list.tsx:87-89](../../../../apps/web/components/run-list.tsx#L87): dollars(): US$x.xx; same at run-panel.tsx:30, workflows-panel.tsx:50, goal-composer.tsx:74, home-activity.tsx:34
  - [apps/web/components/run-inspector.tsx:10-12](../../../../apps/web/components/run-inspector.tsx#L10): dollars() without rounding
  - [apps/web/components/run-workspace.tsx:802-822](../../../../apps/web/components/run-workspace.tsx#L802): One page: rounded 'US$' limit, unrounded spend, then '$' in Usage
  - [apps/web/components/workflow-editor.tsx:658](../../../../apps/web/components/workflow-editor.tsx#L658): Inline formatter
  - [apps/web/components/workflows-panel.tsx:36](../../../../apps/web/components/workflows-panel.tsx#L36): relative() with Intl, same as home-activity.tsx:24
  - [apps/web/components/approvals-panel.tsx:88](../../../../apps/web/components/approvals-panel.tsx#L88): relative() as 'in 5 min' or '3 h'; experts-panel.tsx:310 lastRun is a fourth version
  - [apps/web/components/run-list.tsx:393](../../../../apps/web/components/run-list.tsx#L393): ISO UTC start time, as operations-panel.tsx:420; approvals use toLocaleString (:111)
  - [apps/web/components/home-greeting.tsx:11](../../../../apps/web/components/home-greeting.tsx#L11): The only use of the workspace time zone
- **Evidence:** There are 6 dollars() copies, 6 inline conversions, and 4 relative-time functions with 3 output styles.
  ```
  // run-list.tsx:87-89 and run-inspector.tsx:10-12
  function dollars(micro: number): string { return `US$${(micro / 1_000_000).toFixed(2)}`; }
  function dollars(micro: number): string { return `US$${micro / 1_000_000}`; }
  ```
- **Why it matters:** The same micro-USD value shows as 'US$0.00', 'US$0.001234' or '$0.001234' depending on the screen, sometimes on the same page. Times appear as UTC ISO strings in the run list but in the browser's locale on approvals. Every new screen picks its own convention.
- **Recommendation:** Create apps/web/lib/format.ts with money(micro, { precision }), relativeTime(iso, now), duration(seconds) and instant(iso, timeZone), using the workspace time zone as home-greeting does, with unit tests in tests/unit. Replace the local copies as screens are touched.
- **Rule check:** python-worker.md: exact monetary units, so amounts stay integer micro-USD and are formatted only for display.
- **Verification:** confirmed. Six dollars() copies in two formats, the three styles on run-workspace.tsx:802-822, four relative-time functions, and the ISO (run-list.tsx:393, operations-panel.tsx:420) versus locale (approvals-panel.tsx:111) times confirmed.

### <a id="xdup-18"></a>XDUP-18: Loading, unavailable and empty states are hand-built per screen and announced inconsistently

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 33
- **Where:**
  - [apps/web/components/provider-settings-panel.tsx:236-246](../../../../apps/web/components/provider-settings-panel.tsx#L236): Unavailable text; loading text with no role
  - [apps/web/components/model-policy-panel.tsx:222-231](../../../../apps/web/components/model-policy-panel.tsx#L222): Same pair
  - [apps/web/components/keys-and-vars-panel.tsx:231-240](../../../../apps/web/components/keys-and-vars-panel.tsx#L231): Same pair
  - [apps/web/components/run-list.tsx:284-298](../../../../apps/web/components/run-list.tsx#L284): role=status and data-state on its states
  - [apps/web/components/tool-uses.tsx:262-273](../../../../apps/web/components/tool-uses.tsx#L262): Failed, loading and empty switch, copied at workflow-monitor.tsx:264-273
  - [apps/web/components/jobs-chart.tsx:121-126](../../../../apps/web/components/jobs-chart.tsx#L121): Neither state is announced
- **Evidence:** 19 of 33 loading messages carry role="status" on their own element (found by scanning the enclosing element); 'Sign in, and check that the local API is running' is repeated in 5 components.
  ```
  // model-policy-panel.tsx:229-231
  if (models === null || state === null) {
    return <p className="text-muted-foreground text-sm">Loading models.</p>;
  }
  ```
- **Why it matters:** DH-06 asks for deliberate loading, empty, denied, unavailable and retryable states. Each screen re-decides markup, role and test hooks, so a screen reader announces loading on some screens and not others, and Playwright's data-state hooks exist only where an author added them.
- **Recommendation:** Add components/ui/view-state.tsx with Loading, Unavailable (with retry) and Empty, each with a fixed role and data-state, rendered from the shared loader's state. Adopt it as screens move to that loader.
- **Rule check:** DH-06 and nextjs.md: explicit error, empty and loading states and accessible flows; PRD-Design-System DS-01 to DS-05: shadcn components and Luma tokens.
- **Verification:** confirmed. The cited states were re-read. A heuristic rescan found 18 of 32 loading messages with role=status within five lines, close to the review's 19 of 33. The unavailable sentence (wrapped across lines) repeats in 5 components: data-summary, model-policy, keys-and-vars, provider-settings and run-list.

### <a id="xdup-16"></a>XDUP-16: Budget limits and choices are restated outside domain/budgets.py

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/domain/budgets.py:5-8](../../../../services/agent/src/autobots/domain/budgets.py#L5): BUDGET\_MIN, MAX, STEP and DEFAULT
  - [services/agent/src/autobots/api/run_routes.py:93-97](../../../../services/agent/src/autobots/api/run_routes.py#L93): Messages hard-code US$0.25, US$5.00 and the step
  - [apps/web/components/run-disclosure.tsx:19-20](../../../../apps/web/components/run-disclosure.tsx#L19): MICRO\_USD and a copy of the default budget
  - [apps/web/components/workflow-editor.tsx:118](../../../../apps/web/components/workflow-editor.tsx#L118): useState(1\_000\_000): another copy of the default
  - [apps/web/components/workflow-editor.tsx:144-157](../../../../apps/web/components/workflow-editor.tsx#L144): 'the same budget choices as a goal run', kept by copying the step expansion
  - [apps/web/components/goal-composer.tsx:196-205](../../../../apps/web/components/goal-composer.tsx#L196): Step expansion
  - [apps/web/components/run-controls.tsx:30](../../../../apps/web/components/run-controls.tsx#L30): Third MICRO\_USD
- **Evidence:**
  ```
  # api/run_routes.py:94-95
  "budget_out_of_range": "Choose a budget from US$0.25 to US$5.00.",
  "budget_off_step": "Choose a budget in steps of US$0.25.",
  # domain/budgets.py:5-8
  BUDGET_MIN_MICRO_USD = 250_000 ... BUDGET_DEFAULT_MICRO_USD = 1_000_000
  ```
- **Why it matters:** If the range or step changes in domain/budgets.py (Decision 0022 D11), the API's refusal text keeps stating the old limits, and the editor's fallback default can differ from the composer's. The WF-05 comment promises both screens offer the same choices, which only copying maintains.
- **Recommendation:** Format the messages from the constants using one money formatter, and move the step expansion and default into one web helper fed by RunPreview.budget. The UI's fallback default should come from the preview's BudgetRange.default\_micro\_usd, not a literal.
- **Rule check:** DH-06: avoid duplicated business rules; python-worker.md: exact monetary units, so amounts stay integer micro-USD and are formatted only for display.
- **Verification:** revised. Constants, messages and UI copies confirmed, and contracts/settings.py BudgetRange already carries default\_micro\_usd for the UI fallback. Severity lowered from medium to low: every copy agrees with domain/budgets.py today, both screens expand the same server-supplied range, and the API validates every budget.

### <a id="xdup-19"></a>XDUP-19: Appearance storage keys and values are written twice: in the before-paint script and in the settings control

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/app/layout.tsx:17](../../../../apps/web/app/layout.tsx#L17): BEFORE\_PAINT hard-codes autobots.theme, .serif, .density, .motion and .stream with their values
  - [apps/web/components/appearance-control.tsx:84-96](../../../../apps/web/components/appearance-control.tsx#L84): The same keys and attribute values as a typed table
  - [apps/web/components/theme-provider.tsx:15](../../../../apps/web/components/theme-provider.tsx#L15): Third copy of the theme storage key
- **Evidence:**
  ```
  // appearance-control.tsx:82-83
  // PRD-Studio SE-03: presentation only, stored in this browser. The page applies a saved choice before
  // paint (see app/layout.tsx), and each change here sets the same attribute on the root element.
  ```
- **Why it matters:** Adding or renaming a preference requires a matching edit inside a minified string. A missed edit shows the wrong presentation until hydration, which DS-02's before-paint rule is meant to prevent.
- **Recommendation:** Generate BEFORE\_PAINT from the exported preference table with a small serializer in lib/appearance.ts, and export the theme key for theme-provider. A cheaper alternative is a unit test that every preference key and attribute value appears in BEFORE\_PAINT.
- **Rule check:** nextjs.md and DS-02: an explicit light or dark choice applied before paint and persisted. The script stays inline and minimal, and behavior is unchanged.
- **Verification:** confirmed. BEFORE\_PAINT (layout.tsx:17) hard-codes the keys and values that appearance-control.tsx:84-96 and theme-provider.tsx:15 also define. Added the parity-test alternative, which needs no change to the inline script.

### <a id="xdup-20"></a>XDUP-20: API route modules copy pool access, dependency aliases and idempotency-conflict replies

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 10
- **Where:**
  - [services/agent/src/autobots/api/run_routes.py:63-70](../../../../services/agent/src/autobots/api/run_routes.py#L63): Key alias and \_pool
  - [services/agent/src/autobots/api/workflow_routes.py:62-72](../../../../services/agent/src/autobots/api/workflow_routes.py#L62): Same
  - [services/agent/src/autobots/api/routine_routes.py:29-39](../../../../services/agent/src/autobots/api/routine_routes.py#L29): Same
  - [services/agent/src/autobots/api/settings_routes.py:83](../../../../services/agent/src/autobots/api/settings_routes.py#L83): Inline variant with 'Provider settings are unavailable.' (4 times)
  - [services/agent/src/autobots/api/approval_routes.py:156-159](../../../../services/agent/src/autobots/api/approval_routes.py#L156): Different conflict message
  - [services/agent/src/autobots/api/improvement_routes.py:128-129](../../../../services/agent/src/autobots/api/improvement_routes.py#L128): Another different message
- **Evidence:** \_pool is defined 10 times, the Key alias 5 times and the Member alias 4 times; IdempotencyConflict maps to 409 in 6 places with 3 messages.
  ```
  # run_routes.py:66-70 (same in 9 modules)
  def _pool(request: Request) -> Any:
      pool = request.app.state.pool
      if pool is None:
          raise ApiError(503, "service_unavailable", "The database is unavailable.")
      return pool
  ```
- **Why it matters:** The harm is small today, but every new router copies the block, and one database outage reads as two different messages.
- **Recommendation:** Add api/dependencies.py with Connection (a dependency that yields a pooled connection or raises 503), Key, Member, Owner and User, and map IdempotencyConflict once in the handlers in api/errors.py.
- **Rule check:** DH-06: centralize error handling. Resources stay owned by the FastAPI lifespan.
- **Verification:** confirmed. \_pool 10 times, Key 5, Member 4; IdempotencyConflict mapped to 409 in 6 functions (approval, expert, improvement, routine, run and workflow routes) with 3 messages; 'Provider settings are unavailable.' 4 times in settings\_routes.py. XMOD-11 proposes the same dependencies module from the boundaries side.

## Rejected during verification

No finding was rejected. All 20 were kept, 10 of them revised.

## Not covered

The 8-line detector only finds exact repeats. I found structural duplicates with targeted greps over all 545 in-scope files and opened the code behind every reported pattern, but I did not read every file in full (see filesRead), so near-duplicates outside the listed suspects may remain. Repeats within a single file that the detector flagged (persistent\_install.py 327/539, goal\_loop.py 457/748, improvements.py 205/361, slice-workflows.spec.ts 141/156) are left to the area reviewers. The 40 windows shared by migrations 023 and 027 are the expected forward redefinition of purge\_run\_content and expire\_idempotency\_receipts; their current definitions are easy to find in 027, so they are not reported. Whether purge\_run\_content should also cover run-scoped tables added later (improvement\_replay\_runs in 037, tool\_uses in 038, plan\_task\_times in 048) is a retention-policy question for the py-ops and sql-infra areas. The depth-2 disagreement in the run-tree finding is inferred from code paths and child\_levels = 2, not exercised. This is a static review: no checks or services were run, and nothing here is runtime, H1 or product-acceptance evidence. One grep accidentally included the apps/web/.next build output; those results were discarded. The only files written were scratch detector output in .checks/reviews/review-2026-11-12-09-52-30/sweep-duplication/.
