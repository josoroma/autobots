# Proposed standards

Code quality review of 2026-11-12 09:52:30, revision d0d85d3. [Back to the review](README.md)

[DH-06](../../PRD/PRD-Development-Harness.md#dh-06-coding-and-layer-standards) states the principles: explicit ownership, narrow interfaces, small cohesive modules, validated boundaries, centralized errors, no swallowed exceptions and no duplicated business rules. This document turns them into rules that a tool or a named check can hold, calibrated to the code as it is today. It cites the project's rules instead of restating them: [AGENTS.md](../../../AGENTS.md), [.claude/rules/](../../../.claude/rules/), [DH-03](../../PRD/PRD-Development-Harness.md#dh-03-required-repository-structure), [DH-05](../../PRD/PRD-Development-Harness.md#dh-05-hooks-and-portable-enforcement), [DH-09](../../PRD/PRD-Development-Harness.md#dh-09-verification-profiles-and-completion-rules) and [PRD-Design-System.md](../../PRD/PRD-Design-System.md). Refactoring work lives in [refactor-plan.md](refactor-plan.md), named here by topic.

Every number comes from [metrics.md](metrics.md), from a verified finding (linked by ID), or from a read-only count made for this document and listed with its command under [Counts added for this document](#counts-added-for-this-document). The review is static. It establishes no runtime behavior, no H1 and no product acceptance.

## Summary

Status: **Enforced** means a check holds the rule today. **Partly** means a check holds part of it. **Proposed** means nothing holds it yet. "Today" is the amount of code a proposed check would flag at its starting threshold.

| ID | Rule | Enforced by | Status | Today |
|---|---|---|---|---|
| [STD-01](#std-01) | Service layers import inward; no private names cross modules | ruff TID251 per layer; `layer_imports` convention check | Proposed | domain 0, contracts 1; 33 cross-layer statements; 40 private-name imports |
| [STD-02](#std-02) | Web: primitives, lib and screens import in one direction, without cycles | `import/no-restricted-paths`, `import/no-cycle`; `server-only` at build | Partly | 0 zone hits; 1 cycle (2 hits) |
| [STD-03](#std-03) | A rule that guards money, secrets or state has one implementation | parity tests; review | Partly | 3 secret patterns, 3 admission paths, 4 paid guards |
| [STD-04](#std-04) | The layout follows DH-03 or a recorded amendment; rule scopes match real files | `rule_scopes` convention check; decision record | Partly | 5 dead globs; 5 layout differences |
| [STD-05](#std-05) | Modules stay within length budgets | ESLint `max-lines`; `module_lines` convention check | Proposed | 8 of 139 service modules over 500 lines; 10 of 97 web files over 400 |
| [STD-06](#std-06) | Python complexity, branches, returns and statements stay within limits | ruff C901, PLR0911, PLR0912, PLR0915 | Proposed | 16 hits in services/agent |
| [STD-07](#std-07) | TypeScript complexity, nesting and function length stay within limits | ESLint `complexity`, `max-depth`, `max-lines-per-function` | Proposed | 35 hits in source, 3 in specs |
| [STD-08](#std-08) | Functions take few parameters; more become keyword-only or a parameter object | ruff PLR0913, PLR0917; ESLint `max-params` | Proposed | 25 hits in services/agent; 1 in specs |
| [STD-09](#std-09) | Decisions are pure and unit-tested; reads never write; factories only wire | review checklist; STD-06 limits | Proposed | `_finish`, `apply_command`, `post_run`, 7 tool factories |
| [STD-10](#std-10) | API replies are parsed, never asserted | ESLint `no-restricted-syntax` | Proposed | 30 assertions on JSON in 17 files |
| [STD-11](#std-11) | Request bodies use the generated request types | ESLint `no-restricted-syntax` | Proposed | 24 untyped literal bodies; 0 generated request types used |
| [STD-12](#std-12) | Vocabulary maps are keyed by generated unions; switches are exhaustive | typescript-eslint type-aware rules; ESLint selector | Partly | 28 string-keyed maps; 13 unnecessary assertions |
| [STD-13](#std-13) | SQL, provider and framework boundaries are typed; `Any` needs a reason | ruff ANN401; mypy strict | Partly | 398 ANN401 in src, 221 of them on `connection: Any` parameters |
| [STD-14](#std-14) | State and code vocabularies are enums or Literals with one source | mypy; parity tests | Partly | 12 arg-type bridges; 23 `str` state fields; 9 enums copied |
| [STD-15](#std-15) | Contract models use named configs, strict request primitives, declared errors and UTC timestamps | `test_contract_shape.py` | Partly | 22 of 30 bodies lax; 78 of 78 operations misdeclare errors; 4 + 5 timestamps |
| [STD-16](#std-16) | Persisted documents have versioned record models apart from DTOs | one read test per record type | Proposed | 16 stored reads through request contracts; 34 untyped document sites |
| [STD-17](#std-17) | Money stays exact, time stays UTC, and each language formats them once | ruff DTZ; `money_floats` check; `lib/format.ts` unit tests | Partly | 2 float conversions; 6 `dollars()` copies |
| [STD-18](#std-18) | Generated contracts are regenerated, validated completely and covered by shared fixtures | `contract_drift` (fast); generator keyword check; fixture coverage test | Partly | 2 of 32 parsed schemas have cases; 10 map fields unchecked |
| [STD-19](#std-19) | No blind or silent handlers; cancellation always propagates | ruff BLE001, S110, S112; `broad_suppress` check | Proposed | 27 broad catches; 3 broad `suppress` |
| [STD-20](#std-20) | Causes reach private logs through one helper; log events are registered | `test_log_events.py` | Partly | 13 class-name-only logs; 24 unregistered names |
| [STD-21](#std-21) | Refusals share one base, one HTTP mapping and published codes | `test_refusals.py`; one exception handler | Partly | 61 classes in 4 conventions; 11 route mappers |
| [STD-22](#std-22) | Every web read and write has explicit outcome states | ESLint selector; runtime error split | Proposed | 89 error-discarding catches in 31 files |
| [STD-23](#std-23) | Comments say what holds now and cite resolvably | `specs.py refs`; ruff ERA001 | Partly | 9 stale comments; 36 ambiguous "PRD x.y" |
| [STD-24](#std-24) | Docstrings sit where risk concentrates; every module keeps one | ruff D100, D104; `undocumented_long` check | Proposed | 0 modules without a docstring; 16 long public functions without one |
| [STD-25](#std-25) | Every suppression names a code and a reason; dead ones go | ruff PGH003, PGH004, RUF100; `suppression_reasons` check | Partly | 87 `type: ignore` without a reason; 295 dead `noqa` |
| [STD-26](#std-26) | READMEs route readers to the runbooks | `readmes` convention check | Proposed | none in apps/web, services/agent, scripts, tests/db |
| [STD-27](#std-27) | All Python shares one format and import order | `ruff format --check` on every Python path | Partly | services/agent only; 121 of 131 repository-level files unformatted |
| [STD-28](#std-28) | Web formatting is explicit and covers packages/api-client | `prettier --check`; `.prettierrc.json` | Partly | apps/web only; 2 api-client files unformatted |
| [STD-29](#std-29) | Names describe behavior; one meaning per word; file-name conventions hold | ruff N; `file_names` check | Proposed | 0 service N hits; 7 review-named files; 9 handlers share 4 names |
| [STD-30](#std-30) | Magic values get names; HTTP statuses have one spelling | ruff PLR2004 (src) | Proposed | 52 hits, 34 of them statuses |
| [STD-31](#std-31) | Server Components by default | review checklist | Proposed | 2 of 22 pages read on the server |
| [STD-32](#std-32) | One client data layer for reads, writes and live updates | ESLint `no-restricted-globals`, `no-restricted-imports` | Proposed | 45 `fetch` in 25 files; `csrfFetch` in 19 |
| [STD-33](#std-33) | Pure UI logic lives in lib/ and is unit-tested | ESLint selector; unit-test glob | Partly | 12 helpers and constants exported from screens |
| [STD-34](#std-34) | Screens use shared primitives and design tokens | `test_shared_form_controls.py`; `design_tokens` check | Partly | 212 arbitrary font sizes; 26 copied layout pieces |
| [STD-35](#std-35) | Forms, titles and accessibility scans meet one line | jsx-a11y preset; `page_titles` check; axe import rule | Partly | 0 `aria-invalid`; 6 untitled pages; 21 of 35 scans below the line |
| [STD-36](#std-36) | API routes stay thin: no SQL, shared dependencies, one response type | `api_sql` check; ruff FAST | Proposed | 17 `execute` calls in api/; 10 `_pool` copies; 78 FAST001 |
| [STD-37](#std-37) | Each state has one writer; adapters get capabilities, not connections | `state_writers` check | Partly | 15 run and job writes in 4 modules; 11 approval and receipt writes in 6 |
| [STD-38](#std-38) | Process configuration is read at entry points | ruff TID251 per layer | Proposed | 26 modules read the environment |
| [STD-39](#std-39) | Async resources are owned, bounded and cancellable | ruff ASYNC; `broad_suppress` check; review | Partly | 6 client constructors; 3 hand-run lease keepers |
| [STD-40](#std-40) | New migrations state locks, data and recovery, and are named for content | `migration_headers` check | Proposed | 15 of 53 migrations rewrite data without notes |
| [STD-41](#std-41) | Grants, RLS and indexes are checked from the catalog | `tests/db/catalog_check.py` (db) | Partly | runtime DELETE on 5 tables; 5 unindexed lookups |
| [STD-42](#std-42) | SQL vocabularies and predicates have one source | db parity check; `sql_status_literals` check | Proposed | profiles in 3 CHECKs; terminal predicate 9 times |
| [STD-43](#std-43) | Every test file belongs to a runner, and runners are documented | runner globs; `test_ownership` check; decision record | Partly | 2 suites and 1 static test class run in no profile |
| [STD-44](#std-44) | Tests drive public seams | `layer_imports` check; import-contract check | Proposed | 34 private imports in tests; 26 private overrides |
| [STD-45](#std-45) | Evaluate once, judge that value, fail readably | shared check API; `bare_assertions` check | Proposed | 80 double evaluations; 47 bare `assertTrue(any(...))` |
| [STD-46](#std-46) | Tests share support modules instead of copying helpers | ESLint selector (specs); `copies` check | Proposed | 64 helper copies in 36 specs; 42 `check()` copies |
| [STD-47](#std-47) | Tests are deterministic and isolated | ESLint spec selectors; `subprocess_timeouts` check | Partly | 30 sleeps or `networkidle`; 24 untimed child processes |
| [STD-48](#std-48) | Repository-level Python is linted, formatted, typed and import-checked | `repo_ruff_check`; mypy; import-contract check | Partly | 133 files ungated; 474 lint hits; 56 mypy errors in the 6 trust-boundary modules |
| [STD-49](#std-49) | Gates keep their settings and run without being asked | `gate_settings` check; opt-in pre-commit hook | Partly | settings unguarded; no trigger |
| [STD-50](#std-50) | Scripts share one runner, stack lifecycle, paid guard and report writer | `copies` check | Partly | 29 replay copies; 15 stack copies; 4 paid guards |
| [STD-51](#std-51) | Report, then baseline, then error; never loosen | suppression files; RUF100; fault fixtures | Partly | not applicable |

### Dimension coverage

| Dimension | Standards |
|---|---|
| standards | STD-25, STD-27, STD-28, STD-48, STD-49, STD-51 |
| modules | STD-01, STD-02, STD-03, STD-36, STD-37 |
| size | STD-05, STD-06, STD-07 |
| functions | STD-08, STD-09, STD-33 |
| structure | STD-04, STD-29, STD-43 |
| approach | STD-16, STD-31, STD-32, STD-38, STD-39 |
| comments | STD-23, STD-24, STD-25, STD-26, STD-40 |
| types | STD-10 to STD-18, STD-48 |
| errors | STD-19 to STD-22, STD-50 |
| tests | STD-18, STD-33, STD-43 to STD-47 |
| duplication | STD-03, STD-12, STD-14, STD-17, STD-34, STD-42, STD-46, STD-50 |
| naming | STD-29, STD-30, STD-40 |

### How to read a standard

- **Rule.** MUST is a gate once adopted. SHOULD is a review expectation with a tracked count.
- **Why here.** The concrete cost in this repository, with linked findings.
- **Today.** Counts, with what a check would flag at its starting threshold.
- **Enforce.** The configuration fragment or check. The full files, validated together, are under [Target configuration](#target-configuration). Checks named in `code` style live in the convention module described in [STD-51](#std-51) unless a path is given.
- **Adopt.** Every proposed check follows [STD-51](#std-51): report, then a baseline that only shrinks, then error. Thresholds start at today's level and tighten as baselines empty. Nothing here loosens an existing gate ([DH-04](../../PRD/PRD-Development-Harness.md#dh-04-skills-and-specialist-agents)).

Out of scope for every size and style rule: the generated `packages/api-client/src/generated.ts`, `packages/db-types/src/generated.ts` and `contracts/generated/`, the vendored `infra/supabase/upstream/`, `openspec/`, `docs/`, `research/`, the PRDs and `SPECS.md`. Rules judge how generated code is consumed. No standard needs a new dependency, and none sets a coverage quota ([DH-09](../../PRD/PRD-Development-Harness.md#dh-09-verification-profiles-and-completion-rules)).

## 1. Repository structure and modules

### <a id="std-01"></a>STD-01. Service layers import inward only

- **Rule (MUST).** In `services/agent/src/autobots`, `domain` imports only the standard library and itself. `persistence` may add `domain`; `contracts` may add pydantic, `domain` and `persistence`; `application` may add `contracts`; `adapters` may add `application`, whose ports they implement; `api` may add `adapters`; `operations` may import every layer except `api`. No module imports another module's private (`_name`) member, and a function-level import that breaks a cycle carries a reason ([STD-25](#std-25)).
- **Why here.** goal_loop builds the tool registry, so building the API or the OpenAPI document imports the agent runtime [XMOD-01](findings/sweep-boundaries.md#xmod-01). workflow_runner runs on goal_loop's private lifecycle, and the two import each other [PPRD-02](findings/py-product.md#pprd-02), [XMOD-07](findings/sweep-boundaries.md#xmod-07). Five cycles hide behind function-level imports, and nothing reports them [XMOD-09](findings/sweep-boundaries.md#xmod-09), [XTOL-07](findings/sweep-tooling.md#xtol-07).
- **Today.** domain holds the rule with 0 exceptions. contracts has 1: `contracts/export.py` imports `autobots.api` [PDOM-14](findings/py-domain.md#pdom-14), [XMOD-10](findings/sweep-boundaries.md#xmod-10). Outside the matrix there are 33 import statements: application to adapters 21, application to operations 6, adapters to operations 2, api to operations 2, contracts to api 1 and operations to api 1. There are 40 imports of private names: 6 in src, 16 in services/agent/tests and 18 in tests/db. Function-level imports number 31 in src and 47 in services/agent/tests [PTST-20](findings/py-tests.md#ptst-20). Related: [POPS-03](findings/py-ops.md#pops-03), [PTOL-08](findings/py-tools.md#ptol-08), [PADP-09](findings/py-adapters.md#padp-09), [PPRD-15](findings/py-product.md#pprd-15), [PTOL-07](findings/py-tools.md#ptol-07), [XMOD-12](findings/sweep-boundaries.md#xmod-12).
- **Enforce.** A nested ruff configuration per inner layer, which flags module, submodule and function-level imports alike (validated on a scratch tree), and a stdlib check for the matrix:

  ```toml
  # services/agent/src/autobots/domain/ruff.toml (0 hits today)
  extend = "../../../pyproject.toml"

  [lint.flake8-tidy-imports.extend-banned-api]
  "autobots.api".msg = "domain/ stays independent of the other layers (DH-06)."
  "autobots.application".msg = "domain/ stays independent of the other layers (DH-06)."
  "autobots.adapters".msg = "domain/ stays independent of the other layers (DH-06)."
  "autobots.operations".msg = "domain/ stays independent of the other layers (DH-06)."
  "fastapi".msg = "domain/ is framework-free (DH-06)."
  "psycopg".msg = "domain/ is framework-free (DH-06)."
  "langgraph".msg = "domain/ is framework-free (DH-06)."
  "pydantic".msg = "DTOs live in contracts/ (python-worker.md)."
  "os.environ".msg = "Entry points read configuration and pass it in (STD-38)."
  ```

  ```python
  # tests/harness/test_conventions.py, check layer_imports (stdlib ast, function-level imports included)
  ALLOWED = {
      "domain": set(), "persistence": {"domain"}, "contracts": {"domain", "persistence"},
      "application": {"domain", "persistence", "contracts"},
      "adapters": {"domain", "persistence", "contracts", "application"},
      "api": {"domain", "persistence", "contracts", "application", "adapters"},
      "operations": {"domain", "persistence", "contracts", "application", "adapters"},
  }
  BASELINE = {("application", "adapters"): 21, ("application", "operations"): 6, ("adapters", "operations"): 2,
              ("api", "operations"): 2, ("contracts", "api"): 1, ("operations", "api"): 1}
  PRIVATE_IMPORTS = {"services/agent/src": 6, "services/agent/tests": 16, "tests/db": 18}
  ```
  `contracts/ruff.toml` bans `autobots.api`, `autobots.application`, `autobots.adapters`, `autobots.operations`, `fastapi` and `psycopg` the same way (1 hit today; see [Target configuration](#target-configuration)).
- **Adopt.** The domain configuration starts as an error. Move `contracts/export.py` into `api/` ([PDOM-14](findings/py-domain.md#pdom-14)), then add the contracts configuration as an error. The direction between application and adapters is not settled by DH-03 or DH-06, so record it in a short decision before the matrix check bans either way [XTOL-07](findings/sweep-tooling.md#xtol-07). The matrix above encodes the direction [XMOD-01](findings/sweep-boundaries.md#xmod-01) recommends. Fix first: the registry composition (refactor plan: tool registry at the edge), which removes goal_loop's 11 adapter imports [XMOD-01](findings/sweep-boundaries.md#xmod-01), and the move of `operations/logs.py` to a leaf module, which removes 7 of the 8 imports from application and adapters into operations [XMOD-12](findings/sweep-boundaries.md#xmod-12).

### <a id="std-02"></a>STD-02. Web modules import in one direction, without cycles

- **Rule (MUST).** `components/ui` imports no feature component and no route. `lib/` imports no component and no route. Components never import `app/`. No import cycles. Server-only modules start with `import "server-only"`, and only server code imports them.
- **Why here.** run-list and run-panel import each other, so shared run status has no home [XTOL-07](findings/sweep-tooling.md#xtol-07), [WRUN-09](findings/web-run.md#wrun-09). 24 import edges run sideways between feature components, and 7 of them carry helpers, constants or a hook rather than a component [XWEB-10](findings/sweep-web-architecture.md#xweb-10), [WTAP-07](findings/web-tools-approvals.md#wtap-07), [WCMP-13](findings/web-composer.md#wcmp-13).
- **Today.** The zones report 0 hits (an inverted zone reports 59, which proves the `@/` alias resolves). `import/no-cycle` reports 2 hits, at `components/run-list.tsx:8` and `components/run-panel.tsx:9`. The server-only boundary holds: five lib modules import `server-only`, none of the 39 client modules imports them, and `next build` fails if one does. That part is **enforced**.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: SOURCE
  "import/no-cycle": ["error", { maxDepth: 10 }],
  "import/no-restricted-paths": ["error", { zones: [
    { target: "./components/ui/**/*", from: ["./components/*.tsx", "./app/**/*"], message: "UI primitives stay feature-free." },
    { target: "./lib/**/*", from: ["./components/**/*", "./app/**/*"], message: "lib/ never imports UI or routes." },
    { target: "./components/**/*", from: ["./app/**/*"], message: "Screens never import route modules." },
  ] }],
  ```
- **Adopt.** Zones start as errors. Break the cycle by moving `StateLine` and `STATUS_TEXT` into a lib run-status module, then turn `import/no-cycle` on as an error with no baseline. Component exports are covered by [STD-33](#std-33). Every route handler that reaches the API keeps going through `lib/bff.ts`; the three alias routes that duplicate the `/api/v1` catch-all go [XMOD-16](findings/sweep-boundaries.md#xmod-16), [WSHL-16](findings/web-shell.md#wshl-16).

### <a id="std-03"></a>STD-03. A rule that guards money, secrets or state has one implementation

- **Rule (MUST).** Admission, readiness, approval transitions, paid-call reservation and settlement, run command guards, secret patterns and workflow IR rules each have one implementation, owned by the Python layer that DH-06 assigns. Another layer reads the result through the API, for example a projected `available_commands`, instead of re-deriving it. An unavoidable copy, such as `scripts/evidence.py`, which runs under the system interpreter, keeps a parity test that fails when the copies differ.
- **Why here.** The copies have already drifted. Public-text redaction misses the Tavily, Jina and GitHub token families that log redaction has [XDUP-01](findings/sweep-duplication.md#xdup-01), [PRUN-05](findings/py-run.md#prun-05). Only one of three admission paths is protected against duplicate paid runs [XDUP-03](findings/sweep-duplication.md#xdup-03). Routine admission skips the schema check [POPS-02](findings/py-ops.md#pops-02). Paid-run guards disagree across four entry points [SCRP-03](findings/scripts.md#scrp-03). The adapter's approval reset uses a hard-coded day [XDUP-02](findings/sweep-duplication.md#xdup-02).
- **Today.** Parity tests already pin the tool tables: `test_execution_contract.py`, `test_tool_catalog.py` and `test_tool_guides.py` (sweep-boundaries strengths). Copies without one: 3 secret patterns, 3 admission paths, 2 readiness gates, 7 approval-transition sites, 4 paid guards, 5 paid-call reservations [POPS-06](findings/py-ops.md#pops-06), 4 approval-rule sites [PTOL-04](findings/py-tools.md#ptol-04), 4 key-precedence resolvers [PTOL-12](findings/py-tools.md#ptol-12), web copies of the command table [XMOD-06](findings/sweep-boundaries.md#xmod-06), [WRUN-12](findings/web-run.md#wrun-12) and of the WF-06 IR rules [WBLD-06](findings/web-build.md#wbld-06), and two routine configuration definitions whose trigger, budget and timezone rules differ [PDOM-02](findings/py-domain.md#pdom-02). The proxy's copy of the public-address check has no parity test with the URL guard's [PADP-20](findings/py-adapters.md#padp-20).
- **Enforce.** A parity test per remaining copy, in the existing style; for example `tests/harness/test_secret_patterns.py` asserts that the families in `scripts/evidence.py` equal those of the shared service module. The review checklist in `.claude/skills/autobots-review-change/SKILL.md` gains one line: "Does this change copy a rule that guards money, secrets or state? If so, where is its parity test?"
- **Adopt.** Review line now. Merge the copies in the order of risk: secret patterns and paid guards first, because they guard secrets and spend. When merging, keep the strictest of the drifted behaviors, so no guard is weakened, and delete the superseded copy rather than leave it beside the new one [PADP-21](findings/py-adapters.md#padp-21), [WSHL-21](findings/web-shell.md#wshl-21). As a SHOULD, the same applies to every other copied rule or vocabulary the findings list: [PADP-04](findings/py-adapters.md#padp-04), [PAPI-16](findings/py-api.md#papi-16), [PAPI-21](findings/py-api.md#papi-21), [PDOM-12](findings/py-domain.md#pdom-12), [PDOM-17](findings/py-domain.md#pdom-17), [POPS-13](findings/py-ops.md#pops-13), [PPRD-07](findings/py-product.md#pprd-07), [PPRD-08](findings/py-product.md#pprd-08), [PPRD-09](findings/py-product.md#pprd-09), [PPRD-10](findings/py-product.md#pprd-10), [PPRD-18](findings/py-product.md#pprd-18), [PRUN-09](findings/py-run.md#prun-09), [PTOL-11](findings/py-tools.md#ptol-11), [PTOL-19](findings/py-tools.md#ptol-19), [WRUN-11](findings/web-run.md#wrun-11), [WSYS-18](findings/web-system.md#wsys-18), [WSHL-05](findings/web-shell.md#wshl-05), [XDUP-12](findings/sweep-duplication.md#xdup-12), and the browser preferences written twice [WSHL-11](findings/web-shell.md#wshl-11), [WSYS-11](findings/web-system.md#wsys-11), [XDUP-19](findings/sweep-duplication.md#xdup-19), [XWEB-18](findings/sweep-web-architecture.md#xweb-18).

### <a id="std-04"></a>STD-04. The layout follows DH-03 or a recorded amendment, and rule scopes match real files

- **Rule (MUST).** Every `paths` glob in `.claude/rules/*.md` matches at least one tracked file, and the harness test checks real files rather than invented ones. Where the code and DH-03 disagree, either the code moves or DH-03 is amended by a recorded user decision.
- **Why here.** Five globs match nothing, so the model-gateway and database rules miss the code they govern, while the harness test passes on invented paths [XMOD-04](findings/sweep-boundaries.md#xmod-04), [PADP-10](findings/py-adapters.md#padp-10). The service has no `graphs/` or `workers/` and adds `operations/` and `persistence/`; scripts/ has no `scripts/db/` [XMOD-13](findings/sweep-boundaries.md#xmod-13), [SCRP-15](findings/scripts.md#scrp-15). Tool code has no single home [PTOL-21](findings/py-tools.md#ptol-21), [PPRD-19](findings/py-product.md#pprd-19). tests/db mixes six kinds of file under suffixes that don't say which [TDBC-09](findings/db-tests.md#tdbc-09), and an install helper that handles the real OpenRouter key lives there [TDBC-11](findings/db-tests.md#tdbc-11). Instruction-file checks sit in a test module beside a second frontmatter parser [THRN-05](findings/harness-tests.md#thrn-05).
- **Today.** 5 dead globs: `adapters/persistence/**` (database.md), `graphs/**` and `apps/web/src/app/api/settings/**` (model-gateway.md), `scripts/operations/**` and `**/Dockerfile*` (infrastructure.md). 5 layout differences.
- **Enforce.** Check `rule_scopes`: parse the frontmatter, match each glob against `git ls-files`, fail on an empty match unless the glob is on an explicit forward-looking allowlist (empty today), and require at least one real representative file per rule ([DH-03](../../PRD/PRD-Development-Harness.md#dh-03-required-repository-structure): "test representative paths").
- **Adopt.** Fix the five globs and the matching "Relevant paths" lines in the two skills in the same change, then make the check an error. The DH-03 amendment is the user's decision.

## 2. File size

### <a id="std-05"></a>STD-05. Modules stay within length budgets

- **Rule (MUST not grow; SHOULD stay under).** Python service modules stay at 500 lines or less as formatted by `ruff format`. Python test modules stay at 600 lines or less. TypeScript files in `app`, `components`, `lib` and `hooks`, and browser specs, stay at 400 lines or less, counted without blank and comment lines. A module over its budget may only shrink until it is under.
- **Why here.** Every run story edits `run-workspace.tsx` [WRUN-01](findings/web-run.md#wrun-01). goal_loop is a seven-concern hub [PRUN-01](findings/py-run.md#prun-01). route_qualification doubles as the paid trials' library [POPS-05](findings/py-ops.md#pops-05). A 1,149-line test module spans six production modules [PTST-04](findings/py-tests.md#ptst-04). Also [WTAP-01](findings/web-tools-approvals.md#wtap-01), [WTAP-08](findings/web-tools-approvals.md#wtap-08), [WBLD-11](findings/web-build.md#wbld-11), [PRUN-16](findings/py-run.md#prun-16), [POPS-04](findings/py-ops.md#pops-04), [PADP-14](findings/py-adapters.md#padp-14), [PPRD-04](findings/py-product.md#pprd-04), [PDOM-11](findings/py-domain.md#pdom-11), [PAPI-12](findings/py-api.md#papi-12), [THRN-03](findings/harness-tests.md#thrn-03), [THRN-04](findings/harness-tests.md#thrn-04), [TWEB-03](findings/web-tests.md#tweb-03), [SCRP-02](findings/scripts.md#scrp-02), and at function scale [PTST-15](findings/py-tests.md#ptst-15), [PTST-16](findings/py-tests.md#ptst-16), [WSYS-14](findings/web-system.md#wsys-14).
- **Today.** From [metrics.md section 2](metrics.md#2-size) and the review's line counts: 8 of 139 service modules exceed 500 lines (goal_loop 782, route_qualification 732, loop_middleware 674, run_projection 664, tool_gateway 594, workflows 550, runs 502 and operations 501). 3 Python test modules exceed 600 (test_worker_inference 1,149, test_assistant_assets 783, test_hooks 703). ESLint `max-lines` at 400 flags 10 source files and 6 specs; at 300 it flags 13 and 9.
- **Enforce.** ESLint `max-lines` for TypeScript, and check `module_lines` for Python, because ruff has no file-length rule:

  ```js
  // apps/web/eslint.config.mjs, files: [...SOURCE, ...SPECS]
  "max-lines": ["error", { max: 400, skipBlankLines: true, skipComments: true }],
  ```

  ```python
  # tests/harness/test_conventions.py, check module_lines
  LIMITS = {"services/agent/src/": 500, "services/agent/tests/": 600, "tests/": 600}
  BASELINE = {"services/agent/src/autobots/application/goal_loop.py": 782}  # and 10 more; each may only fall
  ```
- **Adopt.** Baseline the 10 and 6 ESLint hits and the 11 Python modules now. Scripts get no line budget until their one-time reformat ([STD-27](#std-27)), because formatting grows them from 25,788 to about 47,666 lines [XTOL-04](findings/sweep-tooling.md#xtol-04); calibrate then, and prefer the statement and complexity limits of [STD-06](#std-06). Tighten web files to 300 when the 400 baseline is empty. Split first: run-workspace, goal_loop and tool-catalog (refactor plan: hotspot splits).

## 3. Function size and complexity

### <a id="std-06"></a>STD-06. Python complexity, branches, returns and statements stay within limits

- **Rule (MUST).** Cyclomatic complexity 15 or less, 15 branches, 8 returns and 60 statements per function, tightening to complexity 10, 12 branches, 6 returns and 50 statements, which are the thresholds [metrics.md section 4](metrics.md#4-python-complexity-and-parameters) measured.
- **Why here.** `github_pull_request_tool` has complexity 37 and 92 statements, and `_dispatch` holds every guardrail in one 87-line function [PTOL-02](findings/py-tools.md#ptol-02), [PADP-03](findings/py-adapters.md#padp-03). The size of these functions hides helpers from tests and reviewers. Also [PDOM-10](findings/py-domain.md#pdom-10), [PDOM-15](findings/py-domain.md#pdom-15), [PPRD-05](findings/py-product.md#pprd-05), [PPRD-06](findings/py-product.md#pprd-06), [PAPI-02](findings/py-api.md#papi-02), [PAPI-13](findings/py-api.md#papi-13), [POPS-08](findings/py-ops.md#pops-08), [POPS-20](findings/py-ops.md#pops-20), [PRUN-19](findings/py-run.md#prun-19), [SCRP-05](findings/scripts.md#scrp-05), [TDBC-06](findings/db-tests.md#tdbc-06).
- **Today.** No limit is configured [XTOL-05](findings/sweep-tooling.md#xtol-05). At the starting thresholds, services/agent src and tests give C901 5, PLR0911 6, PLR0912 2 and PLR0915 3 (16 hits). C901 gives 17 at 12 and 26 at 10. Repository-level Python, once gated ([STD-48](#std-48)), gives C901 26, PLR0915 52 (34 of them tests/db check mains) and PLR0912 16. Python functions over 80 lines: 24 in src, 17 in scripts, 35 in tests/db ([metrics.md section 3](metrics.md#3-python-functions-and-documentation)).
- **Enforce.**

  ```toml
  # services/agent/pyproject.toml
  [tool.ruff.lint]
  extend-select = ["C90", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917", "PLC0415"]

  [tool.ruff.lint.mccabe]
  max-complexity = 15       # 5 today; then 12 (17), then 10 (26)

  [tool.ruff.lint.pylint]
  max-branches = 15         # 2 today; then 12 (6)
  max-returns = 8           # 6 today; then 6 (11)
  max-statements = 60       # 3 today; then 50 (5)
  ```
- **Adopt.** Run `ruff check --add-noqa="- baseline 2026-11-12 (STD-06)"` once in services/agent; RUF100, already selected, then fails on any marker that is no longer needed, so the baseline only shrinks. Fix first: `_dispatch`, `github_pull_request_tool`, `validate_graph` and `run_goal`. Python function length has no ruff rule, so statements stand in for lines.

### <a id="std-07"></a>STD-07. TypeScript complexity, nesting and function length stay within limits

- **Rule (MUST).** Complexity 15 or less, nesting depth 4 and 150 non-blank, non-comment lines per function, tightening to complexity 10 and 60 lines, the thresholds [metrics.md section 7](metrics.md#7-typescript-and-react) measured.
- **Why here.** The ten longest functions are whole route screens of 260 to 677 lines that own data, stream protocol and markup together [XWEB-05](findings/sweep-web-architecture.md#xweb-05), [WRUN-01](findings/web-run.md#wrun-01), [WBLD-01](findings/web-build.md#wbld-01), [WCMP-03](findings/web-composer.md#wcmp-03). Also [WRUN-05](findings/web-run.md#wrun-05), [WCMP-09](findings/web-composer.md#wcmp-09), [WCMP-10](findings/web-composer.md#wcmp-10), [WBLD-10](findings/web-build.md#wbld-10), [WBLD-12](findings/web-build.md#wbld-12), [WSYS-05](findings/web-system.md#wsys-05), [WSYS-06](findings/web-system.md#wsys-06), [WSYS-07](findings/web-system.md#wsys-07), [WTAP-08](findings/web-tools-approvals.md#wtap-08), [WSHL-18](findings/web-shell.md#wshl-18), [TWEB-12](findings/web-tests.md#tweb-12).
- **Today.** Source code: complexity over 15 in 11 functions (20 over 12, 30 over 10); length over 150 in 24 (32 over 100, 49 over 60); depth over 4 in none. Specs: 1 over complexity 15 and 2 over 150 lines.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: [...SOURCE, ...SPECS]
  complexity: ["error", 15],
  "max-depth": ["error", 4],
  "max-lines-per-function": ["error", { max: 150, skipBlankLines: true, skipComments: true }],
  ```
- **Adopt.** `max-depth` starts as an error with no baseline. Baseline the other two with `eslint --suppress-rule` ([STD-51](#std-51)). Tighten to 12 and 100, then 10 and 60, as baselines empty. The extraction of shared hooks ([STD-32](#std-32)) removes most of the length, so split screens after the hooks exist.

## 4. Function design

### <a id="std-08"></a>STD-08. Functions take few parameters

- **Rule (MUST).** At most 8 parameters and 6 positional ones in Python, tightening to 5 and 5. Parameters past the first few are keyword-only. A function that needs more takes a frozen dataclass or a Protocol. TypeScript functions take at most 4 parameters, and components take props.
- **Why here.** `admit_run` takes 15 parameters and a binding typed `Any` that four different shapes satisfy [PRUN-04](findings/py-run.md#prun-04). `approval_gate` takes 18, three of them optional although Decision 0015 requires them [PTOL-05](findings/py-tools.md#ptol-05). Long positional lists invite swapped arguments [PRUN-18](findings/py-run.md#prun-18), [TWEB-19](findings/web-tests.md#tweb-19).
- **Today.** PLR0913 at 8 arguments: 8 hits; PLR0917 at 6 positional: 17 hits (62 and 38 at 5, [metrics.md section 4](metrics.md#4-python-complexity-and-parameters)). ESLint `max-params` at 4: 0 in source and 1 in specs.
- **Enforce.**

  ```toml
  # services/agent/pyproject.toml
  [tool.ruff.lint.pylint]
  max-args = 8              # 8 today; then 5 (62)
  max-positional-args = 6   # 17 today; then 5 (38)
  ```

  ```js
  // apps/web/eslint.config.mjs, files: [...SOURCE, ...SPECS]
  "max-params": ["error", 4],
  ```
- **Adopt.** Same baseline as STD-06. Fix first: `admit_run` and `approval_gate`, whose parameter objects also close [PPRD-01](findings/py-product.md#pprd-01).

### <a id="std-09"></a>STD-09. Decisions are pure and unit-tested; reads never write; factories only wire

- **Rule (SHOULD; MUST for run, approval, budget and settlement decisions).** A decision is a pure function over typed inputs with a unit test, and its transaction or I/O wrapper calls it. A read path never inserts or updates. A factory, such as a tool factory, only wires: its helpers live at module level, where tests and size metrics see them.
- **Why here.** `_finish` mixes the stop decision with cancellation settlement and raw job writes [PRUN-03](findings/py-run.md#prun-03). `apply_command` packs replay, ownership, guard and cascade into one transaction [PRUN-06](findings/py-run.md#prun-06). `post_run` packs nine admission concerns into one handler [PAPI-02](findings/py-api.md#papi-02). Decision logic sitting inside database functions has little fast coverage [PPRD-16](findings/py-product.md#pprd-16), [PRUN-17](findings/py-run.md#prun-17), and the most complex connector has no fast unit test [PADP-18](findings/py-adapters.md#padp-18). Reading settings inserts rows [POPS-12](findings/py-ops.md#pops-12), [PTOL-18](findings/py-tools.md#ptol-18). Each tool module is one factory closure of 68 to 226 lines [PADP-03](findings/py-adapters.md#padp-03), [PRUN-19](findings/py-run.md#prun-19), [PPRD-05](findings/py-product.md#pprd-05). Also [PADP-08](findings/py-adapters.md#padp-08), [PTOL-14](findings/py-tools.md#ptol-14), [SCRP-11](findings/scripts.md#scrp-11), [SCRP-20](findings/scripts.md#scrp-20), [PAPI-18](findings/py-api.md#papi-18), [PPRD-21](findings/py-product.md#pprd-21), [WSHL-15](findings/web-shell.md#wshl-15), [WSHL-19](findings/web-shell.md#wshl-19), [WSYS-13](findings/web-system.md#wsys-13).
- **Today.** No tool measures purity. The limits in [STD-06](#std-06) count a factory's closures into the factory, which is why `github_pull_request_tool` measures complexity 37; the tighter steps reach the other factories.
- **Enforce.** Review, through one line in the `autobots-review-change` checklist: "Is each new decision a pure function with a unit test, and does any read path write?" The size limits catch closure-heavy factories.
- **Adopt.** Review line now. Extract decisions when their module is next touched, tests first where risk is medium or higher (refactor plan: run lifecycle and paid-path seams).

## 5. Types and contracts

### <a id="std-10"></a>STD-10. API replies are parsed, never asserted

- **Rule (MUST).** Browser code reads every API reply, stream frame and error body through a generated `parse*` function, or through one lib helper built on `parseErrorResponse`. No type assertion over `.json()` or `JSON.parse(...)`.
- **Why here.** A renamed field or code reaches the screen as `undefined` instead of failing as a contract error ([DH-06](../../PRD/PRD-Development-Harness.md#nextjs-and-typescript): "No blanket type assertions to conceal contract mismatches") [XTOL-06](findings/sweep-tooling.md#xtol-06), [XTYP-01](findings/sweep-types.md#xtyp-01), [XWEB-01](findings/sweep-web-architecture.md#xweb-01). Error bodies are cast at 19 sites, with two competing wording policies [XERR-09](findings/sweep-errors.md#xerr-09), [XDUP-07](findings/sweep-duplication.md#xdup-07). Stream frames are a contract nothing declares [XTYP-07](findings/sweep-types.md#xtyp-07). Also [WBLD-03](findings/web-build.md#wbld-03), [WRUN-06](findings/web-run.md#wrun-06), [WCMP-02](findings/web-composer.md#wcmp-02), [WTAP-18](findings/web-tools-approvals.md#wtap-18), [WSHL-06](findings/web-shell.md#wshl-06), and the URL parameters, role bindings and block versions narrowed without a check [WBLD-20](findings/web-build.md#wbld-20).
- **Today.** 30 assertions on JSON in 17 files (28 over `.json()`, 2 over `JSON.parse`), while 25 component files already use generated parsers at 60 sites. The web has 0 explicit `any`, 0 `@ts-ignore` and 0 `eslint-disable`, and `@typescript-eslint/no-explicit-any` and `ban-ts-comment` are **enforced** errors through the Next presets.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: SOURCE
  { selector: "TSAsExpression:has(CallExpression[callee.property.name='json'])", message: PARSED },
  { selector: "TSAsExpression > CallExpression[callee.object.name='JSON'][callee.property.name='parse']", message: PARSED },
  ```
- **Adopt.** Error with the 30 sites baselined. Fix first: the 19 error-body casts through one `readRefusal(reply)` helper, then the 7 success casts with `parseRunAccepted` and `parseSessionView`. The deep clone at `workflow-editor.tsx:81` and the BFF's own `/api/csrf` read have no generated parser and are fixed in place. Browser specs follow later ([XTYP-18](findings/sweep-types.md#xtyp-18), [TWEB-04](findings/web-tests.md#tweb-04)).

### <a id="std-11"></a>STD-11. Request bodies use the generated request types

- **Rule (MUST).** A request body is a value of its generated request type, written `({ ... }) satisfies RunRequest` or through the generated operation. Browser calls move to the generated client once its runtime carries the status and the parsed `ErrorResponse`.
- **Why here.** The generated contract checks only responses: 28 request bodies and 78 path literals are hand-written, and 4 of 78 generated operations are used, all server-side [XMOD-03](findings/sweep-boundaries.md#xmod-03), [XTYP-01](findings/sweep-types.md#xtyp-01). The runtime turns every non-2xx reply into a `ContractError` and drops the typed error, which is why screens bypass it [XDUP-06](findings/sweep-duplication.md#xdup-06), [WSHL-03](findings/web-shell.md#wshl-03). Paths are built by hand, with inconsistent encoding [WRUN-19](findings/web-run.md#wrun-19).
- **Today.** 24 object-literal bodies in 16 files; 0 references to a generated request type.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: SOURCE
  { selector: "Property[key.name='body'] > CallExpression[callee.object.name='JSON'][callee.property.name='stringify'] > ObjectExpression", message: TYPED },
  ```
  `satisfies` wraps the literal, so a typed body no longer matches.
- **Adopt.** Error with the 24 sites baselined, starting with the three run-admission and four session-creation bodies. Then change the hand-written `runtime.ts` and the generator, and regenerate; `generated.ts` is never edited by hand.

### <a id="std-12"></a>STD-12. Vocabulary maps are keyed by generated unions, and switches are exhaustive

- **Rule (MUST).** A map keyed by a contract vocabulary is typed by the generated union, written `satisfies Record<RunStatus, string>`, so that a new state fails `tsc`. Shared vocabularies live in lib/. A `switch` over a union handles every member. Display words stay in UI modules; only their keys come from the contract (contracts.md keeps DTO and UI types apart).
- **Why here.** 28 string-keyed maps restate run status, profile, provider and outcome, and no web file imports `RunStatus`, `ModelProfileId`, `BindingSource` or `ModelRole` [XTYP-06](findings/sweep-types.md#xtyp-06). Contract unions widened to `string` render blank on a new value [WRUN-07](findings/web-run.md#wrun-07). One client key already matches nothing the service emits [XERR-08](findings/sweep-errors.md#xerr-08). Also [WCMP-14](findings/web-composer.md#wcmp-14), [WTAP-06](findings/web-tools-approvals.md#wtap-06), [WSYS-09](findings/web-system.md#wsys-09), [XWEB-08](findings/sweep-web-architecture.md#xweb-08), [WRUN-08](findings/web-run.md#wrun-08), [WBLD-07](findings/web-build.md#wbld-07), [WBLD-13](findings/web-build.md#wbld-13), and the harness tests' hand-typed run states [THRN-13](findings/harness-tests.md#thrn-13).
- **Today.** 28 `Record<string, ...>` maps in 12 component files. Type-aware rules: `switch-exhaustiveness-check`, `no-floating-promises` and `no-misused-promises` report 0 in source; `no-unnecessary-type-assertion` reports 13 (3 in `home-activity.tsx`, 10 in specs). Strict TypeScript with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` is **enforced** ([apps/web/tsconfig.json:7-9](../../../apps/web/tsconfig.json#L7)).
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: [...SOURCE, ...TESTS]
  languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
  rules: {
    "@typescript-eslint/no-floating-promises": "error",
    "@typescript-eslint/no-misused-promises": "error",
    "@typescript-eslint/switch-exhaustiveness-check": "error",
    "@typescript-eslint/no-unnecessary-type-assertion": "error",
  },
  // components (not ui): string-keyed label maps
  { selector: "VariableDeclarator > Identifier > TSTypeAnnotation > TSTypeReference[typeName.name='Record'] > TSTypeParameterInstantiation > TSStringKeyword:first-child", message: "Key label maps by the generated union (STD-12)." },
  ```
- **Adopt.** The three zero-hit type-aware rules start as errors, with `no-floating-promises` off for `tests/unit`, where node:test's calls return promises (7 hits). Fix the 13 unnecessary assertions (6 have an autofix). The map selector joins once lib holds the run-status and profile modules, with its 28 hits baselined. Contract fields that are `str` in Python change first ([STD-14](#std-14)).

### <a id="std-13"></a>STD-13. SQL, provider and framework boundaries are typed; `Any` needs a reason

- **Rule (MUST).** No `Any` in a signature unless a comment names the library gap it bridges. Database access goes through one narrow `SqlConnection` Protocol; multi-column reads go through TypedDict rows in `persistence/` and explicit mappers, as `contracts/adapters.py` maps `RunRow`. Provider replies are validated into small reply models next to their adapter. LangChain hooks use the library's own `ModelRequest`, `ModelResponse` and `ModelCallResult`. An open dictionary whose shape is closed, such as a routine trigger or a workflow node's config, is parsed once into a typed domain value [XTYP-08](findings/sweep-types.md#xtyp-08). Narrowing uses a precise type, not `assert`, `cast` or `getattr` [PTOL-16](findings/py-tools.md#ptol-16).
- **Why here.** Positional rows and `Any` connections make every schema change silent: `tasks_complete` is `row[10]` and `tasks_total` is `row[9]` [XTYP-04](findings/sweep-types.md#xtyp-04). Malformed provider replies fail with different codes or crash consumers [PADP-07](findings/py-adapters.md#padp-07), [XTYP-09](findings/sweep-types.md#xtyp-09). The paid path's model hooks are typed `Any` [XTYP-11](findings/sweep-types.md#xtyp-11), [PADP-16](findings/py-adapters.md#padp-16). Also [PPRD-12](findings/py-product.md#pprd-12), [PRUN-12](findings/py-run.md#prun-12), [PTOL-13](findings/py-tools.md#ptol-13), [POPS-17](findings/py-ops.md#pops-17), [PAPI-08](findings/py-api.md#papi-08), [PAPI-14](findings/py-api.md#papi-14), [PDOM-08](findings/py-domain.md#pdom-08), [PPRD-01](findings/py-product.md#pprd-01), [POPS-16](findings/py-ops.md#pops-16).
- **Today.** ANN401 reports 398 hits in src: application 271, adapters 67, operations 39, api 16 and domain 5; 221 are on `connection` parameters, from 225 `connection: Any` annotations in 42 files. 178 positional row reads in 41 files and one TypedDict row type. Tests add 173 ANN401 hits. mypy strict over src and tests is **enforced** ([services/agent/pyproject.toml:49-53](../../../services/agent/pyproject.toml#L49)).
- **Enforce.**

  ```toml
  # services/agent/pyproject.toml, stage 2
  [tool.ruff.lint]
  extend-select = ["ANN401"]   # with STD-06's list

  [tool.ruff.lint.extend-per-file-ignores]   # extend, so the root's table survives
  "src/autobots/{application,adapters,operations}/**" = ["ANN401"]   # 377 sites, until SqlConnection lands
  "tests/**" = ["ANN401"]
  ```
- **Adopt.** Fix the 21 sites in api and domain and gate them. Add `SqlConnection` and replace the 225 `connection: Any` mechanically, then replace the per-directory ignores with `--add-noqa` markers for what remains, so new `Any` fails everywhere. Row, domain and DTO types stay separate; only the mapping becomes explicit.

### <a id="std-14"></a>STD-14. State and code vocabularies are enums or Literals with one source

- **Rule (MUST).** A status, outcome, stop code or refusal code is a StrEnum or a Literal alias, never a bare `str` bridged by `type: ignore[arg-type]` or `cast`. A contract Literal that mirrors a domain enum either reuses it or has a parity test. Status sets reach SQL as parameters derived from the enum (`status <> all(%s)`), as `model_admission` already does with `OUTSTANDING`. Allowlists and transition tables are frozen (`frozenset`, `MappingProxyType`), as `domain/models.py` already does [PDOM-20](findings/py-domain.md#pdom-20).
- **Why here.** Stop codes are bare strings, and a code missing from `PAUSE_FOR` fails a run permanently [PRUN-02](findings/py-run.md#prun-02); three hand-kept stop lists already disagree [PPRD-03](findings/py-product.md#pprd-03). Approval and receipt states are bare strings changed from six modules [PTOL-03](findings/py-tools.md#ptol-03). Also [XTYP-05](findings/sweep-types.md#xtyp-05), [PDOM-04](findings/py-domain.md#pdom-04), [PDOM-06](findings/py-domain.md#pdom-06), [PDOM-09](findings/py-domain.md#pdom-09), [PTOL-09](findings/py-tools.md#ptol-09), [PTOL-15](findings/py-tools.md#ptol-15), [POPS-11](findings/py-ops.md#pops-11), [PRUN-10](findings/py-run.md#prun-10), [PPRD-13](findings/py-product.md#pprd-13), [PPRD-14](findings/py-product.md#pprd-14).
- **Today.** 12 of the 18 `type: ignore` in src bridge a `str` into a Literal or Enum field, and 2 `cast` calls do the same. 23 public state fields are `str`. Nine domain enums are re-declared by hand in 10 places with no parity check. 29 status literals restate canonical or SQL-owned vocabularies.
- **Enforce.** mypy strict already reports a bridge that is no longer needed (`warn_unused_ignores`). Add `services/agent/tests/test_vocabularies.py`: `set(get_args(Alias)) == {member.value for member in Enum}` for each mirrored pair, and a test that every code reaching `_finish` and every `FailureClass`, `AdmissionRefused` and `LimitReached` value has a disposition [PRUN-02](findings/py-run.md#prun-02).
- **Adopt.** Parity tests first; they change no behavior. Map every stop code to its current disposition before changing any ([PRUN-02](findings/py-run.md#prun-02) leaves the unmapped-code decision to the owner). Contract changes regenerate the client.

### <a id="std-15"></a>STD-15. Contract models use named configs, strict request primitives, declared errors and UTC timestamps

- **Rule (MUST).** Every contract model uses one of the configs named in `contracts/primitives.py`. Request bodies are strict, or use strict primitives such as `MicroUsd = Annotated[int, Strict(), Field(ge=0, le=MAX_SAFE_INTEGER)]`. Every operation declares `ErrorResponse` for the statuses it can return, including 422. Every public timestamp is a `UtcTimestamp`.
- **Why here.** The OpenAPI document misdescribes every error response, so the client exports a parser for a body the server never sends [PAPI-03](findings/py-api.md#papi-03). `MicroUsd` accepts strings and floats in 22 of 30 request bodies [PDOM-05](findings/py-domain.md#pdom-05). Timestamps come in three forms and only one is checked for UTC [XTYP-10](findings/sweep-types.md#xtyp-10). The lax config is copied into 18 places [XTYP-16](findings/sweep-types.md#xtyp-16), [XMOD-15](findings/sweep-boundaries.md#xmod-15). Tool input types under-declare their constraints, so the model never sees them [PDOM-07](findings/py-domain.md#pdom-07).
- **Today.** All 247 contract models refuse unknown fields (**enforced** by the models themselves). 8 of 30 request bodies are strict. 78 of 78 operations document 422 as `HTTPValidationError` and none declares `ErrorResponse`. 13 of 17 date-time fields carry the UTC pattern, and 5 public timestamps are `str`. `VIEW` is defined 9 times and written inline 9 more.
- **Enforce.** `services/agent/tests/test_contract_shape.py`, reading `create_app().openapi()` and the contract modules: no `HTTPValidationError` reference; 422 maps to `ErrorResponse`; every `format: date-time` has the UTC pattern; every `BaseModel` in `contracts` uses a named config; request bodies are strict, with today's lax ones listed and only allowed to shrink.
- **Adopt.** Declare a shared `ERROR_RESPONSES` mapping in `create_app`, regenerate, and switch the first assertion on. The strictness baseline starts at 22. The generated files change only by regeneration.

### <a id="std-16"></a>STD-16. Persisted documents have versioned record models apart from DTOs

- **Rule (MUST).** JSON that the service stores and reads back (event payloads, policy snapshots, idempotency receipts, stored Expert and routine configurations) has one record model shared by writer and reader, with an explicit version and a tolerant read of every shape already stored. Request DTOs stay strict and separate; records map to and from them explicitly.
- **Why here.** Stored JSON is read back with the request contracts, so a contract edit becomes an unversioned storage-format change [PDOM-01](findings/py-domain.md#pdom-01). Persisted documents have no schema shared by writer and reader, and `project_event` drops a payload that fails validation without a log line [XTYP-03](findings/sweep-types.md#xtyp-03). The frozen policy snapshot has one writer and eight hand-written readers [XDUP-04](findings/sweep-duplication.md#xdup-04), [PRUN-08](findings/py-run.md#prun-08).
- **Today.** 16 stored reads go through request or tool contracts. 34 document sites are untyped: 12 `append_event` calls, 11 snapshot reads and 11 receipt replays. [contracts.md](../../../.claude/rules/contracts.md) already requires versioned snapshots and envelopes.
- **Enforce.** One read test per record type, with fixtures captured from the current release, asserting that every stored shape still reads. Writers build payloads from their model (`ToolUseStarted(...).model_dump(mode="json")`).
- **Adopt.** Start with ExpertConfig and RoutineConfig, which have the most read sites, then the policy snapshot. Domain, row, DTO, graph and UI types stay distinct.

### <a id="std-17"></a>STD-17. Money stays exact, time stays UTC, and each language formats them once

- **Rule (MUST).** [DH-06](../../PRD/PRD-Development-Harness.md#python-api-domain-and-workers) and [python-worker.md](../../../.claude/rules/python-worker.md) already require integer or decimal money and explicit UTC. This standard adds the checks: one `micro_usd()` conversion (Decimal, ceiling, `None` when unreadable) and one pricing path; no naive datetimes; one web formatter module for money, relative time and durations, with unit tests.
- **Why here.** Paid trials price calls with a second, float-based catalog parser [POPS-01](findings/py-ops.md#pops-01). Reported charges are rounded differently on two paths: 0.0000125 USD gives 12 micro-USD with `round` and 13 with `ceil` [PADP-12](findings/py-adapters.md#padp-12). The web shows `US$1.00`, `US$0.5` and `$0.5` for one run's figures [XWEB-09](findings/sweep-web-architecture.md#xweb-09), [XDUP-17](findings/sweep-duplication.md#xdup-17), [WRUN-10](findings/web-run.md#wrun-10), [WCMP-12](findings/web-composer.md#wcmp-12), [WBLD-14](findings/web-build.md#wbld-14), [WTAP-10](findings/web-tools-approvals.md#wtap-10). Budget messages restate the domain's limits [XDUP-16](findings/sweep-duplication.md#xdup-16). Tool inputs accept naive `since` datetimes, which crash the pull-request filter [PDOM-03](findings/py-domain.md#pdom-03), [PADP-17](findings/py-adapters.md#padp-17).
- **Today.** 2 float conversions of reported cost ([services/agent/src/autobots/adapters/loop_middleware.py:278](../../../services/agent/src/autobots/adapters/loop_middleware.py#L278), [services/agent/src/autobots/operations/route_qualification.py:246](../../../services/agent/src/autobots/operations/route_qualification.py#L246)). DTZ reports 0 hits in all Python. 6 `dollars()` copies, 6 inline conversions and 4 relative-time helpers.
- **Enforce.** ruff `DTZ` in the shared selection ([Target configuration](#target-configuration)). Check `money_floats`: an AST scan of services/agent/src for a `float(...)` call inside an expression that multiplies by `1_000_000` (2 today). `apps/web/tests/unit/format.test.ts` covers `lib/format.ts`.
- **Adopt.** DTZ as an error now. Fix the two conversions with one helper and a half-micro test, then turn `money_floats` on with an empty baseline. Replace the web copies as screens are touched.

### <a id="std-18"></a>STD-18. Generated contracts are regenerated, validated completely and covered by shared fixtures

- **Rule (MUST).** Generated files are regenerated, never edited (**enforced**: `generate_contracts.py check` runs as `contract_drift` in fast). The hand-written runtime validator enforces every JSON Schema keyword the generated schema uses, or the generator's check fails. Every schema the web parses has a shared boundary case that runs in both languages.
- **Why here.** The validator ignores array bounds and map value schemas, so 10 map fields are never checked, and screens cast `role_overrides` over values nothing validates [XTYP-02](findings/sweep-types.md#xtyp-02), [WSHL-01](findings/web-shell.md#wshl-01), [WSYS-08](findings/web-system.md#wsys-08). The shared fixtures cover 4 of 170 schemas [XTYP-13](findings/sweep-types.md#xtyp-13), [PDOM-16](findings/py-domain.md#pdom-16).
- **Today.** 10 map fields generate as `Record<string, unknown>`; `minItems` (4 uses) and `maxItems` (15 uses) are not enforced. `contracts/fixtures/boundary-cases.json` holds 29 cases for 4 schemas; 2 of the 32 parsers the web calls have cases.
- **Enforce.** In `scripts/generate_contracts.py check`, an allowlist of the keywords `runtime.ts` implements, failing on any other. In `packages/api-client/tests/contract.test.ts`, iterate the parsers the web imports and fail when one has no case.
- **Adopt.** Implement map values and array bounds in `runtime.ts`, regenerate, then add the keyword check. Add cases screen by screen; the coverage test starts with the 30 uncovered parsers as its baseline.

## 6. Errors and logging

### <a id="std-19"></a>STD-19. No blind or silent handlers; cancellation always propagates

- **Rule (MUST).** A broad `except` carries `# noqa: BLE001 - <reason>` and either logs with `error_fields` ([STD-20](#std-20)) or re-raises. Catch the precise type where one exists. No `contextlib.suppress(Exception)` or `suppress(BaseException)`; cancel tasks through one `stop_task` helper that never hides the caller's cancellation. A best-effort side channel, such as the live-result tap, contains its own failures, logs once and never stops the call it observes.
- **Why here.** The tool gateway turns any unexpected tool exception into a bare code with no log line [XERR-02](findings/sweep-errors.md#xerr-02). The live-result tap's JSON reader can stop a paid reply as `partial_stream` [PADP-01](findings/py-adapters.md#padp-01). One cleanup path can discard the caller's cancellation [XERR-13](findings/sweep-errors.md#xerr-13). Broad catches turn defects into user refusals [XERR-15](findings/sweep-errors.md#xerr-15). The only `BLE001` markers suppress a rule nothing runs [XERR-14](findings/sweep-errors.md#xerr-14), [XTOL-08](findings/sweep-tooling.md#xtol-08). Also [XERR-11](findings/sweep-errors.md#xerr-11), [PTOL-10](findings/py-tools.md#ptol-10), [PADP-11](findings/py-adapters.md#padp-11), [PRUN-13](findings/py-run.md#prun-13), [POPS-09](findings/py-ops.md#pops-09).
- **Today.** BLE001 finds 27 broad catches: 22 in src, 3 in scripts and 2 in the hook; about 10 already carry a reason comment. S110 and S112 find 0. `suppress(Exception)` appears twice and `suppress(BaseException)` once, all in `application/browsing_tool.py`. No `except` catches `CancelledError`.
- **Enforce.** `"BLE001", "S110", "S112"` in the shared selection, and check `broad_suppress` (3 today).
- **Adopt.** S110 and S112 as errors now. Run `ruff check --select BLE001 --add-noqa` once and replace each generated marker's text with the real reason; selecting BLE001 before the RUF100 cleanup also keeps the 8 reasoned markers in tests/db ([XTOL-14](findings/sweep-tooling.md#xtol-14)). Replace the three `suppress` calls with `stop_task` and an explicit logged `except`.

### <a id="std-20"></a>STD-20. Causes reach private logs through one helper, and log events are registered

- **Rule (MUST).** Every logged failure passes `**error_fields(error)`: the module-qualified type, the cause chain's types and a few package-relative frames, never messages or locals. Event names come from one registered table using the categories of PRD-LangChain-Deep-Agents section 12.2; context keys are standard (workspace, run, operation); levels follow audience (ERROR needs a person, WARNING is degraded and retrying, INFO is lifecycle); reconnect loops use one rate limit. The API's 500 handler logs before it answers.
- **Why here.** Private logs keep only the exception's class name, so no failure can be located without reproducing it [XERR-01](findings/sweep-errors.md#xerr-01). A run whose processing raises leaves no durable reason [XERR-10](findings/sweep-errors.md#xerr-10), [PRUN-14](findings/py-run.md#prun-14). Log fields, levels and rate limits differ for the same condition [XERR-12](findings/sweep-errors.md#xerr-12). Also [POPS-10](findings/py-ops.md#pops-10), [POPS-15](findings/py-ops.md#pops-15), [XERR-06](findings/sweep-errors.md#xerr-06).
- **Today.** The redacting local JSON logger behind every service log line is **enforced** and pinned by tests (sweep-errors strengths). 25 `log_event` calls in 10 modules use 24 distinct names; 13 pass `error=type(error).__name__`; the 500 handler logs nothing.
- **Enforce.** `services/agent/tests/test_log_events.py`: scan `log_event` call sites with `ast`, fail on a name missing from the registry and on a `type(...).__name__` argument; keep the existing no-message tests.
- **Adopt.** Add `error_fields` and the registry, convert the 13 calls, then make the scan an error. No external log sink is added ([DH-05](../../PRD/PRD-Development-Harness.md#dh-05-hooks-and-portable-enforcement)).

### <a id="std-21"></a>STD-21. Refusals share one base, one HTTP mapping and published codes

- **Rule (MUST).** A refusal whose code reaches a response subclasses one `Refusal` base in domain with a `code` and a `kind` (not found, conflict, invalid, forbidden, unavailable). `api/errors.py` maps kind to status once. Route modules define no mappers of their own. Known refusal and stop codes are published as enum schemas, while the wire field stays an open string.
- **Why here.** Exception classes use four code conventions and 11 route modules map refusals to HTTP, partly by string suffix [XERR-07](findings/sweep-errors.md#xerr-07), [PAPI-05](findings/py-api.md#papi-05). Coded refusals take four shapes [PDOM-13](findings/py-domain.md#pdom-13), [PPRD-17](findings/py-product.md#pprd-17). Codes are plain strings in the contract [XERR-08](findings/sweep-errors.md#xerr-08). A database outage becomes a 500 instead of a retryable 503 [XERR-06](findings/sweep-errors.md#xerr-06).
- **Today.** One `{code, message}` envelope with fixed messages is **enforced** in `api/errors.py` (sweep-errors strengths). 61 exception classes: 20 set the code as a class attribute, 18 in `__init__`, 23 have none.
- **Enforce.** `services/agent/tests/test_refusals.py`: every exception class raised into `api/` subclasses `Refusal` and every code has a message entry; check that `api/*_routes.py` defines no `_error` or `as_api_error` function (baseline: today's mappers).
- **Adopt.** Add the base and the handler, move route modules over as they are touched, then switch the mapper check to an empty baseline. Domain stays free of HTTP: the status table lives in `api/`.

### <a id="std-22"></a>STD-22. Every web read and write has explicit outcome states

- **Rule (MUST).** A read resolves to one union: loading, ready, signed out, denied, not found, unavailable (retryable) or contract mismatch. A write resolves to pending, done, refused or unknown. Screens render these through one `LoadState` and one `Outcome` component with fixed roles and `data-state` markers. A `ContractError` means drift only; an HTTP failure is a separate error carrying status and code. The BFF classifies transport failures and writes one server-side line per class.
- **Why here.** A contract mismatch looks like an outage, or hangs, and nothing records which field failed [XERR-03](findings/sweep-errors.md#xerr-03), [XTYP-14](findings/sweep-types.md#xtyp-14). Screens collapse every failure into one message [XERR-04](findings/sweep-errors.md#xerr-04). Denied runs are polled every second, and 403 or contract errors never leave Loading [WRUN-02](findings/web-run.md#wrun-02). An Auth outage reads as a wrong password [XERR-05](findings/sweep-errors.md#xerr-05), [WSHL-07](findings/web-shell.md#wshl-07). Refusal codes are mapped with nested ternaries, differently across sibling actions [WBLD-16](findings/web-build.md#wbld-16). Also [XWEB-06](findings/sweep-web-architecture.md#xweb-06), [XWEB-07](findings/sweep-web-architecture.md#xweb-07), [XDUP-18](findings/sweep-duplication.md#xdup-18), [WRUN-13](findings/web-run.md#wrun-13), [WBLD-04](findings/web-build.md#wbld-04), [WCMP-05](findings/web-composer.md#wcmp-05), [WCMP-06](findings/web-composer.md#wcmp-06), [WSYS-04](findings/web-system.md#wsys-04), [WTAP-05](findings/web-tools-approvals.md#wtap-05), [WSHL-02](findings/web-shell.md#wshl-02), [WSHL-20](findings/web-shell.md#wshl-20).
- **Today.** 89 `.catch(() => ...)` handlers in 31 component files discard the error. 24 component files hand-write their loaders. [DH-06](../../PRD/PRD-Development-Harness.md#nextjs-and-typescript) and [nextjs.md](../../../.claude/rules/nextjs.md) already require these states; nothing checks them.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: components (not ui)
  { selector: "CallExpression[callee.property.name='catch'] > ArrowFunctionExpression[params.length=0]", message: "Keep the failure kind: use the shared loader or refusal helper (STD-22)." },
  ```
- **Adopt.** Split `HttpError` from `ContractError` in `runtime.ts` first, then add the loader ([STD-32](#std-32)). Turn the selector on with the 89 sites baselined once the loader exists. Start with approvals and operations, whose loaders are written twice.

## 7. Comments and documentation

### <a id="std-23"></a>STD-23. Comments say what holds now and cite resolvably

- **Rule (MUST).** A comment states what holds now, then cites its source: `<rule>. (Decision 0026 G2)`, `PRD-Studio SR-01`, `PRD-LangChain-Deep-Agents section 8.4`. A decision with rows is cited with its row. No delivery narrative ("a later story", "Nothing else exists", "first", "has none") and no review-round IDs (B1, M21, N-4). When a decision amends a requirement row, every comment citing that row is updated in the same change. Citing decisions and stories stays the practice.
- **Why here.** Nine comments describe an earlier state of the code [XDOC-01](findings/sweep-docs-naming.md#xdoc-01), and the conventions the code already follows are written nowhere [XDOC-02](findings/sweep-docs-naming.md#xdoc-02). Also [XDOC-07](findings/sweep-docs-naming.md#xdoc-07), [PAPI-17](findings/py-api.md#papi-17), [PDOM-19](findings/py-domain.md#pdom-19), [PTOL-17](findings/py-tools.md#ptol-17), [PRUN-21](findings/py-run.md#prun-21), [POPS-18](findings/py-ops.md#pops-18), [SCRP-21](findings/scripts.md#scrp-21), [WSHL-17](findings/web-shell.md#wshl-17), [WBLD-18](findings/web-build.md#wbld-18), [WRUN-20](findings/web-run.md#wrun-20), [WTAP-19](findings/web-tools-approvals.md#wtap-19), [WCMP-18](findings/web-composer.md#wcmp-18).
- **Today.** Every one of the 220 decision, 338 story and 364 requirement citations in source resolves. 36 cite "PRD x.y", which names no document, since three PRDs number their sections. ERA001 reports 0 commented-out code everywhere, and owned source has no TODO markers.
- **Enforce.** `scripts/specs.py refs`, run by the harness profile beside `backlog_validation`: resolve every `Decision NNNN [row]`, `US-n.m`, `SP-nnn` and requirement ID, fail on a bare "PRD x.y" beyond the baseline of 36, and warn on the delivery-narrative phrases. `ERA001` in the shared selection. The conventions themselves go in a short "Comments and names" section of AGENTS.md or `.claude/rules/comments.md`.
- **Adopt.** ERA001 and the resolution check as errors now (0 failures). Fix the nine stale comments. The "PRD x.y" baseline shrinks as files are touched.

### <a id="std-24"></a>STD-24. Docstrings sit where risk concentrates, and every module keeps one

- **Rule (MUST for modules; SHOULD for functions).** Every Python module keeps its docstring stating purpose and invariant. A public function that refuses with codes, holds a transaction or lease, or exceeds 60 lines has a docstring, or a `/** */` comment in TypeScript, giving its purpose, its refusal codes in order and its side effects. A screen file over 300 lines opens with a two-line header naming the data, stream and actions it owns.
- **Why here.** Contract documentation is thinnest on the largest entry points: `post_run` (101 lines, nine refusal points) and `run_goal` (90 lines, complexity 14) have none [XDOC-05](findings/sweep-docs-naming.md#xdoc-05), [PRUN-21](findings/py-run.md#prun-21).
- **Today.** 0 service, script or hook modules lack a docstring ([metrics.md section 3](metrics.md#3-python-functions-and-documentation)); only 5 deliberately minimal fault fixtures do. Of public src functions over 60 lines, 20 of 36 are documented, leaving 16; 13 of the 24 functions over complexity 10 have none; 21 of 80 route handlers are documented. ruff's D1 rules would flag more than 200 small functions as well, so they are not proposed.
- **Enforce.** `"D100", "D104"` in the shared selection, ignored for `tests/faults/**` (0 hits; validated with the fault fixtures). Check `undocumented_long`: public functions over 60 lines in services/agent/src without a docstring (baseline 16).
- **Adopt.** D100 and D104 as errors now. Document the 16 when their modules are next touched. Route docstrings become OpenAPI descriptions, so contracts are regenerated in the same change.

### <a id="std-25"></a>STD-25. Every suppression names a code and a reason, and dead ones go

- **Rule (MUST).** Suppressions take the service's existing form: `# noqa: RUF009 - frozen, so sharing the default is safe.`, `# type: ignore[attr-defined]  # <reason>`, and in TypeScript `// eslint-disable-next-line <rule> -- <reason>`. A suppression nothing needs is removed. Third-party typing exceptions stay narrow and documented ([DH-06](../../PRD/PRD-Development-Harness.md#python-api-domain-and-workers)).
- **Why here.** 295 suppressions in scripts and tests/db are dead, written for a linter that never runs there [XTOL-14](findings/sweep-tooling.md#xtol-14), [TDBC-08](findings/db-tests.md#tdbc-08). Comments stand in for types, and suppressions give no reason [XTYP-15](findings/sweep-types.md#xtyp-15). Also [TDBC-12](findings/db-tests.md#tdbc-12), [PTST-06](findings/py-tests.md#ptst-06), [XTYP-17](findings/sweep-types.md#xtyp-17), [PAPI-09](findings/py-api.md#papi-09).
- **Today.** Every service `type: ignore` names a code (PGH003: 0) and every service `noqa` in src gives a reason. None of the `type: ignore` comments gives a reason: 18 in src, 44 in service tests and 25 in repository-level code that no type checker reads. RUF100 reports 295 dead `noqa` at repository level. The web has 0 `eslint-disable`.
- **Enforce.** `"PGH003", "PGH004"` (0 hits) and RUF100 in the shared selection; mypy strict's `warn_unused_ignores` where mypy runs; check `suppression_reasons` (regular expression over tracked Python and TypeScript; baseline 87 `type: ignore`); ESLint `linterOptions: { reportUnusedDisableDirectives: "error" }`.
- **Adopt.** PGH003 and PGH004 as errors now. Settle the shared rule selection, then run `ruff check --select RUF100 --fix` once on repository-level paths as an explicit commit: with BLE001 selected, 287 dead markers go and the 8 reasoned `BLE001` markers stay. Then add reasons as files are touched.

### <a id="std-26"></a>STD-26. READMEs route readers to the runbooks

- **Rule (SHOULD).** apps/web, services/agent, scripts, tests/db and supabase each have a short README with Run, Test and Extend headings that link to the runbook or AGENTS.md section instead of restating it. scripts/README.md lists each script with its target class (pure, disposable, persistent or paid) and its guard flag. The root README describes the current state and points at README-SETUP-RUN.md, AGENTS.md and CODEBASE.md.
- **Why here.** Only generated and fixture folders have a README [XDOC-08](findings/sweep-docs-naming.md#xdoc-08). The root README still describes the product before it was built [XDOC-03](findings/sweep-docs-naming.md#xdoc-03). Live database definitions hide in the last migration that touched them [SQLI-09](findings/sql-infra.md#sqli-09).
- **Today.** READMEs exist only in packages/api-client, packages/db-types, contracts/generated and tests/faults.
- **Enforce.** Check `readmes`: the five files exist and every relative link in them resolves, reusing the link resolution in `scripts/harness_lib.py`.
- **Adopt.** Write the five, then make the check an error. Linking instead of copying follows DH-03's "avoid maintaining contradictory copies".

## 8. Naming and formatting

### <a id="std-27"></a>STD-27. All Python shares one format and import order

- **Rule (MUST).** Every Python path is formatted by `ruff format` with the service's style (double quotes, 100 columns) and sorted by ruff's default isort settings. Formatting is an explicit operation, never a hook action ([DH-05](../../PRD/PRD-Development-Harness.md#dh-05-hooks-and-portable-enforcement)).
- **Why here.** Two Python house styles exist and only the service's is checked: scripts use 8,648 single-quoted strings to 978 double, and some lines reach 578 characters [XTOL-04](findings/sweep-tooling.md#xtol-04), [SCRP-04](findings/scripts.md#scrp-04). Also [TDBC-08](findings/db-tests.md#tdbc-08), [THRN-14](findings/harness-tests.md#thrn-14).
- **Today.** `ruff format --check` is **enforced** for services/agent. Under the shared configuration, 121 of the 131 repository-level files would be reformatted, which grows them from 25,788 to about 47,666 lines and leaves 1,015 E501 hits [XTOL-04](findings/sweep-tooling.md#xtol-04). The isolated run in [metrics.md section 6](metrics.md#6-repository-level-python) gives 5,269 E501 and 119 I001; with `src` set as below, I001 falls to 88.
- **Enforce.**

  ```toml
  # ruff.toml (repository root)
  line-length = 100
  [lint.per-file-ignores]
  "scripts/**" = ["E501"]          # until the one-time reformat
  "tests/**" = ["E501"]
  ".claude/hooks/**" = ["E501"]
  ```
  and, after the reformat, a `repo_ruff_format` step: `ruff format --check scripts tests .claude/hooks`.
- **Adopt.** Gate lint first ([STD-48](#std-48)). Then, after the five source-text tests stop depending on quoting [THRN-12](findings/harness-tests.md#thrn-12) and with no story open on those files, reformat once in one mechanical commit listed in `.git-blame-ignore-revs`, add the format check, and drop the E501 ignores, wrapping the remaining long strings. The reformat touches tests/db and the qualifiers, so harness, db and operations evidence is rerun afterwards.

### <a id="std-28"></a>STD-28. Web formatting is explicit and covers packages/api-client

- **Rule (MUST).** Prettier's options are committed rather than implied by the pinned version, an `.editorconfig` states both languages' widths, and lint and format cover `packages/api-client/src/runtime.ts` and its tests (never `generated.ts`). TypeScript that node:test loads compiles under `erasableSyntaxOnly`.
- **Why here.** The module that validates every response at the trust boundary has looser checks than the screens that consume it [XTOL-12](findings/sweep-tooling.md#xtol-12), [WSHL-09](findings/web-shell.md#wshl-09). An upgrade that changes a default would reformat the app [XTOL-13](findings/sweep-tooling.md#xtol-13). A lib file using an enum would pass `tsc` and fail only under the unit runner [XTOL-15](findings/sweep-tooling.md#xtol-15).
- **Today.** `prettier --check` is **enforced** for apps/web ([apps/web/package.json:7](../../../apps/web/package.json#L7)). The configuration below changes no apps/web file (checked with Prettier 3.9.10); `runtime.ts` and `contract.test.ts` would be reformatted. `erasableSyntaxOnly` is set in packages/api-client and missing in apps/web, which has no such syntax today.
- **Enforce.** `.prettierrc.json` at the repository root, and the compiler flag in apps/web/tsconfig.json:

  ```json
  { "printWidth": 80, "singleQuote": false, "semi": true, "trailingComma": "all" }
  ```

  ```json
  { "compilerOptions": { "erasableSyntaxOnly": true } }
  ```
  plus `"include": ["src/**/*.ts", "tests/**/*.ts"]` in packages/api-client/tsconfig.json, and `api_client_lint` and `api_client_format` steps in fast and full.
- **Adopt.** Commit `.prettierrc.json`, `.editorconfig` and the compiler flag now (no file changes). Format the two api-client files, then add the steps.

### <a id="std-29"></a>STD-29. Names describe behavior, words keep one meaning, and file-name conventions hold

- **Rule (MUST for new code).** Python follows pep8-naming; exception names state the outcome (`ProfileNotOffered`), so N818 stays ignored. Python files are snake_case and TypeScript files kebab-case. Files, tests and migrations are named for the behavior they cover, never for the story or review round that added them; the provenance goes in the docstring. Route handlers are named for their operation ID. A route's client component is `<Feature>Screen`, and `Panel` means a side panel. A short glossary in AGENTS.md gives operation, profile, settings, adapters and workspace one meaning each.
- **Why here.** Names keep the story or first version that introduced them [XDOC-04](findings/sweep-docs-naming.md#xdoc-04), and tests are filed by the story or review that added them, so one module's tests sit in several files [PTST-05](findings/py-tests.md#ptst-05). Five words each name two or three things [XDOC-06](findings/sweep-docs-naming.md#xdoc-06). Nine handlers share four generic names, which FastAPI turns into duplicate summaries [XDOC-09](findings/sweep-docs-naming.md#xdoc-09). Route components use ten suffixes [XWEB-20](findings/sweep-web-architecture.md#xweb-20). Also [XDOC-07](findings/sweep-docs-naming.md#xdoc-07), [PRUN-22](findings/py-run.md#prun-22), [PDOM-18](findings/py-domain.md#pdom-18), [PPRD-20](findings/py-product.md#pprd-20), [PTOL-20](findings/py-tools.md#ptol-20), [PADP-19](findings/py-adapters.md#padp-19), [PAPI-20](findings/py-api.md#papi-20), [XMOD-17](findings/sweep-boundaries.md#xmod-17), [WBLD-19](findings/web-build.md#wbld-19), [WCMP-17](findings/web-composer.md#wcmp-17), [WTAP-16](findings/web-tools-approvals.md#wtap-16), [TWEB-18](findings/web-tests.md#tweb-18), [PTST-19](findings/py-tests.md#ptst-19), [TDBC-14](findings/db-tests.md#tdbc-14), [THRN-15](findings/harness-tests.md#thrn-15), [THRN-19](findings/harness-tests.md#thrn-19), [SQLI-18](findings/sql-infra.md#sqli-18).
- **Today.** pep8-naming without N818 reports 0 in services/agent and 3 N806 in tests/db. File names follow both conventions with no exception. 7 files are named for a review round. 67 of 80 route handlers carry HTTP-verb names; 4 operation summaries are shared by 9 handlers.
- **Enforce.** `"N"` with `ignore = ["N818"]` in the shared selection. Check `file_names`: snake_case and kebab-case patterns (Next.js bracket routes allowed), and no new file named for a review round (`final_review`, `from_review`, `blocker`, `major`), with the 7 files that XDOC-07 lists as the baseline. "Review" alone is a domain word, as in `approval_review_detail`, so it is not banned. Applied migrations keep their names ([database.md](../../../.claude/rules/database.md)).
- **Adopt.** N and `file_names` as errors now, after renaming the 3 tests/db variables. Rename handlers when their module is next touched and regenerate; operation IDs and paths do not change.

### <a id="std-30"></a>STD-30. Magic values get names, and HTTP statuses have one spelling

- **Rule (SHOULD).** A number that carries a rule has a name (`MAX_SERIES_YEARS`, `STREAM_PROOF_CHUNKS`). HTTP statuses use `fastapi.status` constants everywhere, in comparisons and in `ApiError` calls. Header names use the shared constants (`WORKSPACE_HEADER`).
- **Why here.** Statuses are spelled three ways, and header constants are bypassed in the file that imports them [XDOC-10](findings/sweep-docs-naming.md#xdoc-10). Also [WRUN-18](findings/web-run.md#wrun-18), [SCRP-19](findings/scripts.md#scrp-19).
- **Today.** PLR2004 reports 52 magic comparisons in src: 34 HTTP statuses and 18 others. 85 literal statuses in 15 modules.
- **Enforce.** PLR2004 for src (tests ignored), staged with ANN401 in services/agent/pyproject.toml ([Target configuration](#target-configuration)).
- **Adopt.** Convert the statuses mechanically, name or mark the 18 others, then select PLR2004 with an empty baseline.

## 9. React and Next.js

### <a id="std-31"></a>STD-31. Server Components by default

- **Rule (SHOULD).** A read-only screen or section renders on the server through a server-only typed client: `cache: "no-store"`, a token per request, the chosen workspace header, and React `cache()` only within a request. Client Components are for actual interaction. A write that changes data the shell renders calls `router.refresh()`.
- **Why here.** The run inspector is a Client Component only so that it can fetch in an effect, so its first paint is always "Loading" [WRUN-14](findings/web-run.md#wrun-14). Read-only home, data and session views fetch in client effects [WCMP-07](findings/web-composer.md#wcmp-07), [XWEB-14](findings/sweep-web-architecture.md#xweb-14). Each render repeats the same session and readiness reads [WSHL-14](findings/web-shell.md#wshl-14). The page title and width belong to the server page on most routes but to the client screen on run routes [XWEB-19](findings/sweep-web-architecture.md#xweb-19). [DH-06](../../PRD/PRD-Development-Harness.md#nextjs-and-typescript) and [nextjs.md](../../../.claude/rules/nextjs.md) already say this.
- **Today.** 2 of 22 pages load data on the server; 39 modules are client modules.
- **Enforce.** Review, through one line in the `autobots-nextjs` and `autobots-review-change` checklists: "Does this client component hold state other than fetched data?" The number of client modules is tracked in each review's metrics.
- **Adopt.** Convert the inspector first, then the data summary and the first page of the run list. Server reads keep the BFF's per-request checks.

### <a id="std-32"></a>STD-32. One client data layer for reads, writes and live updates

- **Rule (MUST).** Components read through `hooks/use-resource.ts` (one union state, `AbortController`, `reload()`), write through `hooks/use-submit.ts` (pending state that disables the trigger and ignores re-entry, an explicit idempotency-key policy, unknown outcome on a lost reply or 5xx), and refresh live data through one live-resource hook with backoff and coalescing. No `fetch` or `csrfFetch` in a component. The key policy is per call site: per press where a story chose it, as US-4.1 did for the composer, and kept until the outcome is known otherwise, as ContinueRun does.
- **Why here.** Writes have no shared submit path, and run admission is not guarded against a second press [XWEB-03](findings/sweep-web-architecture.md#xweb-03), [WCMP-01](findings/web-composer.md#wcmp-01), [WBLD-02](findings/web-build.md#wbld-02). A lost write reply is reported as a failure, and the retry gets a new key [WRUN-03](findings/web-run.md#wrun-03). Browser data access is hand-written in 31 components [XDUP-06](findings/sweep-duplication.md#xdup-06), [XWEB-02](findings/sweep-web-architecture.md#xweb-02). Also [WCMP-04](findings/web-composer.md#wcmp-04), [WCMP-08](findings/web-composer.md#wcmp-08), [WBLD-05](findings/web-build.md#wbld-05), [WBLD-08](findings/web-build.md#wbld-08), [WRUN-04](findings/web-run.md#wrun-04), [WRUN-16](findings/web-run.md#wrun-16), [WSYS-02](findings/web-system.md#wsys-02), [WSYS-03](findings/web-system.md#wsys-03), [WTAP-03](findings/web-tools-approvals.md#wtap-03), [WTAP-04](findings/web-tools-approvals.md#wtap-04), [WTAP-15](findings/web-tools-approvals.md#wtap-15), [WSHL-04](findings/web-shell.md#wshl-04), [XWEB-13](findings/sweep-web-architecture.md#xweb-13), [XWEB-16](findings/sweep-web-architecture.md#xweb-16), [XWEB-17](findings/sweep-web-architecture.md#xweb-17). [DH-06](../../PRD/PRD-Development-Harness.md#nextjs-and-typescript): "Disable duplicate submits with server idempotency as the correctness mechanism."
- **Today.** `fetch` appears 45 times in 25 component files and `csrfFetch` is imported by 19. Only 2 of the 23 files with hand-rolled read effects abort a stale request, and only 8 of the 19 writing files stop a second press. Two hooks already have the target shape: `useLoaded` in tool-catalog and `useToolUses`.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: components (not ui)
  "no-restricted-globals": ["error", { name: "fetch", message: "Read through hooks/use-resource.ts (STD-32)." }],
  "no-restricted-imports": ["error", { paths: [{ name: "@/lib/csrf-fetch", message: "Write through hooks/use-submit.ts (STD-32)." }] }],
  ```
- **Adopt.** Write the two hooks, generalized from `useLoaded`, before turning either rule on; then baseline the 45 and 19 hits and migrate screens as they are touched, run admission first. These hooks hold request state only; run transitions and scheduling stay in Python ([nextjs.md](../../../.claude/rules/nextjs.md)).

### <a id="std-33"></a>STD-33. Pure UI logic lives in lib/ and is unit-tested

- **Rule (MUST).** A pure helper, vocabulary table or rule used by a screen lives in a lib/ module with no JSX, no `"use client"` and no runtime `@/` import, so node:test can load it, and it has a unit test. Component files export components only.
- **Why here.** Pure logic lives in `.tsx` files the unit runner cannot load, so it is untested or tested only in the browser [WCMP-11](findings/web-composer.md#wcmp-11), [WRUN-15](findings/web-run.md#wrun-15), [XWEB-15](findings/sweep-web-architecture.md#xweb-15), [WTAP-09](findings/web-tools-approvals.md#wtap-09), [WSYS-10](findings/web-system.md#wsys-10), [WBLD-15](findings/web-build.md#wbld-15). The two-press approval shortcut is a decision buried in a handler of complexity 27 [WTAP-02](findings/web-tools-approvals.md#wtap-02). Retention day fields misparse typos before a destructive pass [WSYS-01](findings/web-system.md#wsys-01).
- **Today.** Component files export 7 helper functions and 5 constants outside `components/ui`, such as `commandsFor`, `STATUS_TEXT` and `repair`. apps/web/tests/unit has 3 files for lib/, and only 2 run ([STD-43](#std-43)).
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: components (not ui)
  { selector: "ExportNamedDeclaration > FunctionDeclaration[id.name=/^(?!use[A-Z])[a-z]/]", message: "Component files export components; move helpers to lib/ (STD-33)." },
  { selector: "ExportNamedDeclaration > VariableDeclaration > VariableDeclarator[id.name=/^[A-Z][A-Z0-9_]+$/]", message: "Shared vocabulary lives in lib/, keyed by generated types (STD-12)." },
  ```
- **Adopt.** Error with the 12 baselined. Move `valueFor`, `draftOf`, the approval shortcut rule and the retention parser first, each with a test.

### <a id="std-34"></a>STD-34. Screens use shared primitives and design tokens

- **Rule (MUST).** Recurring layout pieces come from `components/ui`: section block, fact list, segmented control, native-dialog wrapper on popover tokens, settings row, initial tile and a `Field` that wires label, description and error. Type sizes, spacing and radii come from named steps in `globals.css` `@theme`, mapped to the canonical radius base. Colors come only from the Luma tokens ([DS-01](../../PRD/PRD-Design-System.md#ds-01--preserve-the-exact-theme-tokens), [DS-03](../../PRD/PRD-Design-System.md#ds-03--apply-semantic-tokens-across-the-whole-ui)); a type scale adds no color.
- **Why here.** Type sizes and many spacings are arbitrary values outside the theme, and compact density cannot tighten them [XWEB-12](findings/sweep-web-architecture.md#xweb-12), [WSHL-13](findings/web-shell.md#wshl-13). Seven layout pieces are copied 26 times [XWEB-11](findings/sweep-web-architecture.md#xweb-11). The tool modal uses page colors where DS-03 maps dialogs to popover [WTAP-12](findings/web-tools-approvals.md#wtap-12). Also [WSHL-12](findings/web-shell.md#wshl-12), [WSYS-15](findings/web-system.md#wsys-15), [WSYS-16](findings/web-system.md#wsys-16), [WSYS-19](findings/web-system.md#wsys-19), [WSYS-20](findings/web-system.md#wsys-20), [WTAP-11](findings/web-tools-approvals.md#wtap-11), [WTAP-17](findings/web-tools-approvals.md#wtap-17), [WBLD-09](findings/web-build.md#wbld-09), [WBLD-17](findings/web-build.md#wbld-17), [WCMP-15](findings/web-composer.md#wcmp-15), [WCMP-16](findings/web-composer.md#wcmp-16), [WRUN-17](findings/web-run.md#wrun-17).
- **Today.** Raw form controls outside `components/ui` are **enforced** at 0 by `tests/harness/test_shared_form_controls.py`, and the single token definition in `globals.css` by `appearance.spec.ts`. Not checked: 212 arbitrary font sizes in 39 files (13 distinct values), 15 arbitrary pixel spacings, 5 hard-coded radii, 26 `dark:` overrides in 12 files outside `components/ui`, and 8 `oklch()` literals in the theme preview.
- **Enforce.** Check `design_tokens`, in the style of `test_shared_form_controls.py`: count `text-[Npx]`, `rounded-[`, arbitrary pixel spacing and `oklch(` per file in app and components against a baseline that only shrinks, with a fixture proving each pattern is caught. Extend the single-definition test to compare the preview swatches with `luma.css`.
- **Adopt.** Add the type-scale tokens and the missing primitives, then the check with today's counts. Replace values as screens are touched.

### <a id="std-35"></a>STD-35. Forms, page titles and accessibility scans meet one line

- **Rule (MUST).** A described or invalid control is wired through `Field` (`aria-describedby`, `aria-invalid`). Form values are parsed strictly in a lib helper and validated with the generated parser before a write. Radio groups have a fieldset and legend. Every page exports a title through the root layout's template. Every axe scan runs through one helper at [Decision 0010](../../../docs/engineering/decisions/0010-contrast-pass-line.md)'s WCAG 2.1 A and AA line, keeping WCAG 2.2 tags on the scans that select them today.
- **Why here.** Help text and errors are not tied to their controls [WSYS-12](findings/web-system.md#wsys-12). Four settings pages have no document title [WSYS-17](findings/web-system.md#wsys-17). 21 of 35 axe scans fall short of the line Decision 0010 sets [TWEB-05](findings/web-tests.md#tweb-05). Also [WCMP-19](findings/web-composer.md#wcmp-19), [WTAP-13](findings/web-tools-approvals.md#wtap-13), [WSYS-01](findings/web-system.md#wsys-01).
- **Today.** jsx-a11y rules from the Next preset are **enforced** under `--max-warnings=0`. Source has 2 `aria-describedby` and 0 `aria-invalid`. 6 of 22 pages export no metadata (Home, Sign in and the four in [WSYS-17](findings/web-system.md#wsys-17)). Axe scans use four tag sets across 26 spec files.
- **Enforce.** Check `page_titles`: every `app/**/page.tsx` exports `metadata` or `generateMetadata` (baseline 5; Home uses the root title). In specs:

  ```js
  // apps/web/eslint.config.mjs, files: SPECS, ignoring tests/browser/support/**
  "no-restricted-imports": ["error", { paths: [{ name: "@axe-core/playwright", message: "Use support/a11y.ts, which applies Decision 0010's tags (STD-35)." }] }],
  ```
- **Adopt.** Add `support/a11y.ts` with `WCAG_PASS_LINE = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]` and an `extraTags` option, migrate the 26 files, then turn the import rule on with no baseline. Adding WCAG 2.2 everywhere would extend Decision 0010, which is the owner's call.

## 10. Python service layers

### <a id="std-36"></a>STD-36. API routes stay thin

- **Rule (MUST).** A route handler parses the request, calls one application use case and maps refusals ([STD-21](#std-21)). No SQL, no transaction and no use-case rule in `api/`. Shared dependencies (workspace, owner, readiness, provider settings and one typed pool dependency) live in `api/dependencies.py`, and route modules do not import each other. The return annotation is the single response type. List and detail read models use a bounded number of statements in one snapshot, never a query per row [PPRD-11](findings/py-product.md#pprd-11), [PRUN-11](findings/py-run.md#prun-11).
- **Why here.** Route handlers own SQL, transactions and use-case rules [PAPI-01](findings/py-api.md#papi-01). The gate for model-backed work is rebuilt in five handlers [PAPI-04](findings/py-api.md#papi-04), [XDUP-08](findings/sweep-duplication.md#xdup-08). Routes read and write the workspace model policy themselves [XMOD-05](findings/sweep-boundaries.md#xmod-05). Also [PAPI-02](findings/py-api.md#papi-02), [PAPI-06](findings/py-api.md#papi-06), [PAPI-07](findings/py-api.md#papi-07), [PAPI-11](findings/py-api.md#papi-11), [PAPI-13](findings/py-api.md#papi-13), [PAPI-19](findings/py-api.md#papi-19), [XMOD-11](findings/sweep-boundaries.md#xmod-11), [XDUP-20](findings/sweep-duplication.md#xdup-20), [PAPI-15](findings/py-api.md#papi-15).
- **Today.** 17 `execute` calls in 5 api modules (run_routes 5, settings_routes 6, membership 3, event_routes 2, improvement_routes 1). 12 of 14 routers import from `settings_routes`; `_pool` is copied 10 times. FastAPI's FAST001 reports 78 redundant `response_model` arguments.
- **Enforce.** Check `api_sql`: `.execute(` calls per file under `services/agent/src/autobots/api` (baseline 17), and `*_routes.py` importing another `*_routes` module (baseline: today's edges). `"FAST"` selected in services/agent ([Target configuration](#target-configuration)).
- **Adopt.** FAST001's fix is marked unsafe in ruff 0.17.3, so apply it as one explicit `--fix --unsafe-fixes --select FAST001` commit and let `contract_drift` prove the OpenAPI document is unchanged; then select FAST. Add `api/dependencies.py`, then the application model-policy and admission services, which remove most of the SQL.

### <a id="std-37"></a>STD-37. Each state has one writer, and adapters get capabilities, not connections

- **Rule (MUST).** Run and job state change only through the transition surface built on the domain table ([option-b-contract.md](../../../docs/engineering/option-b-contract.md) owns the states). Approval status changes only in `application/approvals.py`, and receipt status only in one receipts module. External tool adapters receive narrow capabilities through `ToolContext`, never a raw connection to run business SQL. Moves keep every lease, fence, generation predicate and approval binding exactly as they are.
- **Why here.** External tool adapters run approval and receipt SQL through `ToolContext`'s raw connection [XMOD-02](findings/sweep-boundaries.md#xmod-02); the pull-request connector rewrites approval state outside a transaction and without the lease [PADP-02](findings/py-adapters.md#padp-02), [XDUP-02](findings/sweep-duplication.md#xdup-02). Approval and receipt states change from six modules [PTOL-03](findings/py-tools.md#ptol-03). Run and job state are written from four modules beside the command table [PRUN-07](findings/py-run.md#prun-07). An approved `browse_goal` call can run again without a person until the approval expires [PTOL-06](findings/py-tools.md#ptol-06). Also [PRUN-06](findings/py-run.md#prun-06), [PRUN-20](findings/py-run.md#prun-20), [PADP-13](findings/py-adapters.md#padp-13).
- **Today.** The transition table and `apply_command` are **enforced** for user commands. Outside them: 15 run and job writes in 4 modules, 11 approval and receipt status statements in 6 modules (one an adapter), and 13 `execute` calls in 8 adapter modules.
- **Enforce.** Check `state_writers`: SQL text that updates `public.runs` or `app_private.run_jobs` status, `public.approval_requests` status or `app_private.tool_receipts`, mapped to its owning module, with today's other writers as a baseline.
- **Adopt.** Move the adapter's approval reset into `approvals.py` first, because it bypasses the lease. Run `tests/db/pull_request_check.py` and `approval_check.py` before and after (db profile).

### <a id="std-38"></a>STD-38. Process configuration is read at entry points

- **Rule (MUST for domain, contracts, application and adapters).** Entry points (`api/main.py`, `operations/*`) read the environment once into a config object and pass it down. Where credentials late-resolve per attempt ([model-gateway.md](../../../.claude/rules/model-gateway.md)), the entry point passes the live environ mapping as a parameter instead of a startup snapshot.
- **Why here.** Process configuration is read at call sites in four layers, and the worker imports the API entry point to get it [XMOD-08](findings/sweep-boundaries.md#xmod-08). Handlers read configuration on every request [PAPI-10](findings/py-api.md#papi-10). Expert tool checks default to the process environment [PPRD-21](findings/py-product.md#pprd-21). Missing web server configuration becomes empty strings far from its cause [WSHL-20](findings/web-shell.md#wshl-20). The reasoning trial's shared US$1 ledger path is relative to the working directory [POPS-07](findings/py-ops.md#pops-07). Also [POPS-14](findings/py-ops.md#pops-14).
- **Today.** 26 modules read `os.environ` or `os.getenv`: domain and contracts 0, application 5 (7 references), adapters 7 (11), api 7 and operations 7.
- **Enforce.** The domain and contracts configurations already ban `os.environ` ([STD-01](#std-01)). Add the same to `application/ruff.toml` and `adapters/ruff.toml`, which flag the 18 references today (checked):

  ```toml
  extend = "../../../pyproject.toml"

  [lint.flake8-tidy-imports.extend-banned-api]
  "os.environ".msg = "Read configuration in the entry point and pass it in (STD-38)."
  "os.getenv".msg = "Read configuration in the entry point and pass it in (STD-38)."
  ```
- **Adopt.** Add a leaf `autobots/config.py`, then the two configurations with their 18 references baselined by `--add-noqa`.

### <a id="std-39"></a>STD-39. Async resources are owned, bounded and cancellable

- **Rule (MUST).** [python-worker.md](../../../.claude/rules/python-worker.md) and [DH-06](../../PRD/PRD-Development-Harness.md#python-api-domain-and-workers) already require lifespan-owned resources, bounded timeouts and propagated cancellation. In addition: HTTP clients come from one factory (`adapters/provider_http.provider_client`: no redirects, `trust_env=False`); the pool has an explicit timeout shorter than the BFF's abort; the lease keeper is an async context manager whose cancelled task is awaited; CPU-bound or uninterruptible work runs where it can be stopped, not in a thread under the GIL.
- **Why here.** A model-supplied regex runs under the GIL and can freeze the worker's event loop [PTOL-01](findings/py-tools.md#ptol-01). Six client constructors use different defaults, and the GitHub token client honors proxy environment variables [PADP-05](findings/py-adapters.md#padp-05), [XDUP-11](findings/sweep-duplication.md#xdup-11). GitHub read tools open a new client and resolve the target for every request, so one call can read two repositories [PADP-06](findings/py-adapters.md#padp-06). The lease keeper is started and stopped by hand in three places [PRUN-15](findings/py-run.md#prun-15). A database outage holds a request for up to 30 seconds [XERR-06](findings/sweep-errors.md#xerr-06). Also [XERR-13](findings/sweep-errors.md#xerr-13), [PADP-15](findings/py-adapters.md#padp-15).
- **Today.** ruff's ASYNC rules are **enforced** in services/agent. 6 `httpx` client constructors; 3 hand-run lease keepers; no pool timeout.
- **Enforce.** Check `broad_suppress` ([STD-19](#std-19)) and review. A ban on `httpx.AsyncClient` was measured and rejected: banned-api also flags the type annotations.
- **Adopt.** Add `stop_task` and the lease context manager with tests that cancel during cleanup, then route the six clients through the factory.

## 11. SQL and migrations

Infrastructure keeps following [infrastructure.md](../../../.claude/rules/infrastructure.md) and [DH-08](../../PRD/PRD-Development-Harness.md#dh-08-docker-and-local-operations-standards) as written. Their open items are planned work rather than new standards: images qualified by a source hash instead of the image that runs [SQLI-02](findings/sql-infra.md#sqli-02), a synthetic stack on images the install doesn't use [SQLI-15](findings/sql-infra.md#sqli-15), missing resource limits and mount completeness [SQLI-19](findings/sql-infra.md#sqli-19), and an opaque browser entrypoint failure [SQLI-20](findings/sql-infra.md#sqli-20).

### <a id="std-40"></a>STD-40. New migrations state locks, data and recovery, and are named for content

- **Rule (MUST, new migrations only).** [database.md](../../../.claude/rules/database.md) and [DH-07](../../PRD/PRD-Development-Harness.md#dh-07-supabase-migrations-seeds-and-database-quality) already require documented locks, backfills and forward recovery, and forbid editing applied migrations. A migration that rewrites rows, swaps a constraint or builds an index on an existing table adds three header lines after its traceability line: `-- Locks:`, `-- Data:` and `-- Recovery:`. Its file name describes its content.
- **Why here.** Migrations that rewrite data or rebuild constraints say nothing about locks or recovery [SQLI-04](findings/sql-infra.md#sqli-04). Some are named for a review round and bundle unrelated changes [SQLI-18](findings/sql-infra.md#sqli-18). Storage policies live in one frozen superuser file with no forward path, so a policy change has no migration to go in [SQLI-07](findings/sql-infra.md#sqli-07).
- **Today.** 15 of 53 migrations rewrite data or rebuild constraints without these notes; 3 describe lock or backfill behavior.
- **Enforce.** Check `migration_headers`: every migration sorted after `20261108000053_routine_removal.sql` that contains `update`, `delete`, a constraint swap or an index build carries the three lines. Applied files stay byte-identical, as the installer's checksum requires.
- **Adopt.** Error now; it applies only to future files. Document the conventions in `supabase/README.md` ([STD-26](#std-26)).

### <a id="std-41"></a>STD-41. Grants, RLS and indexes are checked from the catalog

- **Rule (MUST).** One db check asserts invariants over the catalog, not case by case: RLS on every public table with a member SELECT policy and a runtime policy; no INSERT, UPDATE or DELETE for `authenticated` outside an allowlist; no `anon` privilege in `public`, `app_private` or `agent_runtime`; `search_path` pinned on every definer function; DELETE for the runtime role only where the service deletes; an index behind every run-scoped lookup column.
- **Why here.** The runtime role can delete runs, and the cascade reaches the receipt ledger [SQLI-01](findings/sql-infra.md#sqli-01). RLS and grant conventions are checked case by case, never from the catalog [SQLI-05](findings/sql-infra.md#sqli-05). A harness guard reads only the first grant of one migration [THRN-01](findings/harness-tests.md#thrn-01). Run-scoped lookups scan unindexed columns [SQLI-08](findings/sql-infra.md#sqli-08). Also [SQLI-06](findings/sql-infra.md#sqli-06), [SQLI-13](findings/sql-infra.md#sqli-13), [SQLI-14](findings/sql-infra.md#sqli-14).
- **Today.** All 24 public tables enable RLS with both policies, and all 9 functions pin `search_path`, checked only by named cases in `scripts/app_db.py`. The runtime role holds DELETE on 5 tables, while the service deletes only from `workflow_drafts`. 5 lookups are unindexed.
- **Enforce.** `tests/db/catalog_check.py`, run by `app_db.py` in the db profile on the disposable stack after migrations and bootstrap, querying `pg_class.relrowsecurity`, `pg_policies`, `has_table_privilege`, `has_function_privilege` and `pg_index`.
- **Adopt.** Revoke the extra DELETE grants in a forward migration, moving the qualifier's arranged deletes to the admin connection in the same change ([SQLI-01](findings/sql-infra.md#sqli-01)); add the missing indexes the same way; then run the check with an empty allowlist beyond `workflow_drafts`. Persistent apply stays an explicit guarded operation.

### <a id="std-42"></a>STD-42. SQL vocabularies and predicates have one source

- **Rule (SHOULD).** A vocabulary that SQL owns, such as approved profiles or a status CHECK, is declared once in SQL and mirrored in Python as a StrEnum or Literal with a db parity check, so SQL stays the owner. A repeated predicate (terminal run, run plus descendants, run spend) has one named SQL function or one Python fragment. Python passes status sets as parameters ([STD-14](#std-14)).
- **Why here.** Approved profiles are restated in three CHECK constraints at every change [SQLI-03](findings/sql-infra.md#sqli-03). The terminal predicate is spelled out nine times [SQLI-17](findings/sql-infra.md#sqli-17). Run spend and "run plus descendants" are rewritten in SQL text, with two tree definitions that disagree [XDUP-05](findings/sweep-duplication.md#xdup-05). Also [XDUP-09](findings/sweep-duplication.md#xdup-09), [XDUP-10](findings/sweep-duplication.md#xdup-10), [XWEB-04](findings/sweep-web-architecture.md#xweb-04), [SQLI-12](findings/sql-infra.md#sqli-12), [SQLI-16](findings/sql-infra.md#sqli-16).
- **Today.** Profiles in 3 constraints; the terminal predicate 9 times in SQL; the terminal set restated 11 times across Python, TypeScript and scripts; 4 copies of the ledger SQL and 4 of the subtree query.
- **Enforce.** A parity case in tests/db comparing each mirrored enum with its CHECK constraint, and check `sql_status_literals`: quoted run-status lists inside Python SQL strings (baseline 6, the Python share of [XDUP-09](findings/sweep-duplication.md#xdup-09)).
- **Adopt.** Parity first. New shared SQL functions arrive by forward migration only.

## 12. Tests

### <a id="std-43"></a>STD-43. Every test file belongs to a runner, and the runners are documented

- **Rule (MUST).** Runners select test files by glob, never by name. Each test file is claimed by a runner or listed as manual with a reason. Browser specs are grouped by Playwright projects per environment rather than filename substrings. A short decision records the five test mechanisms and why each exists, including node:test in place of the Vitest and React Testing Library that [DH-06](../../PRD/PRD-Development-Harness.md#nextjs-and-typescript) names.
- **Why here.** Hand-kept test lists let tests drop out unseen: `schema-value.test.ts` runs in no profile although an archived verification cites it as passing [XTOL-02](findings/sweep-tooling.md#xtol-02), [WSHL-08](findings/web-shell.md#wshl-08), [XWEB-15](findings/sweep-web-architecture.md#xweb-15). The static pin and launcher guards run in no profile [THRN-02](findings/harness-tests.md#thrn-02). Suites hand state to each other through alphabetical file order and filename selection [TWEB-01](findings/web-tests.md#tweb-01). The visual walk's inventory says the app has no dialogs or charts and leaves seven routes unmeasured [TWEB-09](findings/web-tests.md#tweb-09). Also [XTOL-10](findings/sweep-tooling.md#xtol-10), [WSHL-10](findings/web-shell.md#wshl-10).
- **Today.** Skips and empty suites never pass (**enforced** by [scripts/verify.py:91-107](../../../scripts/verify.py#L91)). `schema-value.test.ts` and `test_manifests.py` run in no profile, nor does the static Launchers class in `test_non_mutating.py` [THRN-02](findings/harness-tests.md#thrn-02); 28 Playwright name filters live in four scripts; no decision covers the runners.
- **Enforce.** `Step('web_unit_tests', (node, '--test', 'apps/web/tests/unit/**/*.test.ts'), root)` in place of the named files at [scripts/verify.py:161-162](../../../scripts/verify.py#L161), the manifest tests added to the offline toolchain step, and check `test_ownership`: every test file matches a runner glob or a `MANUAL` entry, with a fixture proving an unclaimed file is reported.
- **Adopt.** Globs and the ownership check now. Write the decision record ([DH-09](../../PRD/PRD-Development-Harness.md#dh-09-verification-profiles-and-completion-rules) keeps exceptions in concise ADRs). Adopting Vitest would be a pinned, repo-local install inside its own story.

### <a id="std-44"></a>STD-44. Tests drive public seams

- **Rule (MUST).** Tests use public functions and injected collaborators: keyword-only parameters whose defaults keep production behavior, or narrow Protocols that fakes satisfy without suppressions. No test imports or patches a private name; a seam a test needs gets a public, documented name.
- **Why here.** Paid-path tests replace private LoopMiddleware and ProviderSettings internals [PTST-01](findings/py-tests.md#ptst-01). Db checks import and patch 21 private product names that no fast check reads, so a rename surfaces only in the slow db profile [TDBC-02](findings/db-tests.md#tdbc-02), [XTOL-03](findings/sweep-tooling.md#xtol-03). Test doubles need suppressions because collaborators are typed as concrete classes [XTYP-17](findings/sweep-types.md#xtyp-17). The worker's serve loop opens its own connections, so drain and reconnect are tested only against Docker Postgres [POPS-19](findings/py-ops.md#pops-19). Fixture models take commands through untyped goal text [TDBC-15](findings/db-tests.md#tdbc-15). Also [PRUN-17](findings/py-run.md#prun-17), [XMOD-07](findings/sweep-boundaries.md#xmod-07), [PTST-06](findings/py-tests.md#ptst-06).
- **Today.** 34 private-name imports in tests (16 in services/agent/tests, 18 in tests/db); 26 private overrides on the paid path; 21 `arg-type` suppressions on fakes in 8 test files.
- **Enforce.** The private-import part of check `layer_imports` ([STD-01](#std-01)), and the import-contract check ([STD-48](#std-48)), which makes a renamed name fail in seconds.
- **Adopt.** Add the seams beside the current overrides, write the seam-based tests, then delete the overrides; the baseline falls as each lands.

### <a id="std-45"></a>STD-45. Evaluate once, judge that value, fail readably

- **Rule (MUST).** A check evaluates the observed value once and judges that value, never a second call. A refusal check expects the specific exception or code. A list assertion prints the list on failure. Cases are parametrized or wrapped in `subTest`, not hidden in loops and branches. Tests assert behavior, not source text.
- **Why here.** Checks compute the shown value and the verdict with separate calls, so some can pass broken; 5 of the double calls change state [TDBC-01](findings/db-tests.md#tdbc-01). Refusal checks accept any exception [TDBC-07](findings/db-tests.md#tdbc-07). Most error-list assertions fail with only "False is not true" [THRN-11](findings/harness-tests.md#thrn-11). Arrangements whose failures are never checked let qualifier cases pass vacuously [SCRP-09](findings/scripts.md#scrp-09). Three hook tests' names and assertions disagree [THRN-06](findings/harness-tests.md#thrn-06). Also [THRN-12](findings/harness-tests.md#thrn-12), [PTST-08](findings/py-tests.md#ptst-08), [PTST-17](findings/py-tests.md#ptst-17), [TWEB-08](findings/web-tests.md#tweb-08).
- **Today.** 80 double-evaluation calls in 20 files; 8 any-exception refusal checks; 47 `assertTrue(any(...))` without a message; 5 source-text tests in tests/harness and 5 in services/agent/tests; 25 hidden cases.
- **Enforce.** The shared check API takes the value and a predicate, `case(name, expected, observed, predicate)`, so a second evaluation cannot be written ([STD-46](#std-46)). Check `bare_assertions`: `assertTrue(any(...))` without `msg` in tests/harness and tests/toolchain (baseline 47).
- **Adopt.** Fix the five state-changing double calls now. Convert the rest as checks move to the shared module.

### <a id="std-46"></a>STD-46. Tests share support modules instead of copying helpers

- **Rule (MUST).** tests/db checks use one check module; browser specs use `apps/web/tests/browser/support/` (sign-in per role, CSRF headers, provider key, admission, axe); service tests share fakes for OpenRouter replies, SQL connections and API setup through a support package.
- **Why here.** No shared check module exists; the case protocol and setup are copied into every script [TDBC-03](findings/db-tests.md#tdbc-03). 38 specs carry about 747 lines of copied helpers [TWEB-02](findings/web-tests.md#tweb-02), [XDUP-15](findings/sweep-duplication.md#xdup-15). Copied runners and fakes have drifted [XDUP-14](findings/sweep-duplication.md#xdup-14), [PTST-02](findings/py-tests.md#ptst-02), [PTST-09](findings/py-tests.md#ptst-09), and the shared fake transport still encodes the superseded two-profile policy [PTST-03](findings/py-tests.md#ptst-03). A crash ends every later scenario, and 26 of 43 check scripts then print nothing [TDBC-04](findings/db-tests.md#tdbc-04); checks also arrange browser-suite state and run static scans [TDBC-10](findings/db-tests.md#tdbc-10). Also [PTST-10](findings/py-tests.md#ptst-10), [PTST-11](findings/py-tests.md#ptst-11), [PTST-13](findings/py-tests.md#ptst-13), [PTST-14](findings/py-tests.md#ptst-14), [THRN-08](findings/harness-tests.md#thrn-08), [THRN-09](findings/harness-tests.md#thrn-09), [THRN-10](findings/harness-tests.md#thrn-10), [TWEB-10](findings/web-tests.md#tweb-10), [TWEB-13](findings/web-tests.md#tweb-13).
- **Today.** 42 tests/db files define their own `check()`, in six truncation variants; 64 helper declarations in 36 specs (36 `signIn`, 14 `write`, 5 `ensureKey`, 3 `admit` and 6 others); 11 leak deny-lists in 9 spec files.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: SPECS, ignoring tests/browser/support/**
  { selector: "FunctionDeclaration[id.name=/^(signIn|signInWithKey|write|csrf|headers|saveKey|ensureKey|admit|finishedRun)$/]", message: "Import this helper from tests/browser/support/ (STD-46)." },
  ```
  and check `copies`: top-level `def check(` definitions in tests/db outside the shared module (baseline 42).
- **Adopt.** Create the support modules, then the rules with today's counts. New files must use them; old files migrate when touched, largest first. The DH-W04 expected and observed shape stays, so `app_db.py` parses the output unchanged.

### <a id="std-47"></a>STD-47. Tests are deterministic and isolated

- **Rule (MUST).** Controlled clocks and injected transports, never real sleeps ([DH-06](../../PRD/PRD-Development-Harness.md#python-api-domain-and-workers)). Specs wait for conditions, never `waitForTimeout` or `networkidle`, and locate by role, label or a `data-field` hook, never XPath. Each spec arranges and restores its own state through fixtures, and a file whose tests depend on each other is serial. Every child process has a timeout; browser contexts, temporary directories and patched globals are released. A missing prerequisite fails as unavailable, never as a product failure [TWEB-14](findings/web-tests.md#tweb-14), and a failed spec keeps a Playwright trace [TWEB-15](findings/web-tests.md#tweb-15).
- **Why here.** Fixed sleeps and `networkidle` add about 50 seconds [TWEB-06](findings/web-tests.md#tweb-06). Suites hand state to each other through file order [TWEB-01](findings/web-tests.md#tweb-01), [TWEB-07](findings/web-tests.md#tweb-07). Fourteen child processes in the harness tests have no timeout under a shared 60-second cap [THRN-07](findings/harness-tests.md#thrn-07), [TWEB-11](findings/web-tests.md#tweb-11). Also [PTST-18](findings/py-tests.md#ptst-18), [PTST-07](findings/py-tests.md#ptst-07), [THRN-16](findings/harness-tests.md#thrn-16), [THRN-17](findings/harness-tests.md#thrn-17), [TDBC-05](findings/db-tests.md#tdbc-05), [TDBC-13](findings/db-tests.md#tdbc-13), [TWEB-16](findings/web-tests.md#tweb-16), [TWEB-17](findings/web-tests.md#tweb-17), [PTST-12](findings/py-tests.md#ptst-12).
- **Today.** The service's socket guard and fake transports are **enforced**: default tests reject paid calls (fault fixtures prove it). Specs hold 14 `waitForTimeout` in 9 files, 16 `networkidle` in 5 and 1 XPath. 24 `subprocess` calls in repository-level Python have no timeout (13 in tests/harness, 8 in scripts, 3 elsewhere). 22 browser contexts are never closed.
- **Enforce.**

  ```js
  // apps/web/eslint.config.mjs, files: SPECS, ignoring tests/browser/support/**
  { selector: "CallExpression[callee.property.name='waitForTimeout']", message: "Wait for a condition, not a fixed time (STD-47)." },
  { selector: "Literal[value='networkidle']", message: "Wait for the element or response the test needs (STD-47)." },
  { selector: "Literal[value=/^xpath=/]", message: "Locate by role, label or a data-field hook (STD-47)." },
  ```
  and check `subprocess_timeouts` (baseline 24).
- **Adopt.** Errors with the 31 spec sites and 24 calls baselined. Python async tests use `@pytest.mark.asyncio` (strict mode is configured); `asyncio.run` stays only in sync tests that need it, with a comment ([PTST-12](findings/py-tests.md#ptst-12)).

## 13. Scripts and tooling

### <a id="std-48"></a>STD-48. Repository-level Python is linted, formatted, typed and import-checked

- **Rule (MUST).** scripts/, tests/ and .claude/hooks/ run under the shared ruff configuration in fast and full, with a check domain so the Stop hook and the PostToolUse diagnostic cover them. mypy strict covers the hook's trust boundary (`dispatch.py`, `harness_lib.py`, `verify.py`, `specs.py`, `evidence.py`, `toolchain.py`), then the other scripts. Every name that tests/ and scripts/ import from `autobots` is resolved statically on every profile.
- **Why here.** The code that decides whether every other check passed, and the guarded persistent install, have no static check; defects surface as wrong verdicts or on the real install [XTOL-01](findings/sweep-tooling.md#xtol-01), [SCRP-04](findings/scripts.md#scrp-04), [XTYP-12](findings/sweep-types.md#xtyp-12). A service rename passes fast and breaks only inside the next db run, about 610 s later [XTOL-03](findings/sweep-tooling.md#xtol-03). Two lint rules are enforced only as tests, where a linter would report them at edit time [THRN-18](findings/harness-tests.md#thrn-18). Also [TDBC-08](findings/db-tests.md#tdbc-08), [THRN-14](findings/harness-tests.md#thrn-14).
- **Today.** 133 files and 25,788 lines, 42% of the in-scope Python, run under no gate ([metrics.md section 6](metrics.md#6-repository-level-python)). The shared configuration reports 474 hits there, 418 with safe fixes. Strict mypy reports 56 errors in the six trust-boundary modules, 31 of them bare generics (`type-arg`). 881 names in 68 files are imported from `autobots`, 25 `type: ignore` comments serve no checker, and 14 of those come from one `object` return type in `persistent_install.py`. The PostToolUse diagnostic runs ruff only for the python domain ([.claude/hooks/dispatch.py:161](../../../.claude/hooks/dispatch.py#L161)); `ruff check` and mypy run only inside services/agent ([scripts/toolchain.py:210-213](../../../scripts/toolchain.py#L210)).
- **Enforce.**

  ```python
  # scripts/toolchain.py check_steps, run from the repository root
  Step("repo_ruff_check", (str(venv_bin / "ruff"), "check", "scripts", "tests", ".claude/hooks"), root),
  Step("repo_mypy", (str(venv_bin / "mypy"), "--strict", ".claude/hooks/dispatch.py", "scripts/harness_lib.py",
                     "scripts/verify.py", "scripts/specs.py", "scripts/evidence.py", "scripts/toolchain.py"), root, LONG),
  # scripts/harness_lib.py: a domain for repository-level Python that fast and the Stop hook require
  REPO_PYTHON_STEPS = frozenset({"repo_ruff_check", "repo_mypy"})
  ```
  The mypy step needs `MYPYPATH=scripts:services/agent/src` in its environment. The import-contract check resolves each `from autobots... import name` in tests/ and scripts/ against services/agent/src with `ast`, with a fixture proving a missing name is reported.
- **Adopt.** Report with `ruff check --exit-zero --statistics`. Apply the 418 safe fixes in one explicit commit after the selection is settled ([STD-25](#std-25)). Gate with E501 ignored ([STD-27](#std-27)). Fix the 56 mypy errors, then gate the six modules; widen mypy module by module with an overrides list that only shrinks. The harness profile stays install-free, so these steps run in fast and full with the prepared tools ([AGENTS.md](../../../AGENTS.md)).

### <a id="std-49"></a>STD-49. Gates keep their settings and run without being asked

- **Rule (MUST).** A test asserts the agreed gate settings, and an altered copy of each proves a weakening is caught. The TypeScript fault cases compile through a fixture tsconfig that extends `apps/web/tsconfig.json`. An opt-in Git hook runs the fast profile before a commit, and `make check-fast` exists beside `make check`.
- **Why here.** Deleting `strict = true`, a selected code or `--max-warnings=0` would still pass every profile [XTOL-09](findings/sweep-tooling.md#xtol-09). No CI or Git hook runs any profile, and `make check` covers only the harness [XTOL-11](findings/sweep-tooling.md#xtol-11). [DH-04](../../PRD/PRD-Development-Harness.md#dh-04-skills-and-specialist-agents) forbids approving a failed gate by changing thresholds.
- **Today.** These settings are **enforced** by their tools: TypeScript strict with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` ([apps/web/tsconfig.json:7-9](../../../apps/web/tsconfig.json#L7)), lint failing on any warning ([apps/web/package.json:6](../../../apps/web/package.json#L6)), mypy strict and pytest `--strict-markers --strict-config` ([services/agent/pyproject.toml:49-59](../../../services/agent/pyproject.toml#L49)). `.claude/settings.json` is already guarded key by key. Nothing guards the rest, and the tsc fault cases pass their own flags ([scripts/qualify_faults.py:46-48](../../../scripts/qualify_faults.py#L46)).
- **Enforce.** Check `gate_settings` (stdlib `json` and `tomllib`): the three compiler flags, `--max-warnings=0`, mypy `strict`, the shared ruff selection and the pytest options, each with an altered copy. And:

  ```sh
  #!/bin/sh
  # .githooks/pre-commit. Opt in with: git config core.hooksPath .githooks
  # DH-05: the same runner as the assistant hooks; bypassable, so never the completion check.
  exec python3.12 scripts/verify.py --profile fast
  ```
- **Adopt.** The settings check now. The Git hook is an explicit opt-in documented in the harness runbook, never a silent configuration change; db and operations stay manual because they start disposable Docker projects.

### <a id="std-50"></a>STD-50. Scripts share one runner, stack lifecycle, paid guard and report writer

- **Rule (MUST).** One process runner (own session, group kill on timeout, bounded output, named timeout constant) serves `verify.py`, `toolchain.py` and the qualifiers. One `run_child_check` replays a child check's cases and records a failed case when the child fails or prints nothing. One `disposable_app_stack` context manager and one `write_report` serve every qualifier. One paid guard, with the strictest of today's behaviors, serves every paid entry point. One exit-code module and one `Unavailable` class keep 0, 1 and 2. One dotenv parser follows the app's quoting rules.
- **Why here.** The child-check runner is hand-copied 29 times, with divergent failure handling [SCRP-01](findings/scripts.md#scrp-01). Paid-run guards are copied across four entry points and already disagree [SCRP-03](findings/scripts.md#scrp-03). The disposable-stack skeleton is copied into 13 entry points [SCRP-07](findings/scripts.md#scrp-07), [XDUP-13](findings/sweep-duplication.md#xdup-13). Two unrelated `Unavailable` classes break the exit-code contract [SCRP-08](findings/scripts.md#scrp-08). `verify.py` keeps a weaker runner whose timeout leaves descendants alive [XTOL-16](findings/sweep-tooling.md#xtol-16). Also [SCRP-06](findings/scripts.md#scrp-06), [SCRP-10](findings/scripts.md#scrp-10), [SCRP-12](findings/scripts.md#scrp-12), [SCRP-13](findings/scripts.md#scrp-13), [SCRP-14](findings/scripts.md#scrp-14), [SCRP-16](findings/scripts.md#scrp-16), [SCRP-17](findings/scripts.md#scrp-17), [SCRP-18](findings/scripts.md#scrp-18), [SQLI-10](findings/sql-infra.md#sqli-10), [SQLI-11](findings/sql-infra.md#sqli-11).
- **Today.** The ownership guard inside `disposable_db.remove_stack` is shared by all copies, and the 0/1/2 exit contract holds in `verify.py`, `toolchain.py` and `qualify_faults.py` (**enforced**). 29 replay copies, 15 copied stack lifecycles, 4 paid guards, three process runners of which only two end the whole process group, 2 `Unavailable` classes and 3 dotenv parsers.
- **Enforce.** Check `copies`: the replay statement in scripts (baseline 29), `class Unavailable` definitions (2) and paid-guard `helper()` copies (4), each allowed only to fall.
- **Adopt.** Extract pure decisions with tests first, as [SCRP-03](findings/scripts.md#scrp-03) asks, then the shared modules. Never weaken a guard: the merged paid guard keeps the `--paid` refusal, the reservation before any request and the strictest unreadable-spend behavior.

## 14. Enforcement and ratchet

### <a id="std-51"></a>STD-51. Report, then baseline, then error, and never loosen

- **Rule (MUST).** Every new check passes through three steps. **Report:** measure without failing. **Baseline:** record today's violations in a form that can only shrink. **Error:** fail on anything new. No one raises a threshold, adds a baseline entry or deletes a check to pass a gate ([DH-04](../../PRD/PRD-Development-Harness.md#dh-04-skills-and-specialist-agents)). Every blocking rule is proven by a known-bad fixture.
- **Why here.** Most fixes are configuration with zero or small baselines, and ruff's RUF100 and ESLint's bulk suppressions make those baselines shrink-only [XTOL-05](findings/sweep-tooling.md#xtol-05). `--max-warnings=0` makes a warn-level rule fail lint, so "warn" cannot live inside the gate.
- **Today.** Fault fixtures already prove ruff (F401), mypy, pytest, tsc (TS2322) and ESLint (`no-explicit-any`) bite, counting a fixture only when it fails with its expected marker (**enforced** in full by `scripts/qualify_faults.py`).
- **Enforce.**

  | Tool | Report | Baseline | Error |
  |---|---|---|---|
  | ruff | `ruff check --exit-zero --statistics` | `ruff check --add-noqa="- baseline 2026-11-12 (STD-nn)"`, then RUF100 fails on a stale marker; per-directory ignores only where the count is in the hundreds (STD-13) | the rule in `select` |
  | ESLint | `lint:report`: `eslint --max-warnings=-1 --pass-on-unpruned-suppressions --rule 'complexity: [warn, 10]' ...` | `eslint --suppress-rule <rule> .` writes `eslint-suppressions.json`; a suppression that no longer matches fails unless pruned with `--prune-suppressions` | the rule at `"error"` |
  | Convention checks | `python3.12 -m unittest discover -s tests/harness -p test_conventions.py -v` | `tests/harness/conventions_baseline.json`: per check and file, a count that may fall; a stale entry fails, so it is lowered in the same change | a count over its baseline |

  The convention checks live in one stdlib module, `tests/harness/test_conventions.py`, so they run in every profile, harness included, and each has a fixture proving it catches a violation, in the style of `test_shared_form_controls.py`. ESLint suppression counts are per file and rule, so selectors sharing `no-restricted-syntax` share one budget per file; review watches for one kind of violation traded for another. For a path-scoped ESLint rule, the fault case lints its fixture through stdin under a scoped name: `eslint --stdin --stdin-filename components/fault.tsx --parser-options projectService:false` with the four type-aware rules turned off (checked).
- **Adopt.** In this order. (1) Rules with no hits, as errors: domain bans, DTZ, S602, S604, S605, PGH003, PGH004, ERA001, TID251, D100, D104, N in the service, S110, S112, `max-depth`, the import zones, the three zero-hit type-aware rules, `rule_scopes` after its 5 fixes, `migration_headers`, `file_names`. (2) Calibrated limits and markers with baselines: STD-05 to STD-08, BLE001 (STD-19) and PLC0415 (STD-01), whose markers carry reasons. (3) The repository-level lint gate (STD-48), then the reformat (STD-27). (4) Rules that need a shared module first, each turned on when its module lands: STD-10 and STD-11 with the refusal helper, STD-22 and STD-32 with the hooks, STD-12's map selector with the lib vocabularies, STD-35 and STD-46 with the spec support folder. The harness check runner gets a named timeout before the convention checks are added ([XTOL-16](findings/sweep-tooling.md#xtol-16)), because the harness suite already uses 24 to 27 of its 60 seconds.

### Target configuration

These files were validated together on 2026-11-12: the ruff files with ruff 0.17.3 on a scratch tree and with `--config` against this repository, and the ESLint file with ESLint 9.39.5 and the eslint-config-next 16.4.5 plugins from apps/web (typescript-eslint 8.72.1 with TypeScript 6.0.3, eslint-plugin-import 2.32.0). The fault fixtures still behave: the good ones pass and the bad ones fail with F401 and `no-explicit-any`.

**ruff.toml** (repository root, new). The service extends it, so `scripts/qualify_faults.py`, which passes `--config services/agent/pyproject.toml` with explicit fixture paths, still sees F401 on the bad fixture.

```toml
# The shared Python standard. services/agent/pyproject.toml extends it.
target-version = "py312"
line-length = 100
src = ["scripts", "services/agent/src"]
extend-exclude = ["tests/faults/python/bad_*"]   # deliberately bad fixtures (tests/faults/README.md)

[lint]
select = [
  "E", "F", "W", "I", "B", "UP", "ASYNC", "RUF",            # the service's selection today
  "DTZ", "S602", "S604", "S605", "PGH003", "PGH004",         # 0 hits in all Python
  "ERA001", "N", "TID251", "D100", "D104",                   # 0 hits in services/agent; 3 N806 in tests/db
  "BLE001", "S110", "S112",                                  # 27 broad catches, each with a reasoned noqa
]
ignore = ["N818"]   # exception names state the outcome, e.g. ProfileNotOffered

[lint.flake8-tidy-imports.banned-api]
"anthropic".msg = "Owned code never imports the unused provider SDKs (user decision, 2026-11-05)."
"langchain_anthropic".msg = "Owned code never imports the unused provider SDKs (user decision, 2026-11-05)."
"google".msg = "Owned code never imports the unused provider SDKs (user decision, 2026-11-05)."
"langchain_google_genai".msg = "Owned code never imports the unused provider SDKs (user decision, 2026-11-05)."
"openai".msg = "Application inference is OpenRouter only (AGENTS.md)."
"langchain_openai".msg = "Application inference is OpenRouter only (AGENTS.md)."

[lint.per-file-ignores]
"scripts/**" = ["E501"]                  # until the one-time reformat (STD-27)
"tests/**" = ["E501"]
".claude/hooks/**" = ["E501"]
"tests/faults/**" = ["D100", "D104"]     # minimal fixtures
```

**services/agent/pyproject.toml**, replacing the `[tool.ruff]` and `[tool.ruff.lint]` tables at [services/agent/pyproject.toml:41-47](../../../services/agent/pyproject.toml#L41). Stage 2 lines are marked.

```toml
[tool.ruff]
extend = "../../ruff.toml"
src = ["src", "tests"]

[tool.ruff.lint]
extend-select = ["C90", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917", "PLC0415"]
# stage 2: add "ANN401", "FAST" and "PLR2004", with the per-file ignores below

[tool.ruff.lint.mccabe]
max-complexity = 15

[tool.ruff.lint.pylint]
max-args = 8
max-positional-args = 6
max-branches = 15
max-statements = 60
max-returns = 8

[tool.ruff.lint.extend-per-file-ignores]   # stage 2
"src/autobots/{application,adapters,operations}/**" = ["ANN401"]
"tests/**" = ["ANN401", "PLR2004"]
```

With this selection, services/agent reports 141 hits at stage 1 (PLC0415 78, BLE001 22 and the 41 size and parameter hits), all baselined by `--add-noqa`; stage 2 adds FAST001 78, PLR2004 52 and ANN401 21. The table must be `extend-per-file-ignores`: a plain `per-file-ignores` here replaces the root's table, which drops the fault fixtures' D100 exemption, and `qualify_faults.py`'s good Python fixture then fails (checked).

**services/agent/src/autobots/contracts/ruff.toml** (new; 1 hit until `export.py` moves). `domain/ruff.toml` is shown in [STD-01](#std-01).

```toml
extend = "../../../pyproject.toml"

[lint.flake8-tidy-imports.extend-banned-api]
"autobots.api".msg = "contracts/ is a leaf over domain/ (DH-06); export the OpenAPI document from api/."
"autobots.application".msg = "contracts/ is a leaf over domain/ (DH-06)."
"autobots.adapters".msg = "contracts/ is a leaf over domain/ (DH-06)."
"autobots.operations".msg = "contracts/ is a leaf over domain/ (DH-06)."
"fastapi".msg = "contracts/ holds Pydantic models only."
"psycopg".msg = "contracts/ holds Pydantic models only."
"os.environ".msg = "Entry points read configuration and pass it in (STD-38)."
```

`extend-banned-api` adds to the inherited bans; `banned-api` in a nested file would replace them and drop the SDK bans (checked).

**apps/web/eslint.config.mjs**, replacing [apps/web/eslint.config.mjs:1-10](../../../apps/web/eslint.config.mjs#L1).

```js
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Patterns are relative to apps/web. qualify_faults.py lints fixtures from the repository root,
// where these patterns match nothing, so the fault cases keep the presets only.
const SOURCE = ["app/**/*.{ts,tsx}", "components/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}", "hooks/**/*.{ts,tsx}"];
const SPECS = ["tests/browser/**/*.ts"];
const TESTS = ["tests/unit/**/*.ts", ...SPECS];

const PARSED = "Parse API replies with a generated parse* function or the lib/ refusal helper, never a type assertion (DH-06).";
const TYPED = "Type the body with its generated request type: `({ ... }) satisfies RunRequest` (DH-06).";
const CONTRACT = [
  { selector: "TSAsExpression:has(CallExpression[callee.property.name='json'])", message: PARSED },
  { selector: "TSAsExpression > CallExpression[callee.object.name='JSON'][callee.property.name='parse']", message: PARSED },
  { selector: "Property[key.name='body'] > CallExpression[callee.object.name='JSON'][callee.property.name='stringify'] > ObjectExpression", message: TYPED },
];
const SCREENS = [
  { selector: "ExportNamedDeclaration > FunctionDeclaration[id.name=/^(?!use[A-Z])[a-z]/]", message: "Component files export components; move helpers to lib/ (STD-33)." },
  { selector: "ExportNamedDeclaration > VariableDeclaration > VariableDeclarator[id.name=/^[A-Z][A-Z0-9_]+$/]", message: "Shared vocabulary lives in lib/, keyed by generated types (STD-12)." },
  { selector: "CallExpression[callee.property.name='catch'] > ArrowFunctionExpression[params.length=0]", message: "Keep the failure kind: use the shared loader or refusal helper (STD-22)." },
  { selector: "VariableDeclarator > Identifier > TSTypeAnnotation > TSTypeReference[typeName.name='Record'] > TSTypeParameterInstantiation > TSStringKeyword:first-child", message: "Key label maps by the generated union: `satisfies Record<RunStatus, string>` (STD-12)." },
];
const SPEC_RULES = [
  { selector: "CallExpression[callee.property.name='waitForTimeout']", message: "Wait for a condition, not a fixed time (STD-47)." },
  { selector: "Literal[value='networkidle']", message: "Wait for the element or response the test needs (STD-47)." },
  { selector: "Literal[value=/^xpath=/]", message: "Locate by role, label or a data-field hook (STD-47)." },
  { selector: "FunctionDeclaration[id.name=/^(signIn|signInWithKey|write|csrf|headers|saveKey|ensureKey|admit|finishedRun)$/]", message: "Import this helper from tests/browser/support/ (STD-46)." },
];

const config = [
  { ignores: [".next/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    files: [...SOURCE, ...SPECS],
    rules: {
      complexity: ["error", 15],
      "max-depth": ["error", 4],
      "max-params": ["error", 4],
      "max-lines-per-function": ["error", { max: 150, skipBlankLines: true, skipComments: true }],
      "max-lines": ["error", { max: 400, skipBlankLines: true, skipComments: true }],
    },
  },
  {
    files: SOURCE,
    rules: {
      "import/no-cycle": ["error", { maxDepth: 10 }],
      "import/no-restricted-paths": ["error", { zones: [
        { target: "./components/ui/**/*", from: ["./components/*.tsx", "./app/**/*"], message: "UI primitives stay feature-free." },
        { target: "./lib/**/*", from: ["./components/**/*", "./app/**/*"], message: "lib/ never imports UI or routes." },
        { target: "./components/**/*", from: ["./app/**/*"], message: "Screens never import route modules." },
      ] }],
      "no-restricted-syntax": ["error", ...CONTRACT],
    },
  },
  {
    files: ["components/**/*.{ts,tsx}"],
    ignores: ["components/ui/**"],
    rules: {
      "no-restricted-syntax": ["error", ...CONTRACT, ...SCREENS],
      "no-restricted-globals": ["error", { name: "fetch", message: "Read through hooks/use-resource.ts (STD-32)." }],
      "no-restricted-imports": ["error", { paths: [{ name: "@/lib/csrf-fetch", message: "Write through hooks/use-submit.ts (STD-32)." }] }],
    },
  },
  {
    files: [...SOURCE, ...TESTS],
    languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
    rules: {
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-unnecessary-type-assertion": "error",
    },
  },
  { files: ["tests/unit/**/*.ts"], rules: { "@typescript-eslint/no-floating-promises": "off" } },
  {
    files: SPECS,
    ignores: ["tests/browser/support/**"],
    rules: {
      "no-restricted-syntax": ["error", ...SPEC_RULES],
      "no-restricted-imports": ["error", { paths: [{ name: "@axe-core/playwright", message: "Use support/a11y.ts, which applies Decision 0010's tags (STD-35)." }] }],
    },
  },
];

export default config;
```

With every rule on at once, this configuration reports: complexity 12, `max-lines` 16, `max-lines-per-function` 26, `max-params` 1, `import/no-cycle` 2, `no-unnecessary-type-assertion` 13, `no-restricted-globals` 45, `no-restricted-imports` 45 (19 csrf, 26 axe) and `no-restricted-syntax` 278. Commit each rule when its step in STD-51 comes, with its baseline; until then it stays out of the file. `linterOptions: { reportUnusedDisableDirectives: "error" }` belongs in the first object once a disable comment exists (STD-25).

**.editorconfig** (new)

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true

[*.py]
indent_size = 4
max_line_length = 100

[*.{ts,tsx,mjs,json,css}]
indent_size = 2
max_line_length = 80
```

### Rules considered and not proposed

- **ruff `ALL`.** It is an exploratory superset. Its largest groups are COM812 (438, which conflicts with the formatter), D1 (over 600, mostly small obvious functions; STD-24 targets risk instead), EM101 and TRY003 (425, style only) and CPY001 (139, no licensing need) ([metrics.md section 5](metrics.md#5-python-rule-superset---select-all-servicesagentsrc)).
- **PLC2701 (private-name import) and PLR1702 (nesting).** Both are preview rules in ruff 0.17.3, and enabling preview changes other rules' behavior; the `layer_imports` check covers private names instead.
- **A ruff ban on `httpx.AsyncClient`.** banned-api also flags type annotations, so it reports references, not constructions (STD-39).
- **ESLint `max-statements` (43 hits at 25) and `react/no-multi-comp` (38).** Function length and complexity already measure the same code, and small private components in a file are not a defect.
- **`@typescript-eslint/consistent-type-assertions` with `assertionStyle: "never"` as a gate.** It reports 44 source sites. STD-10's selector covers the 30 over `.json()` and `JSON.parse`, 5 compensate for weak generated map types and go with STD-18, and the rest narrow DOM events, URLs and `unknown` input [XTYP-01](findings/sweep-types.md#xtyp-01). The full rule stays in `lint:report`.
- **Coverage percentages.** DH-09 rules out arbitrary coverage quotas; STD-43 to STD-47 measure ownership and test design instead.

### Counts added for this document

Read-only, at revision d0d85d3 with the two untracked review folders. Scratch configuration files lived outside the repository; nothing in the repository was written except this file.

```sh
# Python, from services/agent (stage 1 selection and starting thresholds)
.venv/bin/ruff check --no-cache --exit-zero --statistics --select C901,PLR0911,PLR0912,PLR0913,PLR0915,PLR0917 \
  --config 'lint.mccabe.max-complexity = 15' --config 'lint.pylint.max-args = 8' --config 'lint.pylint.max-positional-args = 6' \
  --config 'lint.pylint.max-branches = 15' --config 'lint.pylint.max-statements = 60' --config 'lint.pylint.max-returns = 8' src tests
.venv/bin/ruff check --no-cache --exit-zero --statistics --select BLE001,S110,S112,DTZ,S602,S604,S605,ERA001,N,D100,D104,PGH003,PGH004,FAST,PLR2004,PLC0415,ANN401 src
.venv/bin/ruff check --no-cache --exit-zero --output-format concise --select ANN401 src    # grouped by layer
# Repository-level Python, from the root, with the target ruff.toml passed by --config (relative paths resolve to the root)
services/agent/.venv/bin/ruff check --no-cache --exit-zero --statistics --config <scratch>/ruff.toml scripts tests .claude/hooks
services/agent/.venv/bin/ruff format --no-cache --check --config <scratch>/ruff.toml scripts tests .claude/hooks
# Strict mypy on the hook's trust boundary, cache disabled
env MYPYPATH=scripts:services/agent/src services/agent/.venv/bin/mypy --strict --python-version 3.12 --cache-dir /dev/null \
  --follow-imports silent .claude/hooks/dispatch.py scripts/harness_lib.py scripts/verify.py scripts/specs.py scripts/evidence.py scripts/toolchain.py
# Web, from apps/web, with the target eslint.config.mjs loaded through --config and the two imports made absolute
node_modules/.bin/eslint --config <scratch>/target.config.mjs --format json -o <scratch>/target.json .
node_modules/.bin/eslint --config <scratch>/target.config.mjs --suppress-rule complexity --suppressions-location <scratch>/eslint-suppressions.json .
node_modules/.bin/prettier --check --config <scratch>/prettierrc.json app components lib tests eslint.config.mjs next.config.ts playwright.config.ts postcss.config.mjs package.json tsconfig.json
```

The remaining counts came from short `python3.12 -I` scripts: `subprocess.run`, `call`, `check_call` and `check_output` calls without `timeout=` (24); `contextlib.suppress(Exception | BaseException)` in src (3); imports of private `autobots` names by location (40); `type: ignore` and `noqa` comments without a reason (87 and 324); environment reads by layer (26 modules); pages without `metadata` (6 of 22); and, from `contracts/generated/openapi.json`, operations referencing `HTTPValidationError` (78 of 78), date-time fields with the UTC pattern (13 of 17) and shared summaries (4 summaries over 9 handlers). Function and module sizes at the thresholds above were recomputed from the raw `eslint.json`, `loc.txt` and `py_functions.json` of this run.
