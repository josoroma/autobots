# Python: operations, credentials and readiness

The operations, credentials and readiness code is careful where it matters most. Credentials are sealed with AES-GCM bound to their row identity, the master key is never regenerated, resolved keys refuse serialization, logs redact secrets and keep only exception types, and remote tracing is forced off at every entry point. The worker sends heartbeats on its own connection and drains within a time limit, and the paid trials write each call's worst case to an fsync'd, locked ledger before sending it. The main maintainability cost is rules that exist twice and have already drifted. The trials price calls with their own float parser instead of the catalog's Decimal one, which breaks the DH-06 money rule. The worker's routine-admission gate leaves out the schema check that the API's gate applies. Paid-call settlement is copied five times with different exception scope and state names, and three catalog checks catch different errors. Layering is inverted around operations/: nine modules in application, adapters and api import its logger, application imports the worker, and the worker imports api.main. application/operations.py (501 lines) and route_qualification.py (732 lines) now mix several concerns each. browse_trial.run_trial (192 lines) is never run offline, and the status vocabularies are bare strings held together by six type: ignore comments. Errors are typed and carry no secrets, but four problems remain: the credential store leaks decryption errors to seven callers, boundary logs drop where the error happened, CLI exit codes disagree, and owner bootstrap can't resume after a half-finished run. I read the size leads for provider_settings.py (344 lines) and worker.py (342 lines) and judged both cohesive. Their problems are typing, hidden writes and misplaced wiring, not size. [Back to the review](../README.md)

Area `py-ops`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Project ruff and mypy strict pass, but the trials use float money against DH-06, there are 8 type: ignore comments in scope, and 12 swallowing broad excepts rely on review because BLE, T20 and C90 aren't enabled. |
| modules | 3 | credentials/ is cohesive with a narrow surface, but operations/ hosts the shared logger, application imports the worker, the worker imports api.main, and route_qualification serves as the trials' de facto library. |
| size | 3 | Most functions are short. The outliers are application/operations.py (501 lines), route_qualification.py (732) and browse_trial.run_trial (192 lines, 67 statements). |
| functions | 3 | Most functions do one thing, with visible side effects. The exceptions are _settings_row's hidden insert, the monolithic trial runners and the list-cell state in maintenance_step. |
| structure | 3 | operations/ mixes a long-running worker, operator CLIs, paid trials, the shared logger and a test fake. DH-03 names workers/, and the package docstring claims nothing in it runs at startup. |
| approach | 3 | The lifecycle design is strong (heartbeat, bounded drain, worst-case ledger, AAD-bound encryption), but a drifted second readiness gate and a shared spend ledger whose path depends on the working directory undercut it. |
| comments | 4 | Every module has a docstring, and comments explain invariants with requirement and decision IDs. Only 82 of 189 public definitions have docstrings, and a few comments are inaccurate or stand in for types. |
| types | 3 | Frozen dataclasses and Literals appear in places, but there are 35 Any-typed database and store handles, status strings needing 6 type: ignore comments, a cast and an anonymous binding object. |
| errors | 3 | Errors are typed, with stable codes and fixed messages. But decryption errors leak past the store, boundary logs lose where the error happened, CLI exit codes disagree, and bootstrap has no recovery path. |
| tests | 4 | Thorough fake-transport, tamper and readiness tests plus DB checks. The gaps: browse_trial.run_trial is never run offline, and the serve loop's drain, reconnect and final heartbeat are tested only against Docker Postgres. |
| maintainability | 3 | Safe, well-explained code, but several rules are duplicated (pricing, readiness, ledger settlement, catalog status) and the copies have already drifted. |

## Strengths

