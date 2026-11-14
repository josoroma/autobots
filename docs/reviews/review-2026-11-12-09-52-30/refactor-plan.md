# Refactor plan

This plan turns the verified findings of the code-quality review at revision `156534d` (run 2026-11-12 09:52:30) into 68 bounded work items in four waves. All 19 areas and 7 lenses have findings files, so no part is missing from it: 493 kept findings, 70 high, 269 medium and 154 low. Every high finding is addressed by an item, and none is deferred ([High findings and where they are addressed](#high-findings-and-where-they-are-addressed)). Standards are named by topic and defined in [standards.md](standards.md); measurements come from [metrics.md](metrics.md).

The review is static: it read code and ran installed tools. Nothing in this plan is runtime, H1 or product acceptance evidence. Start with the wave 0 guardrails and the four small fixes that open wave 2 ([R-13](#r-13) to [R-16](#r-16)), which close a data-loss path, a paid-run stop, a secret display and a consent bypass for little effort.

## All items

Findings are counted as high / medium / low. "Proved by" names the `scripts/verify.py` profiles that prove the item; every item also passes `harness` before its change is archived.

| ID | Item | Wave | Effort | Risk | Proved by | Findings | Depends on |
|---|---|---|---|---|---|---|---|
| [R-01](#r-01) | Every test file runs in a profile, and the profiles are easy to run | 0 | M | low | harness, full | 2 / 6 / 0 | - |
| [R-02](#r-02) | Declare the error envelope in OpenAPI, and tell HTTP failures from contract drift | 0 | M | high | fast, full | 3 / 1 / 0 | - |
| [R-03](#r-03) | Make the TypeScript runtime and the generator enforce every schema keyword | 0 | M | high | fast, db | 2 / 3 / 1 | - |
| [R-04](#r-04) | Write down the comment, naming and migration-header conventions, and fix the rules' path scopes | 0 | S | low | harness | 0 / 4 / 2 | - |
| [R-05](#r-05) | Ratchet size, complexity, Any, broad excepts and layer direction in the service | 0 | M | low | fast | 0 / 6 / 2 | - |
| [R-06](#r-06) | Ratchet assertions, size and import cycles in the web, and lint the API client | 0 | M | low | fast, harness | 0 / 3 / 4 | - |
| [R-07](#r-07) | One lint, format and type gate for repository Python | 0 | L | low | fast, full, harness | 2 / 5 / 2 | [R-01](#r-01) |
| [R-08](#r-08) | Database checks judge the value they show | 1 | S | low | db | 1 / 1 / 0 | - |
| [R-09](#r-09) | Parse write replies, refusals and stream frames with the generated parsers | 1 | S | low | fast, db | 2 / 4 / 1 | [R-01](#r-01) |
| [R-10](#r-10) | The harness's schema guards read every migration and seed | 1 | S | low | harness, db | 1 / 1 / 0 | - |
| [R-11](#r-11) | Derive Python run-status sets from RunStatus, and delete dead code | 1 | S | low | fast | 0 / 4 / 2 | - |
| [R-12](#r-12) | Correct stale comments, docstrings and the front-door docs | 1 | S | low | fast, harness | 0 / 2 / 13 | [R-04](#r-04) |
| [R-13](#r-13) | Parse retention days strictly before a destructive pass | 2 | S | medium | fast, db | 1 / 0 / 0 | [R-01](#r-01) |
| [R-14](#r-14) | Make the live-result tap total | 2 | S | medium | fast | 1 / 0 / 0 | - |
| [R-15](#r-15) | One secret-pattern module for logs and public text | 2 | S | medium | fast, harness | 2 / 0 / 0 | - |
| [R-16](#r-16) | Bind the approval shortcut to one request, and ignore key repeat | 2 | S | medium | fast, db | 1 / 0 / 0 | [R-01](#r-01) |
| [R-17](#r-17) | Revoke the runtime role's DELETE on runs, and check grants from the catalog | 2 | M | high | db, operations | 1 / 1 / 0 | [R-04](#r-04) |
| [R-18](#r-18) | Guard run admission and the run ledger against duplicate submits | 2 | M | medium | db, fast | 4 / 2 / 0 | [R-02](#r-02), [R-09](#r-09) |
| [R-19](#r-19) | Route the other keyed and settings writes through the submit hook | 2 | M | medium | db, fast | 1 / 4 / 2 | [R-18](#r-18) |
| [R-20](#r-20) | Run code search where its timeout can stop it | 2 | M | medium | fast, db | 1 / 0 / 0 | - |
| [R-21](#r-21) | Move the pull-request re-request into approvals.py, fenced and in one transaction | 2 | M | high | db | 3 / 0 / 0 | - |
| [R-22](#r-22) | Price paid trials with the application's catalog parser | 2 | M | high | fast, operations | 1 / 2 / 1 | - |
| [R-23](#r-23) | One tested paid-run session for the four paid entry points | 2 | M | high | harness, db | 1 / 1 / 0 | [R-07](#r-07) |
| [R-24](#r-24) | One readiness gate for people and routines | 2 | M | medium | fast, db, operations | 1 / 1 / 0 | - |
| [R-25](#r-25) | Keep failure causes in private logs and tool receipts | 2 | M | medium | fast, db | 2 / 6 / 0 | [R-15](#r-15) |
| [R-26](#r-26) | Server reads and the BFF keep failure causes, and stop reporting outages as sign-outs | 2 | M | medium | fast, db | 1 / 6 / 3 | [R-02](#r-02) |
| [R-27](#r-27) | One read hook with explicit view states | 2 | M | medium | fast, db | 3 / 5 / 1 | [R-02](#r-02), [R-09](#r-09) |
| [R-28](#r-28) | The run page stops polling denied runs and keeps refreshes in order | 2 | M | medium | db, fast | 1 / 1 / 0 | [R-27](#r-27) |
| [R-29](#r-29) | One stop-code vocabulary with an explicit disposition table | 2 | M | medium | fast, db | 2 / 1 / 0 | - |
| [R-30](#r-30) | Typed run admission inputs | 2 | M | high | fast, db | 2 / 0 / 0 | - |
| [R-31](#r-31) | An admission use case and one gate for model-backed work | 2 | M | high | fast, db | 1 / 4 / 0 | [R-30](#r-30) |
| [R-32](#r-32) | Seams for the paid-path tests | 2 | M | high | fast, db | 1 / 4 / 2 | - |
| [R-33](#r-33) | A public run-lifecycle module, without the goal_loop and workflow_runner cycle | 2 | M | medium | db, fast | 2 / 3 / 0 | [R-07](#r-07) |
| [R-34](#r-34) | Decide how a pass ends with one pure function | 2 | M | high | fast, db | 1 / 0 / 0 | [R-33](#r-33), [R-29](#r-29) |
| [R-35](#r-35) | Record and bound worker failures | 2 | M | high | db, operations | 0 / 2 / 0 | [R-25](#r-25), [R-33](#r-33) |
| [R-36](#r-36) | Resolve each tool call once in the gateway | 2 | M | medium | fast, db | 1 / 2 / 0 | [R-21](#r-21) |
| [R-37](#r-37) | Shared run vocabulary, labels and formatting for the web | 2 | M | low | fast, db | 0 / 17 / 6 | [R-01](#r-01), [R-06](#r-06) |
| [R-38](#r-38) | A shared module for the database checks | 2 | M | low | db, harness | 1 / 3 / 1 | [R-08](#r-08) |
| [R-39](#r-39) | One qualification runner for child checks, with typed case records | 2 | M | medium | db, operations, harness | 1 / 3 / 0 | [R-07](#r-07) |
| [R-40](#r-40) | A shared support layer for the browser tests | 2 | M | low | db, full | 1 / 7 / 5 | - |
| [R-41](#r-41) | One refusal base, typed ledger exceptions and one HTTP mapping | 2 | M | medium | fast, db | 0 / 6 / 2 | - |
| [R-42](#r-42) | Split goal_loop.py along its seams | 2 | M | medium | db, fast | 1 / 0 / 2 | [R-33](#r-33), [R-34](#r-34) |
| [R-43](#r-43) | Split the workflow editor | 2 | M | medium | db, fast | 1 / 4 / 1 | [R-19](#r-19), [R-27](#r-27), [R-37](#r-37) |
| [R-44](#r-44) | Split the goal composer | 2 | M | medium | db, fast | 1 / 1 / 1 | [R-18](#r-18), [R-27](#r-27), [R-37](#r-37) |
| [R-45](#r-45) | Split the approvals panel | 2 | M | medium | db, fast | 1 / 3 / 0 | [R-16](#r-16), [R-19](#r-19), [R-27](#r-27) |
| [R-46](#r-46) | Split slice-visual.spec.ts into typed probes, data and named steps | 2 | M | medium | db | 1 / 1 / 0 | [R-40](#r-40) |
| [R-47](#r-47) | Register qualify_identity's arrangements as functions | 2 | M | medium | db | 1 / 0 / 0 | [R-39](#r-39) |
| [R-48](#r-48) | A typed browser client for every API call | 3 | L | medium | fast, db | 4 / 1 / 0 | [R-02](#r-02), [R-03](#r-03), [R-18](#r-18), [R-27](#r-27) |
| [R-49](#r-49) | Split RunWorkspaceView, and serve the allowed run commands from the API | 3 | L | medium | db, fast | 2 / 5 / 1 | [R-28](#r-28), [R-37](#r-37) |
| [R-50](#r-50) | Receipt and approval state machines with single writers | 3 | L | high | db, fast | 2 / 3 / 0 | [R-21](#r-21), [R-36](#r-36) |
| [R-51](#r-51) | Typed persisted documents: the policy snapshot, event payloads and receipts | 3 | L | high | fast, db, operations | 1 / 2 / 0 | [R-03](#r-03), [R-30](#r-30) |
| [R-52](#r-52) | Versioned stored records, then one routine configuration | 3 | L | high | fast, db, operations | 2 / 1 / 0 | [R-03](#r-03) |
| [R-53](#r-53) | Build the tool registry at the composition edge | 3 | L | medium | fast, db | 1 / 5 / 2 | [R-42](#r-42) |
| [R-54](#r-54) | A typed SQL boundary | 3 | L | medium | fast, db | 1 / 11 / 2 | [R-05](#r-05) |
| [R-55](#r-55) | Thin route handlers: shared dependencies and no SQL | 3 | L | high | fast, db, operations | 1 / 7 / 6 | [R-31](#r-31), [R-41](#r-41) |
| [R-56](#r-56) | Schema and storage integrity by forward change | 3 | L | high | db, operations | 0 / 8 / 2 | [R-04](#r-04), [R-17](#r-17) |
| [R-57](#r-57) | Bind the browser images to their fingerprint, and split the executor | 3 | L | medium | fast, db | 1 / 1 / 1 | - |
| [R-58](#r-58) | Make the browser suites' environments and preconditions explicit | 3 | L | medium | db, full | 1 / 3 / 2 | [R-40](#r-40), [R-47](#r-47) |
| [R-59](#r-59) | Split the remaining large screens | 3 | L | medium | fast, db | 1 / 13 / 4 | [R-19](#r-19), [R-27](#r-27), [R-37](#r-37) |
| [R-60](#r-60) | Run and job writes through the command table | 3 | L | high | fast, db | 0 / 4 / 1 | [R-33](#r-33), [R-34](#r-34) |
| [R-61](#r-61) | Contract vocabularies and request strictness | 3 | L | high | fast, db | 0 / 8 / 5 | [R-03](#r-03), [R-52](#r-52) |
| [R-62](#r-62) | Adapters by layer: one provider HTTP layer, typed replies, and loop policy in the application | 3 | L | medium | fast, db | 0 / 12 / 3 | [R-32](#r-32) |
| [R-63](#r-63) | Product services and the workflow domain | 3 | L | medium | fast, db | 0 / 12 / 4 | [R-52](#r-52), [R-54](#r-54) |
| [R-64](#r-64) | The operations package and process configuration | 3 | L | medium | fast, operations | 0 / 7 / 8 | [R-24](#r-24), [R-22](#r-22) |
| [R-65](#r-65) | Scripts as packages, one profile registry, and the Makefile's shell in scripts | 3 | L | medium | harness, db, operations | 0 / 8 / 11 | [R-39](#r-39), [R-07](#r-07) |
| [R-66](#r-66) | Test suites filed by subject | 3 | L | low | harness, fast, db | 0 / 18 / 14 | [R-38](#r-38), [R-32](#r-32), [R-07](#r-07) |
| [R-67](#r-67) | Server-rendered reads for read-only views | 3 | L | medium | full, db | 0 / 4 / 3 | [R-26](#r-26), [R-27](#r-27) |
| [R-68](#r-68) | UI primitives and a named type scale | 3 | L | low | fast, full, db | 0 / 5 / 18 | [R-46](#r-46), [R-59](#r-59) |

## Principles

- **Behavior is preserved.** Refactors change structure, not behavior. An item that fixes a defect starts its "Why now" with "Fix.", changes only the defective behavior, and adds the failing test first.
- **One bounded work item at a time.** This review edits no backlog. When the owner adds an item to `SPECS.md` as a story (see [Suggested backlog entries](#suggested-backlog-entries)), `/ohmyorch:deliver` delivers it as one OpenSpec change: select, propose, implement, verify, archive and mark-done, with `CODEBASE.md` kept honest when the item changes what it describes, and one commit per story. Work outside that loop follows DH-W01 to DH-W06 in `PRD-Development-Harness.md`: a plan, an implementation record, an independent review, verification and an exercised runbook. A large item lands as several such changes.
- **Tests come first** when an item's risk is medium or high, and every item names the tests to add before the change.
- **Generated artifacts are regenerated, never edited.** `contracts/generated/`, `packages/api-client/src/generated.ts` and `packages/db-types/src/generated.ts` change only through their generators.
- **Migrations only move forward.** No applied migration is edited. Schema, grant and data changes are new migrations carrying the header from [R-04](#r-04), and a persistent install receives them only through the guarded apply.
- **Each item names the profile that proves it.** `harness` runs the repository checks and `tests/harness`. `fast` runs ruff, mypy, pytest, ESLint, Prettier, tsc, the contract drift check and the API-client and web unit tests for what changed. `full` runs all of `fast` plus the production build, the fault qualification, the offline toolchain tests and the web browser qualification. `db` runs disposable migrations, seeds and authorization, the `tests/db` checks, and the main and slice browser suites with a scripted worker. `operations` runs the operations, backup and upgrade qualifiers on disposable Compose projects with a scripted model. Every item also passes `harness` before its change is archived, as the delivery rule requires. A passing profile is static or disposable evidence about that item, never H1 or product acceptance.
- **Stop and ask** when an item would need a paid model call, a live credential, a persistent database change or reset, a cloud project link, a change outside this repository, a missing tool, or a decision that its sources do not make. Items that need a decision say so under "Decision needed". No item installs a new dependency; [R-05](#r-05) only declares one that is already installed.
- **Nothing here** adds a model provider, a local model, a fallback or hosted tracing; moves business state transitions or scheduling into Next.js; merges domain, row, DTO, graph-state or UI types; drops the practice of citing decisions and stories in comments; or weakens a guardrail, check, lease, fence or approval. Several items tighten one.
- **Standards by topic.** Items refer to sections of [standards.md](standards.md) by topic, such as file size, function size and complexity, errors and logging, or enforcement and ratchet, and never by number.

## Waves

- **Wave 0, guardrails**, whatever their size: the checks and conventions that keep new code within the standards, so that later waves do not refactor against a moving target.
- **Wave 1, quick wins**: `S` effort and low risk.
- **Wave 2, hotspot refactors**: `M` effort, plus `S` items whose risk is medium or high, because those need tests first.
- **Wave 3, structural moves**: `L` effort or cross-cutting work.

Within a wave, items are ordered by value for effort, and a dependency can hold an item back. The waves order the work rather than gate it: an item can start before its wave once its dependencies are done. Effort and risk follow the review's rubric. `S` is up to half a day, `M` is half a day to three days, and `L` is more or cross-cutting; `low` risk is mechanical and covered by tests, `medium` is behavior-sensitive, and `high` touches durable state, contracts, migrations, security boundaries or paid paths.

## Wave 0: guardrails

Enforcement first, so that new code meets the standards while the refactors run. Wave 0 items are placed by purpose, whatever their size.

### <a id="r-01"></a>R-01: Every test file runs in a profile, and the profiles are easy to run

**Addresses.** high: [THRN-02](findings/harness-tests.md#thrn-02), [XTOL-02](findings/sweep-tooling.md#xtol-02); medium: [XTOL-09](findings/sweep-tooling.md#xtol-09), [XTOL-10](findings/sweep-tooling.md#xtol-10), [XTOL-11](findings/sweep-tooling.md#xtol-11), [XWEB-15](findings/sweep-web-architecture.md#xweb-15), [WSHL-08](findings/web-shell.md#wshl-08), [WSHL-10](findings/web-shell.md#wshl-10).

**Why now.** Two suites run in no profile today: `schema-value.test.ts`, which the archived US-16.2 verification record cites as passing, and the offline pin and launcher guards in `tests/toolchain`. Every guard this plan adds is worthless if its test file can drop out unseen, and no profile runs unless someone remembers to start it.

**Steps.**

1. Add a harness test that lists every test file (`apps/web/tests/unit`, `packages/api-client/tests`, `tests/toolchain`, `tests/harness`, `services/agent/tests` and the browser specs) and requires each to be claimed by a profile step or listed as manual with a reason, plus a self-check that an unclaimed temporary file is caught (the `test_shared_form_controls.py` pattern). It fails today on the two unrun suites.
2. Select Node tests by glob in `scripts/verify.py` (`apps/web/tests/unit/**/*.test.ts` and `packages/api-client/tests/**/*.test.ts`); Node 22 expands the patterns itself.
3. Give the offline toolchain modules one filename pattern that `toolchain_scope_tests` discovers: the scope and manifest tests, and the launcher checks (N7) moved out of `test_non_mutating.py`. They run in under a second, so consider adding the step to `fast` as well.
4. Add a static test of the gates' own settings (mypy strictness, the TypeScript strict flags, the ESLint presets and the step arguments), with altered copies that prove each weakening is caught.
5. Keep the Playwright suite filters that four scripts pass as filename substrings in one module that the qualifiers import, so the claim test can read them; [R-58](#r-58) later replaces them with projects.
6. Correct the `verify.py` comment and the development-harness runbook line that say the rest of `tests/toolchain` needs package registries.
7. Add `make check-fast` and `make check-full`, and a tracked, opt-in `.githooks/pre-commit` that runs `fast` on the changed scope, enabled with `git config core.hooksPath .githooks`. `db` and `operations` stay manual because they start Docker projects.
8. Record a short decision on the web unit-test mechanism: `node --test` over JSX-free modules, or Vitest and Testing Library under their own story. DH-06 names the latter, and the code departs from it without a record.

**Files.** `scripts/verify.py`, `scripts/harness_lib.py`, `tests/harness/` (claim and settings tests), `tests/toolchain/`, `Makefile`, `.githooks/pre-commit` (new), `docs/engineering/runbooks/development-harness.md`, and a new record under `docs/engineering/decisions/`.

**Risk and mitigations.** Low. Renamed test modules change the verifier's fingerprint, so every profile is rerun once. The archived US-16.2 change is not edited; whether that story is re-verified is the owner's call.

**Verification.** Tests first: the claim test and its self-check, failing on the two unrun suites. Proved by `harness` (claim and settings tests) and `full` (`web_unit_tests` now runs three files, and `toolchain_scope_tests` runs the manifest and launcher tests).

**Decision needed.** The web unit-test mechanism (step 8): `node --test` over JSX-free modules, or Vitest and Testing Library under a story that pins and records them ([WSHL-10](findings/web-shell.md#wshl-10)).

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-02"></a>R-02: Declare the error envelope in OpenAPI, and tell HTTP failures from contract drift

**Addresses.** high: [PAPI-03](findings/py-api.md#papi-03), [XERR-03](findings/sweep-errors.md#xerr-03), [XTYP-14](findings/sweep-types.md#xtyp-14); medium: [WSHL-03](findings/web-shell.md#wshl-03).

**Why now.** All 78 operations document 422 as `HTTPValidationError`, a body the server never sends, none declares the `ErrorResponse` it does send, and `requestJson` reports every non-2xx reply as a `ContractError`. Until a refusal can be told from drift, no screen can show either correctly, so the web error items depend on this one.

**Steps.**

1. Add a Python test that every operation in the exported schema declares `ErrorResponse` for 401, 403, 404, 409, 422 and 503. It fails today.
2. Define one `ERROR_RESPONSES` mapping in `api/errors.py` and pass it to `include_router` in `create_app`. Declaring 422 replaces FastAPI's default validation schema; no handler, code or message changes.
3. Regenerate with `python3.12 scripts/generate_contracts.py write`. `contracts/generated/` and `generated.ts` are never edited by hand.
4. In the hand-written `packages/api-client/src/runtime.ts`, read a non-2xx body, parse it with the generated `ErrorResponse` parser when it fits, and throw a typed HTTP failure that carries the status and the envelope (or null). Keep `ContractError` for shape mismatches only, and accept per-call headers and an `AbortSignal`.
5. Update `packages/api-client/tests/contract.test.ts`, which pins `ContractError` for a failed status today, with cases for a 409 envelope, a non-JSON 503 and a drifted 200.
6. Move `apps/web/lib/service-status.ts` to the new failure type without changing what it renders; [R-26](#r-26) changes that.

**Files.** `services/agent/src/autobots/api/errors.py`, `api/app.py`, `contracts/generated/openapi.json` (regenerated), `packages/api-client/src/runtime.ts`, `packages/api-client/src/generated.ts` (regenerated), `packages/api-client/tests/contract.test.ts`, `apps/web/lib/service-status.ts`.

**Risk and mitigations.** High, because it changes the published contract. It only adds response declarations; `contract_drift` and the regenerated client prove the shape, and runtime responses do not change. It edits the same runtime file as [R-03](#r-03), so the two land one after the other.

**Verification.** Tests first: the schema test and the runtime contract cases. Proved by `fast` (`pytest`, `contract_drift`, `api_client_tests`, `api_client_typecheck`, `typecheck`) and `full`.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-03"></a>R-03: Make the TypeScript runtime and the generator enforce every schema keyword

**Addresses.** high: [XTYP-02](findings/sweep-types.md#xtyp-02), [WSHL-01](findings/web-shell.md#wshl-01); medium: [PDOM-16](findings/py-domain.md#pdom-16), [XTYP-13](findings/sweep-types.md#xtyp-13), [WSYS-08](findings/web-system.md#wsys-08); low: [WBLD-20](findings/web-build.md#wbld-20).

**Why now.** The generated parsers are the only runtime check at the TypeScript trust boundary, yet 29 constraints in 19 of 170 schemas (15 `maxItems`, 4 `minItems` and 10 schema-valued `additionalProperties`) pass unchecked, and the 10 map fields generate as `Record<string, unknown>`, covered by five casts and two coercions. A keyword that Pydantic starts emitting would pass silently, and the shared cross-language fixtures cover 4 of 170 schemas.

**Steps.**

1. Write the failing cases first in `contracts/fixtures/boundary-cases.json`, which both languages read: a `WorkflowGraph` with 201 nodes, a `ModelPolicyState` whose `role_overrides` names an unapproved profile, and an empty jobs chart. Add `ModelPolicyState` to both model maps.
2. Implement `minItems`, `maxItems` and schema-valued `additionalProperties` in `runtime.ts`, and export the implemented keyword set together with an allow-list of annotations (title, description, default, examples).
3. Make `scripts/generate_contracts.py` emit `Record<string, T>` from schema-valued `additionalProperties`, and make its `check` fail on any keyword the runtime does not implement.
4. Regenerate, then delete the five casts and two coercions in the model-policy, Expert, Experts, workflow-monitor and approvals components, and the unchecked narrowings of role bindings and block versions.
5. Widen the shared fixtures, starting with the request bodies the browser sends (`RunRequest`, `SessionCreate`, the model-policy update) and the stored shapes that [R-51](#r-51) and [R-52](#r-52) will type.

**Files.** `packages/api-client/src/runtime.ts`, `packages/api-client/tests/contract.test.ts`, `scripts/generate_contracts.py`, `contracts/fixtures/boundary-cases.json`, `services/agent/tests/test_contracts.py`, the regenerated `generated.ts`, and the five components.

**Risk and mitigations.** High: a stricter parser could refuse a reply the server sends today. The fixtures show that Pydantic already enforces each bound on the server, so a valid reply cannot fail, and the browser suites run before merging.

**Verification.** Tests first: the boundary fixtures, failing in TypeScript and passing in Python. Proved by `fast` (`contract_drift`, `api_client_tests`, `pytest`, `typecheck`) and `db` (the browser suites that load the policy, workflow and Experts screens).

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-04"></a>R-04: Write down the comment, naming and migration-header conventions, and fix the rules' path scopes

**Addresses.** medium: [PADP-10](findings/py-adapters.md#padp-10), [SQLI-04](findings/sql-infra.md#sqli-04), [XMOD-04](findings/sweep-boundaries.md#xmod-04), [XDOC-02](findings/sweep-docs-naming.md#xdoc-02); low: [SQLI-18](findings/sql-infra.md#sqli-18), [XDOC-07](findings/sweep-docs-naming.md#xdoc-07).

**Why now.** The code follows citation and naming conventions that are written nowhere, files and migrations are still named for the review round that found an issue, and migrations that rewrite data or rebuild constraints say nothing about locks or recovery. Applied migrations cannot be edited, so a header convention helps only if it starts before the next migration, which [R-17](#r-17) writes. Meanwhile five rule path globs match no tracked file, and the model-gateway rule misses the adapter that admits model calls, so those rules never load for the code they govern.

**Steps.**

1. Adopt the comments-and-documentation and naming sections of [standards.md](standards.md) where the project keeps rules (a short section in AGENTS.md, or a new `.claude/rules/` file with its row in AGENTS.md's rule-check table): the citation form, with the document and ID after the statement, and names that describe behavior rather than a story or review round.
2. Define the migration header: locks taken, data rewritten, expected cost on the largest table, and recovery.
3. Add a harness test that every migration newer than today's newest carries the header, with a known-bad fixture. Existing files are exempt by name.
4. Correct the path scopes in `.claude/rules/*.md` so that each glob matches tracked files (the model-gateway rule must cover `adapters/loop_middleware.py`), and make the harness test fail on a glob that matches nothing.

**Files.** `AGENTS.md` or a new `.claude/rules/*.md` file, the path scopes of `.claude/rules/database.md`, `model-gateway.md` and `infrastructure.md`, `tests/harness/` (header and scope tests), and new files under `supabase/migrations/`.

**Risk and mitigations.** Low. Rule files are project configuration, which `project_configuration` checks, and no applied migration changes.

**Verification.** Tests first: the header test and the scope test, each with a known-bad fixture. Proved by `harness`.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-05"></a>R-05: Ratchet size, complexity, Any, broad excepts and layer direction in the service

**Addresses.** medium: [PDOM-14](findings/py-domain.md#pdom-14), [PDOM-15](findings/py-domain.md#pdom-15), [XMOD-09](findings/sweep-boundaries.md#xmod-09), [XERR-14](findings/sweep-errors.md#xerr-14), [XTOL-05](findings/sweep-tooling.md#xtol-05), [XTOL-08](findings/sweep-tooling.md#xtol-08); low: [PAPI-19](findings/py-api.md#papi-19), [XMOD-10](findings/sweep-boundaries.md#xmod-10).

**Why now.** Nothing stops new service code from adding to today's 24 C901, 62 PLR0913 and 398 ANN401 hits ([metrics.md](metrics.md) sections 4 and 5), and nothing enforces layer direction: `contracts/export.py` already imports the API, and five import cycles hide behind function-level imports. The refactors in waves 2 and 3 need a ratchet so their gains stick.

**Steps.**

1. Add the complexity, branch, return, statement and argument rules at the thresholds in the function-size section of standards.md, with per-file ignores for today's offenders. Each refactor item deletes its own ignore lines.
2. Add ANN401 with a per-file baseline, taking `api/` (16 hits) and `domain/` (5) to zero first.
3. Select the rules the code already follows (DTZ, S602, S604, S605, TID251 and FAST), which need no baseline; then BLE001, with `ruff check --add-noqa` and a written reason on each current broad catch.
4. Add a stdlib AST test in `services/agent/tests` that enforces layer direction (domain imports no other layer, contracts imports neither api nor persistence, application imports no api), with a shrinking allowlist that names today's exceptions, including goal_loop's adapter imports and the five function-level cycles.
5. Move `contracts/export.py` to `api/openapi_export.py`, which the drift check proves leaves the artifact unchanged, and declare pydantic as a direct dependency through an explicit offline lock update. If the lock needs the network, stop and ask.

**Files.** `services/agent/pyproject.toml`, `services/agent/uv.lock`, `services/agent/tests/test_layers.py` (new), `services/agent/src/autobots/contracts/export.py`, `scripts/generate_contracts.py`, `services/agent/tests/test_contracts.py`.

**Risk and mitigations.** Low. Every new rule starts at a baseline, so no existing code fails. The lock update is a recorded dependency operation, never part of a check.

**Verification.** Tests first: the layer test, with a planted violation that it must catch. Proved by `fast` (`ruff_check`, `mypy`, `pytest`, `python_lock`, `contract_drift`).

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-06"></a>R-06: Ratchet assertions, size and import cycles in the web, and lint the API client

**Addresses.** medium: [XTOL-06](findings/sweep-tooling.md#xtol-06), [XTOL-07](findings/sweep-tooling.md#xtol-07), [WSHL-09](findings/web-shell.md#wshl-09); low: [THRN-18](findings/harness-tests.md#thrn-18), [XTOL-12](findings/sweep-tooling.md#xtol-12), [XTOL-13](findings/sweep-tooling.md#xtol-13), [XTOL-15](findings/sweep-tooling.md#xtol-15).

**Why now.** The web's ESLint configuration enables only the Next.js presets, so 44 type assertions in non-test code (29 of them on fetched JSON), 83 functions over 60 lines and a run-list and run-panel import cycle pass unchecked, and `packages/api-client` sits outside lint and format.

**Steps.**

1. Enable `@typescript-eslint/consistent-type-assertions` with `assertionStyle: never` for `components` and `lib`, with a file baseline that [R-09](#r-09), [R-48](#r-48) and the screen splits shrink.
2. Add the size and complexity rules from standards.md (function length, statements, complexity, file length, components per file) at warn, then baseline, then error, as its enforcement section describes.
3. Enable the cycle rule of the import plugin that eslint-config-next already loads (eslint-plugin-import 2.32.0), with today's cycle in the baseline until [R-37](#r-37) removes it.
4. Express the shared form-control rule as `no-restricted-syntax`, with an exception for `components/ui/field.tsx`; the import ban that a harness test enforces today becomes ruff TID251 in [R-05](#r-05).
5. Bring `packages/api-client` and the infra JavaScript under ESLint and Prettier, typecheck the client's tests, state Prettier's options explicitly, and add `erasableSyntaxOnly` to `apps/web/tsconfig.json` so that tsc rejects what the Node unit runner cannot execute.
6. Add a harness scan that forbids new raw `fetch(` and `csrfFetch(` calls in components, baselined at today's files, for [R-27](#r-27) and [R-48](#r-48) to shrink.

**Files.** `apps/web/eslint.config.mjs`, `apps/web/tsconfig.json`, `apps/web/package.json`, `packages/api-client/package.json`, `packages/api-client/tsconfig.json`, a Prettier configuration file, and `tests/harness/` (raw-fetch scan).

**Risk and mitigations.** Low; the baselines keep today's code passing.

**Verification.** Tests first: the raw-fetch scan with a known-bad fixture. Proved by `fast` (`lint`, `format_check`, `typecheck`, `api_client_typecheck`) and `harness`.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-07"></a>R-07: One lint, format and type gate for repository Python

**Addresses.** high: [SCRP-04](findings/scripts.md#scrp-04), [XTOL-01](findings/sweep-tooling.md#xtol-01); medium: [TDBC-08](findings/db-tests.md#tdbc-08), [THRN-14](findings/harness-tests.md#thrn-14), [XTOL-03](findings/sweep-tooling.md#xtol-03), [XTOL-04](findings/sweep-tooling.md#xtol-04), [XTYP-12](findings/sweep-types.md#xtyp-12); low: [TDBC-12](findings/db-tests.md#tdbc-12), [XTOL-14](findings/sweep-tooling.md#xtol-14).

**Why now.** 133 files and 25,788 lines, 42% of the Python, run under no lint, format or type gate, including the verifier, the hook and the guarded persistent install, and the database checks import service internals that no static check sees. The wave 2 refactors of `scripts/` and `tests/db` need this gate first.

**Steps.**

1. Add a root `ruff.toml` with the shared standard (target py312, line length 100, the service's rule families) and have `services/agent/pyproject.toml` extend it; exclude the deliberately bad fault fixtures.
2. Add a `repo_ruff_check` step over `scripts`, `tests` and `.claude/hooks` to `fast` and `full`, report-only at first (`--exit-zero --statistics`), and map those paths in `check_domains`, so that `fast`, the Stop hook and the PostToolUse diagnostic cover them.
3. In one explicit commit, apply the 458 safe fixes. Remove the 295 dead suppression comments only after the rule selection is settled, so the reasoned BLE001 markers survive.
4. Gate with E501 ignored for these paths, reformat in a second explicit commit (never in a hook, per DH-05), then drop the E501 ignore one directory at a time.
5. Run mypy strict on the hook's trust boundary first (`dispatch.py`, `harness_lib.py`, `verify.py`, `specs.py`, `evidence.py`, `toolchain.py`), then on the libraries with per-module overrides. Run a non-strict mypy over `tests/db` with `MYPYPATH=services/agent/src:tests/db`, so that a renamed product name fails in seconds rather than in a Docker run.

**Files.** `ruff.toml` (new), `services/agent/pyproject.toml`, `scripts/toolchain.py`, `scripts/harness_lib.py`, `scripts/verify.py`, `.claude/hooks/dispatch.py`, and mechanical fixes across `scripts/`, `tests/` and `.claude/hooks/`.

**Risk and mitigations.** Low, because the changes are mechanical, but the format commit touches many files: land it alone, and rerun every profile because the verifier's fingerprint changes. The hook stays diagnostic.

**Verification.** Tests first: a harness test that `check_domains` maps scripts, tests and hooks to the new steps, and that those steps run the prepared binaries without installing anything. Proved by `fast` and `full` (the new steps) and `harness`; `db` and `operations` run once after the format commit, because their scripts change.

**Effort and dependencies.** L. Depends on [R-01](#r-01).

## Wave 1: quick wins

Small (`S`) items with low risk. They need no new abstraction and can start at once.

### <a id="r-08"></a>R-08: Database checks judge the value they show

**Addresses.** high: [TDBC-01](findings/db-tests.md#tdbc-01); medium: [TDBC-07](findings/db-tests.md#tdbc-07).

**Why now.** `check(name, expected, observed, passed)` takes the shown value and the verdict as separate expressions: 80 calls in 20 files evaluate the same call twice, and 5 of those calls change state. Three lease and claim cases can pass with the guard they name broken, `approval_check.py:185` cannot fail, and refusal checks accept any exception as the expected refusal.

**Steps.**

1. Fix the five state-changing double calls (`claim_next` at `worker_ownership_check.py` lines 74, 144, 146 and 164, and `expire_due` at `approval_check.py:185`): evaluate once, then judge that value.
2. Re-arrange the case at line 144 so that only the pause guard stands between the run and a claim.
3. Make refusal checks catch the named refusal class and code, not any exception.
4. Make each predicate assert what its expected text claims, starting with `verification_check.py:97`.
5. Leave the other 75 double reads to the shared check API in [R-38](#r-38).

**Files.** `tests/db/worker_ownership_check.py`, `tests/db/approval_check.py`, `tests/db/verification_check.py`, and the refusal checks in `tests/db/restore_check.py`, `run_admission_check.py` and `recovery_check.py`.

**Risk and mitigations.** Low. A corrected case may now fail and expose a real defect; it is triaged before merging, never weakened.

**Verification.** Tests first: on a disposable target, break each guard locally (for example, drop the pause predicate) and confirm that the corrected case fails. Proved by `db`.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-09"></a>R-09: Parse write replies, refusals and stream frames with the generated parsers

**Addresses.** high: [WCMP-02](findings/web-composer.md#wcmp-02), [WRUN-06](findings/web-run.md#wrun-06); medium: [XDUP-07](findings/sweep-duplication.md#xdup-07), [XERR-09](findings/sweep-errors.md#xerr-09), [WBLD-03](findings/web-build.md#wbld-03), [WRUN-13](findings/web-run.md#wrun-13); low: [WTAP-18](findings/web-tools-approvals.md#wtap-18).

**Why now.** On the paid admission path a renamed field still compiles and fails quietly (the success link becomes `/runs/undefined`), and a cursor frame without a number becomes `NaN`, so every reconnect asks for `after=NaN` and the page loops. Generated parsers already exist for these bodies, but nothing in `apps/web` uses `parseErrorResponse` or `parseRunAccepted`.

**Steps.**

1. Add JSX-free helpers with `node:test` cases: `readErrorResponse(reply)`, which wraps `parseErrorResponse` and returns null for a non-JSON body such as an HTML error page; `parseCursorFrame(data)`, which accepts safe non-negative integers only; and `splitEventPage(raw)`, which returns the known events plus a count of skipped ones (unknown types are still ignored, per Decision 0017 Q13).
2. Replace the casts on the run screens (continue-run, run-controls, run-panel, unknown-effects, and run-workspace's cursor frame and event page) and the admission screens (goal-composer, session-panel) with `parseRunAccepted`, `parseSessionView` and the helpers, and type the request bodies with `satisfies RunRequest` and `satisfies SessionCreate`.
3. Do the same for the ten reply casts in the Expert and workflow builders and the approval decision's error body.
4. Make handlers that catch only network errors also catch a parse failure, so that a bad body cannot leave a button disabled or a list stuck.
5. Treat a `ContractError` on a 202 admission reply as an unknown outcome, not a refusal; [R-18](#r-18) shares that rule.
6. Remove the cleaned files from the assertion baseline of [R-06](#r-06).

**Files.** `apps/web/lib/api/read-error.ts` and `apps/web/lib/runs/stream-frames.ts` (new, JSX-free), `apps/web/tests/unit/`, and the run, admission, builder and approvals components named above.

**Risk and mitigations.** Low. Success paths are unchanged; only drifted or malformed bodies now surface as errors.

**Verification.** Tests first: `node:test` cases for the helpers (a `NaN` cursor, a reply without `run_id`, an HTML refusal body). Proved by `fast` (`typecheck`, `lint`, `web_unit_tests`) and `db` (the run, composer and Experts suites).

**Effort and dependencies.** S. Depends on [R-01](#r-01).

### <a id="r-10"></a>R-10: The harness's schema guards read every migration and seed

**Addresses.** high: [THRN-01](findings/harness-tests.md#thrn-01); medium: [THRN-10](findings/harness-tests.md#thrn-10).

**Why now.** The guard that keeps private run columns from the authenticated role reads only the first grant of one migration, while five later migrations grant run columns to authenticated; the two seed scanners have drifted apart, and only one of them looks for jobs.

**Steps.**

1. Scan every migration in name order for column-level and table-level grants on `public.runs` to authenticated, and assert that `lease_generation`, `checkpoint_thread_id` and any table-level grant never appear. Add a known-bad fixture with a later grant of `checkpoint_thread_id`.
2. Write one `seed_violations(text)` with the union of both term lists plus `run_jobs`, apply it to both seed files, and give each term a known-bad string.
3. Ask the owner of `scripts/app_db.py` to add a runtime denial of `checkpoint_thread_id` beside the `lease_generation` case.

**Files.** `tests/harness/test_app_db.py`, `tests/harness/test_disposable_guard.py`, `scripts/app_db.py`.

**Risk and mitigations.** Low; the tests read migrations and edit none.

**Verification.** Tests first: the known-bad fixtures. Proved by `harness`, and by `db` for the runtime denial.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-11"></a>R-11: Derive Python run-status sets from RunStatus, and delete dead code

**Addresses.** medium: [PPRD-14](findings/py-product.md#pprd-14), [PRUN-10](findings/py-run.md#prun-10), [PTOL-14](findings/py-tools.md#ptol-14), [XDUP-09](findings/sweep-duplication.md#xdup-09); low: [PADP-21](findings/py-adapters.md#padp-21), [PAPI-18](findings/py-api.md#papi-18).

**Why now.** Canonical run-status sets are restated as literals across the service, so a new status needs edits in many places. The cronjob handler falls through to `run` and narrows with asserts, and two superseded credential helpers and two unreachable branches mislead the next reader.

**Steps.**

1. Derive every status set from `RunStatus` and `TERMINAL` in `domain/runs.py`. Add a test that each derived set equals today's literal, then delete the literals. The TypeScript copies move in [R-37](#r-37) and the SQL predicate in [R-56](#r-56).
2. Dispatch the cronjob tool's seven actions with `match` and an `assert_never` arm, or with a handler table whose completeness a test checks, keeping one tool as Decision 0026 C1 requires.
3. Delete `configured_target` and the test-only `provider_key` (or move it into the test helpers), and drop the branches in `check_run_intent` that its own dependency makes unreachable.

**Files.** `services/agent/src/autobots/domain/runs.py`, `application/run_projection.py`, `application/runs.py`, `application/retention.py`, `application/assignments.py`, `application/routines.py`, `application/workflows.py`, `application/cronjob_tool.py`, `adapters/github_issues.py`, `adapters/provider_http.py`, `api/settings_routes.py`.

**Risk and mitigations.** Low; the equality test proves the sets are unchanged.

**Verification.** Tests first: the set-equality test and a cronjob action-completeness test. Proved by `fast`.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-12"></a>R-12: Correct stale comments, docstrings and the front-door docs

**Addresses.** medium: [XDOC-01](findings/sweep-docs-naming.md#xdoc-01), [XDOC-03](findings/sweep-docs-naming.md#xdoc-03); low: [PAPI-17](findings/py-api.md#papi-17), [PDOM-19](findings/py-domain.md#pdom-19), [POPS-18](findings/py-ops.md#pops-18), [PRUN-21](findings/py-run.md#prun-21), [PTOL-17](findings/py-tools.md#ptol-17), [SCRP-21](findings/scripts.md#scrp-21), [XTYP-15](findings/sweep-types.md#xtyp-15), [WBLD-18](findings/web-build.md#wbld-18), [WCMP-18](findings/web-composer.md#wcmp-18), [WRUN-20](findings/web-run.md#wrun-20), [WSHL-17](findings/web-shell.md#wshl-17), [WSHL-21](findings/web-shell.md#wshl-21), [WTAP-19](findings/web-tools-approvals.md#wtap-19).

**Why now.** Comments that narrate delivery go stale in every layer, several now state something the code no longer does, and the README still describes the product before it was built. They are cheap to fix and mislead every reader until they are.

**Steps.**

1. Fix the nine stale comments that [XDOC-01](findings/sweep-docs-naming.md#xdoc-01) lists by stating what holds now and keeping the citation, for example "Decision 0026 G2: the detail opens in a modal dialog".
2. Fix the stale, misplaced or missing comments and docstrings that the area findings list, and give each `type: ignore` a reason.
3. Rewrite the opening of `README.md` as the current state (what runs, the three model profiles, where to start), move the dated planning paragraphs under a History heading, and align `README-QA.md` and the service's package description.
4. Say in `apps/web/lib/credential-precedence.ts` that no application code calls it and that it is the TypeScript half of the US-3.1 parity fixture, or move it beside its test.

**Files.** The files the findings cite, plus `README.md`, `README-QA.md` and `services/agent/pyproject.toml`.

**Risk and mitigations.** Low; comments and documents only.

**Verification.** No behavior changes, so there are no new tests. Proved by `fast` (lint and format of the touched files) and `harness` (project configuration).

**Effort and dependencies.** S. Depends on [R-04](#r-04).

## Wave 2: hotspot refactors

Medium (`M`) refactors of the hotspots, plus small items whose risk is medium or high. Those need tests first, so they are planned like hotspot work, and they lead the wave when their value is high. Items that fix a defect start their "Why now" with "Fix."

### <a id="r-13"></a>R-13: Parse retention days strictly before a destructive pass

**Addresses.** high: [WSYS-01](findings/web-system.md#wsys-01).

**Why now.** Fix. `Number.parseInt` turns "1,000" into 1, "3O" into 3 and "2e3" into 2, and the save succeeds. The worker's next timed pass then removes the checkpoints, working files and artifact bytes of every run that finished more than a day ago. The loss is irreversible and is reported as a success.

**Steps.**

1. Add `lib/retention.ts` with `parseDays(text)`: empty keeps everything, whole digits only, anything else is invalid. Cover "1,000", "3O", "2e3", "7.9", "abc" and the empty string with `node:test`.
2. Validate the draft with the generated `parseRetentionSettings`, which already checks the contract's 1 to 36500 range, instead of copying the bounds.
3. On an invalid value send nothing, set `aria-invalid` and point `aria-describedby` at an inline message. Show the rule sentence only for `invalid_request`, and the server's message for other refusals.
4. Add a browser case to the operations values spec that types "1,000" and expects no PUT.

**Files.** `apps/web/lib/retention.ts` (new), `apps/web/tests/unit/retention.test.ts` (new), `apps/web/components/operations-panel.tsx`, `apps/web/tests/browser/operations-values.spec.ts`.

**Risk and mitigations.** Medium, because the path is destructive. The server's `RetentionSettings` validation stays the authority, including the cross-field rule; the client only refuses malformed input.

**Verification.** Tests first: the `node:test` cases and the browser case. Proved by `fast` (`web_unit_tests`) and `db` (the operations suites).

**Effort and dependencies.** S. Depends on [R-01](#r-01).

### <a id="r-14"></a>R-14: Make the live-result tap total

**Addresses.** high: [PADP-01](findings/py-adapters.md#padp-01).

**Why now.** Fix. A `save_artifact` call whose content holds a raw newline makes the tap's JSON reader raise. Once the first chunk has arrived, that becomes `partial_stream` or `uncertain_acceptance`: the reservation stays open for reconciliation and the paid run stops. Decision 0022 D4 and the module's own docstring say that a tap failure never stops the run.

**Steps.**

1. Add fake-stream tests with a tap present for a raw control character, an invalid escape and a bad unicode escape, each expecting the reply back with an invalid tool call, and one where `finish()` raises. They fail today.
2. In `flush`, catch `ValueError` around `partial_object` and stop streaming that call; the stored artifact stays the record.
3. In `_streamed`, call `tap.begin`, `feed` and `finish` through a helper that logs `result_text.unavailable` once, disables the tap and never raises.
4. Reword the "tolerant reader" comment: it tolerates incomplete input, not malformed input.

**Files.** `services/agent/src/autobots/adapters/result_stream.py`, `adapters/loop_middleware.py`, `services/agent/tests/test_result_stream.py`.

**Risk and mitigations.** Medium (paid path). Real stream failures keep their model-gateway classification (`partial_stream`, reconciled, not retried), and the tests use fake streams only.

**Verification.** Tests first: the four fake-stream cases. Proved by `fast`.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-15"></a>R-15: One secret-pattern module for logs and public text

**Addresses.** high: [PRUN-05](findings/py-run.md#prun-05), [XDUP-01](findings/sweep-duplication.md#xdup-01).

**Why now.** Fix. `public_text`, which sanitizes the plans, summaries, approval arguments, run goals and search titles shown to every workspace member, misses the Tavily, Jina and GitHub tokens, lowercase bearer values and credentialed URLs that the log redactor masks. Each new tool key widens the gap, because nothing ties the copies together.

**Steps.**

1. Add one shared list of token-shape fixtures and assert that both `logs.redact` and `public_text` mask every entry; `public_text` fails today.
2. Add a stdlib-only `domain/secret_patterns.py` holding the token families and credential shapes now in `operations/logs.py`, compiled into the strictest union.
3. Make `logs.redact` the identifier shortening plus the shared redaction, and `public_text` the shared redaction plus its 500-character cut. Never narrow either copy.
4. Keep `scripts/evidence.py`'s own copy, since it runs under the system interpreter, and add a harness test that fails when its families differ from the shared module.

**Files.** `services/agent/src/autobots/domain/secret_patterns.py` (new), `operations/logs.py`, `application/run_projection.py`, `scripts/evidence.py`, a redaction test in `services/agent/tests/`, and a parity test in `tests/harness/`.

**Risk and mitigations.** Medium: the shared module also feeds log redaction, so the fixture list asserts that log coverage is kept. Display redaction can only get stricter, as SP-011 requires.

**Verification.** Tests first: the shared fixture test. Proved by `fast` and `harness`.

**Effort and dependencies.** S. Depends on nothing.

### <a id="r-16"></a>R-16: Bind the approval shortcut to one request, and ignore key repeat

**Addresses.** high: [WTAP-02](findings/web-tools-approvals.md#wtap-02).

**Why now.** Fix. AP-04 requires a second press within 2 s, but holding ⌘↵ fires repeated keydowns that count as the second press, Alt chords also decide, and an arm that carries no request id can approve a different request after the list reloads.

**Steps.**

1. Write `lib/approval-shortcut.ts` as pure functions (`chord`, `press`) over the arm, the decision, the approval id, the time, `repeat` and truncation, and cover repeat, Alt, a changed approval, expiry and truncation with `node:test`.
2. Call them from a `useApprovalShortcuts` hook that subscribes once through React 19's `useEffectEvent`, ignores `event.repeat`, requires `(metaKey || ctrlKey) && !altKey`, stores the approval id in the arm, and clears the arm when the selection or the pending state changes.
3. Add a browser case: hold Meta, send Enter down twice (the second carries `repeat`), and expect no decision.

**Files.** `apps/web/lib/approval-shortcut.ts` (new), `apps/web/components/approvals-panel.tsx`, `apps/web/tests/unit/approval-shortcut.test.ts` (new), `apps/web/tests/browser/approvals.spec.ts`.

**Risk and mitigations.** Medium. The change tightens a confirmation step, which ground rule 2 allows; `typing()` still gates every shortcut, and the server's hash binding is untouched.

**Verification.** Tests first: the `node:test` cases and the held-key browser case. Proved by `fast` and `db`.

**Effort and dependencies.** S. Depends on [R-01](#r-01).

### <a id="r-17"></a>R-17: Revoke the runtime role's DELETE on runs, and check grants from the catalog

**Addresses.** high: [SQLI-01](findings/sql-infra.md#sqli-01); medium: [SQLI-05](findings/sql-infra.md#sqli-05).

**Why now.** Fix. `autobots_runtime` holds DELETE on runs, run events, workspaces, members and profiles, and 21 cascading foreign keys from 18 tables would erase the receipts, tool uses, approvals and evidence that replay and reconciliation depend on. The service itself deletes only from `workflow_drafts`, and grant conventions are checked one case at a time.

**Steps.**

1. Add database cases first: the runtime role cannot delete a run or a run event, and a catalog check lists every DELETE the runtime role holds and expects `workflow_drafts` only. Both fail today.
2. Move the two arranged deletes in `scripts/qualify_identity.py` (lines 245 and 472) to the admin connection.
3. Write a forward migration that revokes DELETE on `runs`, `run_events`, `workspaces`, `workspace_members` and `user_profiles` from `autobots_runtime`, with the header from [R-04](#r-04) (catalog locks only, no data).
4. Extend the catalog check to the RLS and grant conventions of every public table, replacing per-case checks.
5. Optionally switch `tool_receipts` and `tool_uses` to `ON DELETE RESTRICT` in the same migration.

**Files.** `supabase/migrations/<new>_runtime_cannot_delete_runs.sql`, `scripts/app_db.py`, `scripts/qualify_identity.py`, and a catalog check under `tests/db/`.

**Risk and mitigations.** High (grants on durable state). The catalog check proves that the one DELETE the service uses survives, and a persistent install receives the migration only through the guarded apply, never in a check.

**Verification.** Tests first: the denial cases and the catalog check. Proved by `db`, and by `operations`, whose upgrade qualifier applies new migrations to an older install.

**Effort and dependencies.** M. Depends on [R-04](#r-04).

### <a id="r-18"></a>R-18: Guard run admission and the run ledger against duplicate submits

**Addresses.** high: [XDUP-03](findings/sweep-duplication.md#xdup-03), [XWEB-03](findings/sweep-web-architecture.md#xweb-03), [WCMP-01](findings/web-composer.md#wcmp-01), [WRUN-03](findings/web-run.md#wrun-03); medium: [XWEB-16](findings/sweep-web-architecture.md#xweb-16), [WCMP-04](findings/web-composer.md#wcmp-04).

**Why now.** Fix. A double click on Run in the composer or in a session admits two paid runs, because neither button tracks a pending request; an unknown outcome is shown as "Sign in, then try again"; and after a lost reply on the charge form, the screen invites a resubmission under a new key, which can record one provider charge twice. Only ContinueRun keeps its key until the outcome is known.

**Steps.**

1. Write the browser cases first: double-click Run in the composer and in a session and expect one admission; let the charge request reach the API, abort the reply (`route.fetch`, then `route.abort`), retry, and expect one charge.
2. Add `lib/use-submit.ts`: a pending state that disables the trigger and ignores re-entry; the key policy as an explicit option (`per-press` or `until-known`); a null reply or a 5xx as `unknown`; a typed outcome union; and a request body that stays locked while the outcome is unknown, because the API refuses a reused key with different content.
3. Add a JSX-free `lib/run-admission.ts` with the request, the parsing from [R-09](#r-09) and one refusal table, plus one `AdmissionMessage` (role=status when accepted, role=alert for refusals), and use them in GoalComposer, SessionPanel and ContinueRun.
4. Use `until-known` for ContinueRun, the charge, effect reconciliation and the run commands. A retry resends the first body, and the screen says "This may have been recorded. Pressing again won't record it twice."
5. Keep the composer's one key per press, which US-4.1 chose, until the owner decides otherwise. Add only the in-flight guard, and replace the sign-in copy for an unknown outcome with wording that does not invite a second press.

**Files.** `apps/web/lib/use-submit.ts` and `apps/web/lib/run-admission.ts` (new), `goal-composer.tsx`, `session-panel.tsx`, `continue-run.tsx`, `run-controls.tsx`, `run-panel.tsx`, `unknown-effects.tsx`, and the composer, session and run-workspace browser specs.

**Risk and mitigations.** Medium (paid admission and the run ledger). Server idempotency stays the correctness mechanism, as DH-06 requires; the client only stops minting a key while an outcome is unknown and stops duplicate presses. No run state or scheduling moves into Next.js.

**Verification.** Tests first: the browser cases above, and `node:test` cases for the outcome reducer. Proved by `db` (the identity suites) and `fast`.

**Decision needed.** Whether the composer and the session panel keep one key per press, as US-4.1 chose, or keep the key until the outcome is known, as [WCMP-01](findings/web-composer.md#wcmp-01) and [XDUP-03](findings/sweep-duplication.md#xdup-03) recommend.

**Effort and dependencies.** M. Depends on [R-02](#r-02), [R-09](#r-09).

### <a id="r-19"></a>R-19: Route the other keyed and settings writes through the submit hook

**Addresses.** high: [WBLD-02](findings/web-build.md#wbld-02); medium: [XWEB-07](findings/sweep-web-architecture.md#xweb-07), [WSHL-04](findings/web-shell.md#wshl-04), [WSYS-02](findings/web-system.md#wsys-02), [WTAP-03](findings/web-tools-approvals.md#wtap-03); low: [WBLD-16](findings/web-build.md#wbld-16), [WSYS-13](findings/web-system.md#wsys-13).

**Why now.** Fix. Nine keyed POSTs in the builders mint a new `Idempotency-Key` per click and never disable their buttons, so a double click on Run this version starts two executions with two budgets. `csrfFetch` mints a new token for every write, so overlapping writes can refuse each other, and five settings save flows hand-roll requests and messages that have drifted.

**Steps.**

1. Write the browser cases first: double-click Run this version and expect one execution, and send two overlapping writes and expect both to succeed.
2. Use `useSubmit` from [R-18](#r-18) for the builders' create, publish and run calls (`until-known`, with the key reset when the body changes), the three unkeyed builder writes, approval decisions and the settings save flows, with one outcome shape and one announcement role.
3. Keep one CSRF token per browser session: `/api/csrf` returns the existing cookie value and mints one only when there is none, `csrfFetch` caches it, and after `invalid_csrf` or `missing_csrf` it fetches once more and resends. The guard refuses before forwarding, so a retry cannot duplicate a write.
4. Map refusal codes with one table per screen instead of nested ternaries, and stop the provider panel saying "Saved." after Validate and Disconnect.

**Files.** `apps/web/lib/use-submit.ts`, `lib/csrf-fetch.ts`, `app/api/csrf/route.ts`, `workflow-editor.tsx`, `expert-editor.tsx`, `experts-panel.tsx`, `workflows-panel.tsx`, `approvals-panel.tsx`, `provider-settings-panel.tsx`, `keys-and-vars-panel.tsx`, `model-policy-panel.tsx`, `operations-panel.tsx`, `account-form.tsx`, and their browser specs.

**Risk and mitigations.** Medium. The CSRF step is high risk and lands as its own commit with the overlapping-writes test; the double-submit comparison, the Origin, Host and Sec-Fetch-Site checks and the SameSite=Strict cookie stay as they are.

**Verification.** Tests first: the browser cases. Proved by `db` and `fast`.

**Effort and dependencies.** M. Depends on [R-18](#r-18).

### <a id="r-20"></a>R-20: Run code search where its timeout can stop it

**Addresses.** high: [PTOL-01](findings/py-tools.md#ptol-01).

**Why now.** Fix. A nested-quantifier pattern supplied by the model holds the GIL inside `asyncio.to_thread`: a 0.2 s `wait_for` returned only after 1.9 s while the event loop stalled, so the lease keeper and the status beat stop and the run is handed to another worker. The code comment says the opposite.

**Steps.**

1. Add a unit test with a pathological pattern that asserts the call ends within the limit while a ticker task keeps running. It fails today.
2. Add `application/bounded.py` with `run_in_child(fn, *args, seconds)`: one spawned process (stdlib `multiprocessing`, spawn context) that is terminated on timeout and raises `BoundExceeded`.
3. Keep `search` pure Python in a module with light imports, as Decision 0017 C7 requires, call it through `run_in_child`, and report `ToolFailed('search_timeout')`.
4. Correct the comment.

**Files.** `services/agent/src/autobots/application/code_tools.py`, `application/bounded.py` (new), `services/agent/tests/test_code_tools.py`.

**Risk and mitigations.** Medium: each search now pays for a process start. Measure it in the test, and pass the files by value.

**Verification.** Tests first: the pathological-pattern test. Proved by `fast`, and by `db` for the gateway checks.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-21"></a>R-21: Move the pull-request re-request into approvals.py, fenced and in one transaction

**Addresses.** high: [PADP-02](findings/py-adapters.md#padp-02), [XMOD-02](findings/sweep-boundaries.md#xmod-02), [XDUP-02](findings/sweep-duplication.md#xdup-02).

**Why now.** Fix. When the base has moved, the GitHub adapter runs four autocommit statements with no lease check. A crash between them can leave the receipt reconciled while the approval stays approved or skip a run-event sequence number that is documented as gapless, and a worker that lost its lease can still reset a person's decision. The adapter also hard-codes the one-day TTL.

**Steps.**

1. Add a stale-generation case to `tests/db/pull_request_check.py`, beside its base-moved and re-approval cases, that expects the decision to stay untouched. It fails today.
2. Move `hold_lease` into `application/worker_leases.py`; `tool_gateway` imports `approvals`, so the move avoids a cycle.
3. Add `approvals.return_to_review(connection, *, run_id, generation, operation_id, tool_id, detail)`: one transaction that holds the lease, reconciles the receipt, resets the approval with `DEFAULT_TTL_SECONDS` and appends `approval.requested`.
4. Add `approvals.approved_request(connection, operation_id)` and a `receipt_may_have_sent(status)` predicate, and use them in the gateway and both GitHub adapters instead of their own SQL.
5. Leave the adapter only the GitHub reads that build the new diff, after which it raises `base_moved`.

**Files.** `services/agent/src/autobots/application/approvals.py`, `application/worker_leases.py`, `application/tool_gateway.py`, `adapters/github_pulls.py`, `adapters/github_issues.py`, `tests/db/pull_request_check.py`, `tests/db/approval_check.py`.

**Risk and mitigations.** High, because approvals are a consent boundary. Decision 0022 D15's behavior is kept, only moved, and `pull_request_check` and `approval_check` run before and after.

**Verification.** Tests first: the stale-generation case. Proved by `db`.

**Decision needed.** Whether `base_moved` also enters the decision wait at once, as the expiry path does ([XDUP-02](findings/sweep-duplication.md#xdup-02)). Decide it with a test.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-22"></a>R-22: Price paid trials with the application's catalog parser

**Addresses.** high: [POPS-01](findings/py-ops.md#pops-01); medium: [PADP-12](findings/py-adapters.md#padp-12), [POPS-06](findings/py-ops.md#pops-06); low: [POPS-07](findings/py-ops.md#pops-07).

**Why now.** Fix. Paid trials price calls with a second, float-based parser that ignores cache writes, reasoning tokens, per-request fees and tiers that start below the trial's prompt size, so a route can be reserved below its real worst case in the ledgers that enforce the caps of Decisions 0009 and 0019. Reservation and settlement are hand-rolled five times and have drifted.

**Steps.**

1. Move the override test (`test_route_qualification.py:514-520`) and the three `price_of` uses in `test_reasoning_trial.py` onto `Pricing`, and add a case for each pricing feature the float parser drops. They fail today.
2. Have `prepare` return the `CatalogEntry` it already validates, compute `worst_case_cost(entry.pricing, CONTEXT_TOKENS, OUTPUT_TOKENS)`, refuse on `CostUnavailable`, record `entry.pricing` as the report's catalog price, and delete `Price` and `price_of`.
3. Convert reported costs with one Decimal ceiling helper, also used by `loop_middleware`, which rounds a float today.
4. Give the trial ledger one async context manager that reserves, settles as uncertain on any `BaseException` and re-raises, and otherwise settles from the reported charge; type its entries as a dataclass with a Literal state.
5. Resolve the reasoning trial's shared US$1 ledger path from the repository root, not the working directory.

**Files.** `services/agent/src/autobots/operations/route_qualification.py`, `operations/reasoning_trial.py`, `operations/browse_trial.py`, `adapters/loop_middleware.py`, `adapters/models/catalog.py`, `services/agent/tests/test_route_qualification.py`, `services/agent/tests/test_reasoning_trial.py`.

**Risk and mitigations.** High (paid paths and caps). The shared parser is at least as conservative, so no cap is weakened; everything is proven offline with fake catalogs, and no paid trial runs as part of this item.

**Verification.** Tests first: the moved and new pricing tests. Proved by `fast`, and by `operations` with its scripted model. A live trial is a separate task that the owner authorizes and caps.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-23"></a>R-23: One tested paid-run session for the four paid entry points

**Addresses.** high: [SCRP-03](findings/scripts.md#scrp-03); medium: [TDBC-11](findings/db-tests.md#tdbc-11).

**Why now.** Fix. The spend watchdog, the settlement and the after-run checks are copied across the persistent install's goal and examples, `live_goal` and `qualify_release`, and already disagree: the examples copy can report success without knowing what it spent, and an unreadable spend never stops the worker, so each poll fails open.

**Steps.**

1. Extract pure decisions and test them in `tests/harness` with a fake clock and fake SQL: `watchdog_verdict(committed, limit, unreadable_polls)`, `settlement(started, finals, charged)` and `goal_exit_code(report)`.
2. Make "spend unreadable for N polls" an explicit decision, recorded with the owner.
3. Move the shared mechanics into `scripts/paid_run.py` (a `PaidSession` with the helper call, SQL that returns None when unreadable, sign-in, and worker start and stop) used by all four entry points, and type the ledger through a Protocol so that the 14 `type: ignore` comments go.
4. Move the live-key helper out of `tests/db` into the service's operations package, where ruff, mypy and pytest cover it.

**Files.** `scripts/paid_run.py` (new), `scripts/persistent_install.py`, `scripts/live_goal.py`, `scripts/qualify_release.py`, `tests/db/live_goal_helper.py`, `tests/harness/test_paid_run.py` (new), `services/agent/src/autobots/operations/`.

**Risk and mitigations.** High: these paths spend real money under the shared cap. Keep the `--paid` refusal, `refuse_other_work`, the reservation before any request, the SIGKILL watchdog and the hold-on-unfinished settlement. No paid run is part of this item.

**Verification.** Tests first: the pure decision tests. Proved by `harness`, and by `db` for the persistent install's guarded paths. Live runs stay owner-authorized.

**Decision needed.** What the watchdog does when spend stays unreadable ([SCRP-03](findings/scripts.md#scrp-03)).

**Effort and dependencies.** M. Depends on [R-07](#r-07).

### <a id="r-24"></a>R-24: One readiness gate for people and routines

**Addresses.** high: [POPS-02](findings/py-ops.md#pops-02); medium: [PAPI-10](findings/py-api.md#papi-10).

**Why now.** Fix. When the code is newer than the database (`schema_behind`, Decision 0023 E2), a person's run is refused while the worker still evaluates and admits due routines. Every new blocking condition must be added to two gates, and both re-read the environment on every call, so a malformed `AUTOBOTS_MIN_FREE_BYTES` fails every admission.

**Steps.**

1. Extend database check M14 to arrange `schema_behind` and a held install, and expect a due routine to be refused. The first case fails today.
2. Add `application/readiness.py` with `ReadinessSettings` (data root, minimum free bytes) parsed once per process, `installation_conditions(connection, store, settings)` and `first_blocking(conditions)`.
3. Call it from `api.require_ready` and from the worker's maintenance step, which logs the refusing code, skips routines and keeps retention.
4. Read the other environment values that API handlers parse per request into the same settings object at startup.

**Files.** `services/agent/src/autobots/application/readiness.py` (new), `operations/worker.py`, `api/operation_routes.py`, `api/run_routes.py`, `api/settings_routes.py`, `application/operations.py`, `tests/db/major_check.py`.

**Risk and mitigations.** Medium. It strengthens an admission guard (LM-07, Decision 0023 E2), and scheduling stays in Python.

**Verification.** Tests first: the M14 cases and unit tests of `first_blocking`. Proved by `fast` and `db`, and by `operations`, which exercises the worker's maintenance step.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-25"></a>R-25: Keep failure causes in private logs and tool receipts

**Addresses.** high: [XERR-01](findings/sweep-errors.md#xerr-01), [XERR-02](findings/sweep-errors.md#xerr-02); medium: [POPS-10](findings/py-ops.md#pops-10), [PTOL-10](findings/py-tools.md#ptol-10), [XERR-06](findings/sweep-errors.md#xerr-06), [XERR-11](findings/sweep-errors.md#xerr-11), [XERR-12](findings/sweep-errors.md#xerr-12), [XERR-13](findings/sweep-errors.md#xerr-13).

**Why now.** An unattended worker failure logs only `{"error":"KeyError"}`, an unexpected API failure leaves only uvicorn's reduced line, and the tool gateway records a timeout, an unclear GitHub reply and a parser defect as the same unknown receipt, which is the evidence a person rules on. A database outage during a request becomes a 500 after up to 30 seconds.

**Steps.**

1. Extend `test_operations.py` to require frames and forbid planted secrets, and add gateway tests whose handlers raise `KeyError` and `UnclearReply`, asserting the receipt detail and one log line. They fail today.
2. Add `error_fields(error)` to `operations/logs.py` (the module-qualified type, a bounded cause chain, and the last frames as path, line and function, never messages or locals), use it in `JsonFormatter`, and replace the 13 `error=type(error).__name__` arguments.
3. Log `api.unhandled` with the method and route template before the 500 response, map `psycopg.OperationalError` to a retryable 503 `service_unavailable` with fixed wording, and give the pool an explicit timeout.
4. Add `OutcomeUnknown` with a detail category to the gateway, with one `UnclearReply` subclass for both GitHub adapters, and fill the existing nullable `failure_detail` of unknown and failed receipts with that category or `defect:<qualified type>`. Reads and review denials get the log line only.
5. Add one `stop_task(task)` helper (cancel, then `asyncio.wait`), so that cleanup never discards the caller's cancellation, and use it in `browsing_tool`, `goal_loop`, `workflow_runner` and the worker.
6. Write the logging conventions beside `log_event` (event names by PRD 12.2 category, standard context keys, levels by audience), and give each deliberately tolerated failure one rate-limited WARNING.

**Files.** `services/agent/src/autobots/operations/logs.py`, `api/errors.py`, `api/app.py`, `application/tool_gateway.py`, `adapters/github_issues.py`, `adapters/github_pulls.py`, `operations/worker.py`, `application/routines.py`, `application/retention.py`, `application/browsing_tool.py`, `application/goal_loop.py`, `application/workflow_runner.py`, `services/agent/tests/test_operations.py`, and gateway tests.

**Risk and mitigations.** Medium. No message text or locals reach a log (the leak assertions stay); outcome classes, retries and receipt statuses are unchanged; only the existing `failure_detail` column is filled, and its migration is not edited; nothing goes to a hosted tracer.

**Verification.** Tests first: the log and receipt tests, and an API test that a 500 writes one `api.unhandled` line. Proved by `fast`, and by `db` for the gateway checks.

**Effort and dependencies.** M. Depends on [R-15](#r-15).

### <a id="r-26"></a>R-26: Server reads and the BFF keep failure causes, and stop reporting outages as sign-outs

**Addresses.** high: [WSHL-02](findings/web-shell.md#wshl-02); medium: [XDUP-12](findings/sweep-duplication.md#xdup-12), [XERR-05](findings/sweep-errors.md#xerr-05), [WCMP-06](findings/web-composer.md#wcmp-06), [WSHL-05](findings/web-shell.md#wshl-05), [WSHL-07](findings/web-shell.md#wshl-07), [WSHL-20](findings/web-shell.md#wshl-20); low: [XMOD-16](findings/sweep-boundaries.md#xmod-16), [WSHL-15](findings/web-shell.md#wshl-15), [WSHL-16](findings/web-shell.md#wshl-16).

**Why now.** A role value this build does not know, an API on another revision, a missing internal token and a 3-second timeout all show a signed-in person the Sign in link. Sign-in reports an unavailable Auth service as a wrong password, and no log line in `apps/web` records which of these happened.

**Steps.**

1. Extract `bff.ts`'s pure policy (body limits, header allowlists, refusal mapping) and cover it with `node:test`; add browser cases that make the session read unavailable with `page.route` and expect the unavailable state, not Sign in.
2. Add a server-only `logFailure(operation, error)` that records the operation, the error class, the `ContractError` path, the status and whether a timeout fired, and never bodies, headers, tokens or query strings.
3. Make `service-status` return `ok`, `signed_out` (no token, or a 401) or `unavailable`. Render Sign in only for `signed_out`, and answer `/api/workspace` with 503 when the session read is unavailable.
4. In `forward()`, log the cause and map the BFF's own timeout to 504 `upstream_timeout`. Make the session route tell an Auth outage from a wrong password, and make sign-out report a failure.
5. Fail fast on missing server configuration instead of defaulting to empty strings, build the guard input, error envelope, cookie policy and JSON body read once for the three route files, and drop the alias routes that the `/api/v1` catch-all already forwards, keeping the settings query string.
6. Keep the waiting notifier polling, with backoff, after a 401 or a bad reply.

**Files.** `apps/web/lib/server-log.ts` (new), `lib/service-status.ts`, `lib/bff.ts`, `lib/server-config.ts`, `lib/session.ts`, `app/api/session/route.ts`, `app/api/workspace/route.ts`, `app/api/settings/[...path]/route.ts`, `app/api/models/route.ts`, `components/account-footer.tsx`, `components/sign-in-form.tsx`, `components/sign-out-button.tsx`, `components/waiting-notifier.tsx`.

**Risk and mitigations.** Medium (authentication and the BFF). Server keys never reach props or public responses, logs carry only names, codes, statuses and paths, and the same-origin and CSRF checks stay as they are.

**Verification.** Tests first: the BFF policy tests and the browser cases. Proved by `fast` and `db` (the identity and boundary suites); `full` also runs the boundary spec.

**Effort and dependencies.** M. Depends on [R-02](#r-02).

### <a id="r-27"></a>R-27: One read hook with explicit view states

**Addresses.** high: [XERR-03](findings/sweep-errors.md#xerr-03), [XTYP-14](findings/sweep-types.md#xtyp-14), [XWEB-02](findings/sweep-web-architecture.md#xweb-02); medium: [XERR-04](findings/sweep-errors.md#xerr-04), [XWEB-06](findings/sweep-web-architecture.md#xweb-06), [WBLD-08](findings/web-build.md#wbld-08), [WCMP-05](findings/web-composer.md#wcmp-05), [WCMP-08](findings/web-composer.md#wcmp-08); low: [WRUN-16](findings/web-run.md#wrun-16).

**Why now.** Twenty-eight effects in 23 files hand-roll fetch-in-effect with their own flags, only 2 abort a stale request, and every screen catches a contract mismatch with the same handler as a network error, so drift reads as an outage or as an endless "reconnecting", and nothing records which field failed. The screen splits in this wave need the hook first.

**Steps.**

1. Write `node:test` cases for a pure `loadJson(path, parse)` classification: 401 is signed out, 403 is denied with the envelope's message, 404 and 422 are not found, 5xx and network failures are unavailable and retryable, and a `ContractError` or invalid JSON is out of date, with its path. Non-ok bodies are drained.
2. Move `useLoaded` from `tool-catalog.tsx` into `lib/use-resource.ts`: one discriminated union plus `reload()`, an `AbortController`, body draining, and sharing of identical GETs that are in flight at the same time, keeping nothing after they settle so that no workspace data outlives a sign-out.
3. Add `components/ui/load-state.tsx`, which renders loading, denied, unavailable with Retry, out of date ("This page and the local service disagree. Reload after updating.") and empty with one announcement role, and logs a `ContractError`'s schema and path, never values.
4. Migrate the tool catalog, the run list, home activity and search, and the workflow monitor, which also gets backoff and stops reloading every tool use on each poll. Other screens move when they are split.
5. Remove the migrated files from the raw-fetch baseline of [R-06](#r-06).

**Files.** `apps/web/lib/load.ts`, `apps/web/lib/use-resource.ts` and `apps/web/components/ui/load-state.tsx` (new); `tool-catalog.tsx`, `run-list.tsx`, `home-activity.tsx`, `search-palette.tsx`, `workflow-monitor.tsx`, `tool-uses.tsx`, `apps/web/app/page.tsx`.

**Risk and mitigations.** Medium, because failure wording changes. Keep every `data-*` hook and success-path sentence the suites read (Decision 0021 R1), and add `page.route` cases for 403, 422 and a malformed body.

**Verification.** Tests first: the classification tests, and one `page.route` browser case per state. Proved by `fast` and `db`; `full` for the tools spec.

**Effort and dependencies.** M. Depends on [R-02](#r-02), [R-09](#r-09).

### <a id="r-28"></a>R-28: The run page stops polling denied runs and keeps refreshes in order

**Addresses.** high: [WRUN-02](findings/web-run.md#wrun-02); medium: [WRUN-04](findings/web-run.md#wrun-04).

**Why now.** Fix. On 401 or 404 the run page says the run is unavailable but keeps requesting `/workspace` every second; on 403, 422, a 5xx or a contract error it never leaves Loading; and because every stored event refetches the whole snapshot, an older reply can overwrite a newer one.

**Steps.**

1. Add `page.route` browser cases for 403, 422, a 5xx that recovers and a malformed body, and one that delays an older snapshot reply past a newer one.
2. Extract `useRunWorkspace` with an explicit load state (loading; ready, possibly reconnecting; signed out; denied, with the envelope's message; not found; retrying, with the attempt; invalid, with the path), built on the classification from [R-27](#r-27). It stops on signed out, denied, not found and invalid, and backs off 1 s, 2 s and 4 s up to 30 s with a visible Retry.
3. Coalesce refreshes and discard a reply older than the newest applied cursor, and catch rejections from `start()` instead of discarding them with `void`.
4. Give RunInspectorView and RunList the same classification.

**Files.** `apps/web/components/run-workspace.tsx`, `apps/web/components/runs/workspace/use-run-workspace.ts` (new), `run-inspector.tsx`, `run-list.tsx`, `apps/web/tests/browser/run-workspace.spec.ts`.

**Risk and mitigations.** Medium. Keep every `data-*` hook and sentence the suites read; reads stay idempotent, and no server guard changes.

**Verification.** Tests first: the browser cases above. Proved by `db` and `fast`.

**Effort and dependencies.** M. Depends on [R-27](#r-27).

### <a id="r-29"></a>R-29: One stop-code vocabulary with an explicit disposition table

**Addresses.** high: [PPRD-03](findings/py-product.md#pprd-03), [PRUN-02](findings/py-run.md#prun-02); medium: [PTOL-09](findings/py-tools.md#ptol-09).

**Why now.** A run's fate is decided by membership in five hand-kept string sets in three modules, so a new or misspelled code silently becomes a terminal FAILED run that can never resume, and `parent_not_running` is a wait in `goal_loop` but a node failure in a workflow.

**Steps.**

1. Add `domain/stops.py` with a `StopCode` StrEnum and a `DISPOSITION` table that maps every code reaching `_finish` to today's behavior (verify, suspend, fail or release). This changes no behavior.
2. Add `GatewayCode` beside it for the codes the gateway produces, derive `PAUSE_FOR`, `NOT_OURS`, `STOPPING`, `REPAIRABLE`, `STOPS` and `RETRY_LATER` from the table, and type `LoopResult.outcome`.
3. Add exhaustive tests: every `FailureClass` value, `AdmissionRefused` code, `LimitReached` counter, `STOPPING` member and code that `assign_tool` can raise has a disposition, and each StrEnum value equals the stored string.
4. Reproduce the pause-inside-`_create` race in `blocker_check`, then add `parent_not_running` to the workflow's stops as its own change.
5. Compare outcomes with `ToolOutcome` members rather than `.value` strings.

**Files.** `services/agent/src/autobots/domain/stops.py` (new), `application/goal_loop.py`, `application/workflow_runner.py`, `application/assignments.py`, `application/tool_gateway.py`, `application/plans.py`, `adapters/loop_middleware.py`, `tests/db/blocker_check.py`.

**Risk and mitigations.** Medium. Steps 1 to 3 preserve behavior; step 4 is a behavior fix proven by its reproduction first. Terminal runs still cannot resume (SP-010).

**Verification.** Tests first: the exhaustive disposition tests and the `blocker_check` race case. Proved by `fast` and `db`.

**Decision needed.** Whether an unmapped code should suspend instead of fail ([PRUN-02](findings/py-run.md#prun-02)). The table makes today's choice explicit until the owner decides.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-30"></a>R-30: Typed run admission inputs

**Addresses.** high: [PPRD-01](findings/py-product.md#pprd-01), [PRUN-04](findings/py-run.md#prun-04).

**Why now.** `admit_run` takes 15 parameters and a binding typed `Any`, which three call sites fill with `SimpleNamespace` and one with a class built by `type()`. The binding sets the run's tool grant and instructions and part of the idempotency fingerprint, which must stay byte-identical for replays, yet mypy strict accepts any object.

**Steps.**

1. Add a golden test of `request_hash` payloads for every caller shape, captured from today's code, and a database check that replays an existing receipt before and after the change.
2. Declare an `AdmissionGrant` Protocol and a frozen `RunGrant` dataclass in `runs.py`. `RunBinding` and `Inheritance` satisfy the Protocol structurally, so no types merge.
3. Introduce a frozen `RunAdmission` request with a `Fresh | Inherited` origin, so that "a policy unless inherited" becomes a type rule, and build `RunGrant` at the routines, workflows, improvements and browse-trial call sites.
4. Extract the fingerprint, the continuation check and the inserts, and keep the run, job, first event and receipt in one transaction.

**Files.** `services/agent/src/autobots/application/runs.py`, `application/routines.py`, `application/workflows.py`, `application/improvements.py`, `application/experts.py`, `application/assignments.py`, `operations/browse_trial.py`, `api/run_routes.py`.

**Risk and mitigations.** High (paid admission and durable receipts). The golden hashes and the replay check prove that fingerprints are unchanged, and Decision 0015's `started_by` rule is unchanged.

**Verification.** Tests first: the golden hash test and the replay check. Proved by `fast` (mypy now checks every caller) and `db`.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-31"></a>R-31: An admission use case and one gate for model-backed work

**Addresses.** high: [PAPI-02](findings/py-api.md#papi-02); medium: [PAPI-04](findings/py-api.md#papi-04), [PAPI-15](findings/py-api.md#papi-15), [PPRD-09](findings/py-product.md#pprd-09), [XDUP-08](findings/sweep-duplication.md#xdup-08).

**Why now.** `post_run` packs nine admission concerns into a 101-line handler that no in-process test reaches (the `session_required` branch is tested nowhere), and the gate for model-backed work (policy, key readiness, offered profiles, limit) is rebuilt in five handlers and again in routines and workflows.

**Steps.**

1. Add an `api_client` fixture (settings, a fake membership, a fake pool, a token helper), and branch-by-branch tests of `post_run`'s nine steps and their refusal order against a fake admission use case.
2. Extract `application/run_admission.py`: a frozen `AdmissionInput` and `admit_from_request(...)`, which returns the result or raises typed refusals. The handler gathers dependencies, calls it and maps refusals.
3. Name the gate in the application layer (`workspace_role_policy`, `require_model_ready`, the offered-policy check, `chosen_limit`), with deliberate differences as explicit parameters, and call it from the five handlers, routines, workflows and the preview.
4. Add a helper that turns an `ExpertConfig` into overrides, replacing the comprehension repeated four times.

**Files.** `services/agent/src/autobots/application/run_admission.py` (new), `api/run_routes.py`, `api/improvement_routes.py`, `api/workflow_routes.py`, `application/routines.py`, `application/workflows.py`, `application/workflow_overview.py`, `services/agent/tests/conftest.py`, `services/agent/tests/test_api.py`.

**Risk and mitigations.** High (paid admission and authorization). Refusal codes and their order stay, the Decision 0011 owner-only pin and the PK-02 refusal move with their comments, and the worker still re-checks key readiness before dispatch.

**Verification.** Tests first: the in-process branch tests. Proved by `fast` and `db` (the admission checks and the browser suites that assert refusal codes).

**Effort and dependencies.** M. Depends on [R-30](#r-30).

### <a id="r-32"></a>R-32: Seams for the paid-path tests

**Addresses.** high: [PTST-01](findings/py-tests.md#ptst-01); medium: [PTST-02](findings/py-tests.md#ptst-02), [PTST-03](findings/py-tests.md#ptst-03), [PTST-04](findings/py-tests.md#ptst-04), [PTST-08](findings/py-tests.md#ptst-08); low: [PTST-18](findings/py-tests.md#ptst-18), [XTYP-17](findings/sweep-types.md#xtyp-17).

**Why now.** Paid-path tests subclass `LoopMiddleware` and `ProviderSettings`, or build them without their constructors, to swap private steps, so any behavior-preserving extraction in the 674-line middleware (whose `_admitted_call` has C901 15) would break the budget, busy-slot and cut-off tests at once. The shared fake transport still encodes the superseded two-profile policy.

**Steps.**

1. Add keyword-only seams whose defaults keep today's behavior: `LoopMiddleware` takes `guard` and `admission`, public context managers wrap its two ContextVars, `ProviderSettings` takes the credential store and a settings-row reader, and `CatalogCache` staleness uses its existing `now=`.
2. Move the pure reply helpers (`_charged`, `_finished`, `_retry_after`, `_failure_without_status`) into a public module.
3. Write seam-based tests beside the current ones and see them pass against today's code, then delete the private overrides.
4. Build one fake-provider kit (a completion, a tool call, and a catalog payload derived from `PROFILES`, including Sol) next to `completion_to_sse`, and use it in the six test files and in `tests/db`.
5. Replace source-text checks of paid-path wiring with behavior (call the bound factory and inspect its configuration), and use controlled clocks instead of real sleeps.
6. Split `test_worker_inference.py` (1,149 lines) by the module under test, first moving the tests unchanged in one mechanical commit.

**Files.** `services/agent/src/autobots/adapters/loop_middleware.py`, `adapters/model_replies.py` (new), `application/provider_settings.py`, `services/agent/tests/fake_openrouter.py`, `test_worker_inference.py` (split), `test_operations.py`, `test_readiness.py`, `test_browsing_loop.py`, `test_final_review.py`.

**Risk and mitigations.** High (paid path). The seams default to today's guard and admission, so no production call site passes them and no budget or concurrency check is weakened; the database profile still drives the real ledger.

**Verification.** Tests first: the seam-based tests, green against today's code before any override is deleted. Proved by `fast`, and by `db` for the product inference checks.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-33"></a>R-33: A public run-lifecycle module, without the goal_loop and workflow_runner cycle

**Addresses.** high: [TDBC-02](findings/db-tests.md#tdbc-02), [PPRD-02](findings/py-product.md#pprd-02); medium: [PRUN-15](findings/py-run.md#prun-15), [PRUN-17](findings/py-run.md#prun-17), [XMOD-07](findings/sweep-boundaries.md#xmod-07).

**Why now.** `workflow_runner` imports five private `goal_loop` functions, and `goal_loop` imports `run_workflow` back inside `_drive`. Fourteen database check files use 21 private product names, so renaming one passes `fast` and `full` and then breaks a check that runs only with Docker. The lease keeper is started and stopped by hand in three places, and its cancelled task is never awaited.

**Steps.**

1. Run the non-strict mypy over `tests/db` from [R-07](#r-07), so that a missing name fails in seconds.
2. Create `application/run_lifecycle.py` with `LoopConfig`, `LoopResult`, `finish`, `result_of`, `run_status` and a `lease_heartbeat` async context manager that starts the keeper and then cancels and awaits its task.
3. Break the cycle by injection: `_drive` passes its own child driver to `run_workflow`, so `workflow_runner` never imports `goal_loop`.
4. Give the seams the database checks drive public, documented names (drive a claimed lease, settle a candidate, settle children, keep a lease, commit an instance), keep temporary re-exports until the checks move, and patch only module-level seams with `patch.object`.
5. Add table-driven unit tests for one look of the lease keeper, with the injected `WakeClock`.

**Files.** `services/agent/src/autobots/application/run_lifecycle.py` (new), `application/goal_loop.py`, `application/workflow_runner.py`, `application/tool_gateway.py`, `application/plans.py`, `application/routines.py`, `api/event_routes.py`, and the 14 files in `tests/db` that use private names.

**Risk and mitigations.** Medium, because finish and settle behavior is sensitive. Code moves only; lease checks, fencing, receipts and transaction boundaries stay in the same functions.

**Verification.** Tests first: `blocker_check`, `workflow_run_check` and the goal-loop database checks pass before the move, and the lease-keeper unit tests. Proved by `db` and `fast`.

**Effort and dependencies.** M. Depends on [R-07](#r-07).

### <a id="r-34"></a>R-34: Decide how a pass ends with one pure function

**Addresses.** high: [PRUN-03](findings/py-run.md#prun-03).

**Why now.** Every goal and workflow pass ends in `_finish`, which normalizes the code, settles a cancelled tree, releases a paused job, picks the command and commits it, reading the run status three times. Its decision table can be exercised only through a disposable database, and a refused command is reported as a lost lease, so a parent's assignment sees "lost" for what was a state conflict.

**Steps.**

1. Write table tests for a pure `decide(code, observed)` that cover every row of today's behavior (status, lease ownership, plan state).
2. Read the status and ownership once into a frozen `Observed`, decide with the pure function, then run the effects.
3. Keep the generation and `status='claimed'` predicates on job writes, keep `classify_interrupted` before `FINISH_CANCEL`, and keep the transition and its `stop_reason` in one transaction.
4. Give a refused command its own stop code instead of `lease_lost`.

**Files.** `services/agent/src/autobots/application/run_lifecycle.py`, `application/goal_loop.py`, unit tests in `services/agent/tests/`, `tests/db/blocker_check.py`.

**Risk and mitigations.** High (run state). `apply_command` still re-validates under row locks, so the gain is clarity, testability and honest reporting; the SP-010 cancellation rules and SP-012 fencing are unchanged.

**Verification.** Tests first: the decision-table tests. Proved by `fast` and `db`.

**Effort and dependencies.** M. Depends on [R-33](#r-33), [R-29](#r-29).

### <a id="r-35"></a>R-35: Record and bound worker failures

**Addresses.** medium: [PRUN-14](findings/py-run.md#prun-14), [XERR-10](findings/sweep-errors.md#xerr-10).

**Why now.** Fix. An exception that no handler classifies leaves the job claimed for endless re-claims with no durable reason, and nothing reads the attempt count, so a broken run takes worker time forever and nobody can see why.

**Steps.**

1. Record the owner's decision on the bound and on the state a run reaches when it is hit.
2. Add a database case that makes dispatch raise repeatedly, and expect a bounded number of claims and a visible state.
3. Write a forward migration that adds private failure fields to `app_private.run_jobs` (for example `last_failure_type` and `failed_attempts`), written with the qualified exception type and never its message.
4. In the dispatch step, catch `Exception` (not `BaseException`, so cancellation still propagates), log the run id with `error_fields`, release the job with backoff through `available_at` below the bound, and at the bound move the run to the decided state through `apply_command`.

**Files.** `supabase/migrations/<new>_run_job_failures.sql`, `services/agent/src/autobots/application/worker_leases.py`, `application/goal_loop.py` (or `job_dispatch.py` after [R-42](#r-42)), `operations/worker.py`, `tests/db/`.

**Risk and mitigations.** High (durable worker semantics). A paused run stays resumable, public events carry at most the attempt number, and the migration only moves forward.

**Verification.** Tests first: the repeated-failure database case. Proved by `db`, and by `operations` for the worker runbooks.

**Decision needed.** The bound on consecutive failed attempts, and the state it leads to (SP-012 bounded retries; [XERR-10](findings/sweep-errors.md#xerr-10)).

**Effort and dependencies.** M. Depends on [R-25](#r-25), [R-33](#r-33).

### <a id="r-36"></a>R-36: Resolve each tool call once in the gateway

**Addresses.** high: [PTOL-02](findings/py-tools.md#ptol-02); medium: [PTOL-04](findings/py-tools.md#ptol-04), [PTOL-05](findings/py-tools.md#ptol-05).

**Why now.** `ToolGateway._dispatch` is the single enforcement point for every tool call (C901 19, 15 returns), computes the operation id five times, and is unit-tested only by passing `connection=None`. `approval_gate` takes 18 parameters, three of them optional although Decision 0015 requires them, and the approval rule is written in four places.

**Steps.**

1. Add unit tests for a pure `resolve(registry, scope, name, arguments)`, returning a `Call` or a refusal (grant, registry, qualification, validation, path grants), and for a pure `gate_decision(row, scope_hash, receipt)`.
2. Build a frozen `Call` (tool, parsed arguments, argument hash, operation id) once per dispatch, and pass it to `begin_use`, `complete_use`, `_effect` and `_read`.
3. Split the rest into named steps in today's order (admission refusal, hold for approval, metered budget), with today's codes and `APPROVAL_POLICY_VERSION`.
4. Group the six approval fields into one `ApprovalPolicy` on `ToolDefinition`, used by the gateway, the catalog and the pin test, and extend the pin test to every operation class.
5. Pass `approval_gate` one frozen `ApprovalProposal` with the Decision 0015 fields required.

**Files.** `services/agent/src/autobots/application/tool_gateway.py`, `application/approvals.py`, `application/tool_catalog.py`, `application/tool_uses.py`, `services/agent/tests/test_tools.py`, and gateway unit tests.

**Risk and mitigations.** Medium, because the guard order is the security contract. Keep it, and prove it with `tool_gateway_check`, `approval_check` and `effect_check` (SP-013: arguments are validated before any effect).

**Verification.** Tests first: the `resolve` and `gate_decision` tests, which replace the `connection=None` seams. Proved by `fast` and `db`.

**Effort and dependencies.** M. Depends on [R-21](#r-21).

### <a id="r-37"></a>R-37: Shared run vocabulary, labels and formatting for the web

**Addresses.** medium: [XDUP-10](findings/sweep-duplication.md#xdup-10), [XDUP-17](findings/sweep-duplication.md#xdup-17), [XTYP-06](findings/sweep-types.md#xtyp-06), [XWEB-04](findings/sweep-web-architecture.md#xweb-04), [XWEB-08](findings/sweep-web-architecture.md#xweb-08), [XWEB-09](findings/sweep-web-architecture.md#xweb-09), [XWEB-10](findings/sweep-web-architecture.md#xweb-10), [WBLD-07](findings/web-build.md#wbld-07), [WBLD-13](findings/web-build.md#wbld-13), [WBLD-14](findings/web-build.md#wbld-14), [WCMP-12](findings/web-composer.md#wcmp-12), [WRUN-07](findings/web-run.md#wrun-07), [WRUN-08](findings/web-run.md#wrun-08), [WRUN-09](findings/web-run.md#wrun-09), [WRUN-10](findings/web-run.md#wrun-10), [WRUN-11](findings/web-run.md#wrun-11), [WTAP-07](findings/web-tools-approvals.md#wtap-07); low: [XDUP-16](findings/sweep-duplication.md#xdup-16), [WCMP-13](findings/web-composer.md#wcmp-13), [WCMP-14](findings/web-composer.md#wcmp-14), [WSYS-09](findings/web-system.md#wsys-09), [WTAP-06](findings/web-tools-approvals.md#wtap-06), [WTAP-10](findings/web-tools-approvals.md#wtap-10).

**Why now.** Run status words and tones, money, time and duration formatting, budget choices and model profile names are defined per screen and already disagree, and shared pieces are imported sideways from feature components, including a run-list and run-panel cycle. The screen splits need these modules first, or each split copies them again.

**Steps.**

1. Write `node:test` cases that pin today's output of each copy, and decide one result where they disagree; list each changed string in the change's proposal.
2. Add JSX-free modules: `lib/runs/status.ts` (labels and tones keyed by the generated `RunStatus`, with an exhaustive check), `lib/format.ts` (money, relative time and duration, with one rounding rule), `lib/budget.ts` (choices from the server's range, refusing a step of zero or less and capping the count) and `lib/tools/text.ts` (the tool text that the Expert editor imports from a client component today).
3. Key every label map by the generated unions instead of `Record<string, ...>`.
4. Read profile names and the offered set from the models endpoint instead of three hard-coded copies, and take the default budget from the server.
5. Replace the copies and the sideways imports, remove the cycle and its entry in the cycle-rule baseline of [R-06](#r-06), and write the summarizer-differs rule once.

**Files.** `apps/web/lib/runs/status.ts`, `lib/format.ts`, `lib/budget.ts` and `lib/tools/text.ts` (new), and the run, home, composer, workflow, Experts, approvals, operations and tool-catalog components that hold copies.

**Risk and mitigations.** Low, except that unifying the diverged formats changes some visible strings; the specs that assert them change in the same commit.

**Verification.** Tests first: the `node:test` pins. Proved by `fast` (`web_unit_tests`, `lint`, `typecheck`) and `db`.

**Effort and dependencies.** M. Depends on [R-01](#r-01), [R-06](#r-06).

### <a id="r-38"></a>R-38: A shared module for the database checks

**Addresses.** high: [TDBC-03](findings/db-tests.md#tdbc-03); medium: [TDBC-04](findings/db-tests.md#tdbc-04), [TDBC-05](findings/db-tests.md#tdbc-05), [XDUP-14](findings/sweep-duplication.md#xdup-14); low: [TDBC-13](findings/db-tests.md#tdbc-13).

**Why now.** Forty-two files define their own `check()` in six truncation variants, 24 copy `value()`, 32 insert their own folder into `sys.path`, and 26 of 43 scripts print nothing after a crash, so a change to the case shape or to `admit_run` means editing about 40 files that no tool checks.

**Steps.**

1. Add `tests/db/checklib.py`: the typed case protocol with a `check` that evaluates once; a `refused(...)` helper; `run_check(main)`, which always prints the cases after the leak scan; per-scenario guards; a `Db` wrapper (`value` raising `NoRow`, `admit`, `claim`, `command` reading the current version, `expire`, `approve`, `quiesce`); and helpers for leaked secrets, one pool and a killed worker.
2. Name the isolation step once: end only what `claim_next` could take (queued jobs and expired leases), then assert the claimed run.
3. Delete the 32 `sys.path` inserts and their E402 suppressions now; require the module for new checks, and migrate files when they are next touched, largest first.
4. Swap globals with `patch.object` as a context manager, and use temporary directories for every scratch home.
5. Give `scripts/app_db.py` one `run_check` that records empty output as a failure.

**Files.** `tests/db/checklib.py` (new), `tests/db/*_check.py`, `scripts/app_db.py`, and a harness test for `checklib`.

**Risk and mitigations.** Low. The DH-W04 expected-and-observed record shape stays, so `app_db.py` and the qualifiers parse it unchanged.

**Verification.** Tests first: a harness test that a crashing check still prints its cases and that a refusal of the wrong class fails. Proved by `db` and `harness`.

**Effort and dependencies.** M. Depends on [R-08](#r-08).

### <a id="r-39"></a>R-39: One qualification runner for child checks, with typed case records

**Addresses.** high: [SCRP-01](findings/scripts.md#scrp-01); medium: [SCRP-08](findings/scripts.md#scrp-08), [SCRP-09](findings/scripts.md#scrp-09), [SCRP-10](findings/scripts.md#scrp-10).

**Why now.** The service child-check runner is copied 29 times with divergent failure handling: a child whose last line is not its JSON report raises out of `qualify()`, which catches only `Refused` and `Unavailable`. Two unrelated `Unavailable` classes break the exit-code contract where scripts mix them, and arrangements that fail unchecked let cases pass vacuously.

**Steps.**

1. Add harness tests for `run_child_check` with fake children: a non-zero exit, partial output, a late warning after the report and a missing report each record one failed case and never raise.
2. Add `scripts/qualification/children.py` with `service_env(...)`, built once, and `run_child_check(cases, root, script, *args, label, env, timeout, cwd, err_dir)`, keeping stderr under the profile's `.checks` directory.
3. Express the tool children in `app_db` and the child loop in `qualify_identity` as data tables, keeping each child's arguments, environment and timeout.
4. Type the case record, child report and qualification report (Literal class and transport, TypedDicts) for `Cases`, the step classes in `verify` and `evidence.py`, and keep one `Unavailable` class for exit code 2.
5. Route every arrangement through a helper that records "arranged: <label>" or raises `Unavailable`, and replace escaped newlines with real ones.

**Files.** `scripts/qualification/children.py` (new), `scripts/app_db.py`, `scripts/qualify_identity.py`, `scripts/qualify_operations.py`, `scripts/qualify_upgrade.py`, `scripts/qualify_backup.py`, `scripts/qualify_browse_goal.py`, `scripts/qualify_browser_executor.py`, `scripts/disposable_db.py`, `scripts/toolchain.py`, `scripts/evidence.py`, `scripts/verify.py`.

**Risk and mitigations.** Medium: these scripts produce the `db` and `operations` evidence. A check that could not run stays visible as failed (DH-09.2), and no target guard changes.

**Verification.** Tests first: the fake-child harness tests. Proved by `harness`, `db` and `operations`.

**Effort and dependencies.** M. Depends on [R-07](#r-07).

### <a id="r-40"></a>R-40: A shared support layer for the browser tests

**Addresses.** high: [TWEB-02](findings/web-tests.md#tweb-02); medium: [XDUP-15](findings/sweep-duplication.md#xdup-15), [TWEB-04](findings/web-tests.md#tweb-04), [TWEB-05](findings/web-tests.md#tweb-05), [TWEB-08](findings/web-tests.md#tweb-08), [TWEB-10](findings/web-tests.md#tweb-10), [TWEB-11](findings/web-tests.md#tweb-11), [TWEB-13](findings/web-tests.md#tweb-13); low: [XTYP-18](findings/sweep-types.md#xtyp-18), [TWEB-14](findings/web-tests.md#tweb-14), [TWEB-16](findings/web-tests.md#tweb-16), [TWEB-18](findings/web-tests.md#tweb-18), [TWEB-19](findings/web-tests.md#tweb-19).

**Why now.** Thirty-eight of 41 specs carry about 747 lines of copied sign-in, CSRF, key and axe helpers that already differ, 21 of 35 axe scans fall short of the WCAG 2.1 A and AA pass line that Decision 0010 sets, and API calls in specs are untyped. The screen refactors need suites that are cheap to adapt.

**Steps.**

1. Create `apps/web/tests/browser/support/` with `auth.ts` (sign-in and a users map); `api.ts` (`writeHeaders(page, key = crypto.randomUUID())`, `getJson`, a `send` that asserts the status before parsing with the generated parsers, and `expectRefusal`); `keys.ts`; `a11y.ts` (one helper with the WCAG 2.1 A and AA tags, keeping wcag22aa where scans use it today); `fixtures.ts` (role pages whose contexts it closes); one leak deny-list; and builders for run payloads and graphs.
2. Migrate the specs file by file, and keep `identity.spec.ts` signing in through the form.
3. Give Python helper calls a timeout and a clear error, and fail early with a named message when a required environment variable is missing.
4. Await response bodies in leak checks before asserting, and close every context the specs create.

**Files.** `apps/web/tests/browser/support/*` (new) and the specs.

**Risk and mitigations.** Low: test code only, outside the app bundle. Storage states for disposable roles go to the ignored output directory.

**Verification.** Each migrated spec keeps its test count and names. Proved by `db` (the identity suites) and `full` (the web suites).

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-41"></a>R-41: One refusal base, typed ledger exceptions and one HTTP mapping

**Addresses.** medium: [PADP-11](findings/py-adapters.md#padp-11), [PAPI-05](findings/py-api.md#papi-05), [PDOM-13](findings/py-domain.md#pdom-13), [POPS-09](findings/py-ops.md#pops-09), [PRUN-13](findings/py-run.md#prun-13), [XERR-07](findings/sweep-errors.md#xerr-07); low: [PPRD-17](findings/py-product.md#pprd-17), [XERR-15](findings/sweep-errors.md#xerr-15).

**Why now.** Refusals take four code conventions with no shared base, 11 route modules map them to HTTP partly by string suffix, a bare `ValueError` is read as "recovery closed this attempt", and seven callers compensate for the credential store's escaping decryption errors.

**Steps.**

1. Add parametrized API tests of every refusal-to-status mapping, with today's codes and statuses.
2. Add `domain/errors.py` with a `Refusal` base (a code, an optional internal detail, and a `RefusalKind` of not_found, conflict, invalid, forbidden or unavailable) and make the existing refusal classes subclass it, keeping their names and codes. The status table lives in `api/errors.py`, which registers one handler per kind.
3. Add `AttemptAlreadySettled` (subclassing `ValueError` during the move) and `GoalMissing(LookupError)`, and catch only those.
4. Translate `CredentialDecryptionError` inside the store into a `CredentialUnreadable` subclass of the storage-unavailable error, and drop it from the seven handlers.
5. Replace broad catches where a precise type exists.

**Files.** `services/agent/src/autobots/domain/errors.py` (new), the refusal classes in `domain/` and `application/`, `api/errors.py`, the route modules, `application/model_admission.py`, `adapters/loop_middleware.py`, `application/credentials/store.py`, `application/provider_settings.py`, `application/worker_inference.py`.

**Risk and mitigations.** Medium. Codes, statuses and fixed messages stay identical, and a missing or wrong master key with encrypted rows is still an error (SP-007).

**Verification.** Tests first: the mapping tests. Proved by `fast`, and by `db` for the ledger and credential paths.

**Effort and dependencies.** M. Depends on nothing.

### <a id="r-42"></a>R-42: Split goal_loop.py along its seams

**Addresses.** high: [PRUN-01](findings/py-run.md#prun-01); low: [PRUN-18](findings/py-run.md#prun-18), [PRUN-19](findings/py-run.md#prun-19).

**Why now.** `goal_loop.py` is a 782-line hub of seven concerns (tool registry, graph, prompts, the pass, dispatch, settlement and lease keeping) that other modules use through private names.

**Steps.**

1. With the public lifecycle from [R-33](#r-33) in place, move tool assembly to `application/loop_tools.py`, prompts to `loop_prompts.py`, settlement to `settlement.py` and job dispatch to `job_dispatch.py`, which passes its own drive function to both loops.
2. Keep re-exports in `goal_loop.py` until `tests/db` moves to the public names.
3. Replace long positional signatures with keyword-only parameter objects, and split `plan_tools` into module-level handlers.

**Files.** `services/agent/src/autobots/application/goal_loop.py`, the new `loop_tools.py`, `loop_prompts.py`, `settlement.py` and `job_dispatch.py`, `application/plans.py`, `application/compaction.py`, `tests/db/*`.

**Risk and mitigations.** Medium. Code moves only; lease checks, fencing, receipts and transaction boundaries stay in the same functions.

**Verification.** No new tests beyond those of [R-33](#r-33) and [R-34](#r-34); the whole database profile runs before and after. Proved by `db` and `fast`, where the layer test's allowlist shrinks.

**Effort and dependencies.** M. Depends on [R-33](#r-33), [R-34](#r-34).

### <a id="r-43"></a>R-43: Split the workflow editor

**Addresses.** high: [WBLD-01](findings/web-build.md#wbld-01); medium: [WBLD-04](findings/web-build.md#wbld-04), [WBLD-05](findings/web-build.md#wbld-05), [WBLD-06](findings/web-build.md#wbld-06), [WBLD-15](findings/web-build.md#wbld-15); low: [WBLD-19](findings/web-build.md#wbld-19).

**Why now.** WorkflowEditor is one 617-line component with 11 state hooks, an effect that reads three resources and eight async handlers that write the same message. Drafts have no dirty state, the two publish buttons publish from different sources, and secondary reads fail silently into Loading text.

**Steps.**

1. Add browser cases for dirty state and for a failed secondary read, and `node:test` cases for the IR helpers.
2. Move parse, tidy and `withLabel` to `lib/workflow-ir.ts`, typed with the generated `WorkflowGraph`.
3. Extract `useGraphDraft` (baseline, text, `isDirty`, the graph parsed once, check, validate, save, publish, publish draft, discard) on the submit hook. Show "Unsaved changes", name both publish actions by their source, and disable "Publish saved draft" while the text is dirty.
4. Read the workflow and the block catalog through `useResource`, each with its own unavailable state.
5. Split the markup into WorkflowHeading, DescriptionField, GraphEditor, RunVersionCard and BlockCatalogTable, leaving WorkflowEditor as a layout of about 80 lines.

**Files.** `apps/web/components/workflow-editor.tsx` (becomes `components/workflow-editor/*`), `apps/web/lib/workflow-ir.ts` (new), and unit and browser tests.

**Risk and mitigations.** Medium. `workflows.spec.ts` and `slice-workflows.spec.ts` are the safety net; keep every `data-*` hook and visible string. Publish, draft and run stay API calls that the service owns.

**Verification.** Tests first: the dirty-state cases and the IR unit tests. Proved by `db` and `fast`.

**Decision needed.** Who owns the WF-06 label rule. The preferred end state, a label-free normalized graph, is a contract and hash change that needs its own story ([WBLD-06](findings/web-build.md#wbld-06)).

**Effort and dependencies.** M. Depends on [R-19](#r-19), [R-27](#r-27), [R-37](#r-37).

### <a id="r-44"></a>R-44: Split the goal composer

**Addresses.** high: [WCMP-03](findings/web-composer.md#wcmp-03); medium: [WCMP-11](findings/web-composer.md#wcmp-11); low: [WCMP-17](findings/web-composer.md#wcmp-17).

**Why now.** GoalComposer is 541 lines with 13 state hooks, three effects and a nine-way nested ternary; outcome, run id and refusal are separate hooks updated in pairs; its pure logic lives where the unit runner cannot load it; and a zero budget step from the server would hang the render.

**Steps.**

1. Keep the admission tests from [R-18](#r-18) green, and add `node:test` cases for budget choices and file admission.
2. Extract `useDraft`, `useNewRunFocus`, `useRunOptions`, `useRunPreview` and `useAttachments` over a JSX-free `lib/attachments.ts`, and use the shared admission hook, a reducer over the request's state rather than a second `RunStatus`.
3. Move the markup into RunOptionChips, PreviewChips, AttachmentField and AdmissionMessage, leaving GoalComposer as a layout of about 120 lines.
4. Rename the near-identical state names.

**Files.** `apps/web/components/goal-composer.tsx` (becomes `components/composer/*`), `apps/web/lib/attachments.ts` (new), `lib/budget.ts`, and tests.

**Risk and mitigations.** Medium; `composer.spec.ts` pins today's behavior.

**Verification.** Tests first: the unit cases. Proved by `db` and `fast`.

**Effort and dependencies.** M. Depends on [R-18](#r-18), [R-27](#r-27), [R-37](#r-37).

### <a id="r-45"></a>R-45: Split the approvals panel

**Addresses.** high: [WTAP-01](findings/web-tools-approvals.md#wtap-01); medium: [WTAP-04](findings/web-tools-approvals.md#wtap-04), [WTAP-05](findings/web-tools-approvals.md#wtap-05), [WTAP-09](findings/web-tools-approvals.md#wtap-09).

**Why now.** Every change to the approval gate edits one 300-line closure that loads data, sends decisions and runs the shortcut machine. The list fetch exists twice, and the unguarded copy can show waiting requests under Decided; every load failure becomes one message with no retry.

**Steps.**

1. Add unit tests for the formatters and `parsedFields` (the AP-03 no-reorder rule), and browser cases for a reload under the Decided tab and for a failed load with Retry.
2. Move the formatters and `parsedFields` to `lib/`, and read the list through `useResource` in one place that Operations also uses.
3. Extract `useApprovalDecision` on the submit hook, and use `useApprovalShortcuts` from [R-16](#r-16).
4. Move ApprovalDetail, its parts and the Markdown renderer into their own files; ApprovalsPanel keeps the tab and selection state plus composition.

**Files.** `apps/web/components/approvals-panel.tsx` (becomes `components/approvals/*`), `apps/web/lib/approval-text.ts` and `lib/approval-fields.ts` (new), `operations-panel.tsx`, and tests.

**Risk and mitigations.** Medium. Every decision stays in the API, and AP-04's two-press confirmation and the hash binding are kept.

**Verification.** Tests first: the unit and browser cases. Proved by `db` and `fast`.

**Effort and dependencies.** M. Depends on [R-16](#r-16), [R-19](#r-19), [R-27](#r-27).

### <a id="r-46"></a>R-46: Split slice-visual.spec.ts into typed probes, data and named steps

**Addresses.** high: [TWEB-03](findings/web-tests.md#tweb-03); medium: [TWEB-09](findings/web-tests.md#tweb-09).

**Why now.** The evidence for DS-05 and US-11.11 comes from a 1,057-line file whose measurement code is an untyped string injected into the page and read back by name. A failing run reports only "run-dark", and the inventory omits dialogs, charts and seven page routes.

**Steps.**

1. Capture today's `results.json` from a `db` run to compare against.
2. Move the in-page code into typed, self-contained functions passed to `page.evaluate`, with each result type declared once and one zoom helper.
3. Move the surface table and the absent list into data, arrange through the status-checked helpers from [R-40](#r-40), and add the missing dialogs, charts and routes.
4. Wrap each surface and theme in `test.step` with `expect.soft`, record a surface that never becomes ready as a named finding, and write `results.json` in a `finally` block. Do not use serial mode, which would skip everything after the first failure.
5. Keep the known-bad self-test and the `autobots.visual-evidence/v1` schema.

**Files.** `apps/web/tests/browser/slice-visual.spec.ts`, `apps/web/tests/browser/support/visual/*` (new).

**Risk and mitigations.** Medium: the file produces Decision 0010 evidence. Compare `results.json` before and after; Decision 0010 stays the pass line.

**Verification.** The known-bad self-test still fails as intended, and `results.json` matches apart from the added surfaces. Proved by `db` (the slice suite).

**Effort and dependencies.** M. Depends on [R-40](#r-40).

### <a id="r-47"></a>R-47: Register qualify_identity's arrangements as functions

**Addresses.** high: [SCRP-02](findings/scripts.md#scrp-02).

**Why now.** Every browser story edits one 326-line `qualify()` holding 12 story-labelled arrangement blocks, 15 owner bootstraps and SQL with hand-escaped JSON inside f-strings, and seven of the arrangements record no case, so they break silently.

**Steps.**

1. Introduce an `IdentityRun` record (stack, base URL, ports, keys) and an `Owner` record.
2. Move each story's arrangement into `arrange_<story>(run, cases) -> dict[str, str]`, registered in an ordered tuple, and have each record an "arranged" case.
3. Keep their SQL in fixture files under `tests/db`, or build it with a quoting helper.
4. Name the Playwright suite lists as constants until [R-58](#r-58) replaces them with projects, and rename or split `artifact_cases`.

**Files.** `scripts/qualify_identity.py`, and fixture files under `tests/db/`.

**Risk and mitigations.** Medium. The fixtures stay synthetic and run only on disposable targets (DH-07).

**Verification.** The `db` run records the same cases, plus the new arranged cases. Proved by `db`.

**Effort and dependencies.** M. Depends on [R-39](#r-39).

## Wave 3: structural moves

Large (`L`) or cross-cutting moves. Each lands as a sequence of bounded changes, never as one large diff, and most build on the shared pieces that wave 2 introduces.

### <a id="r-48"></a>R-48: A typed browser client for every API call

**Addresses.** high: [XMOD-03](findings/sweep-boundaries.md#xmod-03), [XDUP-06](findings/sweep-duplication.md#xdup-06), [XTYP-01](findings/sweep-types.md#xtyp-01), [XWEB-01](findings/sweep-web-architecture.md#xweb-01); medium: [WSHL-06](findings/web-shell.md#wshl-06).

**Why now.** Twenty-eight request bodies in 18 files and 78 hand-written `/api/` paths bypass the generated contract, and the browser uses none of the 78 generated request functions, so a renamed request field compiles cleanly and fails as a 422 that the screens misreport.

**Steps.**

1. Until a screen moves, type its request bodies with the generated request types (`satisfies`).
2. Teach `scripts/generate_contracts.py` to emit typed query parameters and declared header parameters (`Idempotency-Key`), and to pass per-call options through; regenerate.
3. Add `apps/web/lib/api/browser.ts` with read options (base `/api`, no-store) and write options (base `/api`, `csrfFetch`), and `failureOf(error)` on the typed failure from [R-02](#r-02).
4. Migrate screens one at a time, the three run admissions and four session creations first, and give the BFF-only bodies (`/api/session`, `/api/workspace`, `/api/csrf`) small parsers.
5. Take the assertion and raw-fetch baselines of [R-06](#r-06) to zero for components and lib.

**Files.** `scripts/generate_contracts.py`, the regenerated `generated.ts`, `packages/api-client/src/runtime.ts`, `apps/web/lib/api/browser.ts` (new), and the 31 component files that call the API.

**Risk and mitigations.** Medium. The BFF's same-origin checks, CSRF and routing stay, and the generator change is proven by `contract_drift` and the client tests.

**Verification.** Tests first: client tests for the generated header and query parameters. Proved by `fast` and `db`.

**Effort and dependencies.** L. Depends on [R-02](#r-02), [R-03](#r-03), [R-18](#r-18), [R-27](#r-27).

### <a id="r-49"></a>R-49: Split RunWorkspaceView, and serve the allowed run commands from the API

**Addresses.** high: [XWEB-05](findings/sweep-web-architecture.md#xweb-05), [WRUN-01](findings/web-run.md#wrun-01); medium: [XMOD-06](findings/sweep-boundaries.md#xmod-06), [XTYP-07](findings/sweep-types.md#xtyp-07), [WRUN-05](findings/web-run.md#wrun-05), [WRUN-12](findings/web-run.md#wrun-12), [WRUN-15](findings/web-run.md#wrun-15); low: [XWEB-17](findings/sweep-web-architecture.md#xweb-17).

**Why now.** RunWorkspaceView is the largest and most complex function in `apps/web` (677 lines, complexity 39), and every run story edits it: data loading, the event stream and reconnects, deduplication, live text, derived view state and every region's markup. The UI also re-derives SP-010's command table, and the stream frames have no declared contract.

**Steps.**

1. Move the pure helpers and view-model derivations to `lib/runs/*.ts` with `node:test` (an exhaustive `describeEvent`, `mergeEvents`, `withDelta`, `latestPublished`, `toWorkspaceView`).
2. Declare `StreamCursor`, `StreamGap` and the frame names in contracts (the stream route stays out of the OpenAPI paths), regenerate, and parse the frames with them in one EventSource module.
3. Extract `useRunEvents` (replay pages, EventSource, backoff, deduplication, live text) and `usePublishedResult` beside `useRunWorkspace`.
4. Extract one component per region, leaving RunWorkspaceView as composition under 60 lines, and run the browser suites after each step.
5. Type `commandsFor` with `RunStatus` in `lib/runs/commands.ts`, with one `sendRunCommand`. Then, as its own story, add the user's allowed commands to `RunWorkspace` from `domain.next_status`, and delete `commandsFor`.
6. Apply the same shape to the eight other run components over 60 lines.

**Files.** `apps/web/components/run-workspace.tsx` (becomes `components/runs/workspace/*`), `apps/web/lib/runs/*`, `run-controls.tsx`, `workflow-monitor.tsx`, `run-list.tsx`, `run-inspector.tsx`, `run-panel.tsx`, `run-disclosure.tsx`, `services/agent/src/autobots/contracts/` (frames, `RunWorkspace`), `api/event_routes.py`.

**Risk and mitigations.** Medium. Decision 0021 R1 froze the `data-*` hooks that the suites read, and business transitions stay on the server, which now projects the allowed commands.

**Verification.** Tests first: `node:test` for each pure helper and the frame parsers. Proved by `db` and `fast`.

**Effort and dependencies.** L. Depends on [R-28](#r-28), [R-37](#r-37).

### <a id="r-50"></a>R-50: Receipt and approval state machines with single writers

**Addresses.** high: [PTOL-03](findings/py-tools.md#ptol-03), [XMOD-02](findings/sweep-boundaries.md#xmod-02); medium: [PADP-13](findings/py-adapters.md#padp-13), [PTOL-06](findings/py-tools.md#ptol-06), [PTOL-15](findings/py-tools.md#ptol-15).

**Why now.** Eleven status writes in six modules, one of them an adapter, change approval and receipt states as bare strings, and adapters query run, lease and approval tables directly. SP-010 asks for these machines to be documented separately from run status, and an approved `browse_goal` call can run again without a person until the approval expires.

**Steps.**

1. Add `domain/effects.py` with `ReceiptStatus` and `ApprovalStatus` StrEnums and their permitted moves, tested so that every permitted move is accepted and every other one is refused.
2. Make a new `application/receipts.py` the only writer of receipt status, and `approvals.py` the only writer of approval status (request, return to review, expire, decide, withdraw); `runs.py`, `recovery.py`, `reconciliation.py` and the adapters call them.
3. Load the approved call into `ToolContext` for approved dispatches and give `remote_files` a `stored_file` helper, then narrow `ToolContext` so that external adapters receive capabilities instead of a raw connection.
4. Move the adapters' run, lease and usage queries to the modules that own those tables, and derive `INTERRUPTING` from `TERMINAL` plus `CANCELLING`.
5. Consume an approval that releases a call leaving no receipt: a forward migration adds `consumed_at`, written in the releasing transaction (Decisions 0018 B6 and 0020 L5).
6. Type the decision commands with the contracts' Literals and share their idempotent-command skeleton, and propose both state tables for the Option B contract, which is an owner edit.

**Files.** `services/agent/src/autobots/domain/effects.py` and `application/receipts.py` (new), `application/approvals.py`, `application/tool_gateway.py`, `application/reconciliation.py`, `application/recovery.py`, `application/runs.py`, `adapters/github_pulls.py`, `adapters/github_issues.py`, `adapters/remote_files.py`, `adapters/loop_middleware.py`, `adapters/browser_executor.py`, `supabase/migrations/<new>_approval_consumed.sql`.

**Risk and mitigations.** High (consent and receipts). Stored values stay the same, so no data migration is needed, and any CHECK constraint is a forward migration. `browser_executor.py` is part of the browser image fingerprint, so its query move lands with [R-57](#r-57) or with a scheduled re-qualification.

**Verification.** Tests first: the transition tests, and a database check that repeats an approved `browse_goal` call and expects `approval_pending`. Proved by `db` and `fast`.

**Effort and dependencies.** L. Depends on [R-21](#r-21), [R-36](#r-36).

### <a id="r-51"></a>R-51: Typed persisted documents: the policy snapshot, event payloads and receipts

**Addresses.** high: [XTYP-03](findings/sweep-types.md#xtyp-03); medium: [PRUN-08](findings/py-run.md#prun-08), [XDUP-04](findings/sweep-duplication.md#xdup-04).

**Why now.** The frozen model-policy snapshot has one writer and eight hand-written readers, a misspelled key in an event dict is stored durably and then filtered silently twice, and receipts are replayed by string key in eight modules. These durable formats are contracts across modules and releases, held together only by string keys.

**Steps.**

1. Capture fixtures of today's stored snapshots, event payloads and receipts from a disposable run (synthetic data only), and add read tests, including legacy shapes such as snapshots without `sources` from before MD-02.
2. Add `contracts/persisted.py`, apart from the DTOs and domain types, with `PolicySnapshot`, `FrozenRoute`, the admission receipt and one receipt model per operation, returned by `existing_receipt(..., kind)`.
3. Build public event payloads with their contract models at the writer (`ToolUseStarted(...).model_dump(mode="json")`), give private payloads their own models, and type `append_event`'s payload as their union.
4. Keep `project_event`'s filter, but log the type and sequence, never the content, when it drops a known type.

**Files.** `services/agent/src/autobots/contracts/persisted.py` (new), `application/runs.py`, `application/run_projection.py`, `application/goal_loop.py`, `application/worker_inference.py`, `application/tool_uses.py`, and the eight modules that replay receipts.

**Risk and mitigations.** High (durable formats). Stored rows are read as they are, legacy shapes are accepted explicitly, and no migration is edited.

**Verification.** Tests first: the captured-fixture read tests. Proved by `fast` and `db`, and by `operations`, whose upgrade qualifier reads data that an older release wrote.

**Effort and dependencies.** L. Depends on [R-03](#r-03), [R-30](#r-30).

### <a id="r-52"></a>R-52: Versioned stored records, then one routine configuration

**Addresses.** high: [PDOM-01](findings/py-domain.md#pdom-01), [PDOM-02](findings/py-domain.md#pdom-02); medium: [XTYP-08](findings/sweep-types.md#xtyp-08).

**Why now.** Sixteen read sites validate stored jsonb with request contracts, so removing a field or tightening a bound makes saved Expert versions, routine occurrences and running goals fail to read, and nothing flags it. This also blocks every contract tightening in [R-61](#r-61). The routine configuration has two definitions whose trigger, budget and timezone rules differ, contrary to Decision 0026 C5.

**Steps.**

1. Capture today's stored shapes of `ExpertConfig`, `RoutineConfig`, `GoalSpec` and `PlanTask` as fixtures, with one test per record type that every stored shape still reads.
2. Add `persistence/records.py` with frozen, lenient (unknown fields ignored), versioned records and explicit mapping to and from the DTOs, starting with `ExpertConfig` and `RoutineConfig`; request DTOs stay strict.
3. Then move `CronjobSchedule` into `contracts/routines.py` unchanged, so that the cronjob v1 schema stays byte-identical; use it for `RoutineConfig.trigger`, dumped with `exclude_none`; share one IANA timezone alias; and type the API's limit as `MicroUsd`.
4. Parse a stored trigger once into typed domain triggers that `occurrences()` consumes, and parse workflow block configurations into typed values the same way, keeping the node-level error codes.
5. If existing rows need normalizing, add a forward data migration; never edit one.

**Files.** `services/agent/src/autobots/persistence/records.py` (new), `contracts/experts.py`, `contracts/routines.py`, `contracts/cronjob.py`, `contracts/plans.py`, `domain/routines.py`, `domain/workflows.py`, `application/experts.py`, `application/routines.py`, `application/plans.py`, `application/cronjob_tool.py`, `application/workflow_overview.py`, `api/run_routes.py`, and `services/agent/tests/fixtures/stored/` (new).

**Risk and mitigations.** High (durable data and contracts). Lenient reads land before any stricter type, and the generated client is regenerated, never edited.

**Verification.** Tests first: the stored-shape tests. Proved by `fast`, `db` and `operations` (the upgrade qualifier).

**Decision needed.** Whether the Routines API takes the cronjob tool's US$1 cap; admission caps each run at the workspace's run limit today ([PDOM-02](findings/py-domain.md#pdom-02)).

**Effort and dependencies.** L. Depends on [R-03](#r-03).

### <a id="r-53"></a>R-53: Build the tool registry at the composition edge

**Addresses.** high: [XMOD-01](findings/sweep-boundaries.md#xmod-01); medium: [PPRD-15](findings/py-product.md#pprd-15), [PTOL-07](findings/py-tools.md#ptol-07), [PTOL-08](findings/py-tools.md#ptol-08), [PTOL-11](findings/py-tools.md#ptol-11), [PTOL-12](findings/py-tools.md#ptol-12); low: [PPRD-19](findings/py-product.md#pprd-19), [PTOL-21](findings/py-tools.md#ptol-21).

**Why now.** Application code imports adapters 21 times, 11 of them in `goal_loop`, the API process loads the agent runtime only to call `execution_block`, and the catalog rebuilds the worker's registry with stand-in arguments, an unwritten second contract. Key precedence is coded in four resolvers, and the run-file readers are copied.

**Steps.**

1. Point `test_execution_contract.py` at the registry the worker builds, and add a test that the catalog and the worker list the same tools (TC-01).
2. Move the tool vocabulary (`ToolScope`, `ToolContext`, `ToolDefinition`, `ToolResult`, `ToolRegistry`, `ToolFailed`, `NotDelivered`) into `application/tool_definitions.py`.
3. Add one `tool_definitions(runtime)` in a composition module (for example `adapters/tool_registry.py`) that imports every definition; with no runtime, a definition still describes itself and its handler fails before any effect.
4. Build it once in `api/main.py` and `operations/worker.py`, pass it to the loop through `LoopConfig` and to the catalog as a parameter, give Experts and routines an availability callable, and move `execution_block` next to the execution contract.
5. Move tool definitions out of the product service modules, and the knowledge store into `knowledge.py`, so that services no longer sit underneath the registry.
6. Make one key resolver over `ITEMS`, keeping the Decision 0024 and 0025 order and the rule that a nonblank invalid higher-priority key blocks fallback, and one run-files module for `tools.py` and `code_tools.py`.

**Files.** `services/agent/src/autobots/adapters/tool_registry.py` and `application/tool_definitions.py` (new), `application/goal_loop.py`, `application/tool_catalog.py`, `application/tool_gateway.py`, `application/experts.py`, `application/routines.py`, `application/tool_keys.py`, `application/tool_key_settings.py`, `application/tools.py`, `application/code_tools.py`, `api/main.py`, `api/run_routes.py`, `api/tool_routes.py`, `operations/worker.py`.

**Risk and mitigations.** Medium. One LangGraph lifecycle still owns execution, `TOOL_VERSIONS` and its parity test still compare against the worker's registry, and `browse_goal` stays registered only while it is qualified and switched on (AB-02, Decision 0025 V6).

**Verification.** Tests first: the registry parity tests. Proved by `fast`, where the layer test drops goal_loop's adapter imports from its allowlist, and `db`.

**Effort and dependencies.** L. Depends on [R-42](#r-42).

### <a id="r-54"></a>R-54: A typed SQL boundary

**Addresses.** high: [XTYP-04](findings/sweep-types.md#xtyp-04); medium: [PAPI-08](findings/py-api.md#papi-08), [PAPI-09](findings/py-api.md#papi-09), [PDOM-08](findings/py-domain.md#pdom-08), [POPS-11](findings/py-ops.md#pops-11), [PPRD-12](findings/py-product.md#pprd-12), [PPRD-13](findings/py-product.md#pprd-13), [PRUN-11](findings/py-run.md#prun-11), [PRUN-12](findings/py-run.md#prun-12), [PRUN-16](findings/py-run.md#prun-16), [PTOL-13](findings/py-tools.md#ptol-13), [XTYP-05](findings/sweep-types.md#xtyp-05); low: [PAPI-14](findings/py-api.md#papi-14), [POPS-17](findings/py-ops.md#pops-17).

**Why now.** There are 225 `connection: Any` annotations in 42 files and 178 positional row reads, so mypy strict checks none of the service's SQL reads: adding a column to one list query shifts 16 reads silently, and `fetchone()` on a missing row raises `TypeError`, which becomes a 500. Statuses come back as `str` and are bridged with suppressions.

**Steps.**

1. Define narrow `SqlConnection` and `SqlCursor` Protocols in the application layer (no psycopg import) and a `one()` helper that raises a typed not-found, and replace the 42 `(await cursor.fetchone())[n]` sites.
2. Replace the 10 `_pool` copies with one typed dependency, add `connection()` to the `Pool` Protocol, and declare process resources in an `AppResources` dataclass instead of an untyped `app.state`.
3. Alias the columns of multi-column SELECTs and read them through per-query TypedDict rows in `persistence/rows.py` (psycopg's `dict_row` or `class_row`), mapped explicitly to DTOs as `contracts/adapters.py` maps `RunRow`.
4. Return state vocabularies as enums so that the `type: ignore` bridges go, and take each module's ANN401 entries out of the baseline from [R-05](#r-05).
5. Turn `run_projection.py` (664 lines, five read models) into a package with one module per view, re-exporting today's names, and read each run view from one snapshot instead of 7 to 19 separate statements.

**Files.** `services/agent/src/autobots/application/sql.py` (new), `persistence/rows.py`, `api/app.py`, `api/main.py`, `api/membership.py`, and the application, API and operations modules, largest first (`run_projection`, `approvals`, `goal_loop`, `workflows`).

**Risk and mitigations.** Medium; the change is mechanical per module, and the database profile proves the queries. SQL migrations keep owning the schema and none is edited, and rows, DTOs and domain types stay separate.

**Verification.** Tests first: unit tests for `one()` and each row mapper. Proved by `fast` (mypy) and `db`.

**Effort and dependencies.** L. Depends on [R-05](#r-05).

### <a id="r-55"></a>R-55: Thin route handlers: shared dependencies and no SQL

**Addresses.** high: [PAPI-01](findings/py-api.md#papi-01); medium: [PAPI-06](findings/py-api.md#papi-06), [PAPI-07](findings/py-api.md#papi-07), [PAPI-11](findings/py-api.md#papi-11), [PAPI-12](findings/py-api.md#papi-12), [PAPI-13](findings/py-api.md#papi-13), [XMOD-05](findings/sweep-boundaries.md#xmod-05), [XMOD-11](findings/sweep-boundaries.md#xmod-11); low: [PAPI-16](findings/py-api.md#papi-16), [PAPI-20](findings/py-api.md#papi-20), [PAPI-21](findings/py-api.md#papi-21), [XDOC-09](findings/sweep-docs-naming.md#xdoc-09), [XDOC-10](findings/sweep-docs-naming.md#xdoc-10), [XDUP-20](findings/sweep-duplication.md#xdup-20).

**Why now.** Route modules hold 13 SQL statements and 3 transactions, including the whole versioned model-policy write path, so no worker, tool or script can reuse them, and they run only through HTTP, never in `fast`. Shared dependencies live in feature route modules, and each router copies the pool accessor.

**Steps.**

1. Add in-process tests for each function before moving it, with the `api_client` fixture from [R-31](#r-31).
2. Create `api/dependencies.py` (pool, `current_workspace`, `require_owner`, the readiness-workspace variant, provider settings, `require_ready`) and import it from every router.
3. Move the model-policy read, save and reset, with the expected-version check and the row lock, into `application/model_policy.py` with a typed stale-version refusal; the reconciliation flow into `reconciliation.py`; the run reads into `runs.py` and `run_projection.py`; and the preview's Expert lookup into `experts.py`.
4. Give each request one owner for its connection, and cap concurrent stream listeners.
5. Split `run_routes.py` and `settings_routes.py` by feature, extract the computation in `get_local_status`, decode the session token once, and name handlers for what they do.

**Files.** `services/agent/src/autobots/api/*_routes.py`, `api/dependencies.py` and `application/model_policy.py` (new), `application/reconciliation.py`, `application/runs.py`, `application/run_projection.py`, `application/experts.py`, `api/security.py`.

**Risk and mitigations.** High: the optimistic version check, the FOR UPDATE lock and the operation receipt move unchanged, and no migration is involved.

**Verification.** Tests first: in-process tests for the moved functions. Proved by `fast`, `db` and `operations`.

**Effort and dependencies.** L. Depends on [R-31](#r-31), [R-41](#r-41).

### <a id="r-56"></a>R-56: Schema and storage integrity by forward change

**Addresses.** medium: [SQLI-03](findings/sql-infra.md#sqli-03), [SQLI-06](findings/sql-infra.md#sqli-06), [SQLI-07](findings/sql-infra.md#sqli-07), [SQLI-08](findings/sql-infra.md#sqli-08), [SQLI-09](findings/sql-infra.md#sqli-09), [SQLI-12](findings/sql-infra.md#sqli-12), [SQLI-13](findings/sql-infra.md#sqli-13), [SQLI-14](findings/sql-infra.md#sqli-14); low: [SQLI-16](findings/sql-infra.md#sqli-16), [SQLI-17](findings/sql-infra.md#sqli-17).

**Why now.** Approved profiles are restated in three CHECK constraints at every change, version references are enforced by a composite key in one table and by nothing in four, a draft graph written through PostgREST skips the API's validation and one bad draft breaks the workflow list, run-scoped lookups scan unindexed columns, and storage policies live in one frozen superuser file with no forward path.

**Steps.**

1. Ship first: make the workflow list and discard paths tolerate a draft that fails `WorkflowGraph` validation (report it as unreadable, delete it by key), and add a CHECK that the graph holds `nodes` and `links` arrays, added `NOT VALID` and then validated.
2. Index the run-scoped lookups and retention guards, and add composite foreign keys for the four unenforced version references.
3. The next time the approved set changes, replace the policies' profile CHECK with a foreign key to `model_profiles`, whose own CHECK stays the one approved list (Decision 0019).
4. Define the terminal-state predicate once, as a SQL function for new migrations, and build the disposable reset's table list from the catalog.
5. Give superuser-owned objects ordered bootstrap files with checksums, applied after the migrations by both the install and `app_db`; `storage.sql` stays first and unchanged.
6. Add a generated, read-only view of the current schema for readers, and decide what `packages/db-types` is for.

**Files.** New files under `supabase/migrations/` and `supabase/bootstrap/`, `scripts/app_db.py`, `scripts/persistent_install.py`, `services/agent/src/autobots/application/workflows.py`, `packages/db-types/*`.

**Risk and mitigations.** High (schema and grants). Forward migrations only, each with the header from [R-04](#r-04); constraints on existing rows are added `NOT VALID` and then validated; a persistent install changes only through the guarded apply.

**Verification.** Tests first: database cases for an invalid draft, a dangling version reference and a bootstrap checksum. Proved by `db` and `operations` (the upgrade qualifier).

**Decision needed.** Whether members need Storage insert, update or delete at all ([SQLI-07](findings/sql-infra.md#sqli-07)), and whether to remove member write grants on drafts, which the plan keeps because US-15.12 and US-15.2 accept them ([SQLI-13](findings/sql-infra.md#sqli-13)).

**Effort and dependencies.** L. Depends on [R-04](#r-04), [R-17](#r-17).

### <a id="r-57"></a>R-57: Bind the browser images to their fingerprint, and split the executor

**Addresses.** high: [SQLI-02](findings/sql-infra.md#sqli-02); medium: [PADP-14](findings/py-adapters.md#padp-14); low: [SQLI-20](findings/sql-infra.md#sqli-20).

**Why now.** The qualifier accepts whatever images carry the local tags and records a hash of the sources, so after an edit to `egress_proxy.py` or a Chromium flag without a rebuild, the old egress sandbox runs while reporting that it is qualified at the current code. `browser_executor.py` also bundles five responsibilities into one fingerprinted file.

**Steps.**

1. Add one build entry point (`make browser-images`, calling a small script) that builds both images with `--label autobots.fingerprint=<digest>` from build contexts narrowed by Dockerfile-specific ignore files, and name the proxy base image's Python version next to its digest.
2. Make the qualifier refuse images whose label differs, and make `executor_qualified` check the label on the images it will start, unit-tested with fake inspect output.
3. In the same change, split `browser_executor.py` into a Docker session module, a CDP module and a qualification module, list each one explicitly in `images_fingerprint` so that the binding stays as strict, and make the browser entrypoint fail clearly when Chromium cannot be found or started.
4. Re-qualify once with `scripts/qualify_browser_executor.py`, which needs the images and network access to the qualification host and runs in no profile.

**Files.** `Makefile`, `scripts/browser_images.py` (new), `infra/browser/*.Dockerfile`, Dockerfile-specific ignore files (new), `infra/browser/browser-entrypoint.js`, `services/agent/src/autobots/adapters/browser_executor.py` (split), `scripts/qualify_browser_executor.py`, `docs/engineering/runbooks/operations.md`.

**Risk and mitigations.** Medium. Until the re-qualification runs, `browse_goal` reports unqualified at the new fingerprint, which fails safe; no egress rule, sandbox flag or qualification case is removed (DH-08, BX-05, Decision 0018 B8).

**Verification.** Tests first: unit tests for the label match. Proved by `fast` and `db`; the live executor qualification is an owner-authorized step outside the profiles.

**Decision needed.** The owner schedules the live executor re-qualification (Decision 0018 B8).

**Effort and dependencies.** L. Depends on nothing.

### <a id="r-58"></a>R-58: Make the browser suites' environments and preconditions explicit

**Addresses.** high: [TWEB-01](findings/web-tests.md#tweb-01); medium: [TWEB-06](findings/web-tests.md#tweb-06), [TWEB-07](findings/web-tests.md#tweb-07), [TWEB-12](findings/web-tests.md#tweb-12); low: [TWEB-15](findings/web-tests.md#tweb-15), [TWEB-17](findings/web-tests.md#tweb-17).

**Why now.** Suites hand workspace state to each other through alphabetical file order (one worker, files sorted with `localeCompare`), 14 comments in 12 files describe what another file must leave behind, four scripts select specs by filename substring, and fixed sleeps add about 50 seconds across the runs.

**Steps.**

1. Declare one Playwright project per environment (web, main, slice, release, install), each with its own `testMatch`, and have the scripts pass `--project` instead of substrings.
2. Give each shared state a fixture that arranges it and restores it in teardown (provider key, worker heartbeats, retention, model policy), or move the remaining owner-A suites to their own arranged workspaces.
3. Check each precondition through the API in `beforeAll`, so that a broken chain fails at its source.
4. Replace fixed sleeps and `networkidle` with `page.clock` and web-first waits, declare serial mode where tests depend on each other or make them independent, wrap phases in named steps, and keep a trace on failure.
5. Write the selector conventions down.

**Files.** `apps/web/playwright.config.ts`, `apps/web/tests/browser/support/fixtures.ts`, the specs, `scripts/qualify_identity.py`, `scripts/qualify_web.py`, `scripts/qualify_release.py`, `scripts/persistent_install.py`.

**Risk and mitigations.** Medium. Only how the scripts select specs changes; no arranged fixture, guard or check is removed.

**Verification.** The per-project test counts equal today's per-script counts. Proved by `db` and `full`.

**Effort and dependencies.** L. Depends on [R-40](#r-40), [R-47](#r-47).

### <a id="r-59"></a>R-59: Split the remaining large screens

**Addresses.** high: [XWEB-05](findings/sweep-web-architecture.md#xweb-05); medium: [XDUP-18](findings/sweep-duplication.md#xdup-18), [WBLD-09](findings/web-build.md#wbld-09), [WBLD-10](findings/web-build.md#wbld-10), [WBLD-11](findings/web-build.md#wbld-11), [WBLD-12](findings/web-build.md#wbld-12), [WCMP-10](findings/web-composer.md#wcmp-10), [WSYS-03](findings/web-system.md#wsys-03), [WSYS-04](findings/web-system.md#wsys-04), [WSYS-05](findings/web-system.md#wsys-05), [WSYS-06](findings/web-system.md#wsys-06), [WSYS-07](findings/web-system.md#wsys-07), [WSYS-10](findings/web-system.md#wsys-10), [WTAP-08](findings/web-tools-approvals.md#wtap-08); low: [WCMP-09](findings/web-composer.md#wcmp-09), [WSHL-18](findings/web-shell.md#wshl-18), [WSHL-19](findings/web-shell.md#wshl-19), [WSYS-14](findings/web-system.md#wsys-14).

**Why now.** Once the shared hooks exist, each large screen can shed its plumbing: ExpertEditor (393 lines, with a save handler of complexity 19), OperationsPanel (377), ModelPolicyPanel (350), WorkflowsPanel (341 and 213), ExpertsPanel (255, with an ExpertCard of complexity 27), ToolCatalogPanel (249) and ToolDetail (174), SearchPalette and JobsPlot.

**Steps.**

1. Take one screen per change, in this order: Operations, model policy, the Expert editor, Experts, workflows, the tool catalog, provider settings and keys, the search palette and the jobs chart. Start each with `node:test` cases for its pure logic in `lib/`.
2. Split along three seams: a data hook on `useResource`, an actions hook on `useSubmit`, and presentational sections, as Server Components where they are read-only.
3. Share the Experts and workflows list-and-detail scaffolding and one filter mechanism, and give each settings panel one initial read and the shared load states.
4. Keep every `data-*` hook the suites read, and delete each screen's lines from the size baseline of [R-06](#r-06).

**Files.** `operations-panel.tsx`, `model-policy-panel.tsx`, `provider-settings-panel.tsx`, `keys-and-vars-panel.tsx`, `expert-editor.tsx`, `experts-panel.tsx`, `workflows-panel.tsx`, `tool-catalog.tsx`, `search-palette.tsx`, `jobs-chart.tsx`, `account-footer.tsx`, `sidebar-nav.tsx` and `readiness.tsx` under `apps/web/components/`.

**Risk and mitigations.** Medium; one screen per change keeps each diff reviewable.

**Verification.** Tests first: the `node:test` cases for each screen. Proved by `fast` and `db`; `full` for the tools spec.

**Effort and dependencies.** L. Depends on [R-19](#r-19), [R-27](#r-27), [R-37](#r-37).

### <a id="r-60"></a>R-60: Run and job writes through the command table

**Addresses.** medium: [PRUN-06](findings/py-run.md#prun-06), [PRUN-07](findings/py-run.md#prun-07), [PRUN-09](findings/py-run.md#prun-09), [XDUP-05](findings/sweep-duplication.md#xdup-05); low: [PRUN-20](findings/py-run.md#prun-20).

**Why now.** Run and job state are written from four modules beside the command table, `apply_command` packs replay, ownership, guard, cancel cascade and job rules into one 97-line transaction, the invocation ledger's states and spend formula are restated in five modules, and two definitions of a run's subtree disagree.

**Steps.**

1. Add table tests for a pure `job_status_after(...)`, and database tests that admission and projection agree on a seeded ledger and on a depth-2 tree.
2. Give the application one transitions surface: `apply_command` for people; `apply_worker_command(lease, ...)`, which writes `stop_reason` in the same transaction; `cascade_command` with an explicit system actor; a claim through `next_status(CLAIM)`; and named job helpers with a `JobStatus` enum. Keep every generation and `status='claimed'` predicate.
3. Move cancel side effects into a helper, make the receipt an optional parameter object, and keep the lock order (job row, then run row).
4. Add `InvocationStatus` and settlement-reason enums beside `FailureClass`, make `ModelAdmission` the only ledger writer, and define spend and the run subtree once, as a shared SQL fragment or as a SQL function in a forward migration.
5. Fence active-time segment writes as `discount_sleep` does.

**Files.** `services/agent/src/autobots/domain/runs.py`, `application/runs.py`, `application/worker_leases.py`, `application/goal_loop.py`, `application/model_admission.py`, `application/recovery.py`, `application/model_attempts.py`, `application/run_projection.py`, `application/workflow_overview.py`, `application/run_usage.py`.

**Risk and mitigations.** High (SP-010 actor authorization and durable state). Cancel and resume semantics are unchanged, and the database profile proves locks and fences.

**Verification.** Tests first: the table tests and the ledger and tree agreement tests. Proved by `fast` and `db`.

**Decision needed.** A system actor extends SP-010's actor table; record it before step 2.

**Effort and dependencies.** L. Depends on [R-33](#r-33), [R-34](#r-34).

### <a id="r-61"></a>R-61: Contract vocabularies and request strictness

**Addresses.** medium: [PADP-17](findings/py-adapters.md#padp-17), [PDOM-03](findings/py-domain.md#pdom-03), [PDOM-04](findings/py-domain.md#pdom-04), [PDOM-05](findings/py-domain.md#pdom-05), [PDOM-06](findings/py-domain.md#pdom-06), [PDOM-07](findings/py-domain.md#pdom-07), [XERR-08](findings/sweep-errors.md#xerr-08), [XTYP-10](findings/sweep-types.md#xtyp-10); low: [PDOM-11](findings/py-domain.md#pdom-11), [PDOM-18](findings/py-domain.md#pdom-18), [PDOM-20](findings/py-domain.md#pdom-20), [XMOD-15](findings/sweep-boundaries.md#xmod-15), [XTYP-16](findings/sweep-types.md#xtyp-16).

**Why now.** At least 23 response fields are typed looser than vocabularies that already exist, strictness is off in 22 of 30 request bodies so that `MicroUsd` accepts strings and floats, tool inputs under-declare constraints the model never sees, and a naive `since`, which the tool input accepts, crashes the pull-request filter.

**Steps.**

1. Ship first: type the tool inputs' `since` fields as UTC timestamps, with a test of a naive value.
2. Put strictness on the primitives (`MicroUsd` as a strict, bounded int, plus strict bool and count aliases), and define the strict, tool and lax configurations once in `primitives.py`.
3. Type response fields with `RunStatus` and the existing Literals, and every public timestamp as a UTC timestamp; keep `str` only where history holds retired values, with a comment saying so.
4. Use the domain StrEnums in contracts, or keep the Literals with a parity test per pair, and publish error and stop codes as enums where they are public.
5. Declare tool field constraints as Annotated aliases in the schema (symbols, domains, HTTPS URLs, run-file and repository paths, issue titles), keeping the URL guard and the cross-field validators.
6. Split `contracts/tools.py` by audience, freeze the domain tables, regenerate the client, and record schema changes as versioned tool changes in `domain/execution.py`.

**Files.** `services/agent/src/autobots/contracts/*.py`, `domain/tools.py`, `domain/runs.py`, `domain/execution.py`, `adapters/github_reads.py`, and the regenerated `contracts/generated/` and `generated.ts`.

**Risk and mitigations.** High (public contracts). `Strict()` leaves the JSON Schema unchanged, and stored reads go through the lenient records from [R-52](#r-52) first.

**Verification.** Tests first: valid and invalid shared boundary fixtures for each tightened field. Proved by `fast` and `db`.

**Effort and dependencies.** L. Depends on [R-03](#r-03), [R-52](#r-52).

### <a id="r-62"></a>R-62: Adapters by layer: one provider HTTP layer, typed replies, and loop policy in the application

**Addresses.** medium: [PADP-03](findings/py-adapters.md#padp-03), [PADP-04](findings/py-adapters.md#padp-04), [PADP-05](findings/py-adapters.md#padp-05), [PADP-06](findings/py-adapters.md#padp-06), [PADP-07](findings/py-adapters.md#padp-07), [PADP-08](findings/py-adapters.md#padp-08), [PADP-09](findings/py-adapters.md#padp-09), [PADP-16](findings/py-adapters.md#padp-16), [PADP-18](findings/py-adapters.md#padp-18), [XDUP-11](findings/sweep-duplication.md#xdup-11), [XTYP-09](findings/sweep-types.md#xtyp-09), [XTYP-11](findings/sweep-types.md#xtyp-11); low: [PADP-15](findings/py-adapters.md#padp-15), [PADP-19](findings/py-adapters.md#padp-19), [PADP-20](findings/py-adapters.md#padp-20).

**Why now.** Each tool module is one factory closure of 68 to 226 lines, status and error mapping is copied per provider and has drifted, six httpx constructors use different defaults (the GitHub token client honors proxy variables), provider replies are read as `Any`, and `loop_middleware.py` holds application policy that application modules import back from adapters.

**Steps.**

1. Add fast tests for the pull-request connector, the gateway middleware and object storage first.
2. Create every client through one factory (`follow_redirects=False`, `trust_env=False`, a required named timeout), and move the request-and-map block into `provider_http`, with one `UnclearReply` and one refused-status table per write class.
3. Parse replies with small, lenient, adapter-private Pydantic models: reads map failures to `provider_reply_malformed`, and an unclear write stays unknown.
4. Turn each factory closure into a frozen connector plus module-level handlers, and resolve the GitHub target once per call.
5. Split `loop_middleware.py` by layer: pure loop policy and the admission and compaction orchestration move to the application, and a thin `AgentMiddleware` and the streaming helpers stay in adapters, with typed hooks.
6. Pin the URL guard's resolved address for the request, and add a parity test with the egress proxy's public-address check.

**Files.** `services/agent/src/autobots/adapters/` (`github_*.py`, `tavily.py`, `jina.py`, `market_data.py`, `provider_http.py`, `url_guard.py`, `loop_middleware.py`, `tool_middleware.py`), new application policy modules, and adapter tests.

**Risk and mitigations.** Medium. The seams from [R-32](#r-32) come first so that the middleware's tests survive, per-attempt clients stay where per-attempt keys require them (PK-01), and `egress_proxy.py`, which is part of the image fingerprint, is not edited here.

**Verification.** Tests first: the new adapter tests. Proved by `fast` and `db`.

**Effort and dependencies.** L. Depends on [R-32](#r-32).

### <a id="r-63"></a>R-63: Product services and the workflow domain

**Addresses.** medium: [PDOM-09](findings/py-domain.md#pdom-09), [PDOM-10](findings/py-domain.md#pdom-10), [PDOM-12](findings/py-domain.md#pdom-12), [PPRD-04](findings/py-product.md#pprd-04), [PPRD-05](findings/py-product.md#pprd-05), [PPRD-06](findings/py-product.md#pprd-06), [PPRD-07](findings/py-product.md#pprd-07), [PPRD-08](findings/py-product.md#pprd-08), [PPRD-10](findings/py-product.md#pprd-10), [PPRD-11](findings/py-product.md#pprd-11), [PPRD-16](findings/py-product.md#pprd-16), [PTST-10](findings/py-tests.md#ptst-10); low: [PDOM-17](findings/py-domain.md#pdom-17), [PPRD-18](findings/py-product.md#pprd-18), [PPRD-20](findings/py-product.md#pprd-20), [PPRD-21](findings/py-product.md#pprd-21).

**Why now.** `workflows.py` mixes definitions, execution binding and the read model; `assign_tool` is 134 lines because its helpers are closures; `_run_block` dispatches ten block kinds through an if-chain that is not tied to the domain's block registry; six receipt-guarded procedures repeat one sequence by hand; list views issue a query per row; and the workflow domain runs on untyped mappings.

**Steps.**

1. Extract the pure rules (instance views, the replay verdict, granted tools, the occurrence decision) and unit-test them with plain values.
2. Replace `_run_block`'s chain with tables keyed by block kind and a test that their keys equal `BLOCKS`, and make the golden-graph tests use the runner's block rules instead of a copy.
3. Add a `receipted` helper and a `next_version` helper (`psycopg.sql.Identifier` over a closed set of tables) for the six create and new-version procedures; receipt hashes stay byte-identical.
4. Share the occurrence admission sequence between run-now and scheduled evaluation.
5. Split `workflows.py` by concern, move `assign_tool`'s closures to module level, batch child reads per list, and add pure graph helpers (`agent_expert_ids`, `needs_model`, `parse_instance_key`) with one topological sort.

**Files.** `services/agent/src/autobots/application/workflows.py`, `workflow_runner.py`, `workflow_overview.py`, `assignments.py`, `experts.py`, `routines.py`, `improvements.py`, `search.py`, `memory.py`, `domain/workflows.py`, `domain/workflow_execution.py`, and tests.

**Risk and mitigations.** Medium. The database checks for receipts, locking and runs pass before and after, and row, domain and DTO types stay separate.

**Verification.** Tests first: the pure-rule unit tests. Proved by `fast` and `db`.

**Effort and dependencies.** L. Depends on [R-52](#r-52), [R-54](#r-54).

### <a id="r-64"></a>R-64: The operations package and process configuration

**Addresses.** medium: [POPS-03](findings/py-ops.md#pops-03), [POPS-04](findings/py-ops.md#pops-04), [POPS-05](findings/py-ops.md#pops-05), [POPS-13](findings/py-ops.md#pops-13), [POPS-15](findings/py-ops.md#pops-15), [XMOD-08](findings/sweep-boundaries.md#xmod-08), [XMOD-13](findings/sweep-boundaries.md#xmod-13); low: [POPS-08](findings/py-ops.md#pops-08), [POPS-12](findings/py-ops.md#pops-12), [POPS-14](findings/py-ops.md#pops-14), [POPS-16](findings/py-ops.md#pops-16), [POPS-19](findings/py-ops.md#pops-19), [POPS-20](findings/py-ops.md#pops-20), [XMOD-12](findings/sweep-boundaries.md#xmod-12), [XMOD-17](findings/sweep-boundaries.md#xmod-17).

**Why now.** Shared logging and process wiring live in the entry-point package that inner layers import, the worker imports the API entry point to read its configuration, `application/operations.py` mixes six concerns, `route_qualification.py` doubles as the paid trials' library, and owner bootstrap can stop between its two writes.

**Steps.**

1. Move `logs.py` to a leaf module, and move the provider and credential context builders, the object-store construction and the configuration loading into one composition module that `api/main.py` and the worker import. Pass the live environ mapping per attempt, as the model-gateway rule requires.
2. Split `application/operations.py` by concern, with the backup readers called through `asyncio.to_thread`.
3. Extract the shared paid-call pieces from `route_qualification.py` into `operations/paid/`, then split the qualification runner into fixtures and orchestration.
4. Make owner bootstrap check the database before it creates the Auth user, print the created user id when the workspace step fails, and accept `--user-id` to finish it; add that recovery to the runbook.
5. Make entry points agree on configuration checks, refusals and exit codes, and stop `_settings_row` inserting on read.
6. Propose the DH-03 amendment (`workers/`, `operations/`, `scripts/db/` and the test directories) to the owner, and move LangGraph glue to `graphs/` once [R-42](#r-42) lands.

**Files.** `services/agent/src/autobots/operations/*`, `application/operations.py`, `application/provider_settings.py`, `api/main.py`, `api/settings.py`, `operations/bootstrap_owner.py`, `docs/engineering/runbooks/local-app.md`.

**Risk and mitigations.** Medium; the operations profile exercises the runbooks that these paths serve.

**Verification.** Tests first: unit tests for the composition module and for the bootstrap ordering. Proved by `fast` and `operations`.

**Decision needed.** Amending DH-03 is the user's decision, recorded under `docs/engineering/decisions/` ([XMOD-13](findings/sweep-boundaries.md#xmod-13)).

**Effort and dependencies.** L. Depends on [R-24](#r-24), [R-22](#r-22).

### <a id="r-65"></a>R-65: Scripts as packages, one profile registry, and the Makefile's shell in scripts

**Addresses.** medium: [SCRP-05](findings/scripts.md#scrp-05), [SCRP-06](findings/scripts.md#scrp-06), [SCRP-07](findings/scripts.md#scrp-07), [SCRP-12](findings/scripts.md#scrp-12), [SCRP-15](findings/scripts.md#scrp-15), [SQLI-10](findings/sql-infra.md#sqli-10), [SQLI-11](findings/sql-infra.md#sqli-11), [XDUP-13](findings/sweep-duplication.md#xdup-13); low: [SCRP-11](findings/scripts.md#scrp-11), [SCRP-13](findings/scripts.md#scrp-13), [SCRP-14](findings/scripts.md#scrp-14), [SCRP-16](findings/scripts.md#scrp-16), [SCRP-17](findings/scripts.md#scrp-17), [SCRP-18](findings/scripts.md#scrp-18), [SCRP-19](findings/scripts.md#scrp-19), [SCRP-20](findings/scripts.md#scrp-20), [SQLI-15](findings/sql-infra.md#sqli-15), [SQLI-19](findings/sql-infra.md#sqli-19), [XTOL-16](findings/sweep-tooling.md#xtol-16).

**Why now.** `scripts/` is a flat mix of entry points and libraries; qualifiers double as libraries, so the Stop hook's domain map misses what a change affects; the disposable-stack skeleton is copied into 13 entry points and only one checks its cleanup listing; each profile's checks are registered in five places; and the Makefile's process supervision is untested shell.

**Steps.**

1. Keep entry-point paths stable, since AGENTS.md, rules, settings, runbooks and tests name them, and move shared code into packages: `scripts/qualification/` and the `scripts/db/` that DH-03 lays out.
2. Give one context manager the disposable-stack lifecycle, recording both cleanup cases and checking every listing's exit code, and use one atomic report writer.
3. Describe each profile once, as data (id, arguments, timeout, class, transport), for `verify`, `report_state` and `evidence`, and derive script domains from each profile's import closure.
4. Turn each long qualifier's closures into a context class and scenario functions run from an ordered tuple.
5. Move the Makefile's process supervision and its Node, image and install-file derivations into tested scripts, and keep one dotenv parser that follows the app's quoting rules and one list of secret-file names.
6. Re-pin the synthetic stack's database and storage images to the install overlay's digests (then requalify `db`), add measured resource limits to the overlay, and check that every upstream init mount survives the merge.

**Files.** `scripts/*`, `Makefile`, `infra/supabase/compose.overlay.yaml`, `infra/disposable/compose.yaml`, `.claude/hooks/dispatch.py`.

**Risk and mitigations.** Medium: these scripts guard disposable targets and the persistent install. Target guards stay, and every profile runs after each move.

**Verification.** Tests first: harness tests for the stack context manager, the profile registry and the domain derivation. Proved by `harness`, `db` and `operations`.

**Effort and dependencies.** L. Depends on [R-39](#r-39), [R-07](#r-07).

### <a id="r-66"></a>R-66: Test suites filed by subject

**Addresses.** medium: [TDBC-06](findings/db-tests.md#tdbc-06), [TDBC-09](findings/db-tests.md#tdbc-09), [TDBC-10](findings/db-tests.md#tdbc-10), [THRN-03](findings/harness-tests.md#thrn-03), [THRN-04](findings/harness-tests.md#thrn-04), [THRN-05](findings/harness-tests.md#thrn-05), [THRN-06](findings/harness-tests.md#thrn-06), [THRN-07](findings/harness-tests.md#thrn-07), [THRN-08](findings/harness-tests.md#thrn-08), [THRN-09](findings/harness-tests.md#thrn-09), [THRN-11](findings/harness-tests.md#thrn-11), [THRN-12](findings/harness-tests.md#thrn-12), [THRN-13](findings/harness-tests.md#thrn-13), [PTST-05](findings/py-tests.md#ptst-05), [PTST-06](findings/py-tests.md#ptst-06), [PTST-07](findings/py-tests.md#ptst-07), [PTST-09](findings/py-tests.md#ptst-09), [PTST-11](findings/py-tests.md#ptst-11); low: [TDBC-14](findings/db-tests.md#tdbc-14), [TDBC-15](findings/db-tests.md#tdbc-15), [THRN-15](findings/harness-tests.md#thrn-15), [THRN-16](findings/harness-tests.md#thrn-16), [THRN-17](findings/harness-tests.md#thrn-17), [THRN-19](findings/harness-tests.md#thrn-19), [PTST-12](findings/py-tests.md#ptst-12), [PTST-13](findings/py-tests.md#ptst-13), [PTST-14](findings/py-tests.md#ptst-14), [PTST-15](findings/py-tests.md#ptst-15), [PTST-16](findings/py-tests.md#ptst-16), [PTST-17](findings/py-tests.md#ptst-17), [PTST-19](findings/py-tests.md#ptst-19), [PTST-20](findings/py-tests.md#ptst-20).

**Why now.** `tests/db` mixes six kinds of file whose mains run 150 to 316 lines and also arrange browser state; service and harness tests are filed by the story or review that added them; `test_hooks.py` is one 45-test class over seven subjects; instruction-file checks live in a test module beside a second frontmatter parser; and most error-list assertions fail with "False is not true".

**Steps.**

1. Split each `tests/db` main into scenario functions in a `SCENARIOS` tuple, the largest eight first, and group the files into `checks/`, `workers/`, `arrange/`, `fixtures/` and `sql/`, with a README table that maps each file to its invoker. Move browser-suite arrangements into `arrange/` scripts and source scans into `tests/harness`.
2. File service tests by module (`test_<module>.py`, with the motivating story or decision in the docstring), and adopt one async style, one SQL fake that refuses unmatched statements, shared API setup in `conftest.py`, restored logging, and parametrized cases instead of loops. Fix the remaining `type: ignore` comments with Protocols.
3. Add `tests/harness/harness_support.py` (fixture repository, executable stub, script copies, `run_cli` with a default timeout, report builders), split `test_hooks.py` and `test_assistant_assets.py` by the unit under test, and move the instruction-file checks and one frontmatter parser into scripts.
4. Assert exact lists with messages, read `RunStatus` from the generated contract, test behavior instead of source text where the entry points allow it, and fix the hook tests whose names and assertions disagree.

**Files.** `tests/db/*`, `services/agent/tests/*`, `tests/harness/*`, `tests/toolchain/test_non_mutating.py`, `scripts/app_db.py` (invoker paths), `scripts/harness_lib.py`.

**Risk and mitigations.** Low; the moves are mechanical. Compare the database profile's case IDs and the pytest and unittest counts before and after.

**Verification.** The case IDs and test counts match before and after. Proved by `harness`, `fast` and `db`.

**Effort and dependencies.** L. Depends on [R-38](#r-38), [R-32](#r-32), [R-07](#r-07).

### <a id="r-67"></a>R-67: Server-rendered reads for read-only views

**Addresses.** medium: [XWEB-13](findings/sweep-web-architecture.md#xweb-13), [XWEB-14](findings/sweep-web-architecture.md#xweb-14), [WCMP-07](findings/web-composer.md#wcmp-07), [WRUN-14](findings/web-run.md#wrun-14); low: [XWEB-19](findings/sweep-web-architecture.md#xweb-19), [WSHL-14](findings/web-shell.md#wshl-14), [WTAP-15](findings/web-tools-approvals.md#wtap-15).

**Why now.** Only two pages load data on the server. The run inspector, home activity and the data summary are Client Components only so that they can fetch in an effect, client writes do not refresh server-rendered shell data, and list filters live in the URL on some screens and in state on others.

**Steps.**

1. Extend `lib/service-status.ts` into a server-only typed client (`lib/server-api.ts`) with the failure mapping from [R-02](#r-02) and a per-request React `cache()`, never a cache shared between requests.
2. Turn the run inspector, the data summary, the tool detail facts, home activity and the first page of the run list into async Server Components, keep interactive leaves as Client Components, and refresh server data after client writes.
3. Keep list filters and selection in the URL on every list, and give the page, not the client screen, the title and width on every route.

**Files.** `apps/web/app/**/page.tsx`, `apps/web/lib/server-api.ts` (new), `run-inspector.tsx`, `home-activity.tsx`, `data-summary.tsx`, `session-panel.tsx`, `tool-catalog.tsx`, `run-list.tsx`, `workflows-panel.tsx`, `app-shell.tsx`.

**Risk and mitigations.** Medium. Server reads keep the BFF's per-request session and workspace checks, and no workspace data enters a shared cache (DH-06).

**Verification.** Tests first: browser cases for a server-rendered page's signed-out and denied states. Proved by `full` (the production build) and `db`.

**Effort and dependencies.** L. Depends on [R-26](#r-26), [R-27](#r-27).

### <a id="r-68"></a>R-68: UI primitives and a named type scale

**Addresses.** medium: [XWEB-11](findings/sweep-web-architecture.md#xweb-11), [XWEB-12](findings/sweep-web-architecture.md#xweb-12), [WSHL-12](findings/web-shell.md#wshl-12), [WSHL-13](findings/web-shell.md#wshl-13), [WSYS-12](findings/web-system.md#wsys-12); low: [XDUP-19](findings/sweep-duplication.md#xdup-19), [XWEB-18](findings/sweep-web-architecture.md#xweb-18), [WBLD-17](findings/web-build.md#wbld-17), [WCMP-15](findings/web-composer.md#wcmp-15), [WCMP-16](findings/web-composer.md#wcmp-16), [WCMP-19](findings/web-composer.md#wcmp-19), [WRUN-17](findings/web-run.md#wrun-17), [WSHL-11](findings/web-shell.md#wshl-11), [WSYS-11](findings/web-system.md#wsys-11), [WSYS-15](findings/web-system.md#wsys-15), [WSYS-16](findings/web-system.md#wsys-16), [WSYS-17](findings/web-system.md#wsys-17), [WSYS-19](findings/web-system.md#wsys-19), [WSYS-20](findings/web-system.md#wsys-20), [WTAP-11](findings/web-tools-approvals.md#wtap-11), [WTAP-12](findings/web-tools-approvals.md#wtap-12), [WTAP-13](findings/web-tools-approvals.md#wtap-13), [WTAP-17](findings/web-tools-approvals.md#wtap-17).

**Why now.** The primitive set has no Label or Dialog, help text and errors are not tied to their controls, recurring layout pieces are private to screens, and type sizes are one-off pixel values outside the theme.

**Steps.**

1. Add Label to `field.tsx` and a Dialog primitive on the native `<dialog>` with the popover color pair, Escape, outside-click close and focus return (Decision 0026 G2 and G3); give Card an `as` prop; and use or delete Separator.
2. Tie help text and errors to their controls with `aria-describedby` in `field.tsx`.
3. Define the type scale and radius steps in `@theme`, replace the arbitrary values, and add a harness baseline for arbitrary pixel classes that ratchets down.
4. Move the segmented tabs-with-counts control, section shells, page headers, the avatar and the status dot into `components/ui`.
5. Keep browser preferences (appearance keys, the before-paint script, the shortcut list) in one module that both the script and the control read, and give every settings page a document title.
6. Check both themes for every changed screen, as DS-05 requires.

**Files.** `apps/web/components/ui/*`, `apps/web/app/globals.css`, `apps/web/app/layout.tsx`, `apps/web/components/appearance-control.tsx`, `apps/web/components/theme-provider.tsx`, and the screens that hold copies.

**Risk and mitigations.** Low, but visual: the appearance spec and the slice visual walk must pass in both themes, and the DS-01 palette is untouched.

**Verification.** Tests first: the arbitrary-pixel baseline scan. Proved by `fast`, `full` (the appearance spec) and `db` (the slice visual walk).

**Effort and dependencies.** L. Depends on [R-46](#r-46), [R-59](#r-59).

## High findings and where they are addressed

All 70 high findings are addressed by at least one item, and none is deferred. Where a step waits on an owner decision, its item says so under "Decision needed", and the rest of the item proceeds without it.

| Finding | Part | Title | Addressed by |
|---|---|---|---|
| [TDBC-01](findings/db-tests.md#tdbc-01) | db-tests | Checks compute the shown value and the verdict with separate calls, so some can pass broken | [R-08](#r-08) |
| [TDBC-02](findings/db-tests.md#tdbc-02) | db-tests | Db checks import and patch 21 private product names that no fast check reads | [R-33](#r-33) |
| [TDBC-03](findings/db-tests.md#tdbc-03) | db-tests | No shared check module: the case protocol and setup are copied into every script | [R-38](#r-38) |
| [THRN-01](findings/harness-tests.md#thrn-01) | harness-tests | Private run-column guard reads only the first grant of one migration | [R-10](#r-10) |
| [THRN-02](findings/harness-tests.md#thrn-02) | harness-tests | Static pin and launcher guards in tests/toolchain run in no profile | [R-01](#r-01) |
| [PADP-01](findings/py-adapters.md#padp-01) | py-adapters | The live-result tap's JSON reader can stop a paid reply as partial_stream or uncertain_acceptance | [R-14](#r-14) |
| [PADP-02](findings/py-adapters.md#padp-02) | py-adapters | The pull-request connector rewrites approval state with inline SQL, outside a transaction and without the lease | [R-21](#r-21) |
| [PAPI-01](findings/py-api.md#papi-01) | py-api | Route handlers own SQL, transactions and use-case rules | [R-55](#r-55) |
| [PAPI-02](findings/py-api.md#papi-02) | py-api | post_run packs nine admission concerns into one 101-line handler | [R-31](#r-31) |
| [PAPI-03](findings/py-api.md#papi-03) | py-api | The OpenAPI document misdescribes every error response | [R-02](#r-02) |
| [PDOM-01](findings/py-domain.md#pdom-01) | py-domain | Stored JSON records are read back with the request contracts, so a contract edit is an unversioned storage-format change | [R-52](#r-52) |
| [PDOM-02](findings/py-domain.md#pdom-02) | py-domain | The routine configuration has two definitions whose trigger, budget and timezone rules differ | [R-52](#r-52) |
| [POPS-01](findings/py-ops.md#pops-01) | py-ops | Paid trials price calls with a second, float-based catalog parser | [R-22](#r-22) |
| [POPS-02](findings/py-ops.md#pops-02) | py-ops | Routine admission re-implements the readiness gate and skips the schema check | [R-24](#r-24) |
| [PPRD-01](findings/py-product.md#pprd-01) | py-product | Run admission takes an Any binding that three call sites fill with SimpleNamespace | [R-30](#r-30) |
| [PPRD-02](findings/py-product.md#pprd-02) | py-product | workflow_runner is built on goal_loop's private lifecycle, and the two modules import each other | [R-33](#r-33) |
| [PPRD-03](findings/py-product.md#pprd-03) | py-product | Stop codes live in three hand-kept lists that already disagree on parent_not_running | [R-29](#r-29) |
| [PRUN-01](findings/py-run.md#prun-01) | py-run | goal_loop.py is a seven-concern hub that other modules use through private names | [R-42](#r-42) |
| [PRUN-02](findings/py-run.md#prun-02) | py-run | Stop codes are bare strings, and any code missing from PAUSE_FOR fails the run permanently | [R-29](#r-29) |
| [PRUN-03](findings/py-run.md#prun-03) | py-run | _finish mixes the stop decision with cancellation settlement and raw job writes, and reads the status three times | [R-34](#r-34) |
| [PRUN-04](findings/py-run.md#prun-04) | py-run | admit_run takes 15 parameters and a binding typed Any that four different shapes satisfy | [R-30](#r-30) |
| [PRUN-05](findings/py-run.md#prun-05) | py-run | Display redaction keeps its own three-pattern regex, weaker than the log redaction | [R-15](#r-15) |
| [PTST-01](findings/py-tests.md#ptst-01) | py-tests | Paid-path tests replace private LoopMiddleware and ProviderSettings internals instead of using seams | [R-32](#r-32) |
| [PTOL-01](findings/py-tools.md#ptol-01) | py-tools | A model-supplied regex runs under the GIL and can freeze the worker's event loop | [R-20](#r-20) |
| [PTOL-02](findings/py-tools.md#ptol-02) | py-tools | `ToolGateway._dispatch` holds every guardrail in one 87-line function and recomputes the call's identity | [R-36](#r-36) |
| [PTOL-03](findings/py-tools.md#ptol-03) | py-tools | Approval and receipt states are bare strings changed from six modules, one of them an adapter | [R-50](#r-50) |
| [SCRP-01](findings/scripts.md#scrp-01) | scripts | The service child-check runner is hand-copied 29 times, with divergent failure handling | [R-39](#r-39) |
| [SCRP-02](findings/scripts.md#scrp-02) | scripts | qualify_identity.py takes on a new inline fixture for nearly every story | [R-47](#r-47) |
| [SCRP-03](findings/scripts.md#scrp-03) | scripts | Paid-run guards are copied across four entry points and already disagree | [R-23](#r-23) |
| [SCRP-04](findings/scripts.md#scrp-04) | scripts | No linter, formatter or type checker covers scripts/ or the hook | [R-07](#r-07) |
| [SQLI-01](findings/sql-infra.md#sqli-01) | sql-infra | Runtime role can delete runs, and the cascade reaches the receipt ledger | [R-17](#r-17) |
| [SQLI-02](findings/sql-infra.md#sqli-02) | sql-infra | Browser images are qualified by source hash, not by the image that runs | [R-57](#r-57) |
| [XMOD-01](findings/sweep-boundaries.md#xmod-01) | sweep-boundaries | goal_loop builds the tool registry, so application imports adapters and the API imports the agent runtime | [R-53](#r-53) |
| [XMOD-02](findings/sweep-boundaries.md#xmod-02) | sweep-boundaries | External tool adapters run approval and receipt SQL through ToolContext's raw connection | [R-21](#r-21), [R-50](#r-50) |
| [XMOD-03](findings/sweep-boundaries.md#xmod-03) | sweep-boundaries | Web request bodies and paths are hand-written, so the generated contract checks only responses | [R-48](#r-48) |
| [XDUP-01](findings/sweep-duplication.md#xdup-01) | sweep-duplication | Three different secret patterns, and the one for public text has fallen behind | [R-15](#r-15) |
| [XDUP-02](findings/sweep-duplication.md#xdup-02) | sweep-duplication | Approval transitions and approved-request reads are re-implemented outside approvals.py | [R-21](#r-21) |
| [XDUP-03](findings/sweep-duplication.md#xdup-03) | sweep-duplication | Three copies of run admission; only one is protected against duplicate paid runs | [R-18](#r-18) |
| [XDUP-06](findings/sweep-duplication.md#xdup-06) | sweep-duplication | Browser data access is hand-written in 31 components, and the generated client can't be used there | [R-48](#r-48) |
| [XERR-01](findings/sweep-errors.md#xerr-01) | sweep-errors | Private logs keep only the exception's class name, so no failure can be located without reproducing it | [R-25](#r-25) |
| [XERR-02](findings/sweep-errors.md#xerr-02) | sweep-errors | The tool gateway turns any unexpected tool exception into a bare code, with no log line and no receipt detail | [R-25](#r-25) |
| [XERR-03](findings/sweep-errors.md#xerr-03) | sweep-errors | The web reports a contract mismatch as an outage, or hangs on it, and nothing records which field failed | [R-02](#r-02), [R-27](#r-27) |
| [XTOL-01](findings/sweep-tooling.md#xtol-01) | sweep-tooling | Repository-level Python runs under no lint, format or type gate | [R-07](#r-07) |
| [XTOL-02](findings/sweep-tooling.md#xtol-02) | sweep-tooling | Hand-kept test lists let tests drop out unseen, and two suites already run in no profile | [R-01](#r-01) |
| [XTYP-01](findings/sweep-types.md#xtyp-01) | sweep-types | Browser writes bypass the generated client: request bodies are hand-built and replies are cast | [R-48](#r-48) |
| [XTYP-02](findings/sweep-types.md#xtyp-02) | sweep-types | Generated map types and runtime checks drop value schemas | [R-03](#r-03) |
| [XTYP-03](findings/sweep-types.md#xtyp-03) | sweep-types | Persisted JSON documents have no schema shared by writer and reader | [R-51](#r-51) |
| [XTYP-04](findings/sweep-types.md#xtyp-04) | sweep-types | The SQL boundary is untyped: Any connections and positional rows | [R-54](#r-54) |
| [XTYP-14](findings/sweep-types.md#xtyp-14) | sweep-types | A contract mismatch on a read looks like an outage | [R-02](#r-02), [R-27](#r-27) |
| [XWEB-01](findings/sweep-web-architecture.md#xweb-01) | sweep-web-architecture | Write requests and error bodies bypass the generated contract | [R-48](#r-48) |
| [XWEB-02](findings/sweep-web-architecture.md#xweb-02) | sweep-web-architecture | No shared client data layer: 23 files hand-roll fetch-in-effect | [R-27](#r-27) |
| [XWEB-03](findings/sweep-web-architecture.md#xweb-03) | sweep-web-architecture | Writes have no shared submit path, and run admission isn't guarded against a second press | [R-18](#r-18) |
| [XWEB-05](findings/sweep-web-architecture.md#xweb-05) | sweep-web-architecture | Screen components own data, stream protocol and markup in one function | [R-49](#r-49), [R-59](#r-59) |
| [WBLD-01](findings/web-build.md#wbld-01) | web-build | WorkflowEditor is one 617-line component that owns eight concerns | [R-43](#r-43) |
| [WBLD-02](findings/web-build.md#wbld-02) | web-build | Create, publish and run calls make a new Idempotency-Key on every click and never disable their buttons | [R-19](#r-19) |
| [WCMP-01](findings/web-composer.md#wcmp-01) | web-composer | Run admission can start duplicate paid runs: no in-flight guard and a new Idempotency-Key on every press | [R-18](#r-18) |
| [WCMP-02](findings/web-composer.md#wcmp-02) | web-composer | Admission replies are cast instead of parsed, and request bodies are untyped | [R-09](#r-09) |
| [WCMP-03](findings/web-composer.md#wcmp-03) | web-composer | GoalComposer is a 541-line component with 13 state hooks, three effects and inline submission | [R-44](#r-44) |
| [WRUN-01](findings/web-run.md#wrun-01) | web-run | RunWorkspaceView is a 677-line, complexity-39 component that every run story edits | [R-49](#r-49) |
| [WRUN-02](findings/web-run.md#wrun-02) | web-run | The run page treats every failed read as temporary: denied runs are polled every second, and 403, 422, 5xx or contract errors never leave Loading | [R-28](#r-28) |
| [WRUN-03](findings/web-run.md#wrun-03) | web-run | A lost write reply is reported as a failure, and the retry is sent with a new idempotency key | [R-18](#r-18) |
| [WRUN-06](findings/web-run.md#wrun-06) | web-run | Write replies and stream frames are cast instead of parsed, although generated parsers exist | [R-09](#r-09) |
| [WSHL-01](findings/web-shell.md#wshl-01) | web-shell | The contract validator ignores array bounds, map value schemas and unknown keywords | [R-03](#r-03) |
| [WSHL-02](findings/web-shell.md#wshl-02) | web-shell | Server reads and the BFF throw away every failure cause, so drift, 401s and timeouts read as signed out or a generic 503 | [R-26](#r-26) |
| [WSYS-01](findings/web-system.md#wsys-01) | web-system | Retention day fields misparse typos before a destructive retention pass | [R-13](#r-13) |
| [TWEB-01](findings/web-tests.md#tweb-01) | web-tests | Suites hand workspace state to each other through alphabetical file order and filename-based selection | [R-58](#r-58) |
| [TWEB-02](findings/web-tests.md#tweb-02) | web-tests | No shared test layer: 38 specs carry about 747 lines of copied sign-in, CSRF, key and axe helpers | [R-40](#r-40) |
| [TWEB-03](findings/web-tests.md#tweb-03) | web-tests | slice-visual.spec.ts packs an untyped in-page script, an arranger, a surface table and a 10-minute loop test into 1,057 lines | [R-46](#r-46) |
| [WTAP-01](findings/web-tools-approvals.md#wtap-01) | web-tools-approvals | approvals-panel.tsx packs data loading, decisions, a shortcut state machine and two large views into one module | [R-45](#r-45) |
| [WTAP-02](findings/web-tools-approvals.md#wtap-02) | web-tools-approvals | The two-press shortcut accepts a held key, Alt chords, and an arm that is not tied to a request | [R-16](#r-16) |

## Decisions the plan needs

These are owner decisions, not refactors. Each item proceeds up to the step that needs its decision, and the delivery rule stops there until the decision is recorded.

- [R-01](#r-01): The web unit-test mechanism (step 8): `node --test` over JSX-free modules, or Vitest and Testing Library under a story that pins and records them ([WSHL-10](findings/web-shell.md#wshl-10)).
- [R-18](#r-18): Whether the composer and the session panel keep one key per press, as US-4.1 chose, or keep the key until the outcome is known, as [WCMP-01](findings/web-composer.md#wcmp-01) and [XDUP-03](findings/sweep-duplication.md#xdup-03) recommend.
- [R-21](#r-21): Whether `base_moved` also enters the decision wait at once, as the expiry path does ([XDUP-02](findings/sweep-duplication.md#xdup-02)). Decide it with a test.
- [R-23](#r-23): What the watchdog does when spend stays unreadable ([SCRP-03](findings/scripts.md#scrp-03)).
- [R-29](#r-29): Whether an unmapped code should suspend instead of fail ([PRUN-02](findings/py-run.md#prun-02)). The table makes today's choice explicit until the owner decides.
- [R-35](#r-35): The bound on consecutive failed attempts, and the state it leads to (SP-012 bounded retries; [XERR-10](findings/sweep-errors.md#xerr-10)).
- [R-43](#r-43): Who owns the WF-06 label rule. The preferred end state, a label-free normalized graph, is a contract and hash change that needs its own story ([WBLD-06](findings/web-build.md#wbld-06)).
- [R-52](#r-52): Whether the Routines API takes the cronjob tool's US$1 cap; admission caps each run at the workspace's run limit today ([PDOM-02](findings/py-domain.md#pdom-02)).
- [R-56](#r-56): Whether members need Storage insert, update or delete at all ([SQLI-07](findings/sql-infra.md#sqli-07)), and whether to remove member write grants on drafts, which the plan keeps because US-15.12 and US-15.2 accept them ([SQLI-13](findings/sql-infra.md#sqli-13)).
- [R-57](#r-57): The owner schedules the live executor re-qualification (Decision 0018 B8).
- [R-60](#r-60): A system actor extends SP-010's actor table; record it before step 2.
- [R-64](#r-64): Amending DH-03 is the user's decision, recorded under `docs/engineering/decisions/` ([XMOD-13](findings/sweep-boundaries.md#xmod-13)).

## Medium and low findings without an item

The items address 479 of the 493 findings. The remaining 1 medium and 13 low findings are local. Fix each one when its file is next touched, following [standards.md](standards.md); the wave 0 ratchets keep their patterns from spreading meanwhile.

- **py-run:** [PRUN-22](findings/py-run.md#prun-22) (low).
- **py-tools:** [PTOL-16](findings/py-tools.md#ptol-16) (low), [PTOL-18](findings/py-tools.md#ptol-18) (low), [PTOL-19](findings/py-tools.md#ptol-19) (low), [PTOL-20](findings/py-tools.md#ptol-20) (low).
- **sweep-docs-naming:** [XDOC-04](findings/sweep-docs-naming.md#xdoc-04) (medium), [XDOC-05](findings/sweep-docs-naming.md#xdoc-05) (low), [XDOC-06](findings/sweep-docs-naming.md#xdoc-06) (low), [XDOC-08](findings/sweep-docs-naming.md#xdoc-08) (low).
- **sweep-web-architecture:** [XWEB-20](findings/sweep-web-architecture.md#xweb-20) (low).
- **web-run:** [WRUN-18](findings/web-run.md#wrun-18) (low), [WRUN-19](findings/web-run.md#wrun-19) (low).
- **web-system:** [WSYS-18](findings/web-system.md#wsys-18) (low).
- **web-tools-approvals:** [WTAP-16](findings/web-tools-approvals.md#wtap-16) (low).

## Suggested backlog entries

This review edits no backlog. The owner decides what enters `SPECS.md`, directly or through `autobots-spec-ingest`, and assigns the story IDs.

- **Placement.** A new epic, for example "Code quality and maintainability", after the epic for a current install with real examples, or each story under the epic that owns its area. Either way, the stories cite this plan and the linked findings as their source, because they come from a review rather than from a PRD.
- **One story per item.** The title is the item's title, and the story reads "As a maintainer, I want the item's outcome, so that its why-now no longer holds". Each test that the item adds first becomes an acceptance scenario, its steps become tasks, and its dependencies become story dependencies.
- **Status.** Every story starts `BLOCKED`. `python3.12 scripts/specs.py promote` moves one to `READY` only when its dependencies are `DONE` and it has no open question, so an item with a "Decision needed" line carries that decision as an open question until the owner answers it. Nothing is hand-edited to `READY`.
- **Order.** Add waves 0 and 1 first, since they are small and their ratchets protect everything after them; then wave 2 in the plan's order; and wave 3 items only when their dependencies are close to done.

An example in the backlog's format, for the first item:

````markdown
### US-<assigned by the owner>: Every test file runs in a profile, and the profiles are easy to run

Status: BLOCKED

As a maintainer
I want every test file claimed by a verification profile, and the profiles easy to run
So that no guard drops out of the checks unseen.

Source:
- Refactor plan R-01 (docs/reviews/review-2026-11-12-09-52-30/refactor-plan.md)
- Findings XTOL-02, THRN-02, WSHL-08, XWEB-15, XTOL-09, XTOL-10, XTOL-11 and WSHL-10 (same folder, findings/)

Acceptance Criteria:

```gherkin
Scenario: An unclaimed test file fails the harness
  Given a test file that no profile step claims and no manual list names
  When the harness profile runs
  Then the claim test fails and names the file

Scenario: Unit tests are selected by glob
  Given a new test file under apps/web/tests/unit
  When the full profile runs
  Then web_unit_tests executes it
```

Dependencies:
- None.

Tasks:
- [ ] Add the claim test and its self-check.
- [ ] Select Node tests by glob, and give the offline toolchain tests one pattern.
- [ ] Add the gate-settings test, the make targets and the opt-in pre-commit hook.

Open Questions:
- Which mechanism runs the web unit tests: node --test over JSX-free modules, or Vitest and Testing Library?
````

Product decisions that these findings raise, and that are not refactors:

- Serve the user's allowed run commands in `RunWorkspace` from `domain.next_status` ([WRUN-12](findings/web-run.md#wrun-12), [XMOD-06](findings/sweep-boundaries.md#xmod-06)), a contract addition that [R-49](#r-49) plans as its own story.
- A label-free normalized workflow graph for WF-06, a contract and hash change ([WBLD-06](findings/web-build.md#wbld-06)).
- Whether the composer keeps one idempotency key per press, as US-4.1 chose ([WCMP-01](findings/web-composer.md#wcmp-01), [XDUP-03](findings/sweep-duplication.md#xdup-03)).
- A bound on consecutive failed worker attempts, with a forward migration ([XERR-10](findings/sweep-errors.md#xerr-10)).
- Whether the Routines API takes the cronjob tool's US$1 cap ([PDOM-02](findings/py-domain.md#pdom-02)).
- The web unit-test mechanism ([WSHL-10](findings/web-shell.md#wshl-10)).
- An amendment of the DH-03 layout ([XMOD-13](findings/sweep-boundaries.md#xmod-13)).
- Which Storage writes members need ([SQLI-07](findings/sql-infra.md#sqli-07)).

## Considered and not recommended

- **A client data library such as SWR or TanStack Query.** [R-27](#r-27) needs no dependency, and DH-06 forbids keeping workspace data in shared caches, so the hook shares only requests that are in flight ([XWEB-02](findings/sweep-web-architecture.md#xweb-02)). A library would also need its own story to pin and record it.
- **A form library for the composer.** Validation is one non-empty check plus the server's refusals, so a library would add little ([WCMP-03](findings/web-composer.md#wcmp-03)).
- **One merged type for `RunBinding`, `Inheritance` and the run grant.** Ground rule 2 keeps these types apart; a structural Protocol types the binding without merging them ([PPRD-01](findings/py-product.md#pprd-01)).
- **A compiled regex engine for code search**, such as `google-re2` or the `regex` package's timeout. Each is a new compiled dependency, and Decision 0017 C7 keeps search in pure Python; a stdlib child process bounds the time without either ([PTOL-01](findings/py-tools.md#ptol-01)).
- **Serial mode for the visual walk.** It skips every later test after the first failure, which defeats keeping partial evidence ([TWEB-03](findings/web-tests.md#tweb-03)).
- **Removing member write grants on workflow drafts.** US-15.12 and US-15.2 accept those writes, so the API is made tolerant instead; removing the grants needs a product decision ([SQLI-13](findings/sql-infra.md#sqli-13)).
- **Editing applied migrations** to add lock and recovery headers or to replace the profile CHECK constraints. Migrations only move forward ([SQLI-03](findings/sql-infra.md#sqli-03), [SQLI-04](findings/sql-infra.md#sqli-04)).
- **Hand-editing `generated.ts`** to fix the map types. The generator changes, and the file is regenerated ([XTYP-02](findings/sweep-types.md#xtyp-02)).
- **Enabling ruff `ALL`, or every extra ESLint rule, as errors now.** `ALL` was an exploratory superset in [metrics.md](metrics.md); rules are adopted at warn, then baselined, then made errors.
- **Reformatting in a hook, or running `db` and `operations` from a Git hook.** DH-05 forbids formatter rewrites in hooks, and those profiles start Docker projects; the opt-in Git hook runs `fast` only ([XTOL-11](findings/sweep-tooling.md#xtol-11)).
- **Making an unmapped stop code suspend by default as part of the refactor.** That changes run behavior, so it is an owner decision; [R-29](#r-29) only makes today's dispositions explicit ([PRUN-02](findings/py-run.md#prun-02)).
- **A shared TypeScript copy of the run command table.** The server projects the allowed commands instead, so no business transition moves into Next.js ([WRUN-12](findings/web-run.md#wrun-12)).
- **Renaming `CronjobSchedule` while moving it.** The rename would change the cronjob tool's v1 schema ([PDOM-02](findings/py-domain.md#pdom-02)).
- **Moving every tool into one package.** The verifier rejected this as taste, with churn and checkpoint-path risk; the registry module in [R-53](#r-53) becomes the single index of tools instead (XMOD-14, rejected).
- **Changing the fault checker's copy of the transition table.** The verifier found that it matches the product's normal exits, so nothing is planned (TDBC-16, rejected). WTAP-14 was merged into [WTAP-08](findings/web-tools-approvals.md#wtap-08).
