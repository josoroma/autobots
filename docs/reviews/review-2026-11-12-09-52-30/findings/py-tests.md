# Python: service tests

The service suite (46 files, 9,379 lines, 496 tests, 77 parametrize decorators) runs offline by design and tests the right risks. conftest.py blocks sockets at import and drops any inherited OpenRouter key. Model tests go through the real SDK and adapter over httpx.MockTransport, and leak, SSRF, credential, budget and fencing behavior is pinned with planted sentinels and typed codes. Its weakness is that no shared test layer ever formed: the suite defines no pytest fixture at all. As a result, fake OpenRouter replies, catalog payloads, API auth setup, SQL connection fakes and graph builders are copied from file to file, and the provider fakes are copied again in tests/db. The shared fake transport has also drifted to the superseded two-profile policy and refuses Sol. Where production offers no seam, tests subclass LoopMiddleware and ProviderSettings, or build them without running their constructors, and override their private methods. The suite has 38 private touches, 26 of them on these paid-path classes. This makes the paid-path middleware, already a measured hotspot, costly to refactor. The same gap shows in 44 type: ignore comments (24 for fakes, placeholders and patched methods standing in for concrete types, 14 caused by the tests' own loose annotations) and 173 Any annotations. Files are partly organized by the story or review that added them rather than by module. test_worker_inference.py (1,149 lines) spans six production modules under section headings that no longer match, test_final_review.py spans eight, and loop_middleware.py has no test file of its own. Of the other files over 300 lines, test_final_review.py is a structure problem. The rest (route qualification, model policy, workflows, browsing loop, GitHub issues, tool keys, model attempts) are mostly cohesive around one module and would shrink once shared fakes exist, so their size alone is not a finding. Order-dependent global state (a gc-based model check, logging reconfigured without restore) and source-text assertions are the remaining risks. Duplication with tests/db is limited to the fake provider builders: the split between offline tests and disposable-database checks is deliberate and documented in module docstrings. Findings come from reading code and read-only tool runs; no test was run. [Back to the review](../README.md)

Area `py-tests`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | The project's ruff and mypy strict runs pass on tests, but nothing enforces pytest-style, private-access or local-import rules (47 function-level imports, 16 private accesses), async style is split between asyncio.run and pytest-asyncio, and DH-06's controlled clocks are not used everywhere. |
| modules | 3 | Two helper modules exist (conftest.py, fake_openrouter.py) but are imported through pytest's sys.path insertion, test_tool_catalog.py imports helpers from test_api.py, and there is no support package, so helpers live wherever they were first needed. |
| size | 3 | Functions are short (8 over 40 lines), but test_worker_inference.py is 1,149 lines, nine files exceed 300 lines, and a fake's `__call__` and one test run 86 and 102 lines. |
| functions | 4 | Most tests check one behavior with a clear arrange, act and assert. A few helpers mix patching, building and running (bind_with, call, real_attempt), and one test helper copies the runner's block logic. |
| structure | 3 | Most files map to one module, but some are filed by story or review (test_final_review.py, parts of test_worker_inference.py), so loop_middleware's tests sit in six files and pricing tests in four. |
| approach | 3 | Transport-level fakes under the real SDK are a model approach, but paid-path internals are tested by overriding private methods, SQL fakes match on substrings with silent defaults, and some wiring is checked by searching source text. |
| comments | 4 | Every file has a docstring giving its scope, its story or decision and where the live or disposable counterpart runs. The section headings in test_worker_inference.py and the two-profile docstring in fake_openrouter.py are stale, and a few comments are hard to parse ([test_operation_values.py:84-85](../../../../services/agent/tests/test_operation_values.py#L84)). |
| types | 3 | mypy strict covers tests and passes, but 44 type: ignore comments and 173 Any annotations mean fakes and helpers are not checked against the production signatures they stand in for. |
| errors | 4 | Failures are asserted by typed code or failure class almost everywhere. Only 3 broad pytest.raises and 2 raises(Exception, match=...) remain, and a few tests convert exceptions to strings to work around the gc-based check. |
| tests | 3 | Coverage of risky logic is strong and offline, but the lack of fixtures, the copied fakes, coupling to private internals and order-dependent global state make the suite costly to change. |
| maintainability | 3 | A careful, well-documented suite without a shared layer: adding a profile, route, SQL query or middleware refactor means editing several copies or several private overrides. |

## Strengths

- **Network and provider key are blocked for the whole session, and tests prove it.** [conftest.py:10](../../../../services/agent/tests/conftest.py#L10) removes OPENROUTER_API_KEY, and lines 23-27 replace socket connect, connect_ex, sendto, create_connection and getaddrinfo at import, so third-party import-time code also runs under the block. [test_model_transport.py:50-54](../../../../services/agent/tests/test_model_transport.py#L50) shows that a real-looking key still ends in SocketBlockedError, and [test_app_factory.py:11-15](../../../../services/agent/tests/test_app_factory.py#L11) and [test_contracts.py:162-168](../../../../services/agent/tests/test_contracts.py#L162) prove the block is in force, as model-gateway.md requires.
- **Fakes sit at the HTTP transport, under the real SDK and adapter.** [test_model_attempts.py:247-271](../../../../services/agent/tests/test_model_attempts.py#L247) proves the SDK retries neither a 5xx nor a connection error, and lines 274-298 check the read timeout the SDK actually sends. [test_worker_inference.py:355-364](../../../../services/agent/tests/test_worker_inference.py#L355) asserts the model, max_tokens and provider routing flags on the wire, and [test_route_qualification.py:226-234](../../../../services/agent/tests/test_route_qualification.py#L226) checks every request the paid runner sends. Faking at the transport covers serialization and client configuration that a mocked client would skip.
- **Leak tests use planted sentinels across every output channel.** [test_worker_inference.py:582-598](../../../../services/agent/tests/test_worker_inference.py#L582) plants reply text in an SDK exception and proves it reaches no log field. [test_result_stream.py:117-126](../../../../services/agent/tests/test_result_stream.py#L117) keeps reasoning, plan arguments and private paths out of notifications. [test_reasoning_trial.py:214-227](../../../../services/agent/tests/test_reasoning_trial.py#L214) checks the report, the ledger and caplog. [test_operation_values.py:224-236](../../../../services/agent/tests/test_operation_values.py#L224) scans the status body for paths, hosts and secrets.
- **Architecture rules are enforced by AST and source scans.** [test_model_policy.py:355-374](../../../../services/agent/tests/test_model_policy.py#L355) fails if any module other than factory.py imports an inference SDK. [test_api.py:201-209](../../../../services/agent/tests/test_api.py#L201) forbids background work in request handlers. [test_route_qualification.py:346-355](../../../../services/agent/tests/test_route_qualification.py#L346) forbids strict-output requests in application code, per Decision 0005.
- **Docstrings and names state scope, source and where the rest is proven.** [test_github_issues.py:1](../../../../services/agent/tests/test_github_issues.py#L1) points to tests/db/connector_check.py for the gateway, [test_credentials.py:1](../../../../services/agent/tests/test_credentials.py#L1) and [test_model_attempts.py:1](../../../../services/agent/tests/test_model_attempts.py#L1) point to scripts/app_db.py, and [test_browser_executor.py:1-5](../../../../services/agent/tests/test_browser_executor.py#L1) points to the Docker qualifier. [test_environment.py:1-5](../../../../services/agent/tests/test_environment.py#L1) states what it does not claim. Test names read as behavior, for example test_a_401_for_a_key_replaced_mid_call_leaves_its_successor_alone at [test_worker_inference.py:954](../../../../services/agent/tests/test_worker_inference.py#L954).
- **Injected clocks and sleepers wherever production offers the seam.** [test_wake_clock.py:6-12](../../../../services/agent/tests/test_wake_clock.py#L6) drives both clocks by hand. [test_model_attempts.py:79-85](../../../../services/agent/tests/test_model_attempts.py#L79) records RetryPolicy sleeps against a fixed now. [test_browsing_loop.py:164-171](../../../../services/agent/tests/test_browsing_loop.py#L164) feeds clock ticks. [test_worker_inference.py:197-215](../../../../services/agent/tests/test_worker_inference.py#L197) advances CatalogCache's clock across the refresh boundary.
- **Shared fixture files drive boundary validation in both languages.** [test_contracts.py:30](../../../../services/agent/tests/test_contracts.py#L30) and 61-75 run every case in contracts/fixtures/boundary-cases.json and check that each required kind is covered. [test_credentials.py:34](../../../../services/agent/tests/test_credentials.py#L34) and 39-49 run credential-precedence.json. contracts.md asks for exactly this kind of shared fixture.
- **Protocol seams let fakes type-check with no ignore.** Membership ([test_api.py:29-37](../../../../services/agent/tests/test_api.py#L29)) satisfies MembershipStore ([api/security.py:14](../../../../services/agent/src/autobots/api/security.py#L14)), FakePool ([test_api.py:159-168](../../../../services/agent/tests/test_api.py#L159)) satisfies the app's Pool protocol ([api/app.py:30](../../../../services/agent/src/autobots/api/app.py#L30)), and Pages ([test_browsing_loop.py:40-54](../../../../services/agent/tests/test_browsing_loop.py#L40)) satisfies browsing_loop.Page ([browsing_loop.py:59](../../../../services/agent/src/autobots/application/browsing_loop.py#L59)). None of them needs a type: ignore, unlike the fakes for concrete classes.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [PTST-01](#ptst-01) | high | tests | Paid-path tests replace private LoopMiddleware and ProviderSettings internals instead of using seams | M | high |
| [PTST-02](#ptst-02) | medium | duplication | Fake OpenRouter replies, catalog payloads and SDK clients are hand-built in six test files and again in tests/db | M | low |
| [PTST-03](#ptst-03) | medium | tests | The shared fake transport still encodes the superseded two-profile policy and refuses Sol | S | low |
| [PTST-04](#ptst-04) | medium | size | test_worker_inference.py is 1,149 lines across six production modules, under section headings that no longer match | M | low |
| [PTST-05](#ptst-05) | medium | structure | Tests are filed by the story or review that added them, so one module's tests sit in several files | M | low |
| [PTST-06](#ptst-06) | medium | types | 44 type: ignore comments: 14 from the tests' own loose annotations, 24 from fakes, placeholders and patched methods standing in for concrete types | M | low |
| [PTST-07](#ptst-07) | medium | tests | Session-global state couples tests: a gc-based model check depends on earlier files, and logging is reconfigured without restore | S | low |
| [PTST-08](#ptst-08) | medium | tests | Paid-path wiring, and the egress proxy's import rule, are checked by searching source text | M | low |
| [PTST-09](#ptst-09) | medium | tests | SQL connection fakes are copied per file, match on substrings, and most answer unmatched SQL silently | S | low |
| [PTST-10](#ptst-10) | medium | duplication | The workflow golden-graph tests run a test-side copy of the runner's block rules, which already lacks the foreach bound | S | medium |
| [PTST-11](#ptst-11) | medium | duplication | API boundary setup is copied into three files, and one test module imports another's helpers | S | low |
| [PTST-12](#ptst-12) | low | approach | Async tests use two styles with no rule: 81 asyncio.run calls in 15 files beside 45 asyncio marks in 10 | M | low |
| [PTST-13](#ptst-13) | low | duplication | Sibling test files copy their scaffolding: tool-adapter context, resolver and gateway-refusal block, and workflow graph builders | S | low |
| [PTST-14](#ptst-14) | low | duplication | test_app_factory.py keeps a hand-written copy of all 68 API paths | S | low |
| [PTST-15](#ptst-15) | low | size | FakeGithub.`__call__` in test_github_reads.py is an 86-line chain of inline payloads | S | low |
| [PTST-16](#ptst-16) | low | size | One 102-line test patches ten route dependencies by name to build the Operations status | S | low |
| [PTST-17](#ptst-17) | low | tests | Test cases hide in loops, branches and either-or assertions instead of one parametrized case each | S | low |
| [PTST-18](#ptst-18) | low | tests | Some tests use the wall clock and real sleeps where DH-06 asks for controlled clocks | S | medium |
| [PTST-19](#ptst-19) | low | naming | Test doubles reuse generic names across files, and fixtures pass bare positional literals | S | low |
| [PTST-20](#ptst-20) | low | standards | 47 imports sit inside test functions, and helper imports rely on pytest putting tests/ on sys.path | S | low |

### <a id="ptst-01"></a>PTST-01: Paid-path tests replace private LoopMiddleware and ProviderSettings internals instead of using seams

- **Severity** high · **Dimension** tests · **Effort** M · **Risk** high · **Occurrences** 26
- **Where:**
  - [services/agent/tests/test_worker_inference.py:770-786](../../../../services/agent/tests/test_worker_inference.py#L770): Busy skips `__init__`, overrides _guard, _sleep and _admitted_call, and calls _with_slot, although the constructor takes sleep= and slot_wait_seconds=
  - [services/agent/tests/test_worker_inference.py:744-763](../../../../services/agent/tests/test_worker_inference.py#L744): Refusing overrides _guard and _admitted_call and calls _summarize
  - [services/agent/tests/test_worker_inference.py:811-831](../../../../services/agent/tests/test_worker_inference.py#L811): Stopping overrides _guard, _compacted, _with_slot and _repair
  - [services/agent/tests/test_operations.py:207-219](../../../../services/agent/tests/test_operations.py#L207): Builds LoopMiddleware with `__new__` and assigns _guard and _compacted
  - [services/agent/tests/test_worker_inference.py:921-945](../../../../services/agent/tests/test_worker_inference.py#L921): Settings(ProviderSettings) skips `__init__`, sets self._store = self and overrides _effective_environment, _settings_row and _record
  - [services/agent/tests/test_readiness.py:83-84](../../../../services/agent/tests/test_readiness.py#L83): Patches ProviderSettings.`__init__` to a no-op
  - [services/agent/tests/test_browsing_loop.py:209-218](../../../../services/agent/tests/test_browsing_loop.py#L209): Sets the private ContextVar _ADMITTED; also at [test_worker_inference.py:1133-1139](../../../../services/agent/tests/test_worker_inference.py#L1133), and _MIDDLEWARE at [test_browsing_tool.py:235](../../../../services/agent/tests/test_browsing_tool.py#L235)
  - [services/agent/src/autobots/adapters/loop_middleware.py:350-380](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L350): The constructor needs connection, scope, limits and route. _guard reads ownership from the connection, and _admitted_call builds ModelAdmission(self._connection) itself at lines 577, 589 and 594
- **Evidence:** To swap out private steps, tests subclass production classes or build them without running their constructors. [test_worker_inference.py:770-786](../../../../services/agent/tests/test_worker_inference.py#L770):
  ```python
  class Busy(LoopMiddleware):
      def __init__(self) -> None:
          self._slot_wait_seconds = 30.0
      async def _guard(self) -> float:
          return 1.0
      async def _sleep(self, seconds: float) -> None:
          waits.append(seconds)
  ```
  The constructor already accepts sleep= and slot_wait_seconds= ([loop_middleware.py:357-358](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L357)). But _guard checks ownership over the connection, and _admitted_call constructs its own admission ledger, so Refusing, Busy and Stopping skip `__init__` and override _guard, _admitted_call, _sleep, _compacted, _with_slot and _repair. ProviderSettings builds its own credential store ([provider_settings.py:85-88](../../../../services/agent/src/autobots/application/provider_settings.py#L85)), so tests subclass it, set self._store = self and override its private row methods. Three files set the private ContextVars _ADMITTED and _MIDDLEWARE. Counted across the suite: 16 private-member accesses (ruff --select SLF001 on tests/), 16 private names imported from autobots in 8 files (an ast scan of the import statements) and 6 classes subclassed or built without running `__init__`, 38 in all. 26 of them reach into the paid path: 15 of the SLF001 hits (LoopMiddleware, its two ContextVars, ProviderSettings, CatalogCache and AttemptModel), the 5 loop_middleware helpers imported by name (_charged, _failure_without_status, _finished, _retry_after and _streamed) and the 6 constructor bypasses. The other 12 touch workflow_runner, tool_gateway, runs, goal_loop, domain.workflows and the route qualifier's _main.
- **Why it matters:** loop_middleware.py is 674 lines, and _admitted_call is a measured hotspot (C901 15, PLR0915 65; the constructor takes 10 parameters, PLR0913), so it is a likely refactor target. Any behavior-preserving extraction there would break the tests for budget refusal during compaction, busy-slot waits and cut-off repair at the same moment, for example moving slot waits or summaries into collaborators, renaming a private method, or turning _sleep into a collaborator. The fast, offline safety net disappears exactly where paid calls are admitted. The disposable db checks (tests/db/goal_loop_check.py, memory_check.py and admission_check.py) still drive the real middleware, but only on the db profile. Because the subclasses skip `__init__`, a new attribute read on these paths raises AttributeError only in tests, and the tests keep passing against overridden steps even when the real guard or admission changes. ProviderSettings' key-rejection and run-intent tests have the same problem.
- **Recommendation:** Add seams, then test through public methods. Write the seam-based tests next to the current ones before deleting the overrides.
  - LoopMiddleware: inject the per-dispatch guard and the admission ledger as keyword-only arguments whose defaults keep today's database-backed behavior, so no production call site passes them. Use the existing sleep=, slot_wait_seconds= and summary_route= parameters. Add public context managers for the two ContextVars, as result_stream already does with use_tap and reset_tap.
  - Pure reply helpers: make _charged, _finished, _retry_after and _failure_without_status public in a small module.
  - ProviderSettings: accept the credential store and a settings-row reader as optional constructor arguments.
  - CatalogCache: it already takes now=, so drive staleness with a clock, as [test_worker_inference.py:197-215](../../../../services/agent/tests/test_worker_inference.py#L197) does, instead of writing _snapshot and _fetch.
  - Reuse the in-memory Ledger at [test_model_attempts.py:50-72](../../../../services/agent/tests/test_model_attempts.py#L50) as the admission fake, adding the reconcile and record_reply methods that _admitted_call also calls.
  - Run ruff SLF001 on tests with today's count as a baseline, so new private access shows up in review.
- **Rule check:** python-worker.md and DH-06 ask for tests of ownership, cancellation and budget behavior through injected collaborators, and model-gateway.md requires budget reservations and concurrency limits to be enforced. The seams default to today's guard and admission, so no lease, fence or budget check is weakened (ground rule 2). Only how tests reach them changes. Tests come first because this is a paid path. The new arguments are keyword-only, default to today's guard and ModelAdmission, and stay unset at every production call site.
- **Verification:** revised. All eight locations and the ruff measures match (SLF001 16, C901 15, PLR0915 65, PLR0913 10), but 12 of the 38 private touches are outside the paid path, so occurrences are now the 26 on LoopMiddleware, ProviderSettings, CatalogCache and AttemptModel. The impact now notes that the db profile still drives the real middleware, and the Ledger fake needs reconcile and record_reply.

```text
adapters/loop_middleware.py
  LoopMiddleware(connection, scope, limits, route, *, guard: Guard | None = None,
                 admission: Callable[[], Admission] | None = None, sleep=..., slot_wait_seconds=..., ...)
    Guard = Callable[[], Awaitable[float]]   # default: today's ownership and time-left check
    Admission: Protocol                       # default: ModelAdmission(connection)
  admitted_scope(), active_middleware(m)    # public context managers for _ADMITTED and _MIDDLEWARE
adapters/model_replies.py                    # charged, finished, retry_after, failure_without_status, reply_facts
application/provider_settings.py
  ProviderSettings(connection, context, *, store: CredentialStore | None = None, rows: SettingsRows | None = None)
tests/support/middleware.py
  middleware(guard=..., admission=Ledger(), sleep=recorder)   # builds the real class with fakes
```

### <a id="ptst-02"></a>PTST-02: Fake OpenRouter replies, catalog payloads and SDK clients are hand-built in six test files and again in tests/db

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 27
- **Where:**
  - [services/agent/tests/fake_openrouter.py:34-51](../../../../services/agent/tests/fake_openrouter.py#L34): The shared fake's completion body
  - [services/agent/tests/test_worker_inference.py:255-298](../../../../services/agent/tests/test_worker_inference.py#L255): A second fake: completion, SSE through completion_to_sse, and an SDK factory
  - [services/agent/tests/test_browse_trial.py:48-82](../../../../services/agent/tests/test_browse_trial.py#L48): Completion and SDK client built inline
  - [services/agent/tests/test_model_policy.py:244-277](../../../../services/agent/tests/test_model_policy.py#L244): recording_factory builds a completion and an OpenRouter client
  - [services/agent/tests/test_reasoning_trial.py:101-134](../../../../services/agent/tests/test_reasoning_trial.py#L101): FakeRoute builds a completion and an AsyncClient
  - [services/agent/tests/test_route_qualification.py:104-146](../../../../services/agent/tests/test_route_qualification.py#L104): A hand-written SSE encoder, beside autobots.operations.fake_stream.completion_to_sse
  - [services/agent/tests/test_worker_inference.py:97-109](../../../../services/agent/tests/test_worker_inference.py#L97): catalog_payload; others at [test_browse_trial.py:21-31](../../../../services/agent/tests/test_browse_trial.py#L21), [test_reasoning_trial.py:31-42](../../../../services/agent/tests/test_reasoning_trial.py#L31), [test_final_review.py:81-91](../../../../services/agent/tests/test_final_review.py#L81), [test_route_qualification.py:31-41](../../../../services/agent/tests/test_route_qualification.py#L31) and 358-368, [test_model_policy.py:483-496](../../../../services/agent/tests/test_model_policy.py#L483)
  - [tests/db/product_inference_worker.py:195-204](../../../../tests/db/product_inference_worker.py#L195): The same completion and SDK factory in the db area; [tests/db/keys_and_vars_check.py:50-51](../../../../tests/db/keys_and_vars_check.py#L50) repeats test_browse_trial.py's catalog exactly
- **Evidence:** Counted with grep:
  - 8 hand-written "object": "chat.completion" bodies: six in service tests (also [test_route_qualification.py:148-172](../../../../services/agent/tests/test_route_qualification.py#L148)) and two in tests/db ([product_inference_worker.py:195](../../../../tests/db/product_inference_worker.py#L195), [sleep_inference_worker.py:54](../../../../tests/db/sleep_inference_worker.py#L54)).
  - 10 catalog-payload builders: seven in six service files and three outside (two in tests/db, [tests/web/fixture_upstream_api.py:40](../../../../tests/web/fixture_upstream_api.py#L40)).
  - 9 SDK client factories: seven call default_sdk_client over MockTransport, five here and two in tests/db, and two more build openrouter.OpenRouter directly.
  [test_route_qualification.py:104-146](../../../../services/agent/tests/test_route_qualification.py#L104) writes its own SSE encoder, although autobots.operations.fake_stream.completion_to_sse exists for exactly this and [test_worker_inference.py:289](../../../../services/agent/tests/test_worker_inference.py#L289) and tests/db already use it. The copies already differ: cost present or absent, an extra provider field, stream pieces of 4 versus 16 characters, and words split by spaces.
- **Why it matters:** A change to the provider's reply shape, like Decision 0022's switch to streaming, has to be made in eight places. The worker's fake and the qualifier's fake can also disagree about the streams they produce, so a parsing bug can pass one suite and fail the other.
- **Recommendation:** Build one fake-provider kit, and let each test choose only its reply policy.
  - Put the pure shape builders (completion, tool_call, catalog_payload, with catalog entries derived from PROFILES) next to completion_to_sse in autobots.operations.fake_stream, which tests/db already imports.
  - Keep the recording transport and the SDK factory helper in tests/fake_openrouter.py.
  - Replace test_route_qualification.py's _stream with completion_to_sse, after checking that the cancellation fixture still gets enough chunks to stop on.
- **Rule check:** model-gateway.md makes fake transports the default test path, and DH-06 asks for fake-transport tests of catalog mapping. The kit keeps every test offline and only removes copies. fake_stream.py's own docstring says the fake transports in tests and qualifiers use it.
- **Verification:** confirmed. Recounted with rg: 8 chat.completion bodies, 10 catalog builders and 9 SDK client factories, 27 in all. completion_to_sse takes a piece argument, so the qualifier's 4-character tool-argument chunks can be kept.

```text
autobots/operations/fake_stream.py   (already shared with tests/db)
  completion(message, finish='stop', *, model, usage=USAGE, cost=None) -> dict
  tool_call(name, arguments, call_id='call-1') -> dict
  catalog_payload(profiles=PROFILES.values(), supported=(...), pricing=PRICE) -> dict
  completion_to_sse(completion, piece=16) -> bytes      # exists
tests/fake_openrouter.py
  class RecordingOpenRouter: bodies, keys, clients; __call__ answers reply(body), streaming when asked
  def sdk_factory(handler, *, sync=False) -> Callable[[str], openrouter.OpenRouter]
```

### <a id="ptst-03"></a>PTST-03: The shared fake transport still encodes the superseded two-profile policy and refuses Sol

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [services/agent/tests/fake_openrouter.py:11-13](../../../../services/agent/tests/fake_openrouter.py#L11): Hardcoded DeepSeek and Terra wire IDs; the allowlist has two entries
  - [services/agent/tests/fake_openrouter.py:18](../../../../services/agent/tests/fake_openrouter.py#L18): The docstring says 'the two-profile policy'
  - [services/agent/tests/fake_openrouter.py:31-33](../../../../services/agent/tests/fake_openrouter.py#L31): Any other model gets a 400 'not an approved profile'
  - [services/agent/tests/test_model_transport.py:21-25](../../../../services/agent/tests/test_model_transport.py#L21): test_each_approved_profile_round_trips_through_the_fake covers two wire IDs
  - [services/agent/tests/test_model_policy.py:79-88](../../../../services/agent/tests/test_model_policy.py#L79): The same suite asserts exactly three profiles
  - [services/agent/src/autobots/domain/models.py:72](../../../../services/agent/src/autobots/domain/models.py#L72): OFFERED_FOR_NEW_RUNS includes SOL
- **Evidence:**
  ```python
  DEEPSEEK_WIRE_ID = "deepseek/deepseek-v4.1-flash-1017"
  TERRA_WIRE_ID = "openai/gpt-6.1-terra"
  APPROVED_WIRE_IDS = frozenset({DEEPSEEK_WIRE_ID, TERRA_WIRE_ID})
          if body.get("model") not in APPROVED_WIRE_IDS or body.get("models"):
  ```
  The file last changed in e793570 on 2026-11-05 (Astra to Terra). Decision 0019 added Sol as the third approved profile on 2026-11-07 (5349d39), and Sol is now offered for new runs.
- **Why it matters:** The shared fake answers Sol, an approved profile that is now offered and is the researcher role's built-in default, with a 400 'not an approved profile'. Its users, test_model_transport.py, one assertion in test_model_policy.py and the three tests/faults/model_transport fixtures, therefore can't exercise Sol through it, and test_each_approved_profile_round_trips_through_the_fake claims every approved profile while covering two. Sol does reach the real factory and SDK in [test_browse_trial.py:45-90](../../../../services/agent/tests/test_browse_trial.py#L45), through that file's own fake, which it needs anyway for an async SDK factory and tool-call replies. The fault fixture's docstring repeats 'two approved profiles' ([tests/faults/model_transport/test_bad_unapproved_model.py:1](../../../../tests/faults/model_transport/test_bad_unapproved_model.py#L1)).
- **Recommendation:** Derive the allowlist from the domain table: APPROVED_WIRE_IDS = frozenset(p.wire_id for p in PROFILES.values()). Parametrize the round-trip test over PROFILES.values(), using profile IDs as test ids, and fix the docstring. [test_model_policy.py:79-88](../../../../services/agent/tests/test_model_policy.py#L79) keeps pinning the exact three identities, so deriving the fake from PROFILES can't hide a wrong entry. The stale fault-fixture docstring belongs to the db-tests area, which covers tests/faults/. Keep the 400 message, which [scripts/qualify_faults.py:79](../../../../scripts/qualify_faults.py#L79) expects from the model_unapproved_bad fixture; 'openai/gpt-unapproved' stays outside PROFILES, so that fixture still fails as intended. The fixtures run under the service environment ([scripts/qualify_faults.py:41-49](../../../../scripts/qualify_faults.py#L41)), so fake_openrouter.py can import autobots.domain.models there.
- **Rule check:** model-gateway.md: exactly three approved profiles by Decision 0019 (S2). The fake still refuses unapproved models and fallback arrays, so no guard is weakened.
- **Verification:** revised. Confirmed the two-entry allowlist, the docstring, the two-ID parametrization and the dates of e793570 and 5349d39. Narrowed the impact to the fake's real users, since test_browse_trial.py needs its own async fake anyway, and sent the stale fixture docstring to db-tests, which owns tests/faults.

```python
from autobots.domain.models import PROFILES
APPROVED_WIRE_IDS = frozenset(profile.wire_id for profile in PROFILES.values())

@pytest.mark.parametrize('profile', list(PROFILES.values()), ids=lambda p: p.id.value)
def test_each_approved_profile_round_trips_through_the_fake(profile: ModelProfile) -> None: ...
```

### <a id="ptst-04"></a>PTST-04: test_worker_inference.py is 1,149 lines across six production modules, under section headings that no longer match

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/tests/test_worker_inference.py:120-150](../../../../services/agent/tests/test_worker_inference.py#L120): '# Pricing': parse_pricing and worst_case_cost
  - [services/agent/tests/test_worker_inference.py:508-553](../../../../services/agent/tests/test_worker_inference.py#L508): More pricing tests, filed under '# Binding a job'
  - [services/agent/tests/test_worker_inference.py:556-831](../../../../services/agent/tests/test_worker_inference.py#L556): loop_middleware: reply facts, log fields, retry-after, summary, slot and repair
  - [services/agent/tests/test_worker_inference.py:918-989](../../../../services/agent/tests/test_worker_inference.py#L918): provider_settings: mark_invalid, run_intent, status, revalidate
  - [services/agent/tests/test_worker_inference.py:1011-1016](../../../../services/agent/tests/test_worker_inference.py#L1011): A CatalogCache test filed under '# The worker's refusal'
  - [services/agent/tests/test_worker_inference.py:1019-1082](../../../../services/agent/tests/test_worker_inference.py#L1019): The operations.worker entry point
  - [services/agent/tests/test_worker_inference.py:1085-1149](../../../../services/agent/tests/test_worker_inference.py#L1085): Browsing researcher routes, still under '# The entry point'
  - [services/agent/tests/test_worker_inference.py:245-298](../../../../services/agent/tests/test_worker_inference.py#L245): A second fake OpenRouter beside tests/fake_openrouter.py
- **Evidence:** The file has 64 tests and 10 section comments, and imports from 16 autobots modules (lines 21-89):
  ```text
  120:# Pricing
  194:# The catalog cache
  447:# Binding a job          <- more pricing tests at 508-553
  556:# What a provider's replies mean for the ledger  <- LoopMiddleware internals at 741-831
  918:# Marking a key rejected <- ProviderSettings
  992:# The worker's refusal   <- a CatalogCache test at 1011-1016
  1019:# The entry point       <- browsing role routes at 1085-1149
  ```
  The file also holds 67 of the suite's 173 Any annotations (ruff ANN401) and 26 asyncio.run calls.
- **Why it matters:** Someone changing adapters/models/catalog.py, loop_middleware.py or provider_settings.py won't find the tests by file name. Pricing tests sit in two places in this file alone, so a new pricing case can land in either. A review of this file mixes six concerns, and edits conflict with unrelated work.
- **Recommendation:** Split the file by the module under test. First move the tests unchanged, as one mechanical, reviewable change. Then remove duplication, merging the local Fake into the shared fake module (see the fake OpenRouter finding). Keep the story and decision references in docstrings.
- **Rule check:** DH-06 asks for small cohesive modules. A move changes no behavior and keeps the story and decision references the project requires.
- **Verification:** revised. Confirmed 1,149 lines, 64 tests, 10 headings, 16 imported autobots modules, 67 ANN401 hits and 26 asyncio.run calls. The sketch now files each test by the module it exercises, keeping CatalogCache, which lives in worker_inference.py, in test_worker_inference.py, so it agrees with the rule in PTST-05.

```text
tests/test_model_catalog.py      parse_pricing and listed prices, for adapters/models/catalog.py (120-146, 515-541)
tests/test_model_admission.py    worst_case_cost (147-150, 508-512, 544-553), with test_model_attempts.py:224-231
tests/test_worker_inference.py   frozen_policy, prepared, CatalogCache, AttemptModel, InferenceSource bind, open_attempt
                                 and role_route (153-240, 299-506, 834-915, 992-1016, 1085-1149)
tests/test_loop_middleware.py    reply facts, uncertain-call fields, retry-after, summary, slot, repair (556-831),
                                 plus the loop_middleware tests from test_final_review.py
tests/test_provider_settings.py  mark_invalid, run_intent, status, revalidate (918-989), joining the existing file
tests/test_worker.py             inference_from_environment and both(), for operations/worker.py (1019-1082)
tests/fake_openrouter.py         the Fake at 245-298, merged with FakeOpenRouter
```

### <a id="ptst-05"></a>PTST-05: Tests are filed by the story or review that added them, so one module's tests sit in several files

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/tests/test_final_review.py:1](../../../../services/agent/tests/test_final_review.py#L1): Filed by provenance: 19 tests over 8 modules
  - [services/agent/tests/test_final_review.py:53-76](../../../../services/agent/tests/test_final_review.py#L53): loop_middleware reservation tests, more at 249-302
  - [services/agent/tests/test_final_review.py:182-207](../../../../services/agent/tests/test_final_review.py#L182): reasoning_trial.key_usage, also tested at [test_reasoning_trial.py:230-253](../../../../services/agent/tests/test_reasoning_trial.py#L230)
  - [services/agent/tests/test_operations.py:167-200](../../../../services/agent/tests/test_operations.py#L167): Compaction summary tests in the redaction file, although test_compaction.py exists
  - [services/agent/tests/test_model_attempts.py:224-231](../../../../services/agent/tests/test_model_attempts.py#L224): worst_case_cost here and in test_worker_inference.py; parse_pricing also at [test_final_review.py:249-263](../../../../services/agent/tests/test_final_review.py#L249) and [test_model_policy.py:482-512](../../../../services/agent/tests/test_model_policy.py#L482)
  - [services/agent/tests/test_workflows.py:292-294](../../../../services/agent/tests/test_workflows.py#L292): run_projection.public_text in the workflows file, also at [test_contracts.py:126-128](../../../../services/agent/tests/test_contracts.py#L126)
- **Evidence:**
  ```python
  """What US-11.12's independent review found, held in place. Fakes only, and no model call."""
  from autobots.adapters.loop_middleware import (
  from autobots.application.operations import (
  from autobots.operations.worker import inference_step
  ```
  The 19 tests in test_final_review.py exercise loop_middleware, worker_inference, operations.logs, application.operations, reasoning_trial, operations.worker, assignments and contracts.run_commands. loop_middleware.py (674 lines) has no test file of its own: grep finds its tests in six files. Pricing is tested in four files, and public_text, key_usage and the compaction summary in two each.
- **Why it matters:** Finding a module's tests takes a grep, and a change to loop_middleware or to pricing means edits in four to six files. New tests keep landing in whichever file the current story or review created, so the scatter grows with each round.
- **Recommendation:** Adopt one rule: a test lives in test_&lt;module>.py for the module it exercises, or in test_&lt;module>_&lt;topic>.py when that file grows large. The story, decision or review that motivated it goes in the test's docstring. Then:
  - Distribute test_final_review.py's tests into those files.
  - Create test_loop_middleware.py and test_model_catalog.py.
  - Move the compaction tests to test_compaction.py and public_text to test_run_projection.py.
  - Record the rule in the tests section of standards.md.
- **Rule check:** Ground rule 2 keeps the practice of citing decisions and stories. The recommendation moves those citations from file names into docstrings.
- **Verification:** confirmed. Confirmed 19 tests over 8 modules in test_final_review.py, loop_middleware imported by 6 test files and pricing tested in 4. It shares the loop_middleware and pricing moves with PTST-04, which splits test_worker_inference.py; this finding owns the filing rule and test_final_review.py.

```text
test_final_review.py -> test_loop_middleware.py   reservation_for, request_bytes, past_known_price, unencodable requests
                     -> test_worker_inference.py   price refusal, reservation passed on
                     -> test_logs.py, test_operations.py   uvicorn loggers; restore_history, database_conditions
                     -> test_reasoning_trial.py, test_assignments.py, test_contracts.py   key_usage, narrowed_tools, RunRequest
test_operations.py:167-200 -> test_compaction.py
```

### <a id="ptst-06"></a>PTST-06: 44 type: ignore comments: 14 from the tests' own loose annotations, 24 from fakes, placeholders and patched methods standing in for concrete types

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 44
- **Where:**
  - [services/agent/tests/test_code_tools.py:16-42](../../../../services/agent/tests/test_code_tools.py#L16): The helper returns object although search() returns SearchFilesOutput, forcing nine attr-defined ignores
  - [services/agent/tests/test_url_guard.py:39-49](../../../../services/agent/tests/test_url_guard.py#L39): An untyped handler causes two ignores
  - [services/agent/tests/test_provider_settings.py:20-43](../../../../services/agent/tests/test_provider_settings.py#L20): validator() -> object, then an operator ignore
  - [services/agent/tests/test_model_attempts.py:101-102](../../../../services/agent/tests/test_model_attempts.py#L101): The Ledger fake is passed where ModelAdmission is named
  - [services/agent/tests/test_final_review.py:221](../../../../services/agent/tests/test_final_review.py#L221): A Source fake for InferenceSource; line 93 passes None for ProviderContext
  - [services/agent/tests/test_browsing_loop.py:223](../../../../services/agent/tests/test_browsing_loop.py#L223): A Middleware fake for LoopMiddleware; also at line 252, [test_browsing_tool.py:235](../../../../services/agent/tests/test_browsing_tool.py#L235) and [test_worker_inference.py:1141](../../../../services/agent/tests/test_worker_inference.py#L1141)
  - [services/agent/tests/test_browser_executor.py:100](../../../../services/agent/tests/test_browser_executor.py#L100): A Stream fake for asyncio.StreamWriter; also at lines 119 and 149
  - [services/agent/tests/test_worker_inference.py:337-352](../../../../services/agent/tests/test_worker_inference.py#L337): source_with(...) -> Any and invoke(model: Any) -> Any carry the fakes
- **Evidence:**
  ```python
  def run(**arguments: object) -> object:  # test_code_tools.py:16
      return search(FILES, SearchFilesInput.model_validate(arguments))
      first = found.matches[0]  # type: ignore[attr-defined]
  ```
  Inventory from grep, by cause:
  - 14 from the tests' own helpers: nine in test_code_tools.py, two in test_url_guard.py, and one each at [test_provider_settings.py:43](../../../../services/agent/tests/test_provider_settings.py#L43), [test_plans.py:41](../../../../services/agent/tests/test_plans.py#L41) and [test_browser_executor.py:38](../../../../services/agent/tests/test_browser_executor.py#L38).
  - 14 fakes for concrete classes: StreamWriter, LoopMiddleware, ModelAdmission, InferenceSource, the CDP client, BrowserExecutor and ToolGateway ([test_workflows.py:318](../../../../services/agent/tests/test_workflows.py#L318), 320 and 377).
  - 5 placeholder values: a string for ModelRoute, None for ProviderContext, SimpleNamespace stand-ins.
  - 5 method replacements on instances.
  - 6 deliberate: three socket patches in conftest.py, an immutability check, a TypedDict override and a third-party attribute.
  ruff ANN401 also finds 173 Any annotations, 67 of them in test_worker_inference.py.
- **Why it matters:** mypy strict runs on tests, but these fakes are never checked against the signatures they stand in for. If InferenceSource.open_attempt or ModelAdmission.settle changes, ScriptedKeys and Ledger still type-check: they fail only at run time, or keep passing on paths the test doesn't reach. Where production declares a Protocol (MembershipStore, Pool, browsing_loop.Page), the fakes need no ignore at all, so this cost is avoidable.
- **Recommendation:** Work in four steps:
  1. Fix the 14 self-inflicted ignores now. Annotate run(...) -> SearchFilesOutput, type the Recorder handler as Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]], declare validator(...) -> Callable[[SecretStr], Awaitable[KeyCheck]], and give rejected() the real parameter types.
  2. Add narrow Protocols at the seams the tests use:
     - AttemptSource (open_attempt, reject_key) for AttemptModel.
     - An admission protocol for call_with_policy; test_model_attempts.py's Ledger already fits it.
     - The one-method middleware protocol that admitted_steps needs.
     - A writer protocol for the egress handlers.
     - A gateway protocol for workflow_runner._tool.
  3. Replace placeholder values with typed fixtures, such as a ROUTE and a ProviderContext.
  4. Give every remaining ignore a reason comment.
- **Rule check:** DH-06 asks for narrow interfaces and for third-party typing exceptions that are narrow and documented. contracts.md keeps domain, row, DTO, graph and UI types distinct; these Protocols describe call seams only and merge no types. The change is type-only, and mypy strict verifies it.
- **Verification:** revised. Recounted all 44 by cause and the breakdown holds: 14 self-inflicted, 14 fakes for concrete classes, 5 placeholders, 5 method replacements and 6 deliberate. The title now names the placeholders and patched methods among the 24, and search() does return SearchFilesOutput.

```python
class AttemptSource(Protocol):
    async def open_attempt(self, workspace_id: UUID, policy: RolePolicy, *,
                           reserved_micro_usd: int | None = ..., role: ModelRole = ...) -> tuple[Any, CredentialReference]: ...
    async def reject_key(self, workspace_id: UUID, used: CredentialReference) -> None: ...
class Admits(Protocol):
    async def admitted(self, request: Any, handler: Handler, route: ModelRoute) -> tuple[Any, bool]: ...
class ByteWriter(Protocol):   # egress_proxy handlers
    def write(self, data: bytes) -> None: ...; async def drain(self) -> None: ...; def close(self) -> None: ...
```

### <a id="ptst-07"></a>PTST-07: Session-global state couples tests: a gc-based model check depends on earlier files, and logging is reconfigured without restore

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/tests/test_environment.py:75-76](../../../../services/agent/tests/test_environment.py#L75): Asserts that no BaseChatModel exists anywhere in the process
  - [services/agent/tests/test_browsing_loop.py:231-245](../../../../services/agent/tests/test_browsing_loop.py#L231): Returns strings instead of raising and calls gc.collect() so that test_environment passes
  - [services/agent/tests/test_browsing_loop.py:248-260](../../../../services/agent/tests/test_browsing_loop.py#L248): The same workaround
  - [services/agent/tests/test_final_review.py:101-120](../../../../services/agent/tests/test_final_review.py#L101): Runs dictConfig(uvicorn) and configure_logging(stream) with no restore
  - [services/agent/tests/test_operations.py:64-66](../../../../services/agent/tests/test_operations.py#L64): Runs configure_logging(stream) with no restore
  - [services/agent/src/autobots/operations/logs.py:70-86](../../../../services/agent/src/autobots/operations/logs.py#L70): Replaces the root handlers and changes root, uvicorn and httpx logger settings
  - [services/agent/tests/test_github_issues.py:260-267](../../../../services/agent/tests/test_github_issues.py#L260): Re-executes a script and writes sys.modules on every call
- **Evidence:**
  ```python
  def test_no_model_is_constructed() -> None:  # test_environment.py:75
      assert [item for item in gc.get_objects() if isinstance(item, BaseChatModel)] == []
  # test_browsing_loop.py:235
          # No traceback is kept, so no model outlives this test (see test_environment).
  ```
  Test files run in alphabetical order, so test_browsing_loop.py runs before test_environment.py, and it has to free every AdmittedModel it builds. After test_final_review.py, the root logger writes to a StringIO that nothing reads, at INFO level, with uvicorn propagation and the httpx level changed. Counted with grep: one gc.get_objects() scan, two tests that call gc.collect() to protect it ([test_browsing_loop.py:245](../../../../services/agent/tests/test_browsing_loop.py#L245) and 260), two tests that reconfigure logging without restoring it ([test_final_review.py:103-107](../../../../services/agent/tests/test_final_review.py#L103) and [test_operations.py:66](../../../../services/agent/tests/test_operations.py#L66)) and one sys.modules write ([test_github_issues.py:265](../../../../services/agent/tests/test_github_issues.py#L265)), 6 sites.
- **Why it matters:** test_environment's import check scans gc.get_objects() without collecting first, so it passes only if every earlier test has freed its models, and thirteen test files sort before it. A new one that leaves a model in a reference cycle, such as a traceback kept by pytest.raises, would fail test_environment far from the cause, and the workaround spreads: exceptions are already being turned into strings to avoid keeping a traceback. After the logging tests, the root logger stays at INFO behind a StringIO handler and the httpx logger at WARNING for every later file. No current assertion depends on that ([test_reasoning_trial.py:217](../../../../services/agent/tests/test_reasoning_trial.py#L217) sets its own caplog level), but any later log assertion would.
- **Recommendation:** Make the import check independent of test order. The smallest step is a gc.collect() before the scan, which already makes the workarounds unnecessary. The precise one checks what the PRD 3.1 import gate means, right after collection: a pytest_collection_finish hook in conftest.py that runs gc.collect() and asserts that no BaseChatModel exists, or a fresh interpreter with sockets blocked. Then drop the gc.collect() calls and the string-returning wrappers. Add a restore_logging fixture that snapshots and restores the root, uvicorn and httpx handlers, levels and propagation, and use it in both logging tests. Load the qualifier script once in a module-scoped fixture, and remove it from sys.modules on teardown.
- **Rule check:** python-worker.md keeps model tests fake and offline. The PRD 3.1 import check stays; it just runs at a point that doesn't depend on test order.
- **Verification:** revised. Confirmed the uncollected gc scan, both workarounds, both unrestored logging reconfigurations and the sys.modules write: 6 sites, not 5. Narrowed the logging impact, since test_reasoning_trial.py sets its own caplog level, and added the smallest fix, a gc.collect() before the scan.

```python
# conftest.py
def pytest_collection_finish(session: pytest.Session) -> None:
    gc.collect()
    built = [o for o in gc.get_objects() if isinstance(o, BaseChatModel)]
    assert not built, 'a chat model was built at import'

@pytest.fixture
def restore_logging() -> Iterator[None]: ...   # snapshot handlers, levels and propagate; restore after
```

### <a id="ptst-08"></a>PTST-08: Paid-path wiring, and the egress proxy's import rule, are checked by searching source text

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/tests/test_final_review.py:266-270](../../../../services/agent/tests/test_final_review.py#L266): Three substring checks on inspect.getsource
  - [services/agent/tests/test_final_review.py:280-290](../../../../services/agent/tests/test_final_review.py#L280): Checks the order of two strings in _admitted_call's source
  - [services/agent/src/autobots/application/worker_inference.py:317-318](../../../../services/agent/src/autobots/application/worker_inference.py#L317): The pinned text: a positional ModelRoute(...) call and reserved_micro_usd=worst_case
  - [services/agent/tests/test_worker_inference.py:485-492](../../../../services/agent/tests/test_worker_inference.py#L485): bind_with() already runs bind but doesn't assert rate, tier or the reservation
  - [services/agent/tests/test_browser_executor.py:157-159](../../../../services/agent/tests/test_browser_executor.py#L157): Checks imports by substring
- **Evidence:**
  ```python
  def test_the_wiring_a_unit_test_cant_reach_is_in_place() -> None:
      """Text only: these three call sites otherwise run only with a real worker."""
      assert "inference_step(config, source, store, stop)" in inspect.getsource(worker_module)
      assert "reserved_micro_usd=worst_case" in inspect.getsource(InferenceSource.bind)
      assert "worst_case, rate, tier)" in inspect.getsource(InferenceSource.bind)
  ```
  [test_browser_executor.py:157-159](../../../../services/agent/tests/test_browser_executor.py#L157) checks with two substring tests that the egress proxy imports nothing from autobots. Counted with grep for inspect.getsource and read_text: three substring checks at [test_final_review.py:268-270](../../../../services/agent/tests/test_final_review.py#L268), one order check at 289-290 and the proxy's import check, 5 in all. The scans at [test_api.py:201-209](../../../../services/agent/tests/test_api.py#L201), [test_model_policy.py:355-374](../../../../services/agent/tests/test_model_policy.py#L355) and [test_route_qualification.py:346-355](../../../../services/agent/tests/test_route_qualification.py#L346) forbid patterns rather than pin wiring, and are not counted.
- **Why it matters:** Switching the ModelRoute call to keyword arguments, renaming a local or a formatter line break would fail these tests with behavior unchanged. A comment containing the same text would keep them green after the real argument is gone. These lines guard whether a fresh price is compared with what was reserved, so a false pass could let an under-reserved paid call through unnoticed. Moving the AdmissionRequest construction into a helper would likewise make [test_final_review.py:290](../../../../services/agent/tests/test_final_review.py#L290) raise ValueError with behavior unchanged.
- **Recommendation:** Assert behavior instead:
  - bind_with() ([test_worker_inference.py:472-482](../../../../services/agent/tests/test_worker_inference.py#L472)) already runs InferenceSource.bind, which returns a model factory with the config. Assert config.route.input_per_million_micro_usd and tier_from_tokens, then call the factory and invoke the AttemptModel it returns with InferenceSource.open_attempt monkeypatched to record reserved_micro_usd, the way [test_final_review.py:210-224](../../../../services/agent/tests/test_final_review.py#L210) records what an AttemptModel passes on, and check that it equals the worst case.
  - Test the unencodable-request ordering through awrap_model_call once the admission seam from the first finding exists: expect LoopStopped('request_unencodable') with no admission recorded.
  - The worker-loop wiring runs for real in tests/db/product_inference_worker.py on a disposable stack. If a fast check is wanted, inject the step builder.
  - Replace the proxy's substring check with an AST import scan like the one at [test_model_policy.py:355-374](../../../../services/agent/tests/test_model_policy.py#L355).
- **Rule check:** python-worker.md keeps model tests fake. Runs on the disposable db profile remain separate evidence, as AGENTS.md separates mocked, disposable and live evidence.
- **Verification:** revised. Confirmed the three substring checks, the order check, and that bind_with() reaches bind without asserting rate, tier or the reservation; worker.main runs for real in tests/db/product_inference_worker.py. The sketch now calls the factory that bind returns, and the title names the egress proxy's import check, a boundary rule rather than paid-path wiring.

```python
def test_bind_reserves_the_worst_case_and_carries_rate_and_tier(monkeypatch):
    seen: list[int | None] = []
    async def recording(self, *_, reserved_micro_usd=None, **__):
        seen.append(reserved_micro_usd); raise ProviderFailure(FailureClass.OTHER)
    monkeypatch.setattr(InferenceSource, 'open_attempt', recording)
    factory, config = bind_with(snapshot(), (None, 777), monkeypatch)
    assert config.route.input_per_million_micro_usd == 1_000_000 and config.route.tier_from_tokens is None
    with pytest.raises(ProviderFailure): asyncio.run(factory().ainvoke([]))
    assert seen == [777]
```

### <a id="ptst-09"></a>PTST-09: SQL connection fakes are copied per file, match on substrings, and most answer unmatched SQL silently

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [services/agent/tests/test_final_review.py:141-172](../../../../services/agent/tests/test_final_review.py#L141): Fakes database_conditions; answers the hold query with an empty tuple at lines 156-157
  - [services/agent/tests/test_schema_release.py:62-100](../../../../services/agent/tests/test_schema_release.py#L62): Fakes the same function; answers the hold query with None at lines 84-85
  - [services/agent/src/autobots/application/operations.py:147-151](../../../../services/agent/src/autobots/application/operations.py#L147): held = await cursor.fetchone() is not None
  - [services/agent/tests/test_tool_keys.py:94-101](../../../../services/agent/tests/test_tool_keys.py#L94): Saved dispatches on SQL text
  - [services/agent/tests/test_tool_keys.py:183-201](../../../../services/agent/tests/test_tool_keys.py#L183): Recorded, with a nested Row class
  - [services/agent/tests/test_tool_keys.py:226-243](../../../../services/agent/tests/test_tool_keys.py#L226): Approvals dispatches on SQL text
  - [services/agent/tests/test_operation_values.py:130-133](../../../../services/agent/tests/test_operation_values.py#L130): Pool, identical to [test_readiness.py:51-54](../../../../services/agent/tests/test_readiness.py#L51)
  - [services/agent/tests/test_worker_inference.py:454-462](../../../../services/agent/tests/test_worker_inference.py#L454): Rows answers every statement with the same value
- **Evidence:**
  ```python
  async def execute(self, statement: str, *_: Any) -> FakeCursor:  # test_final_review.py:153
      if "pg_attribute" in statement:
          return FakeCursor((self.missing_columns,))
      if "installation_holds" in statement:
          return FakeCursor(())
      return FakeCursor((0,))
  ```
  because database_conditions reads an empty tuple as present ("is not None"), this fake quietly arranges a restore hold, which its test never asserts, while test_schema_release.py's fake of the same query arranges none. An ast scan for classes that define execute, fetchone or fetchall, or connection(), leaving out gateway fakes and the lifecycle pool in test_api.py, finds 14 top-level connection, cursor and pool classes in 6 files, and 19 with those nested inside tests. Unmatched SQL gets a plausible row from 4 of them (test_final_review.py's FakeConnection, test_schema_release.py's Connection, test_tool_keys.py's Both and test_worker_inference.py's Rows), None from 3, and an AssertionError only from Saved and Untouched in test_tool_keys.py.
- **Why it matters:** A reworded or added query silently gets (0,) or a fixed value instead of failing. A fake can therefore pass while modeling a different database than its test intends, as the hold above shows. Each new query in operations or tool keys means updating several hand-written fakes.
- **Recommendation:** Add one ScriptedConnection in tests/support/db.py. It holds a list of (SQL fragment, rows) rules, records statements and parameters, supports transaction() and async context use, and raises AssertionError for any statement that no rule matches. Add one FakePool beside it. Rebuild these fakes on it, and in test_final_review.py answer the hold query with None, or assert the hold condition. Real SQL stays covered by the db profile. The API helpers in PTST-11 import FakePool from here.
- **Rule check:** None directly. Real SQL stays covered by the db profile's disposable checks, and these fakes stay offline.
- **Verification:** revised. Confirmed that database_conditions reads an empty tuple as held ([application/operations.py:151](../../../../services/agent/src/autobots/application/operations.py#L151)), so test_final_review.py's fake arranges a hold its test never checks. Recounted 14 top-level fakes in 6 files, 19 with nested ones: 4 answer unmatched SQL with a row, 3 with None and 2 assert, so the title now says most answer silently.

```python
class ScriptedConnection:
    def __init__(self, *rules: tuple[str, list[tuple[Any, ...]]]) -> None: ...
    async def execute(self, sql: str, params: Any = None) -> ScriptedCursor: ...   # raises when no rule matches
    def transaction(self) -> AbstractAsyncContextManager[None]: ...
    statements: list[tuple[str, Any]]
class FakePool:
    def connection(self) -> ScriptedConnection: ...
```

### <a id="ptst-10"></a>PTST-10: The workflow golden-graph tests run a test-side copy of the runner's block rules, which already lacks the foreach bound

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/tests/test_workflow_execution.py:29-63](../../../../services/agent/tests/test_workflow_execution.py#L29): run(): 'The same decisions the runner makes, over plain dictionaries' (ruff C901 13)
  - [services/agent/tests/test_workflow_execution.py:55-57](../../../../services/agent/tests/test_workflow_execution.py#L55): foreach emits every item, with no bound
  - [services/agent/src/autobots/application/workflow_runner.py:175-189](../../../../services/agent/src/autobots/application/workflow_runner.py#L175): The real pure blocks, including the foreach_over_bound check
- **Evidence:**
  ```python
  elif block == "foreach":                                   # test_workflow_execution.py:55
      for index, item in enumerate(step.inputs["items"]):
          emissions[(step.key, "item", index)] = item
  if block == "foreach":                                     # workflow_runner.py:185
      items = step.inputs["items"]
      if len(items) > config["max_items"]:
          raise BlockFailed("foreach_over_bound")
  ```
- **Why it matters:** These tests check domain readiness (next_steps) against emissions produced by the copy, not by _run_block. A change to ports, emission indexes or the foreach bound in the runner goes unseen here, and an over-bound list succeeds in these tests although the runner fails it.
- **Recommendation:** Extract the pure block rules (input, output, join, transform, condition, and foreach with its bound) from _run_block into one domain function, and call it from both the runner and the test helper. Tool-backed blocks stay in the runner. Then add a golden case for an over-bound foreach. Write characterization tests first, because the runner executes durable workflow steps.
- **Rule check:** DH-06 asks to keep domain decisions independent of HTTP and LangGraph and to avoid duplicated business rules. Execution stays in the Python runner; no transition or scheduling moves anywhere.
- **Verification:** confirmed. Confirmed the copied block rules (ruff C901 13), the missing bound at [test_workflow_execution.py:55-57](../../../../services/agent/tests/test_workflow_execution.py#L55) and the real check at [workflow_runner.py:185-188](../../../../services/agent/src/autobots/application/workflow_runner.py#L185). No golden case uses an over-bound list today, so the divergence is latent rather than a current false pass.

```text
domain/workflow_execution.py
  def pure_emissions(block: str, config: Mapping[str, Any], step: Step,
                     inputs: Mapping[str, Any]) -> list[tuple[str, int, Any]] | None
      # None for tool-backed blocks; raises BlockFailed('foreach_over_bound')
application/workflow_runner.py
  _run_block: emitted = pure_emissions(...); if emitted is not None: return emitted; then the tool blocks
tests/test_workflow_execution.py
  run(): records pure_emissions(...) under (step.key, port, index)
```

### <a id="ptst-11"></a>PTST-11: API boundary setup is copied into three files, and one test module imports another's helpers

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [services/agent/tests/test_api.py:17-51](../../../../services/agent/tests/test_api.py#L17): Constants, Membership, token, client and headers
  - [services/agent/tests/test_api.py:138-146](../../../../services/agent/tests/test_api.py#L138): A second MembershipStore fake
  - [services/agent/tests/test_operation_values.py:32-38](../../../../services/agent/tests/test_operation_values.py#L32): The same constants and Settings
  - [services/agent/tests/test_operation_values.py:119-133](../../../../services/agent/tests/test_operation_values.py#L119): Membership and Pool copied
  - [services/agent/tests/test_operation_values.py:203-210](../../../../services/agent/tests/test_operation_values.py#L203): JWT claims and headers built inline, again at lines 275-279
  - [services/agent/tests/test_readiness.py:19-62](../../../../services/agent/tests/test_readiness.py#L19): Constants, Membership, Pool and headers copied again
  - [services/agent/tests/test_tool_catalog.py:17](../../../../services/agent/tests/test_tool_catalog.py#L17): from test_api import client, headers, token
- **Evidence:**
  ```python
  INTERNAL = "fixture-internal"                             # test_api.py:17, test_operation_values.py:32, test_readiness.py:19
  SECRET = "fixture-jwt-secret-with-enough-length"          # the same three files
  WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")  # the same three files
  from test_api import client, headers, token               # test_tool_catalog.py:17
  ```
  Four MembershipStore fakes implement the same three methods, plus a MemberOnly subclass ([test_operation_values.py:263](../../../../services/agent/tests/test_operation_values.py#L263)). Two Pool fakes are identical, and JWT headers are built four times. The suite defines no pytest fixture at all (grep '@pytest.fixture' finds 0). Counted: 3 copies of the identity constants and Settings, 4 MembershipStore fakes, 2 identical pools, 4 JWT builders and 1 cross-module import, 14 in all.
- **Why it matters:** Adding a method to MembershipStore ([api/security.py:14](../../../../services/agent/src/autobots/api/security.py#L14)), or a required header, means editing four fakes in three files. Renaming test_api.py's helpers breaks test_tool_catalog.py. The fakes grant different roles on purpose ([test_readiness.py:38-48](../../../../services/agent/tests/test_readiness.py#L38) documents a member who isn't the owner), but only a docstring says so; a factory would make the role a visible argument.
- **Recommendation:** Create the suite's first shared layer: tests/support/api.py, or fixtures in conftest.py. It holds the identity constants, a members(...) factory that returns a MembershipStore fake for given users and roles, auth_headers(user), and an api_client helper that takes a membership and a pool, using the FakePool of PTST-09. Point test_tool_catalog.py at it instead of at test_api.py.
- **Rule check:** none
- **Verification:** revised. Confirmed the three copies of the identity constants and Settings, four membership fakes plus MemberOnly, two identical pools, four JWT builders, the import from test_api and zero fixtures: 14. The owner-versus-member difference is deliberate and documented, so the impact no longer calls it drift, and FakePool now comes from the support module of PTST-09.

```text
tests/support/api.py
  INTERNAL, SECRET, WORKSPACE, SETTINGS
  def members(roles: Mapping[UUID, str], workspace: UUID = WORKSPACE) -> MembershipStore
  def auth_headers(user: UUID, *, internal: str = INTERNAL) -> dict[str, str]
  FakePool                      # imported from tests/support/db.py (PTST-09)
  def api_client(membership: MembershipStore, pool: Pool | None = None) -> TestClient
```

### <a id="ptst-12"></a>PTST-12: Async tests use two styles with no rule: 81 asyncio.run calls in 15 files beside 45 asyncio marks in 10

- **Severity** low · **Dimension** approach · **Effort** M · **Risk** low · **Occurrences** 81
- **Where:**
  - [services/agent/tests/test_worker_inference.py:1033-1043](../../../../services/agent/tests/test_worker_inference.py#L1033): A go() wrapper that exists only to await one call
  - [services/agent/tests/test_worker_inference.py:197-215](../../../../services/agent/tests/test_worker_inference.py#L197): An inner go() run through asyncio.run; the file has 26 asyncio.run calls
  - [services/agent/tests/test_tool_keys.py:77-83](../../../../services/agent/tests/test_tool_keys.py#L77): A resolve() wrapper
  - [services/agent/tests/test_operation_values.py:163-167](../../../../services/agent/tests/test_operation_values.py#L163): number() is async only so that asyncio.run(number(2)) can return a stub (lines 194-196)
  - [services/agent/tests/test_model_attempts.py:125-137](../../../../services/agent/tests/test_model_attempts.py#L125): The native pytest-asyncio style
  - [services/agent/pyproject.toml:55-59](../../../../services/agent/pyproject.toml#L55): asyncio_mode = 'strict' with pytest-asyncio pinned
- **Evidence:**
  ```python
  def test_a_failing_first_step_does_not_starve_the_second() -> None:
      async def broken(_: Any) -> bool:
          raise RuntimeError("arranged")
      async def working(_: Any) -> bool:
          return True
      async def go() -> bool:
          return await worker.both(broken, working)(None)
      assert asyncio.run(go()) is True
  ```
  15 inner wrapper coroutines exist only to be passed to asyncio.run: six in test_worker_inference.py, three in test_browsing_loop.py, and two each in test_browsing_tool.py, test_result_stream.py and test_tool_keys.py.
- **Why it matters:** Each wrapper adds three to six lines and hides the call under test. Readers can't tell a deliberate asyncio.run (in a sync test that also drives TestClient, which can't run inside a running loop) from habit, and the two styles get mixed as tests move between files.
- **Recommendation:** Write the rule down. Async tests are async def functions marked @pytest.mark.asyncio, or the project sets asyncio_mode = 'auto'. asyncio.run is used only in sync tests that also use TestClient or need a separate loop, with a one-line comment saying why. Make number() a plain function. Convert files when they are next touched, starting with the test_worker_inference.py split.
- **Rule check:** DH-06 asks for pytest with qualified async support; pytest-asyncio 1.4.1.post1 is pinned in the dev group.
- **Verification:** confirmed. Recounted 81 asyncio.run calls in 15 files, 45 asyncio marks in 10, and 15 wrappers passed only to asyncio.run, 16 with number().

```python
@pytest.mark.asyncio
async def test_a_failing_first_step_does_not_starve_the_second() -> None:
    assert await worker.both(broken, working)(None) is True
```

### <a id="ptst-13"></a>PTST-13: Sibling test files copy their scaffolding: tool-adapter context, resolver and gateway-refusal block, and workflow graph builders

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 17
- **Where:**
  - [services/agent/tests/test_jina.py:22-26](../../../../services/agent/tests/test_jina.py#L22): CONTEXT and resolve()
  - [services/agent/tests/test_tavily.py:24-25](../../../../services/agent/tests/test_tavily.py#L24): The identical resolve(); CONTEXT again at line 61
  - [services/agent/tests/test_jina.py:93-99](../../../../services/agent/tests/test_jina.py#L93): The gateway-refusal block
  - [services/agent/tests/test_tavily.py:103-110](../../../../services/agent/tests/test_tavily.py#L103): The same block
  - [services/agent/tests/test_market_data.py:128-134](../../../../services/agent/tests/test_market_data.py#L128): The same block, again at lines 200-206; CONTEXT at line 18
  - [services/agent/tests/test_workflows.py:26-36](../../../../services/agent/tests/test_workflows.py#L26): node() and link()
  - [services/agent/tests/test_workflow_execution.py:16-26](../../../../services/agent/tests/test_workflow_execution.py#L16): Identical node() and link()
  - [services/agent/tests/test_workflow_execution.py:102-114](../../../../services/agent/tests/test_workflow_execution.py#L102): The branch graph again, as in [test_workflows.py:68-81](../../../../services/agent/tests/test_workflows.py#L68); loop() at [test_workflows.py:50-65](../../../../services/agent/tests/test_workflows.py#L50) is the same graph as upper_loop() at lines 66-82
- **Evidence:**
  ```python
  fake = Fake()                                                # test_jina.py:93
  registry = ToolRegistry()
  registry.register(tools(fake)[tool_id])
  scope = ToolScope(uuid4(), uuid4(), 1, {tool_id: 1})
  result = await ToolGateway(registry).execute(None, scope, tool_id, arguments)
  assert (result.outcome.value, result.code) == ("denied", "invalid_arguments")
  assert fake.seen == []
  ```
  The count, by grep: 4 gateway-refusal blocks, 5 ToolContext constants or factories (also [test_github_reads.py:20](../../../../services/agent/tests/test_github_reads.py#L20) and [test_github_issues.py:62](../../../../services/agent/tests/test_github_issues.py#L62)), 2 resolvers, and 2 copies each of node/link, branch and loop.
- **Why it matters:** A change to ToolScope's fields, to the gateway's refusal shape or to the graph IR's node format means editing every copy. The helpers are also bypassed where they exist: [test_workflows.py:421-438](../../../../services/agent/tests/test_workflows.py#L421) writes nodes and links as raw dicts beside node() and link().
- **Recommendation:** Move the tool-adapter helpers into tests/support/tools.py and the graph builders into tests/support/graphs.py, then import them in both files of each pair.
- **Rule check:** none
- **Verification:** revised. Recounted 4 refusal blocks, 5 ToolContext constants or factories, 2 identical resolvers and 2 copies each of node/link, branch and loop: 17. The raw-dict graph at [test_workflows.py:421-438](../../../../services/agent/tests/test_workflows.py#L421) sits beside node() and link() in the same file, so it is cited as a bypassed helper, not as drift between copies.

```text
tests/support/tools.py
  CONTEXT; def context(operation: str | None = None) -> ToolContext
  def resolver(names: Mapping[str, list[str]]) -> Callable[[str, int], Awaitable[list[str]]]
  async def refused_by_gateway(tool: ToolDefinition, arguments: dict[str, Any]) -> ToolResult
tests/support/graphs.py
  node, link, simple, loop, branch, chain
```

### <a id="ptst-14"></a>PTST-14: test_app_factory.py keeps a hand-written copy of all 68 API paths

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/tests/test_app_factory.py:18-88](../../../../services/agent/tests/test_app_factory.py#L18): An unsorted literal of 68 paths in a 71-line test
  - [scripts/verify.py:158](../../../../scripts/verify.py#L158): The contract_drift step already regenerates and compares the committed contract
- **Evidence:**
  ```python
  def test_the_schema_builds_without_any_connection() -> None:
      assert set(create_app().openapi()["paths"]) == {
          "/v1/health",
          "/v1/models",
          "/v1/approvals",
          ...  # 68 paths, unsorted, through line 88
      }
  ```
  The committed contracts/generated/openapi.json holds the same 68 paths. Of the 35 commits that touched this file, 33 added path lines to this literal (git log -p).
- **Why it matters:** Every story that adds a route edits this literal by hand, and a failure prints two 68-item sets to compare. The literal is a second copy of what contract_drift already pins.
- **Recommendation:** Keep the test's purpose, showing that the schema builds with sockets blocked and no key, and compare its paths against the committed generated document, which tests may read but never edit. Alternatively, assert a few sentinel paths and leave the full list to contract_drift.
- **Rule check:** Ground rule 2 forbids hand-editing contracts/generated/; this test only reads it. contracts.md keeps drift detection with the contract_drift step.
- **Verification:** confirmed. Confirmed 68 unsorted paths equal to the committed openapi.json, 33 of the file's 35 commits adding paths, and contract_drift at [scripts/verify.py:158](../../../../scripts/verify.py#L158).

```python
def test_the_schema_builds_without_any_connection() -> None:
    committed = json.loads((REPOSITORY / 'contracts/generated/openapi.json').read_text())
    assert set(create_app().openapi()['paths']) == set(committed['paths'])
```

### <a id="ptst-15"></a>PTST-15: FakeGithub.`__call__` in test_github_reads.py is an 86-line chain of inline payloads

- **Severity** low · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/tests/test_github_reads.py:28-113](../../../../services/agent/tests/test_github_reads.py#L28): Five path branches with inline JSON, and a 599 fallback
- **Evidence:**
  ```python
  def __call__(self, request: httpx.Request) -> httpx.Response:
      self.requests.append(request)
      path = request.url.path
      if path.endswith("/pulls"):
          return httpx.Response(
              200,
              json=[
  ```
  The method routes five endpoints by path suffix, with each endpoint's JSON written inside its branch (the pulls payload alone is 22 lines), and answers any other path with httpx.Response(599).
- **Why it matters:** Adding a read tool or changing a payload means editing inside one long method where data and routing are interleaved. An unexpected path gets a 599, which the tool turns into a typed failure. Today's tests assert exact codes and values, so that shows up as a puzzling mismatch rather than a false pass, but it never says which path was unexpected.
- **Recommendation:** Lift the payloads into module constants, route through a small table, and fail the test on any unknown path.
- **Rule check:** none
- **Verification:** revised. Confirmed the 86-line method with five branches and a 599 fallback. Today's tests assert exact codes and values, so the 'pass for the wrong reason' risk was overstated; the impact now says the failure is confusing rather than silent.

```python
ROUTES = (("/pulls", PULLS), ("/jobs", JOBS), ("/runs", RUNS), ("/search/issues", ISSUES))
def __call__(self, request: httpx.Request) -> httpx.Response:
    self.requests.append(request)
    if "/contents/" in request.url.path:
        return httpx.Response(200, json=file_payload(self.file_size))
    for suffix, payload in ROUTES:
        if request.url.path.endswith(suffix):
            return httpx.Response(200, json=payload)
    raise AssertionError(f"unexpected GitHub path {request.url.path}")
```

### <a id="ptst-16"></a>PTST-16: One 102-line test patches ten route dependencies by name to build the Operations status

- **Severity** low · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/tests/test_operation_values.py:136-237](../../../../services/agent/tests/test_operation_values.py#L136): Nine nested stubs, a socket guard, an app, a JWT and about 20 assertions (ruff C901 15)
  - [services/agent/tests/test_operation_values.py:186-198](../../../../services/agent/tests/test_operation_values.py#L186): Ten module attributes of operation_routes patched by name
  - [services/agent/tests/test_readiness.py:65-89](../../../../services/agent/tests/test_readiness.py#L65): An arranged() helper for the same module already exists here
- **Evidence:**
  ```python
  for name, stub in (
      ("database_conditions", conditions),
      ("storage_condition", storage),
      ...  # ten names in all, lines 187-196
      ("live_workers", asyncio.run(number(2))),
  ):
      monkeypatch.setattr(operation_routes, name, stub)
  ```
- **Why it matters:** Each new data source that operation_routes reads means another stub in this test. test_readiness.py and this file each build their own arrangement for the same routes, so readiness and status tests can drift apart on defaults.
- **Recommendation:** Share one helper that installs default stubs for every dependency of operation_routes and returns a client, so each test overrides only what it asserts on. Then split the 'numbers only' assertions from the 'nothing leaves this Mac' check.
- **Rule check:** Decision 0022 D5's exact list of values stays asserted (D5_VALUES).
- **Verification:** confirmed. Confirmed the 102-line test (ruff C901 15), the ten names patched at lines 187-196 and test_readiness.py's arranged() for the same routes; the shared helper fits beside the API helpers of PTST-11.

```text
tests/support/api.py
  def arranged_operation_routes(monkeypatch, *, membership=members({OWNER: 'owner'}), **stubs) -> TestClient
      # defaults: ready conditions, zero counts, empty lists; stubs override by name
tests/test_operation_values.py
  def test_the_status_holds_d5_numbers_only(monkeypatch): ...
  def test_producing_the_status_sends_nothing_off_this_mac(monkeypatch): ...
```

### <a id="ptst-17"></a>PTST-17: Test cases hide in loops, branches and either-or assertions instead of one parametrized case each

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 25
- **Where:**
  - [services/agent/tests/test_tool_keys.py:306-314](../../../../services/agent/tests/test_tool_keys.py#L306): For a secret item, the assertion passes whatever checked() returns
  - [services/agent/tests/test_workflows.py:170-171](../../../../services/agent/tests/test_workflows.py#L170): Accepts either of two codes
  - [services/agent/tests/test_worker_inference.py:147-150](../../../../services/agent/tests/test_worker_inference.py#L147): pytest.raises(Exception, match=...) where CostUnavailable is the type; again at lines 551-553
  - [services/agent/tests/test_credentials.py:117-135](../../../../services/agent/tests/test_credentials.py#L117): Five cases arranged through an if/elif chain
  - [services/agent/tests/test_code_tools.py:30-42](../../../../services/agent/tests/test_code_tools.py#L30): Seven scenarios in one test
  - [services/agent/tests/test_worker_inference.py:485-492](../../../../services/agent/tests/test_worker_inference.py#L485): Loops over profiles instead of parametrizing
  - [services/agent/tests/test_browser_executor.py:150-154](../../../../services/agent/tests/test_browser_executor.py#L150): A branch on a parameter selects which assertions run
- **Evidence:**
  ```python
  if accepted:                                                          # test_tool_keys.py:310
      assert checked(ITEMS[name], value) == value.strip() or ITEMS[name].secret
  else:
      with pytest.raises(InvalidKey):
          checked(ITEMS[name], value)
  ```
  Counted with an ast scan and grep: 11 branches on a test parameter in 7 files; 10 loops that act once per scenario, out of 22 loops over literal lists in test bodies (also [test_budgets.py:30](../../../../services/agent/tests/test_budgets.py#L30), [test_contracts.py:117](../../../../services/agent/tests/test_contracts.py#L117), [test_credentials.py:92](../../../../services/agent/tests/test_credentials.py#L92), [test_model_policy.py:225](../../../../services/agent/tests/test_model_policy.py#L225), 345 and 433, [test_operation_values.py:280](../../../../services/agent/tests/test_operation_values.py#L280), [test_url_guard.py:202](../../../../services/agent/tests/test_url_guard.py#L202) and [test_workflows.py:316](../../../../services/agent/tests/test_workflows.py#L316); the other 12 arrange files or stubs, or check several results of one act); 2 either-or assertions; and 2 uses of raises(Exception, match=...), 25 in all.
- **Why it matters:** A wrong return value for a secret item passes. A loop stops at its first failing case, and the report names only the test. With branches inside a test, each parametrized id runs different assertions, so the ids don't say what was checked.
- **Recommendation:** Give each scenario its own case:
  - Parametrize scenario lists, with ids.
  - Split accepted and refused inputs into two tests.
  - Pass arrange callables instead of switching on strings.
  - Assert the exact code for each case, and expect the specific exception type (CostUnavailable).
  Enable ruff's PT011 and PT012 for tests (4 hits today).
- **Rule check:** none
- **Verification:** revised. Confirmed each location, and that [test_tool_keys.py:311](../../../../services/agent/tests/test_tool_keys.py#L311) is vacuous for github_token, a secret item. Recounted 10 scenario loops, not 5, for 25 in all; [test_code_tools.py:30-42](../../../../services/agent/tests/test_code_tools.py#L30) holds seven scenarios, not eight, and PT011 plus PT012 do report 4 hits today.

```python
@pytest.mark.parametrize(('name', 'value', 'expected'), ACCEPTED, ids=...)
def test_each_item_accepts_its_shape(name: str, value: str, expected: str) -> None:
    assert checked(ITEMS[name], value) == expected

@pytest.mark.parametrize(('name', 'value'), REFUSED, ids=...)
def test_each_item_refuses_other_shapes(name: str, value: str) -> None: ...
```

### <a id="ptst-18"></a>PTST-18: Some tests use the wall clock and real sleeps where DH-06 asks for controlled clocks

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/tests/test_worker_inference.py:91](../../../../services/agent/tests/test_worker_inference.py#L91): NOW is taken from the wall clock at import
  - [services/agent/tests/test_worker_inference.py:311-320](../../../../services/agent/tests/test_worker_inference.py#L311): ScriptedKeys builds CatalogCache without now=; so does real_source() at line 469
  - [services/agent/tests/test_result_stream.py:89-116](../../../../services/agent/tests/test_result_stream.py#L89): Asserts coalescing from 1 ms sleeps against a patched FLUSH_SECONDS
  - [services/agent/src/autobots/adapters/result_stream.py:189](../../../../services/agent/src/autobots/adapters/result_stream.py#L189): ResultTap reads time.monotonic() directly
  - [services/agent/tests/test_url_guard.py:186-197](../../../../services/agent/tests/test_url_guard.py#L186): Waits a real 0.2 s timeout against a 5 s sleep
  - [services/agent/tests/test_operation_values.py:101-112](../../../../services/agent/tests/test_operation_values.py#L101): Measures a real 10 ms sleep
  - [services/agent/src/autobots/application/worker_inference.py:131](../../../../services/agent/src/autobots/application/worker_inference.py#L131): prepared() checks freshness against datetime.now(UTC); _input_rate does the same at line 295
- **Evidence:**
  ```python
  NOW = datetime.now(UTC)                                        # test_worker_inference.py:91
  monkeypatch.setattr(result_stream, "FLUSH_SECONDS", 0.05)      # test_result_stream.py:92
  assert len(sent) < len([chunk for chunk in chunks if chunk.tool_call_chunks]) / 4  # :116
  ```
  By contrast, [test_model_attempts.py:46](../../../../services/agent/tests/test_model_attempts.py#L46) and [test_model_policy.py:40](../../../../services/agent/tests/test_model_policy.py#L40) use a fixed NOW.
- **Why it matters:** Whether a fixture catalog counts as fresh depends on when the module was imported. Five minutes after import (MAX_CATALOG_AGE), the two tests that expect ModelUnavailable for a missing tool or output limit ([test_worker_inference.py:176-185](../../../../services/agent/tests/test_worker_inference.py#L176)) would pass on staleness instead, and test_a_drifted_mapping_is_unavailable would fail. The coalescing bound can fail on a loaded machine, and the suite pays for real waits.
- **Recommendation:** NOW comes from the wall clock because prepared() and InferenceSource._input_rate read datetime.now(UTC) themselves ([worker_inference.py:131](../../../../services/agent/src/autobots/application/worker_inference.py#L131) and 295), so a fixed NOW alone would make every fixture catalog stale. Give prepared() the now= parameter that prepare_attempt already takes, and InferenceSource a clock that defaults to the wall clock, as CatalogCache does. Then fix NOW to a constant and pass that clock to every CatalogCache and InferenceSource. Give ResultTap and timed_catalog a monotonic parameter that defaults to time.monotonic, and drive them with a fake clock in tests. Keep one real-time timeout test for guarded_fetch, with a comment saying why.
- **Rule check:** DH-06: tests use controlled clocks and injected transports rather than real time. The new clock parameters default to the wall clock, so the MAX_CATALOG_AGE freshness check is unchanged in production; tests come first because it guards the paid path.
- **Verification:** revised. Confirmed the wall-clock NOW, the CatalogCache builds without now=, ResultTap's direct time.monotonic() and the real 0.2 s and 10 ms waits. Revised the fix, because prepared() and _input_rate read the wall clock themselves and a fixed NOW alone would make every fixture catalog stale; risk is now medium since the clock reaches the paid path's freshness check.

```python
def prepared(policy: RolePolicy, catalog: CatalogSnapshot, role: ModelRole = ROLE,
             *, now: datetime | None = None) -> tuple[PreparedAttempt, int]:
    ...
    entry = validated_entry(attempt.profile, catalog, now or datetime.now(UTC))
# InferenceSource gains now: Callable[[], datetime] = lambda: datetime.now(UTC), used by _input_rate
# ResultTap gains monotonic: Callable[[], float] = time.monotonic
```

### <a id="ptst-19"></a>PTST-19: Test doubles reuse generic names across files, and fixtures pass bare positional literals

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 15
- **Where:**
  - [services/agent/tests/test_worker_inference.py:245](../../../../services/agent/tests/test_worker_inference.py#L245): class Fake; more at [test_jina.py:29](../../../../services/agent/tests/test_jina.py#L29), [test_market_data.py:59](../../../../services/agent/tests/test_market_data.py#L59) and [test_route_qualification.py:52](../../../../services/agent/tests/test_route_qualification.py#L52)
  - [services/agent/tests/test_tavily.py:28](../../../../services/agent/tests/test_tavily.py#L28): Another unrelated class Fake
  - [services/agent/tests/test_worker_inference.py:921](../../../../services/agent/tests/test_worker_inference.py#L921): Settings is a ProviderSettings subclass, while three files import autobots.api.settings.Settings
  - [services/agent/tests/test_github_reads.py:23](../../../../services/agent/tests/test_github_reads.py#L23): A FakeGithub that differs from the one at [test_github_issues.py:40](../../../../services/agent/tests/test_github_issues.py#L40)
  - [services/agent/tests/test_worker_inference.py:450-451](../../../../services/agent/tests/test_worker_inference.py#L450): Lease built from positional literals
  - [services/agent/tests/test_model_attempts.py:75-76](../../../../services/agent/tests/test_model_attempts.py#L75): AdmissionRequest built from eight positional values
  - [services/agent/tests/test_final_review.py:44](../../../../services/agent/tests/test_final_review.py#L44): ModelRoute built from positional literals
  - [services/agent/tests/test_worker_inference.py:301-305](../../../../services/agent/tests/test_worker_inference.py#L301): ProviderContext built from six positional values
- **Evidence:**
  ```python
  return Lease(uuid4(), uuid4(), 1, "worker", 1, "running")                                  # test_worker_inference.py:451
  return AdmissionRequest(uuid4(), uuid4(), uuid4(), "coder", "openrouter_terra", "w", 1, 5)  # test_model_attempts.py:76
  ROUTE = ModelRoute("executor", "openrouter_terra", "fixture/model", 34_560, 1_000_000)    # test_final_review.py:44
  class Settings(ProviderSettings):                                                         # test_worker_inference.py:921
  ```
  There are five unrelated classes named Fake, two named FakeGithub and a Settings that shadows the API's Settings, and model_over means different things in two files ([test_model_attempts.py:234](../../../../services/agent/tests/test_model_attempts.py#L234) and [test_worker_inference.py:559](../../../../services/agent/tests/test_worker_inference.py#L559)). Six value objects are built from positional literals: Lease, AdmissionRequest, ProviderContext and three ModelRoutes in test_final_review.py (lines 44, 63 and 260). 15 in all, by grep for the class names and constructor calls.
- **Why it matters:** A search for the fake OpenRouter or the GitHub fake finds unrelated classes. Positional fixtures hide which number is the generation, the attempt count or the budget, and swapping two fields of the same type (generation and attempts in Lease) still type-checks.
- **Recommendation:** Name each double after what it replaces (FakeJina, FakeTavily, ScriptedOpenRouter, GithubReadsApi, StoredProviderSettings). Build value objects with keyword arguments in fixtures, and keep the shared ones in the support modules.
- **Rule check:** none
- **Verification:** revised. Confirmed every name and constructor, and that the sketch's keyword names match Lease's fields. Recounted 15, since test_final_review.py builds three positional ModelRoutes (lines 44, 63 and 260), not one.

```python
def lease() -> Lease:
    return Lease(run_id=uuid4(), workspace_id=uuid4(), generation=1,
                 worker_id='worker', attempts=1, run_status='running')
```

### <a id="ptst-20"></a>PTST-20: 47 imports sit inside test functions, and helper imports rely on pytest putting tests/ on sys.path

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 50
- **Where:**
  - [services/agent/tests/test_tool_catalog.py:147-149](../../../../services/agent/tests/test_tool_catalog.py#L147): The same two imports are repeated in four tests (also lines 163-165, 182-184 and 191-193); 12 local imports in this file
  - [services/agent/tests/test_contracts.py:110-114](../../../../services/agent/tests/test_contracts.py#L110): Re-imports datetime and UTC, already imported at line 4
  - [services/agent/tests/test_final_review.py:191](../../../../services/agent/tests/test_final_review.py#L191): Imports SecretStr inside two tests (lines 191 and 197), though pydantic is already imported at the top for BaseModel
  - [services/agent/tests/test_model_policy.py:408](../../../../services/agent/tests/test_model_policy.py#L408): import autobots.domain.models as models, beside the top-level import at line 29 (again at 426)
  - [services/agent/tests/test_app_factory.py:8](../../../../services/agent/tests/test_app_factory.py#L8): from conftest import SocketBlockedError; also at [test_contracts.py:27](../../../../services/agent/tests/test_contracts.py#L27) and [test_model_transport.py:9](../../../../services/agent/tests/test_model_transport.py#L9)
  - [services/agent/pyproject.toml:55-59](../../../../services/agent/pyproject.toml#L55): No pythonpath is declared for the tests
- **Evidence:**
  ```python
  def test_a_raw_payload_never_projects() -> None:          # test_contracts.py:110
      from datetime import UTC, datetime
      from uuid import uuid4

      from autobots.application.run_projection import project_event, public_text
  ```
  ruff --select PLC0415 finds 47 function-level imports in 12 files. Three files import from conftest. Those imports, and the imports of fake_openrouter and test_api, resolve only because pytest's default prepend import mode puts tests/ on sys.path.
- **Why it matters:** A file's dependencies aren't visible at its top, and re-imports shadow names already in scope. The conftest and helper imports would break under pytest's importlib import mode, or when a file is run any other way.
- **Recommendation:** Move imports to the top of the file unless a comment gives a reason, and add PLC0415 to the ruff rules for tests. Put SocketBlockedError and the other shared helpers in a support module that conftest.py imports, and declare pythonpath = ['tests'] under [tool.pytest.ini_options] so helper imports don't depend on the import mode. Keep the name SocketBlockedError, which [scripts/qualify_faults.py:77-78](../../../../scripts/qualify_faults.py#L77) expects in a fault fixture's output, and keep tests/faults/model_transport/conftest.py able to load the guard.
- **Rule check:** DH-06 makes Ruff the lint gate. Adding a rule for tests is a ratchet within that gate.
- **Verification:** revised. Confirmed 47 PLC0415 hits in 12 files, the three conftest imports and no pythonpath setting. Corrected one note, since test_final_review.py never imports SecretStr at the top, so lines 191 and 197 repeat a local import rather than shadow one; the guard must also keep the SocketBlockedError name that fault qualification matches.

```toml
[tool.pytest.ini_options]
pythonpath = ["tests"]
# tests/support/__init__.py
# tests/support/network.py: SocketBlockedError, block_sockets(); conftest.py calls block_sockets()
```

## Rejected during verification

None. Every finding held up at its cited lines and was kept. Where counts, evidence, impact, recommendation or risk changed, the finding is marked revised and its verification line says what changed.

## Not covered

This was a static review. No test was run: the ground rules forbid scripts/verify.py, and pytest was not among the permitted commands. The order-dependence, timing and logging-leak effects described above are therefore reasoned from code, not observed. Production modules were read only where the tests reach into them: loop_middleware.py at lines 89-140, 208-223, 349-380 and 491-600; worker_inference.py at 137-176 and 317-374; provider_settings.py at 82-105; operations.py at 112-171; workflow_runner.py at 163-235; result_stream.py at 186-198. Of PRD-Development-Harness.md, only DH-03 and DH-06 were read. tests/db, tests/web and tests/faults were sampled only where they duplicate service-test helpers (product_inference_worker.py, sleep_inference_worker.py, keys_and_vars_check.py and one fault fixture); reviewing them belongs to other areas. No coverage measurement was available. Ruff statistics for the selected test-quality rules were written to .checks/reviews/review-2026-11-12-09-52-30/py-tests/ruff_selected.txt.
