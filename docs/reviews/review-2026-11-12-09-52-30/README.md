# Code quality review, 2026-11-12 09:52:30

A repository-wide review of code quality and maintainability at revision `d0d85d3`: 545 tracked files in 19 areas, read again across 7 lenses, with 493 verified findings (70 high, 269 medium, 154 low), [51 proposed standards](standards.md) and a [68-item refactor plan](refactor-plan.md). The review changed no source and edits no backlog.

> **Evidence class.** This review is static. Its metrics come from installed tools, and its findings come from reading code. It is not runtime evidence, and it establishes no H1 and no product acceptance.

## Scope and method

- **Revision.** `d0d85d3863b996e7cfbdb564d6670a7f0c9c8685` on `main`, "Add a narrated usage film for Autobots". HEAD had not moved when this README was written. On 2026-11-19 the owner had `docs/video` purged from `main`'s history. That gave this commit and every later one a new hash, so this README and its findings cite the new one. The commit now adds nothing. Every file the review read is unchanged, since none was under `docs/video`.
- **Working tree.** Two paths were untracked when this invocation started, `.claude/workflows/` and `docs/reviews/`, which hold the review's own workflow and output. The review read tracked files as they were on disk.
- **Scope.** 545 tracked files and 88,682 lines in `apps/web`, `packages/api-client` and `packages/db-types` (without generated files), `services/agent`, `scripts`, `.claude/hooks`, `tests`, `supabase` and non-vendored `infra`, plus the `Makefile` and the root `package.json`. The generated files, the vendored `infra/supabase/upstream/`, `openspec/`, `docs/`, `research/`, the PRDs and `SPECS.md` were out of scope for style and size; the review judged only how generated code is consumed.
- **Areas and lenses.** The workflow assigned every file to exactly one of 19 areas, and no file was left unclaimed. Seven lenses then read across all areas for patterns that span files: module boundaries, duplication, types, comments and naming, errors, tooling, and web architecture.
- **Dimensions.** Findings use the twelve dimensions in [PROMPT.md](PROMPT.md): standards, modules, size, functions, structure, approach, comments, types, errors, tests, duplication and naming. Scores cover the first ten, plus an overall maintainability score.