- **Secrets can't leak through serialization or repr.** ResolvedCredential ([services/agent/src/autobots/application/credentials/store.py:48-72](../../../../services/agent/src/autobots/application/credentials/store.py#L48)) refuses pickling and hides its value in repr. Its docstring explains why: LangGraph's checkpoint serializer writes dataclasses and SecretStr in plaintext. EnvironmentCandidate hides its value too ([precedence.py:15-21](../../../../services/agent/src/autobots/application/credentials/precedence.py#L15)). Both are tested at [services/agent/tests/test_credentials.py:142-166](../../../../services/agent/tests/test_credentials.py#L142).
- **Authenticated encryption bound to row identity, and a master key that is never replaced.** [crypto.py:25-41](../../../../services/agent/src/autobots/application/credentials/crypto.py#L25) seals with a fresh nonce and associated data of workspace|provider|credential|version, and raises an error that carries no detail. [master_key.py:15-43](../../../../services/agent/src/autobots/application/credentials/master_key.py#L15) creates the key with O_EXCL and 0600/0700 permissions, and refuses symlinks or open permissions. [store.py:94-106](../../../../services/agent/src/autobots/application/credentials/store.py#L94) generates a key only when no encrypted row exists (SP-007). Tampering cases are tested at [test_credentials.py:87-140](../../../../services/agent/tests/test_credentials.py#L87).
- **Logs redact by default, and remote tracing is switched off at process start.** [operations/logs.py:12-25](../../../../services/agent/src/autobots/operations/logs.py#L12) redacts provider and tool keys, bearer tokens, JWTs and connection strings. Lines 54-67 keep only the exception type, and lines 93-105 clear LangSmith's cached settings. [api/main.py:39-40](../../../../services/agent/src/autobots/api/main.py#L39), [worker.py:316-317](../../../../services/agent/src/autobots/operations/worker.py#L316) and each trial's _main call these first. Tested at [test_operations.py:64-79](../../../../services/agent/tests/test_operations.py#L64).
- **Paid calls are recorded at worst case before they are sent.** [route_qualification.py:115-176](../../../../services/agent/src/autobots/operations/route_qualification.py#L115) keeps an fsync'd ledger guarded by flock and re-read under the lock. Lines 277-287 keep an unclear outcome charged at worst case, and lines 677-692 send nothing without --paid. Reports carry evidence_class and not_established (lines 648-669). [browse_trial.py:51-54](../../../../services/agent/src/autobots/operations/browse_trial.py#L51) and 256-257 record the start before the call, so the once-only trial can't repeat.
- **The worker lifecycle is deliberate and documented.** [worker.py:74-91](../../../../services/agent/src/autobots/operations/worker.py#L74) sends heartbeats on its own connection, so a long step can't make the worker look dead. Lines 102-122 drain within a bound, lines 158-169 write a final stopped heartbeat, and lines 264-281 keep a failing step from starving the next one. The module docstring (lines 1-11) explains why billed inference is opt-in.
- **Retention is scoped and ordered for crash safety.** [retention.py:101-123](../../../../services/agent/src/autobots/application/retention.py#L101) pages by (updated_at, id), so refused runs can't crowd out later ones. Lines 64-89 remove bytes only after the rows commit, so a crash leaves bytes to retry, never a row pointing at nothing.
- **Tests pin duplicated tables to their source.** [test_schema_release.py:20-22](../../../../services/agent/tests/test_schema_release.py#L20) ties SHIPPED_MIGRATIONS and NEWEST_MIGRATION to supabase/migrations. [test_route_qualification.py:339-343](../../../../services/agent/tests/test_route_qualification.py#L339) requires a qualification route for every approved profile. [precedence.py:1](../../../../services/agent/src/autobots/application/credentials/precedence.py#L1) shares its precedence fixtures with TypeScript ([test_credentials.py:40](../../../../services/agent/tests/test_credentials.py#L40)).
- **Comments explain invariants, not syntax.** [application/operations.py:394-422](../../../../services/agent/src/autobots/application/operations.py#L394) explains why sockets are only detached on macOS, and lines 102-107 explain why p95 rounds up. [master_key.py:1](../../../../services/agent/src/autobots/application/credentials/master_key.py#L1) states the never-replace rule, and requirement and decision IDs trace the code to its sources throughout the area.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [POPS-01](#pops-01) | high | standards | Paid trials price calls with a second, float-based catalog parser | S | high |
| [POPS-02](#pops-02) | high | duplication | Routine admission re-implements the readiness gate and skips the schema check | S | medium |
| [POPS-03](#pops-03) | medium | modules | Shared logging and process wiring live in the entry-point package | M | low |
| [POPS-04](#pops-04) | medium | size | application/operations.py mixes six concerns in 501 lines | M | low |
| [POPS-05](#pops-05) | medium | size | route_qualification.py (732 lines) is also the paid trials' shared library | M | medium |
| [POPS-06](#pops-06) | medium | duplication | Paid-call reservation and settlement are hand-rolled five times and have drifted | S | high |
| [POPS-09](#pops-09) | medium | errors | The credential store lets decryption errors escape, so seven callers compensate | S | medium |
| [POPS-10](#pops-10) | medium | errors | Boundary handlers log only the exception class, and retention's failure log omits the workspace | S | low |
| [POPS-11](#pops-11) | medium | types | Status vocabularies are bare strings, held together by six type: ignore comments | S | low |
| [POPS-13](#pops-13) | medium | duplication | Three catalog-availability checks disagree, and one has no caller | S | low |
| [POPS-15](#pops-15) | medium | errors | Owner bootstrap can stop between its two writes, and reports only the exception class | S | medium |
| [POPS-07](#pops-07) | low | approach | The reasoning trial's shared US$1 ledger path is relative to the working directory | S | high |
| [POPS-08](#pops-08) | low | size | browse_trial.run_trial does the whole trial inline, and its report assembly has no offline test | M | medium |
| [POPS-12](#pops-12) | low | functions | _settings_row inserts on every read, and two writers call it only for that insert | S | medium |
| [POPS-14](#pops-14) | low | errors | Entry points disagree on configuration checks, refusals and exit codes | S | low |
| [POPS-16](#pops-16) | low | types | Trial and seed code bypass existing types and seams | S | low |
| [POPS-17](#pops-17) | low | types | Query rows and database or store handles cross module boundaries untyped | M | low |
| [POPS-18](#pops-18) | low | comments | The readiness lists carry a truncated comment and an over-attributed decision range, and a DB check patches them | S | low |
| [POPS-19](#pops-19) | low | tests | The serve loop opens its own connections, so drain, reconnect and the final heartbeat are tested only against Docker Postgres | S | low |
| [POPS-20](#pops-20) | low | size | apply_retention and concept_seed.seed each run three phases in one body | S | medium |

### <a id="pops-01"></a>POPS-01: Paid trials price calls with a second, float-based catalog parser

- **Severity** high · **Dimension** standards · **Effort** S · **Risk** high · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/operations/route_qualification.py:85-112](../../../../services/agent/src/autobots/operations/route_qualification.py#L85): Price in float USD; price_of reads prompt and completion only and drops every tiered override
  - [services/agent/src/autobots/operations/route_qualification.py:244-246](../../../../services/agent/src/autobots/operations/route_qualification.py#L244): _cost_micro_usd: ceil(float(cost) * 1e6)
  - [services/agent/src/autobots/operations/route_qualification.py:616](../../../../services/agent/src/autobots/operations/route_qualification.py#L616): preflight's worst case per call
  - [services/agent/src/autobots/operations/route_qualification.py:656](../../../../services/agent/src/autobots/operations/route_qualification.py#L656): the report records Price.\_\_dict\_\_ as catalog_price
  - [services/agent/src/autobots/operations/reasoning_trial.py:211](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L211): the reasoning trial reuses price_of for the shared US$1 ledger
  - [services/agent/src/autobots/adapters/models/catalog.py:77-100](../../../../services/agent/src/autobots/adapters/models/catalog.py#L77): canonical Decimal parser: input_cache_write, internal_reasoning, per-request fee, tiers reachable under 32K
  - [services/agent/src/autobots/application/model_admission.py:60-70](../../../../services/agent/src/autobots/application/model_admission.py#L60): canonical integer worst_case_cost
- **Evidence:** price_of reads only `prompt` and `completion`, as floats, and drops every override that has `min_prompt_tokens`:

  ```python
  @dataclass(frozen=True)
  class Price:
      prompt_usd: float
      completion_usd: float
      def worst_case_micro_usd(self) -> int:
          usd = CONTEXT_TOKENS * self.prompt_usd + OUTPUT_TOKENS * self.completion_usd
          return math.ceil(usd * 1_000_000)
  ```

  catalog.parse_pricing parses the same `pricing` object with Decimal and ROUND_CEILING, and also counts input_cache_write, internal_reasoning, a per-request fee and tiers that start under 32K tokens. worst_case_cost works in integer micro-USD. There are 3 call sites of price_of (counted with grep).
- **Why it matters:** DH-06 forbids float arithmetic for money, and the two parsers of one catalog field already disagree. A route can bill reasoning tokens or cache writes above its completion rate, charge per request, or start a price tier below the qualification prompt size. Such a route is reserved below its real worst case in the ledgers that enforce the caps of Decisions 0009 and 0019. Any pricing change has to be made twice, and the application's tests exercise only one copy.
- **Recommendation:** Price trial calls with the application's rules. `prepare` already calls validated_entry, so have it return the CatalogEntry, compute `worst_case_cost(entry.pricing, CONTEXT_TOKENS, OUTPUT_TOKENS)`, and refuse when it raises CostUnavailable. Record entry.pricing as the report's catalog_price, then delete Price and price_of, and move the override test (services/agent/tests/test_route_qualification.py:514-520) and the three price_of uses in services/agent/tests/test_reasoning_trial.py onto Pricing. Convert a reported cost with one Decimal ceiling helper; adapters/loop_middleware.py:276-278 does the same conversion with round(float).
- **Rule check:** DH-06 (Python): exact decimal or integer monetary units, no float arithmetic for money. Decisions 0009 and 0019 S4 count calls at worst case. The shared parser is at least as conservative, so no cap is weakened.
- **Verification:** revised. price_of, its three source call sites (route_qualification.py:616 and :656, reasoning_trial.py:211) and DH-06's ban on float money confirmed against catalog.parse_pricing. The recommendation now also covers the report's catalog_price field and the tests that use price_of; the override test sits at test_route_qualification.py:514-520.

```text
operations/paid/pricing.py
  def worst_case(entry: CatalogEntry) -> int:      # integer micro-USD; refuses an unknown price
      return worst_case_cost(entry.pricing, CONTEXT_TOKENS, OUTPUT_TOKENS)
  def reported_micro_usd(message) -> int | None:   # Decimal(str(cost)) * 10**6, ROUND_CEILING
route_qualification.prepare(route, payload, max_tokens) -> tuple[PreparedAttempt, CatalogEntry]
preflight and reasoning_trial.run_trial: worst = worst_case(entry)
```

### <a id="pops-02"></a>POPS-02: Routine admission re-implements the readiness gate and skips the schema check

- **Severity** high · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/operations/worker.py:178-186](../../../../services/agent/src/autobots/operations/worker.py#L178): unattended_refusal checks adapter, storage and disk only, and parses the environment on every call
  - [services/agent/src/autobots/operations/worker.py:206-215](../../../../services/agent/src/autobots/operations/worker.py#L206): the comment says a routine waits on the same readiness a person would
  - [services/agent/src/autobots/api/operation_routes.py:86-103](../../../../services/agent/src/autobots/api/operation_routes.py#L86): person admission: database, schema, hold, adapter, storage and disk, through is_ready
  - [services/agent/src/autobots/application/operations.py:75](../../../../services/agent/src/autobots/application/operations.py#L75): BLOCKING includes schema
  - [tests/db/major_check.py:337-359](../../../../tests/db/major_check.py#L337): the M14 check arranges only Storage down
- **Evidence:**

  ```python
  async def unattended_refusal(connection: Any, store: Any) -> str | None:
      if not await adapter_qualified(connection):
          return "adapter_unqualified"
      storage = await storage_condition(store)
      ...
      minimum = int(os.environ.get("AUTOBOTS_MIN_FREE_BYTES", DEFAULT_MIN_FREE_BYTES))
      disk = disk_condition(Path(os.environ.get("AUTOBOTS_CONFIG_ROOT") or "."), minimum)
  ```

  The API's _installation_conditions builds [database, schema, hold, adapter, storage, disk], and require_ready applies is_ready to it. It repeats the same two environment parses (operation_routes.py:87 and :95).
- **Why it matters:** The worker's comment and DB check M14 promise one readiness. But when the code is newer than the database (schema_behind, Decision 0023 E2), a person's run is refused while the worker still evaluates and admits due routines. Every new blocking condition has to be added to two gates. Both gates re-read the environment on each call, so a malformed AUTOBOTS_MIN_FREE_BYTES fails every maintenance step and every admission. The worker logs only ValueError and skips retention.
- **Recommendation:** Own installation readiness in one application function that takes a connection and the object store and returns the conditions, with its settings parsed once at process start. The API's require_ready and the worker's maintenance step both call it and refuse on the first blocking condition. Extend M14 to arrange schema_behind and a held install.
- **Rule check:** This strengthens an admission guard (LM-07, Decision 0023 E2), and scheduling stays in Python, with nothing moved to Next.js.
- **Verification:** confirmed. unattended_refusal checks the adapter, Storage and disk, and the hold is checked separately by is_held (worker.py:199), so schema is the one blocking condition a person's admission applies and a routine's doesn't. The M14 check (tests/db/major_check.py:337-359) arranges only Storage down, and Decision 0023 records an install that ran newer code on a database 14 migrations behind.

```text
application/readiness.py
  @dataclass(frozen=True)
  class ReadinessSettings: data_root: Path; min_free_bytes: int     # from_environment(), once per process
  async def installation_conditions(connection, store, settings, probes=None) -> list[Condition]
  def first_blocking(conditions) -> Condition | None                 # BLOCKING minus NOT_BLOCKING
api.require_ready: refuse when first_blocking(await installation_conditions(...)) is not None
worker.maintenance_step: refused = first_blocking(...); log refused.code; skip routines, keep retention
```

### <a id="pops-03"></a>POPS-03: Shared logging and process wiring live in the entry-point package

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** low · **Occurrences** 11
- **Where:**
  - [services/agent/src/autobots/operations/\_\_init\_\_.py:1](../../../../services/agent/src/autobots/operations/__init__.py#L1): says nothing here runs at service startup
  - [services/agent/src/autobots/api/main.py:15](../../../../services/agent/src/autobots/api/main.py#L15): API startup imports configure_logging and forbid_remote_tracing from operations.logs
  - [services/agent/src/autobots/application/operations.py:23](../../../../services/agent/src/autobots/application/operations.py#L23): one of 9 modules outside operations/ that import operations.logs
  - [services/agent/src/autobots/application/cronjob_tool.py:38-42](../../../../services/agent/src/autobots/application/cronjob_tool.py#L38): function-local import of operations.worker, used by the module-level CRONJOB at :181
  - [services/agent/src/autobots/application/goal_loop.py:47](../../../../services/agent/src/autobots/application/goal_loop.py#L47): goal_loop imports CRONJOB at module level, which closes the cycle
  - [services/agent/src/autobots/operations/worker.py:29](../../../../services/agent/src/autobots/operations/worker.py#L29): the worker imports api.main for provider_context_from_environment
- **Evidence:**

  ```python
  async def _environment_check(connection: Any, workspace_id: UUID) -> str:
      """The worker's own readiness answer, so a scheduled and an asked-for occurrence agree."""
      from autobots.operations.worker import credential_check_from_environment

      return await credential_check_from_environment()(connection, workspace_id)
  ```

  The package docstring says "Nothing here runs at service startup". Yet 9 modules outside operations/ import operations.logs (counted with grep): adapters (loop_middleware, result_stream), api (main, operation_routes) and application (operations, retention, goal_loop, routines, worker_inference). goal_loop imports cronjob_tool at module level, cronjob_tool imports the worker inside a function, and the worker imports goal_loop and api.main, which loads api.app and every router.
- **Why it matters:** cronjob_tool → operations.worker → application.goal_loop → cronjob_tool is a cycle that only the function-local import keeps out of import time. To build its provider context, the worker process loads the FastAPI app factory and every router. Readers can't trust the package boundary that the docstring describes. The credential-check callable is also typed under the name CredentialCheck with two different signatures (routines.py:38, cronjob_tool.py:35).
- **Recommendation:** Move logs.py to a leaf module that imports nothing from autobots. Move provider_context_from_environment and credential_check_from_environment to a composition module that api/main and the worker import. The object-store construction repeated in api/main.py:46-49 and worker.py:321-325 belongs there too. Pass the credential check into cronjob_tool from that composition root instead of the local import. Keep operations/, or DH-03's workers/, for entry points.
- **Rule check:** DH-03 lists src/autobots/{api,domain,application,adapters,workers,graphs,contracts}, and DH-06 asks for explicit ownership and narrow interfaces. The move changes no behavior.
- **Verification:** revised. The nine importers of operations.logs, the function-local import and worker.py:29 confirmed. The cycle is now named exactly: goal_loop.py:47 imports cronjob_tool, whose lazy import of the worker would bring goal_loop back at import time.

```text
autobots/observability.py   redact, JsonFormatter, configure_logging, log_event, forbid_remote_tracing (no autobots imports)
autobots/configuration.py   provider_context_from_environment(), object_store_from_environment(), credential_check(context)
operations/worker.py        imports configuration, never api.main
application/cronjob_tool.py receives its credential check from the registry's composition; no local import
```

### <a id="pops-04"></a>POPS-04: application/operations.py mixes six concerns in 501 lines

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/application/operations.py:26-75](../../../../services/agent/src/autobots/application/operations.py#L26): constants for readiness, backups, the catalog and occurrences are interleaved
  - [services/agent/src/autobots/application/operations.py:118-228](../../../../services/agent/src/autobots/application/operations.py#L118): readiness conditions
  - [services/agent/src/autobots/application/operations.py:231-258](../../../../services/agent/src/autobots/application/operations.py#L231): backup manifests and restore logs, read synchronously
  - [services/agent/src/autobots/application/operations.py:384-425](../../../../services/agent/src/autobots/application/operations.py#L384): socket introspection
  - [services/agent/src/autobots/application/operations.py:442-489](../../../../services/agent/src/autobots/application/operations.py#L442): 24-hour jobs chart SQL
  - [services/agent/src/autobots/application/operations.py:492-501](../../../../services/agent/src/autobots/application/operations.py#L492): NOT_BLOCKING and is_ready, far from BLOCKING at :75
  - [services/agent/src/autobots/api/operation_routes.py:177-182](../../../../services/agent/src/autobots/api/operation_routes.py#L177): the async status route calls the blocking backup readers
- **Evidence:** One module holds six concerns:

  - the admission gate: Condition, BLOCKING, the database, storage, disk, queue and worker conditions, and is_ready
  - operator values: ProbeTimes, counts, migrations, disk bytes, the checkpoint adapter and catalog timing
  - backup-file parsing: backup_age_hours and restore_history
  - routine occurrences
  - host socket introspection: loopback_only
  - the jobs-chart query: _JOB_HOURS

  api/operation_routes.py imports 22 names from it (lines 14-37). backup_age_hours and restore_history glob and read files with blocking calls, and they run inside the async local-status route.
- **Why it matters:** The admission gate is reviewed and changed amid chart SQL and file parsing, and its two halves, BLOCKING at line 75 and NOT_BLOCKING with is_ready at lines 492-501, sit 400 lines apart. Each local-status request also does blocking file reads on the event loop, which DH-06 says to keep off it; the files are small, so this costs little today.
- **Recommendation:** Split the module by concern, keeping names importable through re-exports during the move. Call the backup readers through asyncio.to_thread.
- **Rule check:** DH-06: small cohesive modules, and keep blocking work off the async event loop.
- **Verification:** revised. Six concerns and their line ranges confirmed. operation_routes.py imports 22 names from the module, not 20. The speculation that the mix explains the worker's second gate was dropped; the backup readers do run synchronously in the async route.

```text
application/readiness.py         Condition (Literal name and state), BLOCKING, NOT_BLOCKING, is_ready, RequiredSchema,
                                 database/storage/disk/queue/worker conditions, installation_conditions
application/operation_values.py  ProbeTimes, QueueCounts, queue_counts, live_workers, applied_migrations,
                                 stored_bytes, disk_bytes, checkpoint_adapter, timed_catalog, loopback_only
application/backups.py           backup_age_hours, restore_history -> list[RestoreRow], called through to_thread
application/activity.py          job_hours with _JOB_HOURS, delayed_occurrences -> list[DelayedRow]
```

### <a id="pops-05"></a>POPS-05: route_qualification.py (732 lines) is also the paid trials' shared library

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/operations/route_qualification.py:115-176](../../../../services/agent/src/autobots/operations/route_qualification.py#L115): Ledger, used by Corpus, the reasoning trial and scripts/persistent_install.py:292
  - [services/agent/src/autobots/operations/route_qualification.py:266-533](../../../../services/agent/src/autobots/operations/route_qualification.py#L266): Corpus: 12 fixtures as methods, plus the run loop
  - [services/agent/src/autobots/operations/route_qualification.py:566-574](../../../../services/agent/src/autobots/operations/route_qualification.py#L566): read_key, reused by the other trials
  - [services/agent/src/autobots/operations/reasoning_trial.py:37-48](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L37): imports 10 names, including the private _cost_micro_usd
  - [services/agent/src/autobots/operations/browse_trial.py:38](../../../../services/agent/src/autobots/operations/browse_trial.py#L38): imports Refused and read_key
  - [services/agent/src/autobots/operations/route_qualification.py:625-632](../../../../services/agent/src/autobots/operations/route_qualification.py#L625): qualify takes 6 parameters (PLR0913)
- **Evidence:**

  ```python
  from autobots.operations.route_qualification import (
      CALL_SECONDS, CapReached, Ledger, LookupCode, Refused, Route,
      _cost_micro_usd, prepare, price_of, read_key,
  )
  ```

  The file holds the route table and caps, price parsing, a flock-guarded ledger, tool and schema models, the 12-fixture runner, verdict helpers, key reading, report assembly and the CLI.
- **Why it matters:** The spend ledger that Decision 0009's shared cap and the persistent install rely on lives inside one route's runner. Other trials depend on its private helper, and the install script imports the whole runner just to reach the ledger. The names still describe the original use: Corpus is the runner, and `only` holds per-fixture rerun counts.
- **Recommendation:** First extract the shared paid-call pieces, then split the qualification runner into fixtures and orchestration. Rename Corpus to QualificationRun and `only` to `reruns` along the way.
- **Rule check:** The caps of Decisions 0009 and 0019 S4 and the --paid gate stay as they are. The fake-transport tests in services/agent/tests/test_route_qualification.py cover the move.
- **Verification:** revised. 732 lines, the 10-name import in reasoning_trial including the private _cost_micro_usd, and the 6-parameter qualify confirmed. The Ledger serves the qualification run, the reasoning trial and persistent_install.py's goal and examples; browse_trial imports only Refused and read_key, so the note no longer says three runners.

```text
operations/paid/ledger.py                  LedgerEntry, Ledger (+ charge context manager), CapReached
operations/paid/keys.py                    read_key, Refused
operations/paid/pricing.py                 worst_case(entry), reported_micro_usd(message)
operations/route_qualification/fixtures.py tool and schema models; QualificationRun (was Corpus) with its fixture methods
operations/route_qualification/__main__.py ROUTES, AUTHORIZED_CAPS, preflight, qualify(reruns=...), CLI
```

### <a id="pops-06"></a>POPS-06: Paid-call reservation and settlement are hand-rolled five times and have drifted

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** high · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/operations/route_qualification.py:277-287](../../../../services/agent/src/autobots/operations/route_qualification.py#L277): _call
  - [services/agent/src/autobots/operations/route_qualification.py:289-309](../../../../services/agent/src/autobots/operations/route_qualification.py#L289): _stream
  - [services/agent/src/autobots/operations/route_qualification.py:392-403](../../../../services/agent/src/autobots/operations/route_qualification.py#L392): _call_structured
  - [services/agent/src/autobots/operations/route_qualification.py:471-493](../../../../services/agent/src/autobots/operations/route_qualification.py#L471): cancellation: reserves, then settles in finally
  - [services/agent/src/autobots/operations/reasoning_trial.py:180-192](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L180): _paid_call: except Exception and 'no_reported_charge'
  - [services/agent/src/autobots/operations/route_qualification.py:152-175](../../../../services/agent/src/autobots/operations/route_qualification.py#L152): entries are dict[str, Any], and state is any string
  - [services/agent/src/autobots/operations/route_qualification.py:585-589](../../../../services/agent/src/autobots/operations/route_qualification.py#L585): planned_calls hard-codes 13 calls, apart from the fixture list at 496-509
- **Evidence:**

  ```python
  # route_qualification.py:281-286
          except BaseException:
              self.ledger.settle(entry, None, "uncertain")
              raise
          self.ledger.settle(entry, cost, "settled" if cost is not None else "usage_unreported")
  # reasoning_trial.py:187-191
      except Exception:
          ledger.settle(entry, None, "uncertain")
  ```

  reasoning_trial then settles the same unreported outcome as "no_reported_charge".
- **Why it matters:** The copies already disagree. An interrupted or cancelled reasoning-trial call is left as "reserved" instead of "uncertain"; committed() still holds it at worst case, so the cap is safe, but the record no longer says what happened. One outcome has two names in a ledger file that is shared with the install's goals, which add "not_started" and "run_not_finished" (scripts/persistent_install.py:331-683). Adding a fixture without also editing planned_calls makes the preflight undercount.
- **Recommendation:** Give Ledger one async context manager. It reserves, settles as "uncertain" on any BaseException and re-raises, and otherwise settles from the reported charge. Type the entries as a dataclass with a Literal state. Derive the planned calls from a fixture table that also drives Corpus.run.
- **Rule check:** Two rules are kept: Decision 0009 holds a call at its worst case until it settles, and DH-06 propagates cancellation after cleanup. Unifying on BaseException brings the reasoning trial in line.
- **Verification:** confirmed. Five reserve-and-settle copies confirmed (route_qualification.py:277, 289, 392 and 471; reasoning_trial.py:180). Only the reasoning trial catches Exception, and persistent_install.py settles with not_started and run_not_finished. The impact now notes that committed() keeps a reserved entry at worst case.

```text
LedgerState = Literal['reserved', 'settled', 'usage_unreported', 'uncertain', 'not_started', 'run_not_finished']
@dataclass class LedgerEntry: label: str; worst_case: int; reported: int | None; state: LedgerState; at: str
@asynccontextmanager
async def charge(self, label: str, worst: int) -> AsyncIterator[Receipt]:
    entry = self.reserve(label, worst)
    try: receipt = Receipt(); yield receipt
    except BaseException: self.settle(entry, None, 'uncertain'); raise
    self.settle(entry, receipt.reported, 'settled' if receipt.reported is not None else 'usage_unreported')
FIXTURE_CALLS = {'plain_text': 1, ..., 'continuation': 2}   # planned_calls sums it
```

### <a id="pops-09"></a>POPS-09: The credential store lets decryption errors escape, so seven callers compensate

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/application/credentials/store.py:145-161](../../../../services/agent/src/autobots/application/credentials/store.py#L145): translates MasterKeyUnavailable but not unseal's CredentialDecryptionError
  - [services/agent/src/autobots/application/provider_settings.py:142](../../../../services/agent/src/autobots/application/provider_settings.py#L142): catches the pair
  - [services/agent/src/autobots/application/provider_settings.py:161](../../../../services/agent/src/autobots/application/provider_settings.py#L161): catches the pair
  - [services/agent/src/autobots/application/provider_settings.py:220-221](../../../../services/agent/src/autobots/application/provider_settings.py#L220): re-raises it as CredentialStorageUnavailable
  - [services/agent/src/autobots/application/provider_settings.py:243](../../../../services/agent/src/autobots/application/provider_settings.py#L243): catches the pair
  - [services/agent/src/autobots/application/provider_settings.py:268](../../../../services/agent/src/autobots/application/provider_settings.py#L268): catches it with CredentialMissing
  - [services/agent/src/autobots/application/worker_inference.py:248-250](../../../../services/agent/src/autobots/application/worker_inference.py#L248): catches the pair
  - [services/agent/src/autobots/application/tool_keys.py:179](../../../../services/agent/src/autobots/application/tool_keys.py#L179): catches the pair
- **Evidence:**

  ```python
          try:
              key = load_master_key(self._key_path)
          except MasterKeyUnavailable as error:
              raise CredentialStorageUnavailable("the master key is unavailable") from error
          aad = associated_data(workspace_id, self._provider, row[0], row[1])
          plaintext = unseal(key, Sealed(bytes(row[2]), bytes(row[3]), bytes(row[4])), aad)
  ```

  Six handlers catch (CredentialStorageUnavailable, CredentialDecryptionError) together, and revalidate re-raises one as the other.
- **Why it matters:** Every caller has to know about an exception from the lower crypto module and treat it like the store's own. A new caller that catches only CredentialStorageUnavailable would turn a damaged row into an internal error, because settings_routes.as_api_error maps only the store's types. The boundary also leaks the other way: provider_settings.py:205-209 and tool_key_settings.py:125 mark credential rows deleted by writing the store's table directly.
- **Recommendation:** Translate CredentialDecryptionError inside load_active, as it already does for MasterKeyUnavailable. Raise a store-level subclass such as CredentialUnreadable(CredentialStorageUnavailable), so the existing handlers and settings_routes.as_api_error catch it while worker_inference's type-only log still tells a damaged row from a missing key. Then drop CredentialDecryptionError from the seven handlers. Add ProviderCredentialStore.delete_active to replace the two direct writes, and rename resolve_for_attempt_blocked_check (store.py:75), which is a guard, to require_usable.
- **Rule check:** SP-007: a missing or wrong master key with encrypted rows stays an error, never a replacement. Error codes and fixed messages are unchanged.
- **Verification:** revised. All seven handler sites and both direct status writes confirmed, and every caller treats the two errors alike. The recommendation now raises a subclass, because worker_inference.py:77 logs only the exception type and a plain translation would hide a damaged row behind 'storage unavailable'.

```text
class CredentialUnreadable(CredentialStorageUnavailable):
    """A stored row that this master key can't open. Holds no detail."""

async def load_active(self, workspace_id: UUID) -> ResolvedCredential:
    ...
    try:
        plaintext = unseal(key, sealed, aad)
    except CredentialDecryptionError as error:
        raise CredentialUnreadable("the stored key cannot be read") from error
```

### <a id="pops-10"></a>POPS-10: Boundary handlers log only the exception class, and retention's failure log omits the workspace

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [services/agent/src/autobots/operations/worker.py:143-149](../../../../services/agent/src/autobots/operations/worker.py#L143): worker.step_failed
  - [services/agent/src/autobots/operations/worker.py:276-277](../../../../services/agent/src/autobots/operations/worker.py#L276): the same handler, copied in both()
  - [services/agent/src/autobots/operations/worker.py:89-90](../../../../services/agent/src/autobots/operations/worker.py#L89): worker.heartbeat_lost
  - [services/agent/src/autobots/application/operations.py:153-155](../../../../services/agent/src/autobots/application/operations.py#L153): database.unavailable
  - [services/agent/src/autobots/application/operations.py:205-206](../../../../services/agent/src/autobots/application/operations.py#L205): storage.unavailable
  - [services/agent/src/autobots/application/operations.py:356-357](../../../../services/agent/src/autobots/application/operations.py#L356): migrations.unreadable
  - [services/agent/src/autobots/application/retention.py:171-172](../../../../services/agent/src/autobots/application/retention.py#L171): no workspace field
  - [services/agent/src/autobots/operations/logs.py:64-66](../../../../services/agent/src/autobots/operations/logs.py#L64): the formatter keeps only the exception type
- **Evidence:**

  ```python
          except Exception as error:
              log_event(logger, "retention.failed", logging.WARNING, error=type(error).__name__)
  ```

  JsonFormatter writes `record.exc_info[0].__name__` and nothing else, and every handler passes `error=type(error).__name__`. So a failing worker step logs `{"event": "worker.step_failed", "error": "KeyError"}`, with no step, module or line. The success line for retention carries `workspace=`, but the failure line doesn't.
- **Why it matters:** A recurring failure in the long-running worker or in readiness can only be located by reproducing it, and a retention failure can't be tied to a workspace. DH-06 asks to preserve causes in private logs. Dropping the message is right, since it can carry a connection string, but that doesn't require dropping the location too.
- **Recommendation:** Add error_fields(error) to the logging module. It returns the exception class plus the innermost autobots frame as module:function:line, with no message text. Use it at these seven sites; the handler copied into both() can share one helper with serve. Add workspace=workspace_id to retention.failed.
- **Rule check:** LM-07 and test_operations.py:64-79 keep messages out of logs. A frame location carries no message, secret or identifier, so both still hold.
- **Verification:** confirmed. The seven broad handlers that log only the class (worker.py:89, 143 and 276; operations.py:153, 205 and 356; retention.py:171) and the formatter's type-only rule confirmed. The worker step and retention handlers gain the most, since the readiness events already name what they probed.

```text
def error_fields(error: BaseException) -> dict[str, str]:
    frames = [f for f in traceback.extract_tb(error.__traceback__) if '/autobots/' in f.filename]
    last = frames[-1] if frames else None
    where = f'{Path(last.filename).stem}:{last.name}:{last.lineno}' if last else 'unknown'
    return {'error': type(error).__name__, 'where': where}
```

### <a id="pops-11"></a>POPS-11: Status vocabularies are bare strings, held together by six type: ignore comments

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [services/agent/src/autobots/application/operations.py:78-82](../../../../services/agent/src/autobots/application/operations.py#L78): Condition.state: str  # ok, degraded or unavailable
  - [services/agent/src/autobots/application/provider_settings.py:164-175](../../../../services/agent/src/autobots/application/provider_settings.py#L164): three arg-type ignores
  - [services/agent/src/autobots/application/provider_settings.py:298-301](../../../../services/agent/src/autobots/application/provider_settings.py#L298): a fourth ignore
  - [services/agent/src/autobots/application/provider_settings.py:231-247](../../../../services/agent/src/autobots/application/provider_settings.py#L231): run_intent returns str, through seven literal returns
  - [services/agent/src/autobots/application/worker_inference.py:68-72](../../../../services/agent/src/autobots/application/worker_inference.py#L68): a string-keyed map from run_intent codes
  - [services/agent/src/autobots/operations/worker.py:225-227](../../../../services/agent/src/autobots/operations/worker.py#L225): no_credential repeats a code literal
  - [services/agent/src/autobots/api/operation_routes.py:172](../../../../services/agent/src/autobots/api/operation_routes.py#L172): ignore needed because Condition's fields are str
  - [services/agent/src/autobots/api/operation_routes.py:180](../../../../services/agent/src/autobots/api/operation_routes.py#L180): ignore needed because timed_catalog returns str
- **Evidence:**

  ```python
  @dataclass(frozen=True)
  class Condition:
      name: str
      state: str  # ok, degraded or unavailable
  ...
              source=source,  # type: ignore[arg-type]
              auth_status=auth_status,  # type: ignore[arg-type]
              catalog_status=await self.catalog_status(),  # type: ignore[arg-type]
  ```
- **Why it matters:** mypy strict can't catch a misspelled state or code inside the application. run_intent's codes are compared with != "ready" and looked up in INTENT_FAILURES, which raises KeyError for any code it lacks. A wrong value surfaces only as a ValidationError when the DTO is built. The credential check that returns these codes is typed Awaitable[str], under one alias name with two signatures (routines.py:38, cronjob_tool.py:35). The database already limits auth_status to the four AuthStatus values (supabase/migrations/20261105000005_provider_settings.sql:5-6).
- **Recommendation:** Type each vocabulary once, with Literal aliases or StrEnums for condition name and state, auth status, catalog status, credential source and run intent. Where provider_settings already imports contracts.settings, reuse its AuthStatus, CatalogStatus and CredentialSource. Narrow the database strings once, when the settings row is read. Then remove the ignores.
- **Rule check:** contracts.md keeps domain, row and DTO types distinct. Sharing a Literal vocabulary merges no models, and the Pydantic DTOs remain the public contract.
- **Verification:** confirmed. The six status-related ignores confirmed (provider_settings.py:168-170 and 301, operation_routes.py:172 and 180). contracts/settings.py already defines AuthStatus, CatalogStatus and CredentialSource, and RunIntentCheck.code lists run_intent's codes; the scope holds eight ignores in all.

### <a id="pops-13"></a>POPS-13: Three catalog-availability checks disagree, and one has no caller

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/operations.py:275-288](../../../../services/agent/src/autobots/application/operations.py#L275): timed_catalog: 3 s; catches TimeoutError, OSError and ValueError
  - [services/agent/src/autobots/application/operations.py:291-301](../../../../services/agent/src/autobots/application/operations.py#L291): openrouter_availability: the same logic, with no caller (git grep)
  - [services/agent/src/autobots/application/provider_settings.py:124-128](../../../../services/agent/src/autobots/application/provider_settings.py#L124): catalog_status: no timeout; catches OSError only
  - [services/agent/src/autobots/application/provider_settings.py:274-277](../../../../services/agent/src/autobots/application/provider_settings.py#L274): models: no handling at all
  - [services/agent/src/autobots/adapters/models/openrouter_metadata.py:46](../../../../services/agent/src/autobots/adapters/models/openrouter_metadata.py#L46): reply.json() raises ValueError on a non-JSON 200
- **Evidence:**

  ```python
  # operations.timed_catalog and openrouter_availability
          payload = await asyncio.wait_for(fetch_catalog(), seconds)
      except (TimeoutError, OSError, ValueError):
  # provider_settings.catalog_status
          try:
              return "available" if await self._context.fetch_catalog() is not None else "unavailable"
          except OSError:
              return "unavailable"
  ```
- **Why it matters:** When the catalog answers 200 with a body that isn't JSON, Operations shows "unavailable", but GET /v1/settings/model-providers and GET /v1/models end in an internal error. Settings also waits up to the HTTP client's 15 s, where Operations waits 3 s. The dead copy is a third one to maintain.
- **Recommendation:** Write one application helper that fetches within a time limit, maps every expected failure to unavailable, and returns the status, payload and elapsed time. Use it in Operations and in ProviderSettings.status and models. Delete openrouter_availability.
- **Rule check:** MP-04 and SP-007: catalog status stays independent of authentication, and no model call is added.
- **Verification:** confirmed. catalog_fetcher catches only httpx.HTTPError and calls reply.json() unguarded, so a non-JSON 200 raises ValueError: Operations maps it to unavailable, while ProviderSettings.status and models let it escape. git grep finds no caller of openrouter_availability.

### <a id="pops-15"></a>POPS-15: Owner bootstrap can stop between its two writes, and reports only the exception class

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [services/agent/src/autobots/operations/bootstrap_owner.py:62-74](../../../../services/agent/src/autobots/operations/bootstrap_owner.py#L62): an Auth user, then a workspace, under one generic handler
  - [services/agent/src/autobots/operations/bootstrap_owner.py:25-35](../../../../services/agent/src/autobots/operations/bootstrap_owner.py#L25): Auth admin API create; not idempotent
  - [docs/engineering/runbooks/local-app.md:35](../../../../docs/engineering/runbooks/local-app.md#L35): 'Run it once'; no recovery step
- **Evidence:**

  ```python
      try:
          user_id = create_auth_user(...)
          workspace_id = create_workspace(
              os.environ["AUTOBOTS_DATABASE_URL"], user_id, args.workspace_name
          )
      except (error.URLError, psycopg.Error, ValueError, KeyError) as failure:
          print(f"ERROR: bootstrap was refused: {type(failure).__name__}.", file=sys.stderr)
          return 1
  ```
- **Why it matters:** If the Auth user is created and the workspace insert then fails, for example because of a wrong runtime URL or a missing grant, nothing says that a user now exists. A rerun is refused because the email is taken, and the runbook gives no way to finish except finding and removing the Auth user by hand.
- **Recommendation:** Open and check the database connection before creating the Auth user, so a wrong URL or a missing grant fails while nothing exists yet. When the workspace step still fails, print the created user ID with a distinct status, still exiting 1. Accept --user-id so the workspace can be finished for an existing Auth user, and add that recovery to the runbook.
- **Rule check:** SP-015 (secure owner setup) and SP-018 (runbook recovery). Auth is still written only through its admin API.
- **Verification:** revised. The two writes, the single type-only handler and the runbook's 'Run it once' (docs/engineering/runbooks/local-app.md:35) confirmed. The recommendation now checks the database first, which removes the likeliest cause before any user exists.

### <a id="pops-07"></a>POPS-07: The reasoning trial's shared US$1 ledger path is relative to the working directory

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** high · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/operations/reasoning_trial.py:51-53](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L51): SHARED_LEDGER = Path('.checks/decision-0009/ledger.json')
  - [services/agent/src/autobots/operations/reasoning_trial.py:366](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L366): Ledger(Path(arguments.ledger), ...) uses the path as given
  - [services/agent/src/autobots/operations/reasoning_trial.py:417](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L417): --ledger default
  - [services/agent/src/autobots/operations/route_qualification.py:115-123](../../../../services/agent/src/autobots/operations/route_qualification.py#L115): the docstring says a rerun can't spend the cap twice, but a missing file starts empty
  - [scripts/persistent_install.py:750](../../../../scripts/persistent_install.py#L750): the same literal
  - [scripts/persistent_install.py:759](../../../../scripts/persistent_install.py#L759): and again
  - [scripts/persistent_install.py:796-800](../../../../scripts/persistent_install.py#L796): joined to project_root(), so the install is not affected
- **Evidence:**

  ```python
  # Decision 0009: the whole of what this trial and US-11.3's goals may spend, in micro-USD.
  SHARED_CAP_MICRO_USD = 1_000_000
  SHARED_LEDGER = Path(".checks/decision-0009/ledger.json")
  ...
          ledger = Ledger(Path(arguments.ledger), SHARED_CAP_MICRO_USD)
  ```

  A Ledger starts with no entries when its file doesn't exist (route_qualification.py:121-123). persistent_install.py repeats the literal at :750 and :759 but joins it to project_root() at :796 and :800, so only the reasoning trial depends on the working directory.
- **Why it matters:** Started from services/agent with an absolute --key-file, the reasoning trial opens a new, empty ledger, and Decision 0009's shared cap starts over without a warning. The runbook runs it from the repository root (docs/engineering/runbooks/operations.md:75), and with the default --key-file .env a run from elsewhere stops on the missing key file before anything is sent, so the gap needs an unusual invocation. The Ledger docstring's promise that a rerun can't spend the cap twice still rests on it.
- **Recommendation:** Define the shared ledger path once, beside SHARED_CAP_MICRO_USD, and resolve --ledger against the repository root as persistent_install.py already does. When the ledger is meant to be shared, say in the trial's output that it created a new ledger file, or refuse to create one without an explicit flag.
- **Rule check:** Decision 0009's US$1 shared cap. The change only makes the cap harder to bypass.
- **Verification:** revised. Confirmed for reasoning_trial.py, which passes Path(arguments.ledger) as given. persistent_install.py joins the same literal to project_root(), so the claim about it was withdrawn. Lowered to low: the runbook runs from the root, and a default run elsewhere stops on the missing .env before any call.

### <a id="pops-08"></a>POPS-08: browse_trial.run_trial does the whole trial inline, and its report assembly has no offline test

- **Severity** low · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/operations/browse_trial.py:137-328](../../../../services/agent/src/autobots/operations/browse_trial.py#L137): 192 lines, 67 statements, 7 parameters
  - [services/agent/src/autobots/operations/browse_trial.py:146-158](../../../../services/agent/src/autobots/operations/browse_trial.py#L146): 12 imports inside the function
  - [services/agent/src/autobots/operations/browse_trial.py:160](../../../../services/agent/src/autobots/operations/browse_trial.py#L160): mutates os.environ
  - [services/agent/src/autobots/operations/browse_trial.py:257](../../../../services/agent/src/autobots/operations/browse_trial.py#L257): 'started' is written before the paid call, which blocks a rerun
  - [services/agent/src/autobots/operations/browse_trial.py:291-322](../../../../services/agent/src/autobots/operations/browse_trial.py#L291): the report is built by zipping rows with column tuples
  - [services/agent/src/autobots/operations/reasoning_trial.py:202-274](../../../../services/agent/src/autobots/operations/reasoning_trial.py#L202): 73 lines, complexity 11, 8 returns
  - [services/agent/tests/test_browse_trial.py:17](../../../../services/agent/tests/test_browse_trial.py#L17): imports refuse_repeat, TrialModel, hosts and inside, never run_trial
- **Evidence:** browse_trial.run_trial does the whole trial in one body. It creates an Expert, builds a binding, admits a run, checks the frozen Sol route, claims the job twice, drives the gateway, approves, writes the start record, reads invocations and tool uses, and assembles the report. The module says "It runs in no verification profile" (browse_trial.py:13), as US-14.16#1 requires, and no test calls run_trial. US-14.16 is DONE, so the trial has run once. reasoning_trial.run_trial, which test_reasoning_trial.py exercises with a fake transport, mutates one TrialResult across eight early returns.
- **Why it matters:** The code that spends the once-only Sol trial budget (Decision 0019 S6) runs only live. It matters when the owner asks for a repeat: a defect in report assembly after the call, such as a zip(strict=True) column mismatch, would surface after money is spent and after the start record is written, and that record refuses another repeat without the owner. The environment mutation also leaks into whatever runs next in the process.
- **Recommendation:** Before any owner-requested repeat, split the browse trial into named steps and make the report a pure function over typed rows, unit-tested with fixed rows; that needs no database, executor or model. Keep run_trial itself out of the verification profiles, as US-14.16#1 states. In reasoning_trial, return early through one small stop type instead of mutating the result in eight places.
- **Rule check:** Decision 0019 S6 (one live trial), US-14.16#1 (no verification profile) and the --owner-requested-repeat refusal stay. DH-06 and model-gateway.md make fake transports and pure units the default test path.
- **Verification:** revised. 192 lines, 67 statements, 7 parameters, 12 inline imports and the os.environ write confirmed; no test calls browse_trial.run_trial. Lowered to low because US-14.16 is DONE and a repeat needs the owner. The recommendation now unit-tests a pure report instead of running the trial in the db profile, which US-14.16#1 keeps out of verification.

```text
async def run_trial(...):                                        # about 30 lines
    run, policy = await _admit_trial_run(db, workspace, actor)    # Expert, admission, Sol check
    pending = await _execute(db, await _claim(db, run), runtime)  # gateway inside middleware.active()
    await _approve(db, workspace, actor, run)
    _write(out, started(run)); result = await _execute(db, await _claim(db, run), runtime)
    return build_report(run, route, result, await _read_spend(db, run), executor.log)
def build_report(run, route, result, rows: SpendRows, log) -> dict    # pure; unit-tested with fixed rows
reasoning_trial: _first_call(...) -> Reply | Stop; _continue(...) -> Reply | Stop; _compare(...) -> TrialResult
```

### <a id="pops-12"></a>POPS-12: _settings_row inserts on every read, and two writers call it only for that insert

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/application/provider_settings.py:101-114](../../../../services/agent/src/autobots/application/provider_settings.py#L101): insert on conflict, then select
  - [services/agent/src/autobots/application/provider_settings.py:135](../../../../services/agent/src/autobots/application/provider_settings.py#L135): auth_status
  - [services/agent/src/autobots/application/provider_settings.py:147](../../../../services/agent/src/autobots/application/provider_settings.py#L147): status, behind a GET
  - [services/agent/src/autobots/application/provider_settings.py:234](../../../../services/agent/src/autobots/application/provider_settings.py#L234): run_intent, the gate before each model call and each routine admission
  - [services/agent/src/autobots/application/provider_settings.py:228](../../../../services/agent/src/autobots/application/provider_settings.py#L228): revalidate discards the result
  - [services/agent/src/autobots/application/provider_settings.py:271](../../../../services/agent/src/autobots/application/provider_settings.py#L271): mark_invalid discards the result
- **Evidence:**

  ```python
      async def _settings_row(self, workspace_id: UUID, lock: bool = False) -> tuple[int, str, Any]:
          await self._connection.execute(
              "insert into app_private.provider_settings (workspace_id) values (%s) "
              "on conflict (workspace_id) do nothing",
              (workspace_id,),
          )
  ```

  revalidate and mark_invalid call `await self._settings_row(workspace_id)` and ignore what it returns, so that the following _record update finds a row.
- **Why it matters:** This getter also writes. Every status read and every run-intent check, which runs before each model call and each routine admission, issues an insert. The runtime role already holds insert on the table, so the cost is clarity rather than privilege, but the two calls that discard the result hide why they exist. The positional boolean `lock` is what ruff's FBT001 flags.
- **Recommendation:** Split the function. _ensure_settings_row serves the writers (save_credential, disconnect, revalidate, mark_invalid). _read_settings(workspace_id, *, for_update=False) returns the table defaults (version 0, "missing", no validated_at) when no row exists.
- **Rule check:** SP-014 and MP-05: version-checked settings mutations keep their row lock, and reads stop writing.
- **Verification:** revised. The insert-then-select and its callers confirmed. Lowered to low: the runtime role is granted insert on provider_settings anyway, and an insert that conflicts writes no row. The table defaults the recommendation relies on are version 0, 'missing' and a null validated_at (supabase/migrations/20261105000005_provider_settings.sql:2-8).

### <a id="pops-14"></a>POPS-14: Entry points disagree on configuration checks, refusals and exit codes

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/operations/bootstrap_owner.py:58-61](../../../../services/agent/src/autobots/operations/bootstrap_owner.py#L58): missing env: 'ERROR: set ...', exit 2
  - [services/agent/src/autobots/operations/concept_seed.py:415-418](../../../../services/agent/src/autobots/operations/concept_seed.py#L415): missing URL: 'REFUSED: ...', exit 2
  - [services/agent/src/autobots/operations/concept_seed.py:343](../../../../services/agent/src/autobots/operations/concept_seed.py#L343): SystemExit(str) raised inside seed(), exit 1
  - [services/agent/src/autobots/operations/worker.py:319-320](../../../../services/agent/src/autobots/operations/worker.py#L319): missing URL: SystemExit, exit 1
  - [services/agent/src/autobots/operations/browse_trial.py:342](../../../../services/agent/src/autobots/operations/browse_trial.py#L342): os.environ[...] and UUID(...) raise tracebacks
  - [services/agent/src/autobots/operations/route_qualification.py:695-701](../../../../services/agent/src/autobots/operations/route_qualification.py#L695): a malformed --only raises an uncaught ValueError
- **Evidence:** A missing AUTOBOTS_DATABASE_URL gets a different outcome in each entry point:

  - bootstrap_owner: exit 2 with "ERROR: set ..."
  - concept_seed: exit 2 with "REFUSED: ..."
  - worker: exit 1 through SystemExit
  - browse_trial: a KeyError traceback

  Refusal prefixes vary too: "ERROR: bootstrap was refused", "REFUSED, nothing sent", "REFUSED, nothing further sent" and "REFUSED:". The trials and the worker also write JSON log lines to the same stderr.
- **Why it matters:** Wrappers and runbooks can't tell "not configured" from "refused" the same way across entry points, and bad arguments surface as tracebacks. bootstrap_owner documents exit 2 for missing configuration, matching what AGENTS.md uses for verify.py's unavailable prerequisite, but the other entry points don't follow it. No script tells these codes apart today, so the cost is operator confusion.
- **Recommendation:** Add a small shared CLI helper with three parts: require_env(*names), which exits 2; refuse(reason), with one stderr format and exit 1; and argparse type= parsers for UUIDs and name=count pairs. Library code raises typed errors, such as seed's missing owner, instead of SystemExit. Keep stdout JSON as the result contract that the wrappers parse.
- **Rule check:** Follows the AGENTS.md exit codes (0 passed, 1 failed, 2 prerequisite unavailable) and bootstrap_owner's own docstring. scripts/qualify_identity.py:60 reads stdout JSON, which stays unchanged.
- **Verification:** revised. Each exit path confirmed, including the uncaught ValueError from a malformed --only. Lowered to low: the qualifiers only test for a nonzero exit and read the JSON on stdout, so nothing depends on 1 versus 2 yet.

### <a id="pops-16"></a>POPS-16: Trial and seed code bypass existing types and seams

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/src/autobots/operations/route_qualification.py:596](../../../../services/agent/src/autobots/operations/route_qualification.py#L596): cast(ModelProfile, route), though a Route has no id
  - [services/agent/src/autobots/operations/concept_seed.py:153](../../../../services/agent/src/autobots/operations/concept_seed.py#L153): graph: Any, with its real type in a comment
  - [services/agent/src/autobots/operations/browse_trial.py:175-185](../../../../services/agent/src/autobots/operations/browse_trial.py#L175): an anonymous Binding class for admit_run's binding: Any
  - [services/agent/src/autobots/operations/browse_trial.py:229-233](../../../../services/agent/src/autobots/operations/browse_trial.py#L229): sets loop_middleware._MIDDLEWARE (SLF001); also tests/db/browse_goal_check.py:119 and services/agent/tests/test_browsing_tool.py:235
  - [services/agent/src/autobots/operations/route_qualification.py:477-486](../../../../services/agent/src/autobots/operations/route_qualification.py#L477): AsyncIterator annotation, then type: ignore on aclose
- **Evidence:**

  ```python
      profile = cast(ModelProfile, route)
      graph: Any  # Callable[[Mapping[str, UUID]], dict[str, Any]]
          binding = type("Binding", (), {"session_id": None, "expert_id": expert.id, ...})()
              token = loop_middleware._MIDDLEWARE.set(middleware)
                  await stream.aclose()  # type: ignore[attr-defined]
  ```
- **Why it matters:** Each hides a mismatch that mypy could report. PreparedAttempt.profile can hold a Route without an id, so a future attempt.profile.id would fail only during a paid qualification. The anonymous binding exists because admit_run takes Any and RunBinding requires a session. LoopMiddleware's activation is reached through a private name in three places.
- **Recommendation:** Where only wire_id and canonical_id are read, accept a small Protocol with those two fields. Annotate graph with its Callable type. Give admit_run a binding Protocol with session_id: UUID | None. Add a public LoopMiddleware.active() context manager, and type the stream as AsyncGenerator.
- **Rule check:** SP-017: validate runtime data rather than trusting casts. Under contracts.md the types stay distinct, since a Protocol merges nothing.
- **Verification:** revised. All five seams confirmed, including the private _MIDDLEWARE in tests/db/browse_goal_check.py:119 and test_browsing_tool.py:235. Risk lowered to low, since each change is type-only or a mechanical wrapper. admit_run's binding: Any is also PRUN-04 in the py-run review.

### <a id="pops-17"></a>POPS-17: Query rows and database or store handles cross module boundaries untyped

- **Severity** low · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 71
- **Where:**
  - [services/agent/src/autobots/application/operations.py:261-272](../../../../services/agent/src/autobots/application/operations.py#L261): delayed_occurrences returns tuples...
  - [services/agent/src/autobots/api/operation_routes.py:141-149](../../../../services/agent/src/autobots/api/operation_routes.py#L141): ...that another module reads by position
  - [services/agent/src/autobots/application/provider_settings.py:321-340](../../../../services/agent/src/autobots/application/provider_settings.py#L321): qualification_from_record indexes record[1] to record[5]
  - [services/agent/src/autobots/operations/browse_trial.py:259-322](../../../../services/agent/src/autobots/operations/browse_trial.py#L259): column names written in the SQL and again for zip
  - [services/agent/src/autobots/application/retention.py:64-65](../../../../services/agent/src/autobots/application/retention.py#L64): store: Any
  - [services/agent/src/autobots/application/artifacts.py:25-29](../../../../services/agent/src/autobots/application/artifacts.py#L25): an ObjectStore Protocol already exists (without ping)
  - [services/agent/src/autobots/persistence/rows.py:1](../../../../services/agent/src/autobots/persistence/rows.py#L1): the project's row TypedDict convention
- **Evidence:** The scope has 35 untyped handle parameters (26 `connection: Any`, 1 `pool: Any`, 8 `store: Any`) and 36 lines in six files that index query rows by position. Both were counted with a regex over the 18 files, the second matching row, record, found, active, zone, present and result indexed by a digit, and fetchone())[0]. `delayed_occurrences(...) -> list[tuple[Any, ...]]` is consumed as row[0] to row[3] by api/operation_routes.py. Yet persistence/rows.py says "A row is never a public response; adapters convert it explicitly", and adapters/checkpoints.py:70 already uses psycopg's dict_row.
- **Why it matters:** Reordering a select silently changes meaning in another module. mypy can't check the store's ping and remove or a connection's methods, so the ObjectStore Protocol and the row convention protect nothing here.
- **Recommendation:** Where rows leave a module, return a small dataclass or TypedDict, using psycopg's class_row or dict_row. Type store parameters as ObjectStore extended with ping, or as a narrow Pingable protocol. Type connections as psycopg.AsyncConnection or a narrow protocol.
- **Rule check:** Follows persistence/rows.py's convention and DH-06's ban on broad untyped dictionaries. Rows stay separate from DTOs.
- **Verification:** revised. Handle count confirmed at 35. The positional-index count is 36 lines with the wider name set (29 with row, record and fetchone() alone), not 35, so occurrences is 71.

### <a id="pops-18"></a>POPS-18: The readiness lists carry a truncated comment and an over-attributed decision range, and a DB check patches them

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/application/operations.py:30](../../../../services/agent/src/autobots/application/operations.py#L30): 'Add the one a required new migration creates.'
  - [services/agent/src/autobots/application/operations.py:44](../../../../services/agent/src/autobots/application/operations.py#L44): cites migrations 38 to 53 to Decision 0023 E2
  - [services/agent/src/autobots/application/operations.py:51](../../../../services/agent/src/autobots/application/operations.py#L51): truncated sentence
  - [supabase/migrations/20261108000049_applied_migration_count.sql:5](../../../../supabase/migrations/20261108000049_applied_migration_count.sql#L5): the count is null with neither history table present
  - [tests/db/review_check.py:177-180](../../../../tests/db/review_check.py#L177): reassigns operations.REQUIRED_COLUMNS to test it
  - [docs/engineering/decisions/0023-install-current-and-real-examples.md:21](../../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#L21): E2: the lists cover migrations 38 to 49, for a database with no readable history
- **Evidence:**

  ```python
  # The relations a release can't run without. Add the one a required new migration creates.
      # Migrations 38 to 53 (Decision 0023 E2), for a database with no readable history.
  # A migration can add only columns, which a relation check can't see. The newest code relies on.
  ```

  Decision 0023 E2 names migrations 38 to 49. applied_migration_count() returns null when neither history table exists, and schema_condition then lets the lists decide (operations.py:177-185), so they are what shows such a database as behind.
- **Why it matters:** The comment credits E2 with a range it doesn't state, and the truncated sentence leaves the column list's purpose unclear. Nothing in the code says that the lists exist for a database whose history can't be counted, which is why each later migration still adds an entry. Because database_conditions reads the module globals, the DB check reassigns operations.REQUIRED_COLUMNS to exercise them.
- **Recommendation:** Replace the three comments with one docstring that says what the lists are for (a database whose applied history can't be counted, Decision 0023 E2, extended to each later migration) and finishes the column list's sentence. Pass a RequiredSchema argument that defaults to the constants, so tests don't have to patch module state.
- **Rule check:** Aligns the comment with Decision 0023 E2 and keeps the practice of citing decisions in comments.
- **Verification:** revised. The truncated sentence, the 38-to-53 citation and the patch in tests/db/review_check.py:177-180 confirmed. The original claim that the applied count makes per-migration entries unnecessary was withdrawn: the count is null without a history table, and then only the lists can show the database behind.

### <a id="pops-19"></a>POPS-19: The serve loop opens its own connections, so drain, reconnect and the final heartbeat are tested only against Docker Postgres

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [services/agent/src/autobots/operations/worker.py:78-80](../../../../services/agent/src/autobots/operations/worker.py#L78): _beat connects itself
  - [services/agent/src/autobots/operations/worker.py:135-137](../../../../services/agent/src/autobots/operations/worker.py#L135): serve connects itself
  - [services/agent/src/autobots/operations/worker.py:162-164](../../../../services/agent/src/autobots/operations/worker.py#L162): the last heartbeat connects itself
  - [services/agent/src/autobots/operations/worker.py:102-122](../../../../services/agent/src/autobots/operations/worker.py#L102): _run_step's drain takes its connection as an argument, yet has no unit test
  - [services/agent/tests/test_worker_inference.py:1031-1081](../../../../services/agent/tests/test_worker_inference.py#L1031): both() already has three unit tests, the pattern to extend
  - [services/agent/src/autobots/operations/worker.py:195-196](../../../../services/agent/src/autobots/operations/worker.py#L195): state kept in one-element lists
  - [services/agent/tests/test_final_review.py:42](../../../../services/agent/tests/test_final_review.py#L42): imports only inference_step from the worker
- **Evidence:** serve, _beat and the final heartbeat each run `async with await psycopg.AsyncConnection.connect(config.database_url, autocommit=True) as connection:`. tests/db/operations_worker.py drives serve against a disposable database. both() already has three unit tests (services/agent/tests/test_worker_inference.py:1031-1081), and _run_step takes its connection as an argument, yet no unit test exercises the drain. maintenance_step keeps its state in `last_retention: list[float] = []` and `said: list[str] = []`.
- **Why it matters:** Several behaviors can only be checked by the db and operations profiles, with real time: the drain cut short, reconnecting after OperationalError, and the final stopped heartbeat. DH-06 asks for controlled clocks and injected transports, and python-worker.md asks for cancellation and restart tests where behavior changes.
- **Recommendation:** Unit-test _run_step's drain now, with a slow fake step and a short drain_seconds; it needs no change. Inject a connect callable into serve, defaulting to psycopg's, to unit-test reconnect and the final heartbeat with a fake connection. Keep the maintenance state in a small dataclass.
- **Rule check:** python-worker.md: test cancellation, duplicate delivery and restart where behavior changes. DH-06: controlled clocks and injected transports.
- **Verification:** revised. The three self-opened connections and the missing drain test confirmed. both() is not untested: test_worker_inference.py has three tests for it, so that location was replaced, and the drain test needs no refactor.

### <a id="pops-20"></a>POPS-20: apply_retention and concept_seed.seed each run three phases in one body

- **Severity** low · **Dimension** size · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [services/agent/src/autobots/application/retention.py:92-157](../../../../services/agent/src/autobots/application/retention.py#L92): 66 lines: purge loop, objects, receipts, log
  - [services/agent/src/autobots/application/retention.py:104-117](../../../../services/agent/src/autobots/application/retention.py#L104): keyset parameters repeated by position
  - [services/agent/src/autobots/operations/concept_seed.py:334-401](../../../../services/agent/src/autobots/operations/concept_seed.py#L334): 68 lines: owner, Experts, workflows
  - [services/agent/src/autobots/operations/concept_seed.py:346](../../../../services/agent/src/autobots/operations/concept_seed.py#L346): report: dict[str, Any] mixes 'kept' strings and dicts
- **Evidence:**

  ```python
                  "and (%s::timestamptz is null or (updated_at, id) > (%s::timestamptz, %s::uuid)) "
                  ...
                      position[0] if position else None,
                      position[0] if position else None,
                      position[1] if position else None,
  ```

  seed records "kept" as a string for existing items, and dicts such as {"created": True, "without": [...]} for new ones.
- **Why it matters:** The keyset placeholders have to stay aligned with their positional values by hand. seed's report has two shapes per entry, which callers must special-case. Neither function can be tested one phase at a time.
- **Recommendation:** Extract the phases, use named parameters for the keyset query, and give the seed a typed report. Update tests/db/concept_seed_check.py with it, since that check reads 'kept' as a bare string.
- **Rule check:** SP-015 (repeatable seeds) and SP-014 (retention scoping) are unchanged; this is extraction only. tests/db/operations_check.py and tests/db/major_check.py cover retention.
- **Verification:** confirmed. Both function spans (retention.py:92-157, concept_seed.py:334-401), the positional keyset parameters and the two report shapes confirmed. tests/db/concept_seed_check.py:65-66 relies on the 'kept' string, so the recommendation now names it.

```text
apply_retention: policy, moment -> await _purge_expired_runs(conn, ws, cutoff, report)   # named %(after_at)s, %(after_id)s
                -> await _remove_expired_objects(...) -> await _expire_receipts(conn, ws, cutoff, report)
seed: actor = await _owner(conn, ws)
      experts, expert_outcomes = await _seed_experts(conn, ws, actor, usable)
      workflow_outcomes = await _seed_workflows(conn, ws, actor, usable, experts)
      return SeedReport(experts=expert_outcomes, workflows=workflow_outcomes)
```

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| None | | Every finding was kept. Corrections are recorded on each revised finding. |

## Not covered

This was a static reading only, with no runtime check. mypy was not run because it is not in the allowed command list; ruff ran in check mode on the scope. I read PRD-Development-Harness.md only from DH-03 to DH-06, and docs/engineering/option-b-contract.md only in sections 5 to 7. I did not open PRD-Model-Providers.md, so MP-* references come from code comments. I read files outside the area only at the cited lines: api/operation_routes.py, api/settings_routes.py, application/worker_inference.py, application/cronjob_tool.py, application/runs.py, adapters/models/catalog.py, adapters/loop_middleware.py, scripts/persistent_install.py and the tests/db checks. I did not rerun the DB-backed checks and judged their coverage from source. The comparison with an earlier review is left to the synthesis step.

Verification recounted with grep and Python ast walks run as `python3.12 -I` scratch scripts outside the repository, measured docstring coverage (82 of 189 public definitions), and read the cited tests/db checks, runbooks and Decision 0023. Nothing was run against a database, Docker or a model, and mypy was not run.
