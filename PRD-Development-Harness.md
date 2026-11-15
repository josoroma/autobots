# PRD — Option B development harness and engineering standards

**Decision date:** 2026-11-04. **Status:** Requirements finalized, and the harness, application tooling and database fixtures are implemented. [US-11.12's Gate 0](docs/engineering/evidence/US-11.12/summary.md) records what they show. Actual Claude event delivery stays unqualified, and US-10.2 assesses H1. See [current codebase](CODEBASE.md) and [adaptation evidence](docs/engineering/evidence/HARNESS-ADAPT-001/summary.md).

This is **Gate 0**, the first work for [Option B: Next.js + LangGraph/Deep Agents](PRD-LangChain-Deep-Agents.md). [SPECS.md](SPECS.md) supplies the ordered implementation work items and their stable IDs. Complete H0 and H1 below before feature implementation, product migrations or production worker logic. Minimal scaffolding and disposable fixtures needed to qualify the harness are allowed during these stages. The [deployment contract](PRD-Local-Mac-Deployment.md) and [provider contract](PRD-Model-Providers.md) remain authoritative.

## DH-01. Outcome and boundaries

Make coding standards executable and consistent across the Next.js interface, Python API/worker, local Supabase and Docker configuration. A contributor should discover the architecture, make a bounded change, run the relevant checks and obtain reproducible evidence without relying on a particular assistant's memory.

Provide repository-owned `.claude` configuration with skills, specialist agents, rules and command hooks, backed by a **mandatory portable verification runner**. Runtime activation of the Claude adapter is optional and requires actual compatibility evidence; an unavailable adapter cannot disable the runner. Instructions explain intent; tools check properties that can be measured; review addresses behavior and tradeoffs. Neither a prompt nor a successful lint run proves correctness.

Every implementation work item follows a proportional **plan → implement → independent review → verify → exercised runbook** record. The record connects the requested behavior to changed code and observed results. It applies to the harness itself as well as later features. One concise record and an existing runbook update can be sufficient; this is an evidence requirement, not a new permission or approval ceremony.

These are **development assistants**, distinct from the application's 14 inference roles and end-user skills. Application execution stays local; application inference stays exclusively on OpenRouter with the approved DeepSeek default and selectable Terra. This milestone adds no model provider, Anthropic SDK, local model server, model-based hook, hosted reviewer or remote CI dependency. It does not assume the two application model IDs work in Claude Code. Any assistant adapter must respect the existing OpenRouter-only constraint; use the portable harness if a compatible assistant route is unavailable.

All required quality checks run locally without inference credentials or paid requests. Downloading pinned development dependencies is a bootstrap operation, not a hidden action in an edit hook. Optional assistant reviews cannot replace deterministic gates or silently authorize another service.

## DH-02. First implementation tasks

The user explicitly selected an adapted [OhMyOrch spec-ingestor workflow](docs/engineering/decisions/0001-ohmyorch-adaptation.md). The local implementation uses `.claude/autobots.json`, a read-only ingestor plus writing skill, source-traceable EPIC/US stories, Gherkin acceptance and generated backlog navigation. `scripts/specs.py` and the implemented `harness` verification profile cover that bounded foundation; they do not satisfy the pending language/database/product gates. [Provenance and adaptations](docs/engineering/ohmyorch-adaptation.md)

| Order | Required task | Concrete exit evidence |
|---|---|---|
| H0.1 | Inspect repository state and local tool availability; preserve existing work; establish version control and ignores if absent; open the first work-item plan | Inventory plus stable SPECS/requirement IDs, acceptance criteria, scope and verification/runbook plan; no secret values |
| H0.2 | Add shared instructions, `.claude` rules/skills/agents/settings, engineering decision records and evidence templates | Files validate against documented syntax; rules link to checks/review responsibilities; DH-W01–06 record contracts exist and templates are visibly unexecuted |
| H0.3 | Establish pinned Node/pnpm and Python 3.12/uv toolchains, manifests, compatible lockfiles and minimal non-feature scaffolding | Reproducible install; no blanket dependency upgrades; Python/OpenRouter constraints from the implementation PRD preserved |
| H0.4 | Implement the portable runner, deterministic hook adapter, fixtures and evidence/manifest validation | Direct runner works with Claude unavailable; stale hashes, missing review/runbook evidence, skipped prerequisites and failures are distinct |
| H1.1 | Activate the portable baseline and prove it catches deliberate faults; qualify a Claude adapter only when compatible | Known-good fixtures pass; known-bad lint/type/contract/hook fixtures fail; optional assistant delivery recorded separately; no paid calls |
| H1.2 | Qualify disposable database/Compose checks and guarded migration/seed wrappers | Test target isolated from persistent data; replay, seed repeatability and negative authorization fixtures pass |
| H1.3 | Independently review the harness, exercise its runbook and publish the redacted baseline evidence | DH-A01–16 pass for the portable baseline, with DH-A03 stated as partial where [Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md) applies; DH-W01–06 records are complete, and for H0 and H1 stories delivered under Decision 0003 the record of the final review and Gate 0 carries the baseline, by [Decision 0013](docs/engineering/decisions/0013-release-closure.md); an unqualified Claude integration is either explicitly inactive, or in use as a guardrail and reported as configured and not qualified, never as enabled or qualified ([Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md)) |
| Next | Start Option B's local foundation, then its durable vertical slice | Each SPECS work item uses DH-W01–06; add actual feature-specific evidence as functionality arrives |

H1 may use a disposable minimal web/API shell, stub worker and synthetic SQL migration. It does not require a completed product or real model execution. Separate **configuration validation**, **script behavior** and **actual assistant event delivery** in evidence. Synthetic hook stdin alone cannot prove Claude loaded the project settings. A missing optional Claude adapter must not block use of the tested portable runner; a missing required check does block Gate 0.

## DH-03. Required repository structure

The following paths are implementation deliverables, not files claimed to exist today:

```text
AGENTS.md                              shared engineering instructions
CLAUDE.md                              short entry point importing @AGENTS.md
.claude/
  settings.json                        versioned project configuration
  rules/                               concise, path-scoped standards
  skills/<name>/SKILL.md                focused engineering workflows
  agents/<name>.md                      development specialist definitions
  hooks/dispatch.py                    deterministic event-to-check adapter
docs/engineering/                      architecture, conventions and ADRs
docs/engineering/work-items/<id>.md     concise plan, implementation and review record
docs/engineering/runbooks/<id>.md       reproducible operating/verification procedures
docs/engineering/evidence/<id>/        versioned redacted manifests and summary.md
scripts/verify.py                       portable local verification entry point
scripts/app_db.py, disposable_db.py     target-checked migration/seed operations
tests/harness/                         accepted/rejected inputs and failure fixtures
tests/{db,web,faults,qualification,toolchain}/  disposable-database, browser, fault, qualifier and toolchain checks
apps/web/                              Next.js UI and BFF
services/agent/
  pyproject.toml
  uv.lock
  src/autobots/{api,domain,application,adapters,contracts,persistence,operations}/
  tests/
packages/api-client/                   generated TypeScript API boundary
packages/db-types/                     generated public-schema types, a drift-checked exposure artifact
contracts/generated/                  versioned OpenAPI/JSON Schema artifacts
supabase/migrations/                   application SQL migration source of truth
supabase/seeds/                        bootstrap and disposable fixtures separated
infra/supabase/                        reviewed upstream Compose plus local overlay
.checks/<work-id>/<evidence-id>/        ignored bulky redacted logs/artifacts; declared retention
```

The service's packages follow its layout ([Decision 0029 F6](docs/engineering/decisions/0029-refactor-decisions-delegated-r41-r68.md)). `operations/` holds the process entry points, which are the worker (`python -m autobots.operations.worker`), the operator commands and paid qualification, and the process configuration they share, which the API's entry, `api/main.py`, also builds from. `logs.py` sits beside the packages, a leaf every layer may import. LangGraph and Deep Agents wiring lives in the goal-loop modules under `application/`. The database tools are `scripts/app_db.py` and `scripts/disposable_db.py`, each refusing any target it can't verify. `packages/db-types/` exposes the columns signed-in users may select, and `scripts/app_db.py` fails when it drifts from the migrations.

Keep persistent volumes, `.env` files, credentials and the provider master key outside agent-editable workspaces or explicitly protected as specified in the deployment contract. Ignore `.claude/settings.local.json`, local transcripts, bulky `.checks` outputs, caches and disposable data. Version reusable policy, hooks and redacted evidence summaries/manifests, not machine credentials, user data or preferences. Official Claude configuration distinguishes shared project settings from personal overrides; inspect effective settings rather than assuming a repository file overrides all other scopes. [Settings scopes](https://code.claude.com/docs/en/settings)

Use `AGENTS.md` for common principles, commands and domain boundaries; keep `CLAUDE.md` short. Path-specific `.claude/rules/*.md` cover web, Python, database, infrastructure and contracts. Use supported `paths` frontmatter for scoping and test representative paths; do not invent schema keys. Avoid maintaining contradictory copies of the same rule. [Project instructions and rules](https://code.claude.com/docs/en/memory)

## DH-04. Skills and specialist agents

Author small project skills instead of installing an unreviewed collection. Each skill defines its trigger, relevant paths, prerequisites, workflow, expected evidence and failure behavior. It links to detailed standards without loading the whole repository. Use `.claude/skills/<name>/SKILL.md`; validate frontmatter against the qualified CLI. Skills applying persistent operational changes must be explicitly invoked, using supported `disable-model-invocation: true`, and call guarded scripts. Ordinary implementation, review and disposable verification skills do not require a new user confirmation when their work is already authorized. A skill's `allowed-tools` grants preapproval; it is not a tool sandbox. [Skill configuration](https://code.claude.com/docs/en/skills)

| Required skill | Responsibilities and expected result |
|---|---|
| `autobots-plan-change` | Map requirement to layers, contracts, affected states, migration impact and smallest useful verification plan |
| `autobots-implement-item` | Execute the authorized task scope from its plan; record changed paths, behavior, contracts/migrations and deviations against stable requirement IDs |
| `autobots-nextjs` | App Router boundaries, Auth/BFF, generated clients, forms, accessibility, loading/error states and browser tests |
| `autobots-python` | Typed domain/application code, async resource ownership, validated input/output, error taxonomy and focused tests |
| `autobots-durable-worker` | Graph reducers, leases/fencing, outbox, cancellation, recovery and operation receipts |
| `autobots-contracts` | Pydantic/OpenAPI generation, TypeScript client regeneration, schema/event compatibility and drift checks |
| `autobots-supabase` | Author/review migrations, RLS/grants, deterministic seeds, isolated replay and type generation; operational apply remains explicit |
| `autobots-docker-local` | Inspect rendered configuration safely, local ports, ARM64 images, health, resource limits, volumes and restore evidence |
| `autobots-model-gateway` | OpenRouter allowlist, role bindings, credentials, budgets, structured results and mocked transport tests |
| `autobots-verify-change` | Run appropriate verification profiles, inspect evidence and report unresolved checks accurately |
| `autobots-review-change` | Independently inspect the diff, requirements and current evidence; record actionable findings and verify their resolution without silently editing the author's implementation |
| `autobots-runbook-evidence` | Exercise the relevant local procedure on the declared target; record real commands, expected/observed behavior, recovery/cleanup and durable evidence links |

Provide development agents for architecture/contracts, Next.js, Python/workers, database/RLS, local infrastructure, and independent review. Store each at `.claude/agents/<name>.md`. Assign explicit scope, permitted tools, inputs and a concise result contract: findings with paths, invariants checked, evidence, remaining uncertainty. Reviewer agents have no mutation tools; an agent that runs tests is not automatically read-only just because its description says so. Use supported agent `tools`/`disallowedTools` controls and qualified permissions. [Subagent configuration](https://code.claude.com/docs/en/sub-agents)

The coordinator delegates only useful independent work, gives each writer file ownership and resolves cross-layer changes. Do not launch every specialist for every edit. Avoid concurrent migration numbering or contract generation. The independent review can be a separate qualified reviewer context or a human reviewer; it is not an extra user-permission step. No new paid assistant service is implicitly authorized. No agent may approve its own failed gate by changing thresholds, deleting tests or declaring an unsupported capability passed. Fix policy defects explicitly with a documented rationale and independent review of consequential changes.

## DH-05. Hooks and portable enforcement

Use local **command hooks** only. Initial proposed event responsibilities:

| Event | Project behavior |
|---|---|
| `SessionStart` | Print a brief version/readiness summary and standards entry point; do not install dependencies, read secrets or run paid probes |
| `PreToolUse` | Check protected paths and known dangerous operational targets before supported edit/command tools; no broad auto-approval |
| `PostToolUse` | Mark affected check domains dirty and run bounded check-only diagnostics for relevant completed edits |
| `Stop` | Inspect fresh evidence for the changed scope; request repair for missing/failed checks without an endless completion loop |
| `SubagentStop` | Require concise findings/evidence for specialist work; final integration still runs the portable verifier |

Hooks attach automation to assistant lifecycle events; the event adapter is thin and all substantive checks live in repository scripts. No automatic formatter rewrites, dependency installs, database mutation or infrastructure startup on ordinary edits. Explicit fix commands remain available. [Hook lifecycle guide](https://code.claude.com/docs/en/hooks-guide)

The qualified Claude version must support the chosen settings. Current docs require **v2.1.295+** for command-hook `onFailure: "block"`. Apply it to blocking pre-tool checks; a crash or timeout must not silently authorize the action. That field does not protect `Stop`/`SubagentStop` or asynchronous hooks. Use event-specific output, and guard repeated Stop processing with `stop_hook_active`. Completion evidence remains independently required. [Hook failure semantics](https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails)

Implementation requirements for our dispatcher:

- Parse bounded JSON input, validate event/tool names and canonicalize paths. Treat tool input and filenames as data; use subprocess argument arrays, never interpolate them into shell code.
- Keep stdout reserved for the documented hook response; send redacted diagnostics separately. Test malformed JSON, Unicode/spaces, symlinks, shell metacharacters, timeout, missing executable and unsupported event cases.
- Separate deny, diagnostic failure and unsupported integration. Return each event's documented blocking signal; do not assume conventional exit code 1 blocks a tool.
- Use deadlines, a per-worktree check lock and bounded output. Invalidate evidence after changes to code, configuration, locks, generated contracts or the checks themselves.
- Do not claim a command-name regex prevents arbitrary shell execution or provides a security sandbox. Protect secrets/data with actual filesystem, process, database and container boundaries.
- Never silently change global assistant settings, managed policy or unrelated projects. No universal permission bypass and no blanket Bash allowlist.

The required standalone interface is `python3 scripts/verify.py --profile <profile>`. It uses the qualified local toolchain and returns nonzero for required failures or unavailable prerequisites. Define `harness`, `fast`, `full`, `db` and `operations` profiles. The last two operate only on explicit qualified test targets unless an operator explicitly runs a separate persistent-operation command. Git hooks may call the same runner after repository initialization, but bypassable Git/assistant hooks are not the only completion check.

Results use DH-W04's evidence contract: scope, input hashes, tool/config versions, redacted check commands, expected/observed behavior, assertions, status and duration. Cache only against the complete relevant input fingerprint, including untracked source files. A clean Git diff or old report is not proof. Full verification reruns required checks; skipped checks never count as green. Retain reviewed redacted manifests/summaries under `docs/engineering/evidence/`; raw logs remain local under the declared retention policy. No external log sink is required.

## DH-06. Coding and layer standards

Use explicit ownership, narrow interfaces, readable names and small cohesive modules. Keep domain decisions independent of HTTP, Supabase clients and LangGraph internals. Validate data at trust boundaries, centralize error handling, preserve causes in private logs and expose safe typed errors. Avoid speculative frameworks, broad `any`/untyped dictionaries, swallowed exceptions and duplicated business rules. Explain nonobvious invariants in code; avoid comments that restate syntax.

### Next.js and TypeScript

Use strict TypeScript with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`, scoped and documented exceptions only. Prefer Server Components; use Client Components for actual interaction. Keep credentials/provider factories server-only. Authenticate and authorize each BFF mutation/read independently of navigation guards. Prevent workspace data from leaking through shared caches, serialized props, errors or bundles.

Use generated API types, explicit response parsing at untrusted boundaries and accessible forms. Represent loading, empty, denied, unavailable and retryable states deliberately. Disable duplicate submits with server idempotency as the correctness mechanism. Browser state is a view of durable state, not a second scheduler. No blanket type assertions to conceal contract mismatches.

Frontend skills, planning/review checklists and implementation must enforce [PRD-Design-System.md](PRD-Design-System.md) DS-01–DS-05: shadcn components, the exact [Luma tokens](docs/design/luma.css), dark on first visit independently of OS preference, and an explicit light/dark preference applied before paint. Use shared semantic tokens across the shell, forms, overlays, state indicators and workflow UI; do not reintroduce the superseded warm-neutral/forest-green palette or invent per-screen theme overrides. Keep theme preference separate from credentials and durable agent state.

Adopt compatible pinned ESLint with Next.js/React/TypeScript rules and Prettier for supported text formats. Run lint explicitly: Next.js 16 removed `next lint`, and `next build` no longer runs lint. Generate route types before standalone `tsc --noEmit`; do not set `ignoreBuildErrors`. [Next.js 16 migration](https://nextjs.org/docs/app/guides/upgrading/version-16), [route-aware types](https://nextjs.org/docs/app/api-reference/config/typescript)

Use Vitest/React Testing Library for relevant pure/client behavior and Playwright for key browser flows, especially Auth, server-rendered interactions, credential setup and reconnects. Include keyboard operation and accessible labels. Validate the production build in full checks; development rendering alone is insufficient. [Next.js Playwright guidance](https://nextjs.org/docs/app/guides/testing/playwright)

When the web tooling is implemented, browser evidence must cover fresh-visit dark rendering under both OS preferences, persisted explicit light/dark after navigation/reload, first-paint/hydration behavior, token use and accessible states in both modes. Capture representative implemented-screen screenshots with source/config fingerprints. Generated concepts are design references, not passing browser or accessibility results; documentation-only theme changes do not claim these pending product gates have run.

### Python API, domain and workers

Use the selected Python 3.12 baseline, a `src` package, `pyproject.toml` and committed `uv.lock`. Qualify the combined LangGraph/Deep Agents/OpenRouter/Pydantic dependency set before freezing it. Use `uv sync --locked` for an explicit install; verification uses the locked prepared environment and must not silently update it. [uv locking semantics](https://docs.terral.sh/uv/concepts/projects/sync/)

Check lock freshness explicitly and run checks with environment synchronization disabled after bootstrap. Generate OpenAPI through a pure application factory: import-time schema generation must not open database pools, require model keys or contact OpenRouter. Initialize and release resources in the API lifespan so contract checks work before services start. [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)

Use Ruff for lint/format, mypy strict for owned modules, and pytest with qualified async support. Keep third-party typing exceptions narrow and documented. Pydantic models define external contracts; choose explicit coercion/strictness per field. Use timezone-aware UTC dates, exact decimal or integer monetary units, explicit enums/unions and validated identifiers. Do not use float arithmetic for money or encode distinct states as ambiguous nullable fields.

Own DB pools/HTTP clients in process lifecycles; close them on shutdown. Bound timeouts, retries and concurrency. Keep blocking work off the async event loop. Propagate cancellation after cleanup; do not catch and discard it. Tests use controlled clocks and injected transports rather than real time or paid model calls. Ruff check and formatting are separate gates; safe autofix is an explicit operation. [Ruff linter](https://docs.terral.sh/ruff/linter/)

### Models, contracts and state

Distinguish domain entities, persistence rows, public DTOs, graph checkpoint state and UI view models. Pydantic-generated OpenAPI/JSON Schema is the public API source; generate the TypeScript client instead of hand-maintaining duplicate API interfaces. SQL migrations own database schema, with generated Supabase types limited to intended exposed schemas. Shared fixtures test validation semantics in both languages; compile-time types alone do not validate JSON.

Version event envelopes, workflow IR, checkpoint-compatible state and role-policy snapshots. Generate to a temporary directory and compare normalized artifacts to detect drift. Define compatibility/migration behavior for renamed/removed fields and unknown enum values. Keep secrets and provider clients out of DTOs/checkpoints; persist references only.

Implement a documented transition table with permitted source/target states, actors, guards, writes, events, retry/cancellation semantics and terminal-state rules, using the states in the Option B PRD. Use optimistic versions/fencing for concurrent mutations. Test invalid transitions, repeated commands and event ordering; do not invent a second state enum for the UI. Preserve distinct run, step, tool-attempt, approval and credential states.

For LangGraph, define typed state and reducers deliberately, including concurrent updates and replace-versus-append behavior. Keep routing ownership unambiguous: mixing static edges with `Command` routing can execute both destinations. Never forward raw graph value streams to the browser: private state channels are not automatically hidden from streaming. Map to a sanitized public event projection and test for leakage. [Graph routing](https://docs.langchain.com/oss/python/langgraph/graph-api#command), [private channels and streaming](https://docs.langchain.com/oss/python/langgraph/graph-api-state#private-channels-and-streaming)

### Durable workers and model gateway

Keep HTTP admission separate from durable execution. Test transactional enqueue/outbox, lease expiry, monotonic fencing, heartbeat loss, duplicate delivery, cancellation and graceful shutdown. Use database time for ownership decisions. Replay must preserve operation receipts and reconcile ambiguous external effects; a checkpoint does not make arbitrary side effects exactly once. Include restart fixtures with previously pending approvals and unknown model responses.

All 14 model roles use the one OpenRouter factory. Test catalog mapping, unsupported parameters, credentials missing/invalid/rotated, immutable bindings, budget reservations, incomplete streams and tool argument validation using a fake transport. Default tests must reject external inference even if the developer shell contains a real key. No direct SDK default, embedding call, reviewer, summary or background task may bypass this contract. Real model qualification is a separate explicitly initiated acceptance task with its own limits.

## DH-07. Supabase migrations, seeds and database quality

Use `supabase/migrations/<timestamp>_<description>.sql` as the single application schema history. Do not introduce competing Alembic or ORM migrations for the same objects. Apply each released migration once with recorded history; never edit an applied migration. Use reviewed follow-up migrations and expand/migrate/contract changes for data-bearing tables. Document transaction boundaries, locks, timeouts, indexes, backfills and forward recovery. Framework-managed checkpoint/store upgrades remain vendor-owned but versioned and coordinated in the same deployment sequence.

The persistent self-hosted Compose database is not a linked cloud project or automatically CLI-managed. Supabase CLI supports `db push --db-url` and `--dry-run`; qualify the pinned CLI's migration history and explicit target handling against our direct local connection before using a wrapper. Never require cloud login or linking. Dry-run lists pending work; it does not prove SQL correctness or restoreability. [Supabase CLI](https://supabase.com/docs/reference/cli/supabase-db-push)

Migration wrappers verify instance identity, database name, direct port, expected schema baseline and target class. Use a dedicated migration role; runtime roles cannot perform arbitrary DDL. Redact credentials and connection strings. Reset/clean commands require a disposable-target marker and reject the persistent instance, even when environment variables point to it. Neither hooks nor ordinary verification apply persistent migrations, reset data, remove volumes or invoke prune.

Separate three seed responsibilities:

| Seed class | Rule |
|---|---|
| Required reference/bootstrap data | Deterministic identifiers and upserts; repeatable without overwriting user edits; explicit version policy |
| Test/demo fixtures | Synthetic bounded data in disposable environments only, with fixed clock/IDs and explicit fixture ownership |
| Owner credentials and secrets | Separate secure bootstrap through supported Auth APIs; no committed passwords, real tokens, direct writes to Auth internals or model calls |

The CLI runs configured seeds during its local start/reset lifecycle; Compose does not automatically execute our repository's seed files. Provide explicit ordered seed wrappers after migrations. Test two executions for stable rows and relationships. Keep DDL in migrations, not seeds; do not seed demo tasks into the persistent workbench by default. [Supabase seeding](https://supabase.com/docs/guides/local-development/seeding-your-database)

Database acceptance includes clean replay and upgrade from a supported prior fixture, constraints/foreign keys, least-privilege grants, RLS isolation, anonymous/other-workspace denial, private-schema exclusion, Storage authorization and seed idempotency. Use two fixture users/workspaces and actual authenticated roles; a service-role success cannot prove RLS. Verify generated public DB types after migrations. Use the same pinned Compose family for integration coverage; a CLI-only test cannot establish production-stack compatibility.

## DH-08. Docker and local operations standards

Preserve the deployment PRD's native Mac UI/API/workers and Docker-hosted Supabase topology. Do not add containers for every service merely to use Docker. Use reviewed image versions/digests, Apple Silicon qualification and deliberate upgrades. For application/tool images where needed, use small maintained bases, multi-stage builds, `.dockerignore`, non-root execution and no copied credentials or Docker socket. [Docker build guidance](https://docs.docker.com/build/building/best-practices/)

Validate rendered Compose configuration without logging expanded secret values. Check loopback publications, direct DB versus pooler routing, authenticated Studio, disabled Studio AI, resource limits, health checks and persistent mounts. Distinguish liveness from dependency readiness. Test ordinary stop/start and restart without volume deletion. Tool containers have bounded workspaces, time/resources and network policy; they do not inherit host model keys.

Use distinct project names, ports and volumes for disposable tests. Test cleanup proves ownership before removing anything. Backup tests restore database plus Storage bytes and the separate key into an isolated instance, then verify actual records/hashes. Destructive lifecycle operations never run from generic format/lint/check hooks. Migration readiness, schema version, queue lag and structured redacted logs are part of operations evidence, not additional hosted services.

## DH-09. Verification profiles and completion rules

| Profile | Required scope |
|---|---|
| `harness` | Configuration/frontmatter validation; hook input/output/error fixtures; command/path safety; stale-report detection; known-good and known-bad checker fixtures |
| `fast` | Changed-scope lint/format checks, strict types and focused behavior tests; contract generation/drift when relevant; no services or network inference |
| `full` | Complete web/Python static checks, meaningful unit/contract tests, production web build, deterministic model/worker tests and configured browser fixtures |
| `db` | Qualified disposable Supabase target; migration replay/upgrade, repeatable seeds, RLS/Storage tests and generated type drift |
| `operations` | Disposable Compose validation, health, restart/recovery, backup/restore and resource checks with explicit target identity |

Package scripts implement pinned commands such as `eslint`, `prettier --check`, `next typegen`, `tsc --noEmit`, `next build`, `ruff check`, `ruff format --check`, `mypy` and `pytest`; the runner orchestrates them with repository-specific paths. Do not label this list executable until manifests, versions and actual scripts exist. Missing test tools fail prerequisites rather than falling through to download-at-runtime launchers.

Tests should prove behavior, boundary conditions and failure handling. Avoid tests that merely restate implementation or inflate coverage. Documentation-only changes need documentation checks; schema, authorization and worker changes need the corresponding integration gates. Change-impact classification determines required profiles, with a conservative full run for shared contracts or check infrastructure. Record exact requirements tested and material gaps; no passing badge for an empty suite.

Completion requires a reviewed diff, current evidence for required profiles and truthful remaining limitations. Keep decisions and exceptions in concise ADRs with scope, rationale and a regression check. Do not turn stylistic preferences into speculative frameworks, arbitrary coverage quotas or mandatory assistant approval ceremonies.

### DH-09.1. Work-item evidence contract

These stable requirement IDs apply to each implementation work item in SPECS, including H0/H1. They describe deliverables to create during implementation; this PRD update is not itself evidence that the harness exists.

| ID | Required contract |
|---|---|
| **DH-W01 — Plan and traceability** | Before editing implementation, open `docs/engineering/work-items/<work-item-id>.md`. Cite its stable SPECS ID and applicable PRD requirement/acceptance IDs. Record intended behavior, scope, key invariants, affected layers/contracts/states, migration/operational impact and the smallest sufficient verification/runbook plan. Keep it proportional; a small fix may need only a few bullets. |
| **DH-W02 — Implementation record** | Update the same record with changed paths, actual resulting behavior, contract/migration/configuration changes and material deviations from the plan. Link the diff/revision and relevant implementation symbols. Distinguish implemented paths, stubs and deferred work; code presence alone does not establish working behavior. |
| **DH-W03 — Independent review** | A reviewer other than the implementation author, or a separate qualified reviewer context, inspects the current diff, requirements and evidence. Record reviewer identity, reviewed fingerprint, findings and dispositions. The author cannot replace this with a self-asserted review. A review that changes code becomes authorship for those changes and needs another review of the affected scope. Routine review is an engineering check, not a request for additional user permission. Routine delivery through `/ohmyorch:deliver` follows Decision 0003, with one independent review of the final code before a release ([Decision 0009](docs/engineering/decisions/0009-release-scope-from-blocking-findings.md)). |
| **DH-W04 — Verification evidence** | Produce a versioned redacted manifest and `summary.md` under `docs/engineering/evidence/<work-item-id>/`. Map each assertion to requirement IDs, expected behavior, observed result and exact inputs/tools/commands. Distinguish static, mock, disposable integration and live acceptance evidence; record model transport separately. Include failures, errors, skips, unresolved gaps and the inputs needed to reproduce results. |
| **DH-W05 — Exercised runbook** | Create or update `docs/engineering/runbooks/<runbook-id>.md` with prerequisites, target identity, real commands, expected checkpoints, recovery and cleanup. Exercise applicable steps on the qualified target and link their evidence. If operating behavior is unchanged, say so and reference the existing verified procedure plus the relevant regression/check command; do not invent a new operating procedure. Untested instructions are explicitly untested. |
| **DH-W06 — Completion gate** | Mark a work item complete only when its required behavior is implemented, blocking review findings are resolved, required checks have current passing evidence and the applicable runbook has been exercised. Verify traceability and source/config/lock fingerprints before closure. A template, empty suite, old result, mocked provider success or unexecuted runbook cannot satisfy an unrelated live requirement. |

The plan and work record are living notes, not separate approval documents. Review and verification may iterate in whichever order exposes failures fastest; both must cover the final relevant inputs. Fixes invalidate affected evidence and review, not unrelated checks whose declared inputs are unchanged. Record nonblocking limitations honestly. A required behavior that still depends on a stub or unavailable check leaves that work item incomplete or blocked rather than “implemented and working.”

Independent review can use an identified human reviewer or an already qualified development assistant with separate review context. It does not require another paid provider, a different model family, or an automatic review-model call. The review must assess observable behavior and actual changes, not merely paraphrase the author's summary.

### DH-09.2. Fingerprints, manifests and retained artifacts

Bind evidence to a canonical manifest of all relevant inputs: tracked and untracked source files, nonsecret configuration, lockfiles, generated contracts, migration/fixture revisions and verifier code. Store content hashes and tool/runtime versions; a Git commit alone misses uncommitted inputs. Exclude report output files from their own input fingerprint to avoid circular hashes. Exclude raw secrets and user data entirely: fingerprint the redacted configuration and declared profile, with authorized credential references/versions only where relevant. Do not hash or copy `.env` contents into an evidence artifact.

Each check records its target instance/profile, argv or reproducible redacted command, working directory, UTC start/end, exit code, expected and observed assertions, status and artifact references. Use distinct statuses `passed`, `failed`, `error`, `skipped` and `not_run`; only an executed successful check can be `passed`. Record verification class per check (`static`, `mock`, `disposable`, `live`) and model transport (`none`, `mock`, `openrouter_live`) so a real local API using a fake model is not presented as provider qualification. Actual paid qualification remains a separately initiated bounded task under the provider contract.

Version concise, reviewed manifests as `docs/engineering/evidence/<work-item-id>/<evidence-id>.json` and maintain a readable `summary.md` containing requirement coverage, results, review/runbook links and remaining limits. Large redacted logs/screenshots belong in ignored `.checks/<work-item-id>/<evidence-id>/`; reference their hashes, local paths, availability and retention policy. Keep raw evidence available through review and acceptance, longer when needed for an unresolved failure or release gate. Record later deletion or unavailability. The versioned summary must preserve the observed assertions and reproduction details so a result does not depend solely on an ephemeral log path. Never commit credentials, production/user content or unredacted transcripts as proof.

This illustrative template is **not executed evidence**; implementation must define and validate its schema:

```yaml
schema_version: autobots.work-evidence/v1
template: true
work_item_id: <stable SPECS work-item ID>
evidence_id: <unique execution ID>
requirement_ids: [<PRD/SPECS acceptance IDs>]
fingerprint:
  source_manifest_sha256: null
  nonsecret_config_sha256: null
  lockfiles_sha256: {}
  generated_contracts_sha256: null
  verifier_sha256: null
tool_versions: {}
checks:
  - id: <check ID>
    requirement_ids: [<covered IDs>]
    verification_class: mock
    model_transport: none
    command_argv: []
    target_ref: <qualified target or fixture>
    expected: <observable assertion>
    observed: null
    status: not_run
    started_at_utc: null
    finished_at_utc: null
    exit_code: null
    artifacts: []
review:
  reviewer_id: null
  reviewed_fingerprint: null
  outcome: pending
  findings: []
runbook:
  path: <versioned runbook>
  revision_sha256: null
  exercised_evidence_ids: []
raw_artifacts:
  local_root: .checks/<work-item-id>/<evidence-id>/
  availability: not_created
  retention: <declared local policy>
```

Use a short work-item Markdown record with **Plan**, **Implemented**, **Review**, **Verification** and **Runbook** entries linking to these artifacts. Required evidence entries must have real values, `template: false`, and validated fingerprints before closure. The runner derives check statuses from captured execution and assertions; completion consumes those records rather than hand-written passing badges. The validator rejects missing execution records, inconsistent status/result pairs and pending examples. Never fabricate an execution or claim an unrun check passed. Hashes make evidence attributable and detect stale inputs; they do not prove that an assertion was correct, so review and meaningful tests remain necessary.

## DH-10. Acceptance and closure

| Gate | Required evidence |
|---|---|
| DH-A01 | Shared instructions, all required rules/skills/agents and valid project settings exist; links and scope match the implementation layout |
| DH-A02 | Portable runner operates without Claude/model credentials; required failures and missing prerequisites return failure |
| DH-A03 | Hook adapter accepts valid fixtures and rejects malicious/malformed inputs; pre-tool crash/timeout behavior and Stop recursion handling are qualified for any Claude integration claimed as qualified. Hooks in use as guardrails without that are reported as not qualified, and this gate stays partial ([Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md)) |
| DH-A04 | Deliberate TypeScript, Python and generated-contract faults fail; corrections pass; tool versions and locks recorded |
| DH-A05 | Good/bad state-transition, reducer and public-event fixtures detect invalid transitions and private-data leakage |
| DH-A06 | Disposable migrations replay and upgrade correctly; seeds run twice consistently; persistent target reset is refused |
| DH-A07 | RLS/grants/private schemas and Storage tests include anonymous and cross-workspace failures using nonprivileged identities |
| DH-A08 | Model fakes verify the two-profile OpenRouter policy and missing-key handling; all baseline tests prevent paid inference |
| DH-A09 | Stub worker crash/duplicate/lease-expiry fixtures exercise fencing and receipts before feature workers are written |
| DH-A10 | Compose target isolation, redaction and persistent-volume protection checks pass; no implicit cloud or assistant integration |
| DH-A11 | Changed/untracked inputs invalidate prior verification; skipped checks and optional integration limitations are visible |
| DH-A12 | Gate 0 report separates installed configuration, deterministic tests and actual assistant delivery; no untested component is marked activated |
| DH-A13 | A sample H0/H1 work item satisfies DH-W01–06 with stable requirement IDs, plan, implementation record, independent review and durable redacted evidence links |
| DH-A14 | Manifest validation rejects templates, missing reviewer/runbook evidence, changed source/config/lock/verifier fingerprints, inconsistent status/result combinations and unresolved blocking findings |
| DH-A15 | Static/mock/disposable/live and model-transport classifications remain distinct; a successful fake model cannot satisfy a live provider gate; failures/errors/skips are visible in the versioned summary |
| DH-A16 | The portable harness runbook is exercised on its declared target, including one failure/recovery path; real commands and observed checkpoints are retained, and raw-artifact retention/availability is explicit |

The first deliverable is the implemented and proven portable engineering baseline plus validated `.claude` configuration, followed by Option B's product foundation. Claude event delivery is claimed only for a separately qualified active adapter. Each later work item closes through DH-W01–06 with evidence of its actual required behavior. The current adaptation creates project harness files and checks specification/hook behavior; it does not install application dependencies, start Docker, mutate databases, qualify live inference or complete all gates above.