| Step | Method | Agents in a full run |
|---|---|---:|
| Measure | Installed tools only. Every command is in [metrics.md](metrics.md#9-commands). | 1 |
| Review | One reviewer per area, reading every file in its scope, and one reviewer per lens. | 26 |
| Verify | Adversarial: re-open every cited location, recount occurrences, calibrate severity, effort and risk, and reject what fails. Related parts share a verifier. | 14 |
| Synthesize | [standards.md](standards.md) and [refactor-plan.md](refactor-plan.md) from verified findings only, then this README. | 3 |
| Check | Links, anchors, finding IDs, plan coverage of high findings, and the scorecard and counts. | 1 |

**Measured with tools** (ruff 0.17.3, Python 3.12.16, Node v22.23.2, ESLint v9.39.5):

- line counts for the 545 files, and Python function lengths, parameters, docstring coverage and broad `except` clauses with `ast`;
- ruff in `services/agent`: the project's own rules on `src` and `tests`, then the complexity, branch, return, statement and argument rules and `--select ALL` as an exploratory superset (2,846 hits) on `src`; plus the repository-level Python under `--isolated` settings, because `scripts/`, `tests/` and `.claude/hooks/` have no configuration of their own;
- ESLint on `apps/web` with extra size, complexity and assertion rules passed on the command line as warnings;
- the latest `scripts/verify.py` reports, read from `.checks/<profile>/latest.json` and not rerun.

[standards.md](standards.md) adds a few read-only counts of its own, such as a strict mypy check of six trust-boundary modules, each listed with its command under [Counts added for this document](standards.md#counts-added-for-this-document).

**Read by agents:**

- Area reviewers read every file in their scope in full, and all 19 reported doing so. They read other areas' files only at the lines they cite.
- Lens reviewers swept all 545 files with grep and `ast` scans and opened the code behind every pattern they cite, without reading every file in full.
- Verifiers re-opened every cited location. They confirmed 255 findings, revised 238 (a corrected location, count, severity or recommendation) and rejected or merged 3.
- Metrics served as leads, never as findings on their own.

**Invocations.** The run was interrupted and finished by a resume from disk.

| Invocation | Agents started | What happened |
|---|---:|---|
| First, from 09:52 | 43 | Measured, reviewed and verified. At about 11:17 local time the account's weekly usage limit stopped 9 agents: the sweep-docs-naming review and eight verifiers. The standards and plan writers were stopped before they wrote anything. |
| Resume through the run cache | 10 | The cache replays agent calls in order, and parallel agents finish in a different order each time, so it redid finished reviews. It was stopped after about a minute, and none of its agents wrote findings. |
| Resume from disk (this one) | 12 before this README, 0 retries | The 25 finished reviews were restored from the first invocation's run journal into `.checks/reviews/review-2026-11-12-09-52-30/reviews/`, with finding IDs numbered in their original order. The 12 parts already verified were kept as written. By the workflow's grouping, the 12 agents were the inventory step, a new sweep-docs-naming review, eight verifiers for the other 14 parts, and the standards and plan writers. This README's writer and the checker follow. |

## Executive summary

- **A sound core that is costly to change.** The durable core is strong: a pure domain layer, one run transition table enforced under row locks, fenced leases, receipts before effects, an integer money ledger, generated parsers on every successful read, and comments whose citations resolve. Around it, 22 of the 26 parts score maintainability 3, and the three that score 2, scripts, db-tests and web-tests, are the code that produces the project's evidence. Verification kept 493 findings: 70 high, 269 medium and 154 low.
- **Fix four small defects first.** A retention window typed as "1,000" saves as 1 day and feeds an irreversible purge ([WSYS-01](findings/web-system.md#wsys-01)); a malformed `save_artifact` call can stop a paid run ([PADP-01](findings/py-adapters.md#padp-01)); public text shows Tavily, Jina and GitHub tokens that the logs redact ([XDUP-01](findings/sweep-duplication.md#xdup-01)); and a held ⌘↵ or a stale arm can decide an approval ([WTAP-02](findings/web-tools-approvals.md#wtap-02)). Each is a small fix with its test written first: [R-13](refactor-plan.md#r-13) to [R-16](refactor-plan.md#r-16).
- **Paid runs can be admitted twice.** Run admission in the composer and the session panel, and nine keyed POSTs in the builders, mint a new Idempotency-Key on every press, and their buttons stay enabled while a request is pending. Only ContinueRun keeps its key until the outcome is known ([WCMP-01](findings/web-composer.md#wcmp-01), [XDUP-03](findings/sweep-duplication.md#xdup-03), [WBLD-02](findings/web-build.md#wbld-02)). Spread its rule through one submit hook ([R-18](refactor-plan.md#r-18), [R-19](refactor-plan.md#r-19)); R-18 needs the owner to decide whether US-4.1's one key per press still stands.
- **The contract stops at errors and writes.** All 78 operations document a 422 body that the server never sends and declare none of the error bodies it does send ([PAPI-03](findings/py-api.md#papi-03)); the TypeScript validator skips 29 schema constraints ([WSHL-01](findings/web-shell.md#wshl-01)); browser writes bypass the generated client ([XTYP-01](findings/sweep-types.md#xtyp-01)); and a contract mismatch shows as an outage or an endless Loading ([XERR-03](findings/sweep-errors.md#xerr-03), [WRUN-02](findings/web-run.md#wrun-02)). Start with [R-02](refactor-plan.md#r-02), [R-03](refactor-plan.md#r-03) and [R-09](refactor-plan.md#r-09); the shared read hook ([R-27](refactor-plan.md#r-27)), the run page's read and polling fix ([R-28](refactor-plan.md#r-28)) and the typed browser client ([R-48](refactor-plan.md#r-48)) build on them.
- **Failures lose their causes.** Private logs keep only the exception's class name ([XERR-01](findings/sweep-errors.md#xerr-01)); the tool gateway records any unexpected tool exception as a bare `outcome_unknown` with no log line ([XERR-02](findings/sweep-errors.md#xerr-02)); and server reads show a signed-in person the Sign in link for contract drift, a missing internal token or a timeout ([WSHL-02](findings/web-shell.md#wshl-02)). [R-25](refactor-plan.md#r-25) and [R-26](refactor-plan.md#r-26) keep message-free causes.
- **Durable state has more than one writer.** The pull-request connector resets approval state in four autocommit statements without the lease ([PADP-02](findings/py-adapters.md#padp-02)); approval and receipt states are bare strings written from six modules ([PTOL-03](findings/py-tools.md#ptol-03)); the runtime role can delete runs, and 21 cascading foreign keys reach the receipt ledger ([SQLI-01](findings/sql-infra.md#sqli-01)); and five hand-kept sets of stop codes decide whether a run fails for good ([PRUN-02](findings/py-run.md#prun-02)). [R-21](refactor-plan.md#r-21), [R-17](refactor-plan.md#r-17) and [R-29](refactor-plan.md#r-29) come first, then the state machines in [R-50](refactor-plan.md#r-50).
- **Enforcement stops at directory lines.** 133 repository-level Python files, 42% of the Python and including the verifier, the hook and the persistent installer, run under no lint, format or type gate ([XTOL-01](findings/sweep-tooling.md#xtol-01)). Two test suites run in no profile, and an archived verification record cites one of them as passing ([XTOL-02](findings/sweep-tooling.md#xtol-02)). In the database checks, 80 calls evaluate the shown value and the verdict separately, so some lease and claim cases can pass with their guard broken ([TDBC-01](findings/db-tests.md#tdbc-01)). Waves 0 and 1 close these: [R-01](refactor-plan.md#r-01), [R-07](refactor-plan.md#r-07), [R-08](refactor-plan.md#r-08).
- **Size sits in a few hotspots.** Every run story edits RunWorkspaceView (677 lines without blanks or comments, complexity 39); WorkflowEditor (617) owns eight concerns and GoalComposer (527) holds 13 state hooks; and the 782-line `goal_loop.py` mixes seven concerns that other modules reach through private names ([WRUN-01](findings/web-run.md#wrun-01), [WBLD-01](findings/web-build.md#wbld-01), [WCMP-03](findings/web-composer.md#wcmp-03), [PRUN-01](findings/py-run.md#prun-01)). Split them after the shared hooks and vocabularies land: [R-42](refactor-plan.md#r-42) to [R-44](refactor-plan.md#r-44) and [R-49](refactor-plan.md#r-49).

## Scorecard

Scores run from 1 to 5: 5 is a model for the rest of the repository, 4 is good with minor issues, 3 is adequate with notable friction, 2 is weak and causes recurring cost, and 1 blocks safe change. Each score's one-line reason is in the part's findings file. No part scored `duplication` or `naming`, which the workflow leaves out of its score list; those dimensions appear in the [finding counts](#finding-counts) instead.

### Areas

| Area | Files | Standards | Modules | Size | Functions | Structure | Approach | Comments | Types | Errors | Tests | Maintainability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| [web-run](findings/web-run.md) | 13 | 3 | 3 | 2 | 2 | 3 | 3 | 4 | 3 | 2 | 3 | 3 |
| [web-composer](findings/web-composer.md) | 10 | 3 | 3 | 2 | 2 | 3 | 3 | 4 | 3 | 2 | 3 | 3 |
| [web-build](findings/web-build.md) | 10 | 3 | 3 | 2 | 3 | 3 | 2 | 4 | 3 | 2 | 3 | 3 |
| [web-tools-approvals](findings/web-tools-approvals.md) | 5 | 3 | 3 | 2 | 3 | 3 | 3 | 4 | 3 | 2 | 3 | 3 |
| [web-system](findings/web-system.md) | 14 | 3 | 3 | 2 | 3 | 3 | 3 | 4 | 3 | 2 | 3 | 3 |
| [web-shell](findings/web-shell.md) | 56 | 3 | 4 | 4 | 4 | 4 | 3 | 4 | 3 | 2 | 3 | 3 |
| [py-domain](findings/py-domain.md) | 42 | 3 | 3 | 4 | 4 | 3 | 3 | 4 | 3 | 3 | 3 | 3 |
| [py-run](findings/py-run.md) | 13 | 3 | 2 | 2 | 3 | 3 | 4 | 4 | 2 | 2 | 3 | 3 |
| [py-tools](findings/py-tools.md) | 13 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 2 | 3 | 3 | 3 |
| [py-product](findings/py-product.md) | 11 | 3 | 3 | 3 | 3 | 4 | 4 | 4 | 2 | 3 | 3 | 3 |
| [py-adapters](findings/py-adapters.md) | 22 | 3 | 2 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 3 |
| [py-api](findings/py-api.md) | 21 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 3 |
| [py-ops](findings/py-ops.md) | 18 | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 4 | 3 |
| [scripts](findings/scripts.md) | 30 | 2 | 2 | 2 | 2 | 3 | 3 | 4 | 2 | 3 | 3 | 2 |
| [db-tests](findings/db-tests.md) | 95 | 2 | 2 | 2 | 2 | 2 | 3 | 4 | 2 | 2 | 3 | 2 |
| [sql-infra](findings/sql-infra.md) | 64 | 4 | 3 | 4 | 4 | 3 | 3 | 4 | 3 | 4 | 3 | 3 |
| [web-tests](findings/web-tests.md) | 42 | 3 | 2 | 2 | 3 | 2 | 3 | 4 | 2 | 3 | 3 | 2 |
| [harness-tests](findings/harness-tests.md) | 20 | 2 | 3 | 3 | 4 | 3 | 4 | 4 | 3 | 3 | 3 | 3 |
| [py-tests](findings/py-tests.md) | 46 | 3 | 3 | 3 | 4 | 3 | 3 | 4 | 3 | 4 | 3 | 3 |

### Lenses

Repository-wide scores. A dash means the lens did not score that dimension.

| Lens | Standards | Modules | Size | Functions | Structure | Approach | Comments | Types | Errors | Tests | Maintainability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| [sweep-boundaries](findings/sweep-boundaries.md) | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 3 |
| [sweep-duplication](findings/sweep-duplication.md) | 3 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 3 |
| [sweep-types](findings/sweep-types.md) | 3 | 3 | - | - | - | 3 | 4 | 3 | 3 | 3 | 3 |
| [sweep-docs-naming](findings/sweep-docs-naming.md) | 3 | - | - | - | 4 | - | 4 | - | - | 4 | 4 |
| [sweep-errors](findings/sweep-errors.md) | 3 | 3 | - | 3 | - | 3 | 4 | 2 | 3 | 3 | 3 |
| [sweep-tooling](findings/sweep-tooling.md) | 3 | 3 | 2 | 3 | 3 | 4 | 3 | 3 | 3 | 3 | 3 |
| [sweep-web-architecture](findings/sweep-web-architecture.md) | 3 | 3 | 2 | 3 | 3 | 2 | 4 | 3 | 3 | 3 | 3 |

What the scores show:

- No part scores 1 or 5. Comments score 4 in all 19 areas and in six of the seven lenses.
- Size scores 2 in nine areas: the five web screen areas, py-run, scripts, db-tests and web-tests. Errors score 2 in eight: all six web areas, py-run and db-tests. Types score 2 in six: py-run, py-tools, py-product, scripts, db-tests and web-tests.
- Maintainability is 3 in 16 areas and 2 in scripts, db-tests and web-tests. Every lens gives it 3, except the comments, documentation and naming lens, which gives 4.
- The strongest areas are sql-infra (4 for standards, size, functions and errors), web-shell (4 for modules, size, functions and structure) and py-domain (4 for size and functions).

## Top recommendations

Recommendations 1 to 3 are where the plan starts: the wave 0 guardrails and the four small fixes that open wave 2. The rest are grouped by theme. Each names its plan items with the wave, effort and risk that the plan gives them, and any owner decision they wait on; the plan's [table of all items](refactor-plan.md#all-items) lists their dependencies.

1. **Make every test count, and gate all Python.** Select tests by glob, add a test that every test file belongs to a runner, give repository Python one shared lint, format and type gate, and ratchet size, complexity, `Any`, broad excepts and assertions from today's counts, so that later refactors stick.

   Plan: [R-01](refactor-plan.md#r-01) (wave 0, M, low risk) and [R-07](refactor-plan.md#r-07) (L, low), with the ratchets [R-05](refactor-plan.md#r-05) and [R-06](refactor-plan.md#r-06) (M, low). Findings: [XTOL-02](findings/sweep-tooling.md#xtol-02), [THRN-02](findings/harness-tests.md#thrn-02), [XTOL-01](findings/sweep-tooling.md#xtol-01), [SCRP-04](findings/scripts.md#scrp-04). Standards: [STD-43](standards.md#std-43), [STD-48](standards.md#std-48), [STD-51](standards.md#std-51).
2. **Land the four small fixes.** Parse retention days strictly before a destructive pass, make the live-result tap total, keep one secret-pattern module for logs and public text, and bind the approval shortcut to one request while ignoring key repeat.

   Plan: [R-13](refactor-plan.md#r-13), [R-14](refactor-plan.md#r-14), [R-15](refactor-plan.md#r-15) and [R-16](refactor-plan.md#r-16) (wave 2, each S, medium risk, failing test first; R-13 and R-16 wait for the web unit tests that R-01 brings into a profile). Findings: [WSYS-01](findings/web-system.md#wsys-01), [PADP-01](findings/py-adapters.md#padp-01), [XDUP-01](findings/sweep-duplication.md#xdup-01), [PRUN-05](findings/py-run.md#prun-05), [WTAP-02](findings/web-tools-approvals.md#wtap-02). Standard: [STD-03](standards.md#std-03).
3. **Declare the error envelope, and enforce every schema keyword.** Declare `ErrorResponse` on every operation and regenerate; have the runtime raise a typed HTTP failure and keep `ContractError` for shape mismatches; implement `minItems`, `maxItems` and schema-valued `additionalProperties`, with a test that fails on any keyword the runtime ignores. Runtime responses do not change.

   Plan: [R-02](refactor-plan.md#r-02) and [R-03](refactor-plan.md#r-03) (wave 0, each M, high risk because the published contract changes). Findings: [PAPI-03](findings/py-api.md#papi-03), [XERR-03](findings/sweep-errors.md#xerr-03), [XTYP-14](findings/sweep-types.md#xtyp-14), [WSHL-01](findings/web-shell.md#wshl-01), [XTYP-02](findings/sweep-types.md#xtyp-02). Standards: [STD-15](standards.md#std-15), [STD-18](standards.md#std-18).
4. **Stop duplicate paid submissions.** Build one admission client and submit hook that keeps the Idempotency-Key until the outcome is known and disables the button while a request is pending, as ContinueRun does; then route the builders' keyed writes and the settings saves through it.

   Plan: [R-18](refactor-plan.md#r-18) and [R-19](refactor-plan.md#r-19) (wave 2, M, medium; after R-02 and R-09). Decision needed: whether US-4.1's one key per press stands. Findings: [WCMP-01](findings/web-composer.md#wcmp-01), [XDUP-03](findings/sweep-duplication.md#xdup-03), [XWEB-03](findings/sweep-web-architecture.md#xweb-03), [WRUN-03](findings/web-run.md#wrun-03), [WBLD-02](findings/web-build.md#wbld-02). Standard: [STD-32](standards.md#std-32).
5. **Give approval state one fenced writer, and stop runtime deletes of runs.** Move the pull-request re-request into `approvals.py` as one leased transaction; revoke the runtime role's DELETE on runs, run events, workspaces, members and profiles in a forward migration, and check grants from the catalog; then give receipts and approvals state machines with single writers.

   Plan: [R-21](refactor-plan.md#r-21) and [R-17](refactor-plan.md#r-17) (wave 2, M, high), then [R-50](refactor-plan.md#r-50) (wave 3, L, high). Findings: [PADP-02](findings/py-adapters.md#padp-02), [XDUP-02](findings/sweep-duplication.md#xdup-02), [XMOD-02](findings/sweep-boundaries.md#xmod-02), [SQLI-01](findings/sql-infra.md#sqli-01), [PTOL-03](findings/py-tools.md#ptol-03). Standards: [STD-37](standards.md#std-37), [STD-41](standards.md#std-41).
6. **One implementation for each paid-path guard.** Price paid trials with the application's catalog parser, share one tested paid-run session among the four paid entry points, use one readiness gate for people and routines, and run model-supplied regex searches where their timeout can stop them.

   Plan: [R-22](refactor-plan.md#r-22) and [R-23](refactor-plan.md#r-23) (wave 2, M, high), [R-24](refactor-plan.md#r-24) and [R-20](refactor-plan.md#r-20) (M, medium). Decision needed for R-23: what the watchdog does when spend stays unreadable. Findings: [POPS-01](findings/py-ops.md#pops-01), [SCRP-03](findings/scripts.md#scrp-03), [POPS-02](findings/py-ops.md#pops-02), [PTOL-01](findings/py-tools.md#ptol-01). Standards: [STD-03](standards.md#std-03), [STD-17](standards.md#std-17).
7. **Keep failure causes, and show each failure as what it is.** Add message-free cause fields to private logs and a detail to unknown tool receipts; have server reads tell signed-out from unavailable; give screens one read hook with explicit loading, denied, not-found, retryable and invalid states; and stop the run page polling denied runs.

   Plan: [R-25](refactor-plan.md#r-25), [R-26](refactor-plan.md#r-26), [R-27](refactor-plan.md#r-27) and [R-28](refactor-plan.md#r-28) (wave 2, M, medium). Findings: [XERR-01](findings/sweep-errors.md#xerr-01), [XERR-02](findings/sweep-errors.md#xerr-02), [WSHL-02](findings/web-shell.md#wshl-02), [XWEB-02](findings/sweep-web-architecture.md#xweb-02), [WRUN-02](findings/web-run.md#wrun-02). Standards: [STD-20](standards.md#std-20), [STD-22](standards.md#std-22).
8. **Parse what the browser sends and receives.** Now, parse write replies, refusals and stream frames with the generated parsers that already exist. Later, give the browser a typed client for every call, so request bodies use the generated types.

   Plan: [R-09](refactor-plan.md#r-09) (wave 1, S, low), then [R-48](refactor-plan.md#r-48) (wave 3, L, medium). Findings: [WCMP-02](findings/web-composer.md#wcmp-02), [WRUN-06](findings/web-run.md#wrun-06), [XTYP-01](findings/sweep-types.md#xtyp-01), [XWEB-01](findings/sweep-web-architecture.md#xweb-01), [XMOD-03](findings/sweep-boundaries.md#xmod-03), [XDUP-06](findings/sweep-duplication.md#xdup-06). Standards: [STD-10](standards.md#std-10), [STD-11](standards.md#std-11).
9. **Untangle the run lifecycle and admission.** Give stop codes one vocabulary with an explicit disposition table, type the admission inputs, publish a run-lifecycle module without the `goal_loop` and `workflow_runner` cycle, and decide how a pass ends in one pure function; then split `goal_loop.py` and build the tool registry at the composition edge.

   Plan: [R-29](refactor-plan.md#r-29), [R-30](refactor-plan.md#r-30), [R-33](refactor-plan.md#r-33), [R-34](refactor-plan.md#r-34) and [R-42](refactor-plan.md#r-42) (wave 2, M, medium to high), then [R-53](refactor-plan.md#r-53) (wave 3, L, medium). Decision needed for R-29: whether an unmapped stop code should suspend instead of fail. Findings: [PRUN-01](findings/py-run.md#prun-01), [PRUN-02](findings/py-run.md#prun-02), [PRUN-03](findings/py-run.md#prun-03), [PRUN-04](findings/py-run.md#prun-04), [PPRD-01](findings/py-product.md#pprd-01), [PPRD-02](findings/py-product.md#pprd-02), [PPRD-03](findings/py-product.md#pprd-03), [XMOD-01](findings/sweep-boundaries.md#xmod-01). Standards: [STD-01](standards.md#std-01), [STD-14](standards.md#std-14).
10. **Make the evidence code judge what it shows, and share its support.** Evaluate once and judge that value in the database checks now; then add seams for the paid-path tests and shared support for the database checks, the child-check runners and the browser specs.

    Plan: [R-08](refactor-plan.md#r-08) (wave 1, S, low), then [R-32](refactor-plan.md#r-32) (M, high), [R-38](refactor-plan.md#r-38) (M, low), [R-39](refactor-plan.md#r-39) (M, medium) and [R-40](refactor-plan.md#r-40) (M, low). Findings: [TDBC-01](findings/db-tests.md#tdbc-01), [PTST-01](findings/py-tests.md#ptst-01), [TDBC-03](findings/db-tests.md#tdbc-03), [SCRP-01](findings/scripts.md#scrp-01), [TWEB-02](findings/web-tests.md#tweb-02). Standards: [STD-44](standards.md#std-44), [STD-45](standards.md#std-45), [STD-46](standards.md#std-46).

After these come the larger moves, each once its dependencies are done: typed persisted documents and versioned stored records ([R-51](refactor-plan.md#r-51), [R-52](refactor-plan.md#r-52); [XTYP-03](findings/sweep-types.md#xtyp-03), [PDOM-01](findings/py-domain.md#pdom-01), [PDOM-02](findings/py-domain.md#pdom-02)), a typed SQL boundary ([R-54](refactor-plan.md#r-54); [XTYP-04](findings/sweep-types.md#xtyp-04)), and the screen splits, [R-43](refactor-plan.md#r-43) to [R-45](refactor-plan.md#r-45) in wave 2 and [R-49](refactor-plan.md#r-49) and [R-59](refactor-plan.md#r-59) in wave 3 ([WBLD-01](findings/web-build.md#wbld-01), [WCMP-03](findings/web-composer.md#wcmp-03), [WTAP-01](findings/web-tools-approvals.md#wtap-01), [WRUN-01](findings/web-run.md#wrun-01), [XWEB-05](findings/sweep-web-architecture.md#xweb-05)). The plan maps every high finding to an item and defers none ([High findings and where they are addressed](refactor-plan.md#high-findings-and-where-they-are-addressed)). Twelve items stop at a named step until the owner decides ([Decisions the plan needs](refactor-plan.md#decisions-the-plan-needs)).

## Strengths to keep

- **A pure domain and one run state machine.** The 11 domain modules import only the standard library and each other, and `apply_command` enforces the canonical transition table under the job and run row locks with the expected version ([domain/runs.py](../../../services/agent/src/autobots/domain/runs.py#L24), [application/runs.py](../../../services/agent/src/autobots/application/runs.py#L390)). Recorded by [py-domain](findings/py-domain.md#strengths), [py-run](findings/py-run.md#strengths) and [sweep-boundaries](findings/sweep-boundaries.md#strengths).
- **Durable effects with receipts and fences.** A receipt commits under the lease before any effect, failures split into failed and unknown, and interrupted effects are read back rather than resent ([tool_gateway.py](../../../services/agent/src/autobots/application/tool_gateway.py#L435)). Claims use database time and a rising generation, and every create and version command goes through an idempotency receipt. Recorded by [py-tools](findings/py-tools.md#strengths), [py-run](findings/py-run.md#strengths) and [py-product](findings/py-product.md#strengths).
- **Exact money, reserved before the call.** No contract or domain type uses a float for money ([domain/budgets.py](../../../services/agent/src/autobots/domain/budgets.py#L34)), the integer ledger reserves the worst case before dispatch, and paid trials write each call's worst case to an fsync'd, locked ledger before sending it ([route_qualification.py](../../../services/agent/src/autobots/operations/route_qualification.py#L115)). The trials' float price parser is the one exception ([POPS-01](findings/py-ops.md#pops-01)). Recorded by [py-domain](findings/py-domain.md#strengths), [py-run](findings/py-run.md#strengths) and [py-ops](findings/py-ops.md#strengths).
- **A defended HTTP contract.** All 247 Pydantic contract models refuse unknown fields, 25 component files parse their replies with 32 generated parsers (for example [run-workspace.tsx](../../../apps/web/components/run-workspace.tsx#L194)), and [boundary-cases.json](../../../contracts/fixtures/boundary-cases.json) runs in both languages. Extend this pipeline to errors and writes rather than replace it. Recorded by [sweep-types](findings/sweep-types.md#strengths), [sweep-boundaries](findings/sweep-boundaries.md#strengths) and the web areas.
- **Safe errors and logs.** One `{code, message}` envelope with fixed text that never echoes input ([api/errors.py](../../../services/agent/src/autobots/api/errors.py#L19)), a redacting local JSON logger behind every service log line, and no `except` clause that catches a cancellation. Recorded by [py-api](findings/py-api.md#strengths) and [sweep-errors](findings/sweep-errors.md#strengths).
- **Secrets kept out of reach.** Resolved credentials refuse pickling and hide their value in `repr` ([credentials/store.py](../../../services/agent/src/autobots/application/credentials/store.py#L48)), secret fields never enter React state ([provider-settings-panel.tsx](../../../apps/web/components/provider-settings-panel.tsx#L221)), and leak tests plant sentinels and search logs, rows, responses and pages for them. Recorded by [py-ops](findings/py-ops.md#strengths), [web-system](findings/web-system.md#strengths), [py-tests](findings/py-tests.md#strengths) and [db-tests](findings/db-tests.md#strengths).
- **Checks that cannot overclaim.** Checks run offline and fail when they change locks, manifests, files or installed packages, even if every step passed ([toolchain.py](../../../scripts/toolchain.py#L299)); empty or skipped suites fail ([verify.py](../../../scripts/verify.py#L91)); and known-bad fixtures prove that each checker bites ([qualify_faults.py](../../../scripts/qualify_faults.py#L55)). Recorded by [sweep-tooling](findings/sweep-tooling.md#strengths), [harness-tests](findings/harness-tests.md#strengths) and [scripts](findings/scripts.md#strengths).
- **Tests that exercise real failure.** Database checks SIGKILL a real worker inside a model call, after an effect or after a commit, then check fencing ([goal_loop_check.py](../../../tests/db/goal_loop_check.py#L194)); service tests block sockets at import ([conftest.py](../../../services/agent/tests/conftest.py#L23)); and browser suites inject lost replies, dropped streams and offline periods. Recorded by [db-tests](findings/db-tests.md#strengths), [py-tests](findings/py-tests.md#strengths) and [web-tests](findings/web-tests.md#strengths).
- **Comments that explain why, with citations that resolve.** The 220 decision, 338 story and 364 requirement citations in source resolve (the only misses are synthetic fixture IDs in `tests/harness`), ruff finds no commented-out code, and owned source has no TODO markers. Comments score 4 in every area. Recorded by [sweep-docs-naming](findings/sweep-docs-naming.md#strengths).
- **SQL discipline.** No migration was edited after it was added, the installer refuses a misnamed, missing or changed file ([persistent_install.py](../../../scripts/persistent_install.py#L251)), all 24 public tables enable RLS, and all nine SECURITY DEFINER functions pin `search_path`. Recorded by [sql-infra](findings/sql-infra.md#strengths).
- **Patterns ready to spread.** ContinueRun keeps its idempotency key until the outcome is known ([continue-run.tsx](../../../apps/web/components/continue-run.tsx#L20)); `useLoaded` is a typed, abortable load hook ([tool-catalog.tsx](../../../apps/web/components/tool-catalog.tsx#L156)); and the phase-split [browser_executor_check.py](../../../tests/db/browser_executor_check.py#L85) and [tests/toolchain/support.py](../../../tests/toolchain/support.py) show the shape for scenario functions and shared test support. [R-18](refactor-plan.md#r-18), [R-27](refactor-plan.md#r-27) and [R-66](refactor-plan.md#r-66) build on them.

## Finding counts

Verification kept 493 findings, 70 high, 269 medium and 154 low, and rejected or merged 3. The 19 areas hold 378 of them (49 high, 203 medium, 126 low) and the 7 lenses 115 (21 high, 66 medium, 28 low). By the rubric, kept findings take S (279), M (194) or L (20) effort, and their changes carry low (286), medium (170) or high (37) risk.

| Part | Kind | Files | High | Medium | Low | Kept | Rejected or merged |
|---|---|---:|---:|---:|---:|---:|---:|
| [web-run](findings/web-run.md) | area | 13 | 4 | 11 | 5 | 20 | 0 |
| [web-composer](findings/web-composer.md) | area | 10 | 3 | 8 | 8 | 19 | 0 |
| [web-build](findings/web-build.md) | area | 10 | 2 | 13 | 5 | 20 | 0 |
| [web-tools-approvals](findings/web-tools-approvals.md) | area | 5 | 2 | 6 | 10 | 18 | 1 |
| [web-system](findings/web-system.md) | area | 14 | 1 | 9 | 10 | 20 | 0 |
| [web-shell](findings/web-shell.md) | area | 56 | 2 | 11 | 8 | 21 | 0 |
| [py-domain](findings/py-domain.md) | area | 42 | 2 | 13 | 5 | 20 | 0 |
| [py-run](findings/py-run.md) | area | 13 | 5 | 12 | 5 | 22 | 0 |
| [py-tools](findings/py-tools.md) | area | 13 | 3 | 12 | 6 | 21 | 0 |
| [py-product](findings/py-product.md) | area | 11 | 3 | 13 | 5 | 21 | 0 |
| [py-adapters](findings/py-adapters.md) | area | 22 | 2 | 15 | 4 | 21 | 0 |
| [py-api](findings/py-api.md) | area | 21 | 3 | 11 | 7 | 21 | 0 |
| [py-ops](findings/py-ops.md) | area | 18 | 2 | 9 | 9 | 20 | 0 |
| [scripts](findings/scripts.md) | area | 30 | 4 | 8 | 9 | 21 | 0 |
| [db-tests](findings/db-tests.md) | area | 95 | 3 | 8 | 4 | 15 | 1 |
| [sql-infra](findings/sql-infra.md) | area | 64 | 2 | 12 | 6 | 20 | 0 |
| [web-tests](findings/web-tests.md) | area | 42 | 3 | 10 | 6 | 19 | 0 |
| [harness-tests](findings/harness-tests.md) | area | 20 | 2 | 12 | 5 | 19 | 0 |
| [py-tests](findings/py-tests.md) | area | 46 | 1 | 10 | 9 | 20 | 0 |
| [sweep-boundaries](findings/sweep-boundaries.md) | lens | - | 3 | 8 | 5 | 16 | 1 |
| [sweep-duplication](findings/sweep-duplication.md) | lens | - | 4 | 13 | 3 | 20 | 0 |
| [sweep-types](findings/sweep-types.md) | lens | - | 5 | 9 | 4 | 18 | 0 |
| [sweep-docs-naming](findings/sweep-docs-naming.md) | lens | - | 0 | 4 | 6 | 10 | 0 |
| [sweep-errors](findings/sweep-errors.md) | lens | - | 3 | 11 | 1 | 15 | 0 |
| [sweep-tooling](findings/sweep-tooling.md) | lens | - | 2 | 9 | 5 | 16 | 0 |
| [sweep-web-architecture](findings/sweep-web-architecture.md) | lens | - | 4 | 12 | 4 | 20 | 0 |
| **Total** | | **545** | **70** | **269** | **154** | **493** | **3** |

The three not kept: [TDBC-16](findings/db-tests.md#rejected-during-verification), because the fault checker's copy of the transition table matches the product's normal exits; [XMOD-14](findings/sweep-boundaries.md#rejected-during-verification), mostly taste and subsumed by [XMOD-01](findings/sweep-boundaries.md#xmod-01); and [WTAP-14](findings/web-tools-approvals.md#rejected-during-verification), merged into [WTAP-08](findings/web-tools-approvals.md#wtap-08).

By dimension, duplication is the most frequent, and types and errors hold the most high findings:

| Dimension | High | Medium | Low | Total |
|---|---:|---:|---:|---:|
| duplication | 9 | 55 | 28 | 92 |
| types | 13 | 39 | 11 | 63 |
| errors | 12 | 32 | 7 | 51 |
| approach | 8 | 27 | 14 | 49 |
| size | 8 | 26 | 8 | 42 |
| standards | 3 | 24 | 14 | 41 |
| tests | 5 | 27 | 8 | 40 |
| modules | 8 | 21 | 4 | 33 |
| naming | 0 | 2 | 25 | 27 |
| functions | 3 | 5 | 12 | 20 |
| comments | 0 | 3 | 15 | 18 |
| structure | 1 | 8 | 8 | 17 |
| **Total** | **70** | **269** | **154** | **493** |

## Documents in this folder

| Document | Contents |
|---|---|
| [standards.md](standards.md) | 51 proposed standards, STD-01 to STD-51, in 14 sections from repository structure to enforcement and ratchet. Each gives the rule, why it matters here, today's counts with finding IDs, the enforcing check and an adoption path: report, then baseline, then error. 27 are partly held by an existing check and 24 are proposed. A [target configuration](standards.md#target-configuration) closes the document. |
| [refactor-plan.md](refactor-plan.md) | 68 bounded items in four waves: 7 guardrails, 5 quick wins, 35 hotspot refactors and 21 structural moves. They address 479 of the 493 findings, including all 70 high ones; the other 14 are local fixes. It also lists the 12 owner decisions the items need, suggested backlog entries (the review edits no backlog) and ideas considered and not recommended. |
| [metrics.md](metrics.md) | Sizes, Python function and complexity measurements, ruff and ESLint rule counts, the latest verification reports, and the exact commands that produced them. |
| [findings/](findings/) | For each of the 19 areas and 7 lenses, `<part>.md` and `<part>.json`: summary, scores, strengths, verified findings, findings rejected during verification, and what was not covered. |
| [PROMPT.md](PROMPT.md) | A copy of the review prompt: dimensions, ground rules, rubrics and formats. |
| [workflow.js](workflow.js) | A copy of the workflow that ran the review. |

Raw tool output, the saved reviews and some reviewers' scratch output are in `.checks/reviews/review-2026-11-12-09-52-30/`, which Git ignores. They are not part of the versioned record.

## Coverage and limitations

- **Static evidence.** The review is static. Metrics come from installed tools, and findings come from reading code. Nothing here is runtime evidence, and it establishes no H1 and no product acceptance.
- **Verification reports.** The `scripts/verify.py` reports listed in [metrics.md](metrics.md#8-baseline-checks) were read, not rerun, and their revisions were not compared with this run's. The `fast` (2026-11-09) and `full` (2026-11-08) reports may predate HEAD. The `fast` report passed 11 of its 24 checks, the harness, Python and contract-drift checks, and lists the other 13 as `not_run`, "outside the changed scope of this fast run": every Node check, the build, and the fault, browser and toolchain tests. The check step read those statuses from the report; [metrics.md](metrics.md#8-baseline-checks) did not inspect them.
- **Carried parts.** web-run, web-composer, web-build, web-tools-approvals, py-domain, py-run, py-tools, py-product, sweep-boundaries, sweep-duplication, sweep-errors and sweep-tooling were verified by the first invocation and kept as written, so their coverage comes from their own notes. The new sweep-docs-naming reviewer found scratch output from the interrupted attempt, used it only for leads and recomputed every number. Every part has both findings files, and verification left no gaps. Each part's own limits are in the "Not covered" section of its findings file, for example [web-run](findings/web-run.md#not-covered).
- **What was read.** File coverage is self-reported: all 19 area reviewers reported reading every file in their scope (`coverage.txt` in the raw folder). Lenses covered most files through scans, so their counts can miss variants; the ten stale comments that sweep-docs-naming reports are a verified sample, not a census, and sweep-duplication's detector finds only exact repeats of eight lines or more. Files outside an area, `PRD-Development-Harness.md` (mostly DH-03 and DH-06) and `docs/engineering/option-b-contract.md` were read only in the parts a finding needed, or not at all. Where a reviewer did not open the product PRD behind a cited requirement (PRD-Studio for web-system and sweep-web-architecture, PRD-Model-Providers for py-ops, and the sources of py-api's cited IDs), those IDs were judged for clarity, not for conformance.
- **Commands not run.** No app, BFF, API, worker, database, Compose stack, browser suite or verification profile was started. Reviewers did not run mypy, pytest or tsc, which were not among their permitted commands, so type findings rest on reading code. The only mypy count is standards.md's strict check of six trust-boundary modules (56 errors); what a type gate over the rest of `scripts/` and `tests/` would report is unmeasured. Most web reviewers took ESLint counts from the measure step's run, which did not cover `apps/web/playwright.config.ts`. The other runs were small and changed no tracked file: ruff in check mode, ESLint with extra rules and on stdin probes, `tests/toolchain/test_manifests.py` (15 passed in 0.08 s), `tests/harness/test_shared_form_controls.py`, contract models validated in memory, an import of `create_app` with the service interpreter, and a timed `harness_lib.evidence_state` call.
- **Reproduced outside the product.** A few defects were reproduced with fakes or scratch scripts rather than in the running product: the tap failure in memory with a fake stream ([PADP-01](findings/py-adapters.md#padp-01)), the secret patterns compiled from source and run on synthetic tokens ([PRUN-05](findings/py-run.md#prun-05), [XDUP-01](findings/sweep-duplication.md#xdup-01)), the retention parser re-run in node ([WSYS-01](findings/web-system.md#wsys-01)), and the regex stall timed in a standalone script under Python 3.12.16, not inside the worker ([PTOL-01](findings/py-tools.md#ptol-01)).
- **Reasoned from code, not reproduced.** These come from reading code or documented framework behavior and were not observed. Where the plan fixes one, its failing test comes first and will be the first observation:
  - the run page's endless retry and polling, the lost-reply double charge and the snapshot race ([WRUN-02](findings/web-run.md#wrun-02), [WRUN-03](findings/web-run.md#wrun-03), [WRUN-04](findings/web-run.md#wrun-04));
  - duplicate submits, the held-key shortcut, a tab switch during an in-flight decision, and the stale search box after a sidebar link ([WCMP-01](findings/web-composer.md#wcmp-01), [WBLD-02](findings/web-build.md#wbld-02), [WTAP-02](findings/web-tools-approvals.md#wtap-02), [WTAP-04](findings/web-tools-approvals.md#wtap-04), [WTAP-15](findings/web-tools-approvals.md#wtap-15));
  - the waiting notifier that stops for good after a 401, the workflow monitor's polling load, secondary reads that fail silently, and an unhandled rejection after a malformed save reply ([WCMP-06](findings/web-composer.md#wcmp-06), [WBLD-08](findings/web-build.md#wbld-08), [WBLD-04](findings/web-build.md#wbld-04), [WSYS-02](findings/web-system.md#wsys-02));
  - the `parent_not_running` pause race, which a `blocker_check` case should confirm before any fix ([PPRD-03](findings/py-product.md#pprd-03));
  - endless reclaim of a failing run and the cancellation window in `browsing_tool.py` ([XERR-10](findings/sweep-errors.md#xerr-10), [XERR-13](findings/sweep-errors.md#xerr-13));
  - pool exhaustion and the per-request `ValueError` from a malformed `AUTOBOTS_MIN_FREE_BYTES` ([PAPI-11](findings/py-api.md#papi-11), [PAPI-10](findings/py-api.md#papi-10));
  - anon keeping EXECUTE on `can_access_artifact`, and the cost of the unindexed lookups ([SQLI-05](findings/sql-infra.md#sqli-05), [SQLI-08](findings/sql-infra.md#sqli-08));
  - DNS rebinding past the URL guard ([PADP-15](findings/py-adapters.md#padp-15));
  - the NaN-cursor reconnect loop, the receipt `KeyError` and the skipped route check ([XTYP-07](findings/sweep-types.md#xtyp-07), [XTYP-03](findings/sweep-types.md#xtyp-03));
  - the stale server-rendered approvals badge, and whether repeated server reads in one request are deduplicated ([XWEB-14](findings/sweep-web-architecture.md#xweb-14));
  - the depth-2 run-tree disagreement ([XDUP-05](findings/sweep-duplication.md#xdup-05));
  - order coupling between service test files, logging reconfigured without restore, and wall-clock timing in the service tests ([PTST-07](findings/py-tests.md#ptst-07), [PTST-18](findings/py-tests.md#ptst-18));
  - psql's handling of a doubled backslash before `n`, and the PostgREST status codes in the qualifiers' canary cases ([SCRP-09](findings/scripts.md#scrp-09));
  - web-shell's judgment that `..` segments in the BFF's catch-all route expose nothing the route does not already forward, because every API router sits under `/v1` with docs and OpenAPI disabled; how Next.js 16 passes such segments into catch-all params was not exercised;
  - the claim that an unread refusal holds its connection open, which comes from the project's own comment ([run-disclosure.tsx:53](../../../apps/web/components/run-disclosure.tsx#L53)), not from a measurement.
- **Not reviewed.**
  - Requirement conformance. One reviewer noted in passing that TS-01 lists side effects for each tool row while `side_effects` is rendered nowhere in `apps/web`; acceptance owners may want to check.
  - Contrast, focus and both themes (DS-04, DS-05), which need rendered checks. Accessibility was judged from markup, not with axe or a screen reader.
  - Error handling inside SQL functions, in the Makefile and in shell, the exit-code semantics of each `tests/db` script beyond its broad handlers, and the behavior of Server Components that throw (no `error.tsx` or `loading.tsx` exists, so Next.js defaults apply).
  - Test coverage as a measurement. None was available, so coverage of risky logic was judged by reading tests. py-product did not read `search.spec.ts` or `workflow-list.spec.ts`, so whether they cover `expert_chain`, `preview_steps` or search escaping is unconfirmed ([PPRD-16](findings/py-product.md#pprd-16)).
  - Whether workflow node progress emits run events, which decides whether the workflow monitor could follow the run event stream instead of polling ([WBLD-08](findings/web-build.md#wbld-08)). The plan keeps polling and adds backoff ([R-27](refactor-plan.md#r-27)).
  - Whether Pydantic class docstrings on tool inputs reach the model's tool schemas. `adapters/tool_middleware.py` passes an explicit description, which normally replaces them, but the comments and naming lens ran no code to confirm it.
  - Query costs, per-test durations, and whether each bad fault fixture still fails for its stated reason. The roughly 50 seconds of fixed sleeps in the browser suites is summed from source.
  - `tests/qualification/tasks.json`, `tests/qualification/dev_tasks.json` and the fault expectation JSON files, which fall outside the listed scope.
  - SQL, YAML, Dockerfiles and the Makefile, which have no static tooling. No SQL linter was evaluated, because adopting one needs a new dependency and a decision.
- **An open question for module moves.** The boundaries lens did not check whether a LangGraph checkpoint stores classes by import path, and no other part reports checking it. The plan's module moves, for example [R-33](refactor-plan.md#r-33), [R-42](refactor-plan.md#r-42), [R-53](refactor-plan.md#r-53) and [R-64](refactor-plan.md#r-64), do not address it, so check it before moving a module that checkpointed state may reference.
- **An open question for retention.** `purge_run_content`, last defined in migration 027, deletes a run's checkpoints, files, offloads and summaries and expires its artifacts. Run-scoped tables added later, `improvement_replay_runs` (037), `tool_uses` (038) and `plan_task_times` (048), are outside it. The duplication lens left whether they belong in the purge to py-ops and sql-infra as a retention-policy question; no part reports on it, and neither the plan nor the standards take it up. It is the owner's decision, and any change would be a forward migration.
- **Measurement caveats** (see [metrics.md](metrics.md#10-limitations)). Line counts are approximate: ESLint function lengths skip blank and comment lines while the Python counts include them, and nested Python functions count twice in area totals. ruff `ALL` is an exploratory superset, the repository-level ruff settings were chosen for measurement rather than taken from a project configuration, and the extra ESLint rules were passed ad hoc on the command line. Several pattern counts come from grep or `ast` patterns and can miss differently named variables. The lenses' scans have limits of their own: the boundaries lens's import graph is static, so it misses `importlib` and other dynamic imports, and its TypeScript graph covers only `apps/web` app, components and lib; the tooling lens simulated Playwright's filter matching with Python regular expressions ([XTOL-02](findings/sweep-tooling.md#xtol-02)), resolved imports with a stdlib resolver written for the review ([XTOL-03](findings/sweep-tooling.md#xtol-03)), passed `projectService` to ESLint on the command line for its type-aware counts, and measured format churn on a scratch copy outside the repository ([XTOL-04](findings/sweep-tooling.md#xtol-04)); and the types lens grouped the 398 `ANN401` hits by parameter name and sampled them rather than opening each ([XTYP-04](findings/sweep-types.md#xtyp-04)). The measure step reported no problems; one supporting `cat -A` command failed on macOS without effect.
- **Scores.** No part scored `duplication` or `naming`, and lenses scored only the dimensions they judged.
- **Ground-rule notes.** The project hook refused one read-only search in py-tools and one in sweep-boundaries, because the pattern named the provider master-key file. Both were rerun on a constant name; as a result, py-tools did not compare the default key-file path in `tool_keys.py` with other modules. A few runs wrote outside the two output folders, all to ignored or temporary locations: one ruff run without `--no-cache` refreshed the ignored `services/agent/.ruff_cache` (py-adapters), one import may have refreshed ignored `__pycache__` files (sweep-types), and scratch scripts and configurations lived in session scratch folders outside the repository (py-tools, scripts and the standards writer). Some reviewers also ran project code, which goes beyond the read-only commands the workflow lists for reviewers: in-memory checks with the service's interpreter (py-domain, py-adapters, py-api and sweep-types), a timed `harness_lib.evidence_state` call (scripts), and two test modules (web-system and harness-tests). None started a service or touched a database or a model. When this README was written, `git status` listed only the two untracked paths present at the start.
- **Findings without a plan item.** All 70 high findings map to plan items, and none is deferred. Fourteen findings, 1 medium and 13 low, have no item; the plan lists them as local fixes for when their files are next touched ([Medium and low findings without an item](refactor-plan.md#medium-and-low-findings-without-an-item)).
- **Link check.** Every link, anchor, linked line number and finding ID in this folder resolves. When this review ran, the workflow's link and ID checker reported four problems, and all four were false positives. Three were in [PROMPT.md](PROMPT.md), a verbatim copy whose links resolve from `docs/reviews/`; two of those are examples in its "Finding format" code block. The fourth was a Python call in the sketch of [PDOM-10](findings/py-domain.md#pdom-10) that has the shape of a Markdown link. After the run, the checker was changed to skip code and to resolve the copied prompt's links from `docs/reviews/`. It now reports no problems in this folder.

## Changes since the previous review

This is the first review. No earlier `docs/reviews/review-*/findings/*.json` exists, so there are no resolved or persisting findings to report, and all 493 findings are new. The next run should compare with this folder's [findings](findings/) by area, title and file, because finding IDs are numbered within each run.

## How to rerun

- **With the workflow (recommended).** Ask Claude Code to "run the code-quality-review workflow". A session started before the workflow file existed does not list it by name, so ask for it by path: `.claude/workflows/code-quality-review.js`. It writes a new `docs/reviews/review-<timestamp>/` and stops if that folder already holds files. A full run starts about 45 agents and takes one to two hours. Optional arguments:
  - `{"timestamp": "yyyy-mm-dd-hh-mm-ss"}` names the run; the default is the current time.
  - `{"timestamp": "<the stopped run's timestamp>", "resume": true}` continues a stopped run from disk. It keeps each part whose findings files exist, verifies the reviews saved under `.checks/reviews/review-<timestamp>/reviews/`, and reviews only what is missing.
  - `"notes": ["..."]` adds lines to the run facts that the README reports.
- **Do not resume by run ID.** The run cache replays agent calls in order, and parallel agents finish in a different order each time, so it redoes finished work. This run's second invocation did exactly that.
- **In one session.** Paste [PROMPT.md](PROMPT.md) from "Goal" down. One context cannot read the whole repository closely, so expect less depth per area.
- **To change the review,** edit the rules, rubrics and formats in [docs/reviews/PROMPT.md](../PROMPT.md), and the areas, lenses and agent counts in `.claude/workflows/code-quality-review.js`. The copies in this folder, [PROMPT.md](PROMPT.md) and [workflow.js](workflow.js), are the versions that finished this run. Both files were last changed at about 12:06, after the first invocation started at 09:52, so the earlier invocations may have run an earlier version of them.
