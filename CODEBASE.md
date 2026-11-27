# Autobots codebase context

Analyzed revision: 095a97614b4fe65427072c74c166218a70213723
Working tree: dirty. Modified: `openspec/delivery/goal.md` only (the delivery loop's status record: EPIC-15 goal set to COMPLETE and US-15.25 to DONE, not committed). Nothing untracked is described.

**Inspected:** 2026-11-08, at HEAD on `main` (committed 2026-11-08T13:37:14-06:00, no remote). **Scope:** what the repository currently is. This file supplies no product requirements.

## System Summary

The repository holds:
- product PRDs and a backlog where every story traces to its sources;
- local delivery and verification tooling;
- a local application: a Next.js web app, a FastAPI API, and a Python worker that runs goals through Deep Agents and LangGraph, with self-hosted Supabase in Docker and inference through OpenRouter only.

`SPECS.md` has 15 epics and 105 stories, all `Status: DONE`. EPIC-14 is the tool catalog and EPIC-15 is the Studio product surfaces.

The worker claims and runs admitted jobs only when `AUTOBOTS_WORKER_INFERENCE=enabled`. By default it does maintenance only. That path has run on fake transports, on disposable stacks with a real provider, and on one persistent install on this Mac. The install's latest record (US-12.6) leaves it stopped at migration 35, and nothing since records applying migrations 36–49 to it.

[The US-10.2 release record](docs/engineering/evidence/US-10.2/summary.md) reads H1 as "met, with its stated limits" and leaves release to the owner. Passing a verification profile establishes neither H1 nor product acceptance. Neither do the EPIC-14 and EPIC-15 per-story records, which each say so.

## Repository Map

- **Intent:** `docs/PRD/PRD-*.md` (10 files, including `PRD-Studio.md` and `PRD-Tool-Catalog.md`) and `SPECS.md`, mapped through `.claude/autobots.json`. The technical contract is `docs/engineering/option-b-contract.md`.
- **Source:**
  - `services/agent/src/autobots/`: the Python service (`domain/`, `contracts/`, `application/`, `adapters/`, `api/`, `operations/`, `persistence/`).
  - `apps/web/`: Next.js (`app/`, `components/`, `lib/`).
  - `packages/api-client/src/runtime.ts`: the client runtime.
  - SQL: `supabase/migrations/` (62 files), `supabase/seeds/`, `supabase/bootstrap/`.
  - `infra/`: Compose files, the vendored Supabase release in `infra/supabase/upstream/`, and the browser executor images in `infra/browser/`.
- **Generated:**
  - `contracts/generated/openapi.json`;
  - `packages/api-client/src/generated.ts`;
  - `packages/db-types/src/generated.ts` (the columns a member can select) and `supabase/schema.snapshot.sql` (a schema-only dump of the three app schemas, for reading, never applied), both written by `python3.12 scripts/app_db.py types` and drift-checked;
  - the backlog navigation in `SPECS.md`.
- **Tests:**
  - `services/agent/tests/`: 40 `test_*.py` modules, plus `conftest.py` and `fake_openrouter.py`.
  - `apps/web/tests/`: 38 browser specs and 2 unit tests.
  - `tests/db/`: disposable-stack checks and their workers, grouped as `checks/`, `workers/`, `arrange/`, `fixtures/` and `sql/` (h1 and app), with a README that maps each file to its invoker. The eight largest checks run their scenarios from a `SCENARIOS` tuple (after the analyzed revision, refactor plan R-66).
  - `tests/harness/`, `tests/web/` (fixture API, upstream and worker), `tests/faults/`, `tests/toolchain/`, `tests/qualification/`. `tests/db/fixtures/checklib.py` holds the database checks' shared case protocol, `tests/harness/harness_support.py` what the harness tests share, `scripts/instruction_checks.py` the instruction-file checks that `project_configuration` reports, and `services/agent/tests/sql_fakes.py` the one SQL fake that refuses unscripted statements, and `scripts/qualification/` the qualifiers' one child-check runner and typed records; `scripts/paid_run.py` is the one paid-run session (after the analyzed revision).
  - `contracts/fixtures/`: shared cases.
- **Tooling:** `scripts/` (27 tracked files), `Makefile` (wraps the persistent install), and `.claude/` (7 agents, 13 skills, 9 rules, `hooks/dispatch.py`, `settings.json`, `ohmyorch/`).
- **Operator guides:** `README-DEV.md` Part 1 (set up, start, stop) and the runbooks in `docs/engineering/runbooks/`. After the analyzed revision, `README-Deep-Research-Content-Writer.md` records US-16.7's live runs of the Deep research writer and its workflow on the owner's install: five attempts with their outcomes, artifacts and costs (Decision 0034 R2). They are one-off observations, not a test.
- **Delivery records:** `openspec/` (105 archived changes, 74 specs, `delivery/goal.md`), `.claude/ohmyorch/project.json`. The empty `SPEC-LOGS/` scaffold was removed after the analyzed revision (Decision 0030).
- **Engineering records:** `docs/engineering/` holds:
  - `decisions/`: 0001–0022;
  - `runbooks/`: 9;
  - `evidence/`: 27 directories;
  - `work-items/`: 15;
  - `templates/` and `prerequisite-inventory.md`.
- **Design:** `docs/design/luma.css`, `docs/design/studio-extensions.css`, and the concept images in `docs/imagine/`.
- **Research:** `research/`. `research/upstream/` is git-ignored (`.gitignore:7`) and is not repository input.
- **No CI:** no check runs in CI. After the analyzed revision, `.github/workflows/pages.yml` publishes `docs/site/`, the project's one-page GitHub Pages site, on a push to `main` that changes it; it runs no check.

## Runtime and Tooling

Versions as recorded in the previous refresh (2026-11-06). Neither the manifests nor the lock files changed since 4315944.

- **Tools:** Python 3.12, uv, Docker, Supabase CLI, OpenSpec 1.13.2 (doctor), jq 1.7.1-apple (doctor) and Claude Code. Having a tool installed doesn't make it qualified.
- **Node:** pinned to 22.23.2 in `.node-version` and `package.json` `engines`, and `scripts/toolchain.py` selects it per process. pnpm 12.16.1 is pinned through Corepack (`packageManager`).
- **Python service (`services/agent/pyproject.toml`):**
  - `requires-python ==3.12.*`, locked with `uv.lock`.
  - Pins: `deepagents` 0.7.32, `langgraph` 1.2.19, `langgraph-checkpoint-postgres` 3.2.0, `langchain` 1.4.8, `langchain-openrouter` 0.2.9, `openrouter` 0.11.46, `fastapi` 0.162.0, `httpx` 0.28.1, `psycopg` 3.3.8, `psycopg-pool` 3.3.3, `cryptography` 50.0.2, `langchain-mcp-adapters` 0.3.2.
  - Dev tools: ruff, mypy (strict), pytest.
- **Web (`apps/web/package.json`):** Next 16.4.5, React 19.3.1, TypeScript 6.0.3, Tailwind 4.3.4, `@supabase/ssr` 0.12.7, Playwright 1.64.1 and `@axe-core/playwright` 4.14.0. The lock is `pnpm-lock.yaml`.
- **Infrastructure:**
  - `infra/disposable/compose.yaml` pins images by digest.
  - `infra/supabase/compose.overlay.yaml` binds the gateway and database to `127.0.0.1`.
  - `infra/browser/browser.Dockerfile` uses the Playwright image by digest, and `stealth.Dockerfile` (US-20.1, after the analyzed revision) the same image with Google Chrome. `infra/browser/proxy.Dockerfile` runs the standard-library egress proxy on a Python base pinned by digest.
- **Makefile:** `make help`, `first-time`, `install`, `owner`, `build`, `migrate`, `start`/`stop` (stack, api, web, worker), `status`, `logs`, `check`.
  - It wraps `scripts/persistent_install.py`, and its header says it removes no container or volume.
  - Inference stays off unless `INFERENCE=enabled` is named on the command line.

## Architecture

Layers under `services/agent/src/autobots/`:

- **`domain/`:** pure rules.
  - `models.py`: three approved profiles, 14 roles, `BindingSource` (run override, workspace override, workspace default, built-in default), `OFFERED_FOR_NEW_RUNS = {Terra, Sol}`, and `MAX_OUTPUT_TOKENS = 512`. Since Decision 0034 L1 and L4, after the analyzed revision, `MAX_OUTPUT_TOKENS` is 4,096 and `MODEL_CALL_SECONDS` is 300.
  - `budgets.py`: US$0.25–US$5.00 in US$0.25 steps.
  - Also `runs.py`, `tools.py`, `tool_catalog.py`, `workflows.py` (`ir_normalized`), `workflow_execution.py`, `routines.py`, `execution.py`.
  - `secret_patterns.py`, added after the analyzed revision: the secret shapes that both log redaction and shown text (`public_text`) mask.
  - Added by the R-21 to R-40 refactors, after the analyzed revision: `stops.py` (the stop-code vocabulary and each code's disposition), `repetition.py` (rate-limited logging), and `ModelRoute` in `models.py`.
- **`contracts/`:** the public Pydantic DTOs, which are the source of OpenAPI. Since R-61, after the analyzed revision, `primitives.py` defines the strict, lax and tool configurations and the strict primitives (`MicroUsd`, `Count`, `Version`, `Flag`, `UtcInput`), response vocabularies use the domain enums or Literals held to them and to the SQL CHECKs by parity tests, tool contracts are split into `tool_catalog.py`, `github_tools.py`, `file_tools.py` and `tool_fields.py`, and every tool version's schema digest is pinned. Row helpers are in `persistence/rows.py`. Since R-54, after the analyzed revision, `application/sql.py` defines psycopg-free `SqlConnection`, `SqlCursor` and `SqlPool` Protocols, `one()` (a missing row is a `RowNotFound` defect unless the site refuses it itself) and `required_row`/`optional_row`/`all_rows`, which build the frozen per-query rows in `persistence/rows.py` by column name; `api/resources.py` holds the process resources as one typed `AppResources`, and `run_projection` is a package whose run views each read from one read-only snapshot. Since R-51, after the analyzed revision, `contracts/persisted.py` types the durable documents: the frozen `PolicySnapshot` (read through `runs.frozen_snapshot`), the stored event payloads (`StoredEvent`) and one receipt model per operation, replayed through `existing_receipt(..., kind)`; stored-shape fixtures pin their bytes and hashes. Since R-52, after the analyzed revision, stored Expert and routine configurations, goals and plan tasks are read through `persistence/records.py`: frozen, lenient records with a `record_version` that is absent while it is 1, mapped to the DTOs in their application modules, and pinned by the stored-shape fixtures in `services/agent/tests/fixtures/stored/`.
- **`application/`:**
  - Admission: `runs.py` (typed `RunAdmission`), `run_admission.py` (the request's use case and the gate for model-backed work), `readiness.py` (one installation gate for people and routines).
  - Goal loop: `goal_loop.py` (the pass and its graph), `loop_prompts.py`, `settlement.py` (a candidate's verdict), `run_lifecycle.py` (how a pass ends, the lease keeper, bounded worker failures and `pass_registry`), `plans.py`, `run_usage.py`, `verification.py`, `recovery.py`, `compaction.py`, `bounded.py` (a child interpreter a timeout can stop, and `stop_task`). Job dispatch (`process_next`, `drive_lease`) is in `operations/job_dispatch.py` (Decision 0029 F7).
  - Model spend: `model_admission.py`, `model_attempts.py`, `worker_inference.py`, `profiles.py`.
  - Tools: `tool_definitions.py` (the tool vocabulary), `tool_gateway.py`, `tools.py`, `run_files.py`, `tool_catalog.py`, `tool_grants.py`, `tool_uses.py`, `code_tools.py`, `browsing_loop.py`, `browsing_tool.py`, `reconciliation.py`, `approvals.py`. Since R-53, after the analyzed revision, `adapters/tool_registry.py` builds the registry once at the composition edge (`api/app.py` and the worker's `loop_config`), the loop receives it through `LoopConfig.tool_set`, the catalog, Experts, routines and search through a `Catalog`, and one resolver in `tool_keys.py` applies key precedence for every item; adapters read keys through `ToolContext.key()` and `setting()`, never its connection.
  - Product surfaces: `experts.py`, `assignments.py`, `workflows.py`, `workflow_overview.py`, `workflow_runner.py`, `routines.py`, `memory.py`, `improvements.py`, `artifacts.py`, `run_projection.py`, `search.py`. Since R-63, after the analyzed revision, `workflow_executions.py` holds execution binding and its read model beside `workflows.py`, `idempotency.py` holds `receipted` and `next_version` for the receipt-guarded create and new-version procedures, the knowledge store is `knowledge.py`, and the product tools live in `artifact_tool.py`, `assignment_tool.py`, `improvement_tool.py`, `memory_tools.py` and `workflow_approval.py`; the workflow domain dispatches blocks through `PURE_BLOCKS` and the runner's `TOOL_BLOCKS`, whose keys together equal `BLOCKS`, with one `topological_order`.
  - Local operations: `operations.py`, `retention.py`, `worker_leases.py`, `provider_settings.py`, `credentials/`.
- **`adapters/`:**
  - Dispatch: `loop_middleware.py` (the thin `AgentMiddleware`, `AdmittedModel` and streaming), `tool_middleware.py`, `model_replies.py` (a reply's charge, finish and retry facts). Since R-62, after the analyzed revision, the loop's policy is in `application/loop_policy.py` and `application/loop_admission.py` (`LoopAdmission`: the guard, slot wait, admitted call, late charge, compaction and tool-dispatch stops).
  - Storage and checkpoints: `checkpoints.py`, `object_storage.py`.
  - Live text: `result_stream.py`.
  - Outbound HTTP: `provider_http.py`, `url_guard.py`, `remote_files.py`, `tavily.py`, `jina.py`, `market_data.py`, `github_connector.py`, `github_issues.py`, `github_reads.py`, `github_pulls.py`. Since R-62, after the analyzed revision, every client comes from `provider_http.http_client` (no redirects, no proxy or certificate variables, a required named timeout), provider replies are read through lenient adapter-private models, refused statuses are one table per write class, and each provider is a frozen connector with module-level handlers.
  - Browser: `browser_executor.py`, `browser_cdp.py`, `browser_qualification.py` (the images' source fingerprint, checked off the event loop and cached per digest), `browser_page.py`, `egress_proxy.py`, with the sweeper's lease and attempt queries in the fingerprinted `application/browser_leases.py`. `browser_use_box.py` runs a browse on browser-use in the box and judges its outcome (US-17.3, after the analyzed revision).
  - Models: `models/` (`catalog.py`, `factory.py`, `openrouter_metadata.py`). After the analyzed revision, US-23.1 adds `local_server.py`, the loopback client a local profile's `ChatOpenRouter` uses (Decision 0041 A2, A3).
- **`api/`:** `app.py` (factory), `main.py` (configured entry), 17 route modules, `dependencies.py`, `security.py`, `membership.py` and `errors.py`. Since R-55, after the analyzed revision, route modules hold no SQL but the stream's LISTEN, take their shared dependencies from `api/dependencies.py` (workspace and owner rules, readiness, the key check), decode the session token once per request, and cap stream listeners at 10; the model-policy write path is `application/model_policy.py`.
  - `contracts/generated/openapi.json` lists 66 paths under `/v1`.
  - Outside the schema (`include_in_schema=False`): artifact download and `/v1/runs/{id}/events/stream`.
- **`operations/`:** `worker.py`, `composition.py` (the provider context over the live environment, the object store and the configuration checks that `api/main.py` and the worker share), `cli.py` (exit 0, 1 `REFUSED:`, 2 `ERROR:` for a missing or malformed setting), `bootstrap_owner.py`, `route_qualification.py` with `route_fixtures.py` and the paid-call pieces in `paid/`, `reasoning_trial.py`, `browse_trial.py`, `concept_seed.py`, `fake_stream.py`, `live_key.py` (moved from `tests/db` after the analyzed revision). Since R-64, after the analyzed revision, the JSON logger is the leaf module `autobots/logs.py`.

**Working context.** Since Decision 0034 C1, after the analyzed revision, `compaction.state_block` also pins the run's plan, each task done or open, and says to continue it. Since Decision 0034 L6 to L8, `domain/models.CONTEXT_TOKENS` and `RESERVED_PROMPT_TOKENS` are 64,000, and `application/compaction.py` compacts toward 192,000 characters, offloads tool output over 48,000 characters and keeps 16 read-back pages in view.

**Run-tree limits.** `application/run_usage.RootLimits` holds each root's limits, and `tool_uses.METERED_TOOL_CALLS` its metered tool calls. Since Decision 0034 L2 and L3, after the analyzed revision, they are 64 model calls, 96 tool dispatches, 8 children, 45 active minutes and 40 metered calls, with one repair, two plan revisions, two child levels and two outstanding assignments.

**The model path.** `goal_loop.py` builds the graph with `create_deep_agent` around `AdmittedModel`, which refuses any call outside an admitted dispatch. For each dispatch, `LoopMiddleware` (`adapters/loop_middleware.py`, calling `application/loop_admission.py`):
- rechecks ownership, parent status and active time;
- consumes the root's `model_calls` limit;
- bounds a call at 120 s, 300 s since Decision 0034 L4 after the analyzed revision, and interrupts it on cancel;
- compacts the model's view through the same admission;
- allows one shorter retry after a `length` cut-off;
- reserves the route's worst case plus an amount for prompt bytes, and stops with `cost_unavailable` or `request_unencodable`;
- reconciles a late reply on a lost lease as `source="provider"`.

Every admitted call streams. `_streamed` assembles the `astream` chunks and parses the tool-call arguments strictly. A failure after the first chunk is `partial_stream` (`application/model_attempts.py`), which is reconciled, not retried.

**Uncertain calls.** `_log_uncertain` writes a `worker.call_uncertain` WARNING. It holds type names, the HTTP status and a `reason`, and never message text. No column or screen shows it ([Decision 0014](docs/engineering/decisions/0014-release-limits-accepted.md)).

**Routes.** All 14 role bindings resolve and freeze at admission. Each binding's source is recorded in the effective policy and in the run snapshot.
- `builtin_default` gives `researcher` Sol while Sol is offered, and Terra otherwise.
- A run dispatches through its `executor` binding.
- A `summarizer` binding that differs pauses a run needing compaction with `route_not_bound` ([Decision 0009](docs/engineering/decisions/0009-release-scope-from-blocking-findings.md)).

**Transitions.** Since R-60, after the analyzed revision, `domain/runs.py` lists which actors may apply each run command (`ACTORS`), with a `system` actor for cascades and expiries (Decision 0029 F5), mirrored by the SP-010 table in the Option B contract. `application/runs.py` is the one surface: `apply_command` for people, `apply_worker_command` for a lease (its stop reason in the same transaction), `cascade_command` for the system and `apply_claim`, always locking the job row before the run row; `job_status_after` and `JobStatus` decide the job. `ModelAdmission` is the only writer of the invocation ledger, and admission, the run projection, the run list and the workflow overview share one spend fragment, admission's, with a child's own calls added to its view (F10).

**Ownership.** `worker_leases.py` claims jobs by database time with a rising generation. Triggers from `20261105000008_worker_ownership.sql` refuse checkpoint writes from any other generation. `WakeClock` and the lease keeper in `run_lifecycle.py` handle sleep and wake ([US-12.5](docs/engineering/evidence/US-12.5/summary.md)).

**Live result text.** `goal_loop.run_goal` creates a per-run `ResultTap` (`adapters/result_stream.py`).
- It reads only the growing `content` of `save_artifact` calls whose path is under `outputs/`.
- It coalesces it (0.15 s, 1,500-character pieces) and sends it with `NOTIFY` on `autobots_result_text`. A tap failure never stops the run.
- The stream route opens its own `LISTEN` connection (`api/event_routes.py`, `_listener`) and forwards this run's notes as `event: live` frames carrying a `result.text.delta` `RunEvent`, with no `id:`, so they never move the replay cursor and are never stored.

**Web.**
- Pages are under `apps/web/app/`. The same-origin BFF routes under `app/api/` (7 route files) forward through `lib/bff.ts`.
- `packages/api-client` is the generated client. Since R-48, after the analyzed revision, it types each operation's query and declared headers (`Idempotency-Key` is a required argument), and the browser calls the API only through it: `apps/web/lib/api/browser.ts` gives reads (shared in flight, no-store) and writes (through `csrfFetch`), `failureOf` and the BFF-only bodies in `lib/api/bff-bodies.ts`. `tests/harness/test_raw_fetch.py` allows a raw `fetch(` in four transport files only.
- Form controls come from `components/ui/field.tsx`, which `tests/harness/test_shared_form_controls.py` enforces.
- The shell is `components/app-shell.tsx` with `sidebar-nav.tsx` (Work: Home, Runs, Approvals; Build: Experts, Workflows, Tools; System: Operations, Models, Settings).

## Entry Points

- **API:** `uvicorn --factory autobots.api.main:create_configured_app`. It turns inherited tracing off first and logs JSON lines with no access lines (`autobots/logs.py`).
- **Worker:** `python -m autobots.operations.worker`.
  - It always runs `maintenance_step`: expiring approvals, evaluating routines, and `retention.apply_all` hourly.
  - `AUTOBOTS_WORKER_INFERENCE=enabled` adds `inference_step` (`operations/job_dispatch.process_next`).
  - It exits on a partial configuration: `AUTOBOTS_DATABASE_URL`, an absolute `AUTOBOTS_CONFIG_ROOT`, and the Supabase URL and service key (`operations/worker.py:284–323`).
- **Web:** `next start` in `apps/web`, or `make start-web` ([local app runbook](docs/engineering/runbooks/local-app.md)).
- **Owner bootstrap:** `python -m autobots.operations.bootstrap_owner`. Since R-64 it inserts the workspace before it creates the Auth user, prints the user id and a `--user-id` command when the workspace step fails after that, and the [local app runbook](docs/engineering/runbooks/local-app.md) gives both recoveries.
- **Concept seed:** `python -m autobots.operations.concept_seed --workspace <id>`.
- **Paid operations modules:** `operations/route_qualification.py`, `operations/reasoning_trial.py`, and `operations/browse_trial.py` (through `scripts/browse_trial.py`).
- **Install and data:**
  - `scripts/persistent_install.py`: `init`, `up`, `setup`, `status`, `apply`, `goal`, and, after the analyzed revision (US-16.4, US-16.5), `screens` (read-only owner browser checks, `install-current.spec.ts`) and `examples` (paid, US$0.45 from the shared ledger). `reset` and `apply --reset` exist only to refuse.
  - `scripts/local_backup.py`: `keygen`, `backup`, `restore`, `verify`.
- **Paid or real-world runners, in no profile:**
  - `scripts/live_goal.py`, `scripts/qualify_release.py`;
  - `scripts/qualify_github_connector.py`, `scripts/qualify_browser_executor.py`, `scripts/qualify_browse_goal.py`, `scripts/browse_trial.py`;
  - `scripts/qualify_mac_sleep.py`, which needs a person to sleep the Mac.
- **Hooks:** `.claude/hooks/dispatch.py`, for `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop` and `SubagentStop` in `.claude/settings.json`.

## Data and Persistence

- **Migrations:** `supabase/migrations/` holds 66 ordered files, from `20261105000001_workspaces.sql` to `20261119000066_browse_steps.sql` (migration 66, US-17.4 after the analyzed revision, adds `app_private.browse_steps`; migration 65, US-17.1 after the analyzed revision, adds `app_private.browsing_settings` and `runs.browsing_yolo`; US-14.17's Tavily and Jina providers and `app_private.tool_key_settings`, US-14.18's GitHub provider and saved values, US-14.19's `routines.removed_at` and `action_marked` approval rule, R-17's revocation of the runtime role's DELETE on runs, run events, workspaces, members and profiles, R-35's private `failed_attempts` and `last_failure_type` on `app_private.run_jobs`, R-50's `approval_requests.consumed_at`, which makes an approval that releases a call leaving no receipt single-use, and R-56's run-lookup indexes, `app_private.run_is_terminal`, the draft graph's shape CHECK and four composite version foreign keys, validated by migration 61, and migration 62's caveat on Sol's qualified limits that concurrent admission was never tested (SQLI-12), after the analyzed revision), in the schemas `public`, `app_private` and `agent_runtime`. Migration 63, `20261118000063_serpapi_provider.sql` (US-14.22, after the analyzed revision), adds `serpapi` to the provider lists of `app_private.provider_credentials` and `app_private.tool_key_settings`. Since migration 35:

| Migration | Change |
|---|---|
| 36 | `runs.started_by`. On `approval_requests`: `requested_by`, `requested_by_agent`, `scope_snapshot`, `policy_version`, `policy_rule`, which a trigger makes immutable |
| 37 | `app_private.improvement_replays` and `improvement_replay_runs` |
| 38 | `app_private.tool_uses` |
| 39 | `tool_uses.instance_key` (the workflow node instance) |
| 40 | Adds Sol to the profile checks and `model_profiles` |
| 41 | Sol's row in `route_qualifications` |
| 42 | `public.user_profiles`, with RLS and `shares_workspace_with` |
| 43 | `model_policies.default_profile` becomes nullable |
| 44 | The per-run limit defaults to 5,000,000 µUSD |
| 45 | `workflows.description` |
| 46 | `public.workflow_drafts`. Members read it; owners write it through `is_workspace_owner` |
| 47 | `approval_requests.review_detail` |
| 48 | `app_private.plan_task_times` |
| 49 | `app_private.applied_migration_count()`, a security-definer function returning a count only, from `autobots_install.migrations` or `autobots_disposable.migrations` |

- **Seeds and bootstrap:** `supabase/seeds/reference.sql` is the repeatable model reference, and `supabase/bootstrap/` holds roles and Storage policies. Since R-56, after the analyzed revision, `storage.sql` and then the numbered bootstrap files are applied as superuser after the migrations and the seed, by `persistent_install.guarded_apply` and `app_db.apply_bootstrap` through one `app_db.bootstrap_plan`; each file gets a `bootstrap/<file>` row with its sha256 in the migration history, and an edited, missing or misnamed file is refused (`tests/harness/test_bootstrap_history.py`). `20261115000001_storage_members_read_only.sql` leaves members only the read policy on Storage objects and revokes anon's EXECUTE on `can_access_artifact` (Decision 0029 F3). The concept Experts and workflows are not in any seed or migration.
- **Public tables:**
  - workspaces (with `timezone`), members, `user_profiles`;
  - runs, `run_events`, `artifacts`, `approval_requests`;
  - Experts and their versions, `sessions`;
  - workflows with versions, drafts, executions, node instances and emissions;
  - routines with versions and occurrences. Since US-14.19, after the analyzed revision, a removed routine keeps them with `removed_at` set, and the Expert-only `cronjob` tool (`application/cronjob_tool.py`, group Automation, approval `by_action`) lists, creates, updates, pauses, resumes, runs now and removes them through `application/routines.py`;
  - `memory_items`, the improvement and knowledge tables, `model_profiles`.
- **Private tables:**
  - jobs, goal specs, plans, `plan_task_times`, usage, verifications;
  - `model_invocations`, `tool_receipts`, `tool_uses`, assignments, improvement replays;
  - credentials, policies, spend limits, idempotency receipts;
  - heartbeats, retention, `installation_holds`.
- **`agent_runtime`:** LangGraph checkpoints, `adapter_qualifications`, `route_qualifications`.
- **Schema readiness:** `application/operations.py` checks `REQUIRED_RELATIONS` and `REQUIRED_COLUMNS` (through migration 56), and compares `app_private.applied_migration_count()` with `SHIPPED_MIGRATIONS` in `application/schema_release.py`: fewer is `schema_behind` and blocks, more is `schema_ahead`, degraded and not blocking. A harness test (`tests/harness/test_app_db.py`) and `services/agent/tests/test_schema_release.py` fail unless that record matches `supabase/migrations`. Operations shows "N of M migrations applied" (`lib/schema-value.ts`). Changed by US-16.2, after the analyzed revision.
- **Install-only schema:** `autobots_install` holds the install's identity and applied-migration digests (`scripts/persistent_install.py`).
- **Ephemeral channel:** Postgres `NOTIFY autobots_result_text`. Nothing is stored.
- **Objects and files:**
  - Artifacts live in private Supabase Storage (`adapters/object_storage.py`).
  - Provider keys are sealed with AES-256-GCM under a master key file (`application/credentials/`). Since US-14.17, after the analyzed revision, the same store also holds a workspace's Tavily and Jina keys, and, since US-14.18, the GitHub token, saved at Settings → Keys & vars (`application/tool_key_settings.py`). The GitHub repository and the browsing switch are saved there too, as plain values in `app_private.tool_key_settings.value`.
  - Backups are cold and encrypted, with a signed manifest, and restore only into a new held disposable project.
  - The shared ledger is `.checks/decision-0009/ledger.json` (ignored).
  - The install's record, secrets and logs are at `~/.local/share/autobots-install` (Makefile `INSTALL_DIR`). This analysis did not read them.

## Integration points

**Internal.**
- `.claude/autobots.json` maps the documents, the verifier report and the upstream pins. `.claude/ohmyorch/project.json` activates OhMyOrch.
- `scripts/specs.py` (`validate`, `render`, `promote`) checks structure, sources, Gherkin, statuses and dependencies. It can't prove semantic entailment.
- `scripts/generate_contracts.py` (`write`, `check`) generates OpenAPI and the TypeScript client offline. `scripts/app_db.py types` generates the `public` row types.

**External.** The variable names are in `.env.example`: `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `JINA_API_KEY`, `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, `AUTOBOTS_BROWSER_EXECUTOR`.
- **OpenRouter** is the only inference provider (`adapters/models/factory.py`, `openrouter_metadata.py`). After the analyzed revision, US-23.1 adds local routes, answered by the owner's `llama-server` on 127.0.0.1 (Decision 0041):
  - The same `ChatOpenRouter` runs on `adapters/models/local_server.LoopbackClient` over httpx, with no key or retries, the profile's `chat_template_kwargs`, reasoning removed and a reported cost of 0.
  - `check_served` reads `/v1/models` before each call. A different model is `model_unavailable`, and nothing listening is the SUSPEND stop code `local_model_server_unavailable`.
  - `worker_inference` reads no catalog or credential for a local profile, and reserves 0.
  - The port is `AUTOBOTS_LOCAL_MODEL_PORT`, default 9931.
  - The profiles `local_bonsai_2_5_27b` and `local_inkling_2_mini` (migration `20261127000068`) are approved and not offered, and the model list leaves them out.
  - US-23.2 adds a local branch to `operations/route_qualification.py`, `qualify_local`. It runs US-3.4's fixtures at no spend with a 1,800-second call time. It measures the route with `operations/local_route_measurements.py`, and its report's `offerable` gates on the five fixtures in `GATING`. `application/local_offering.local_offers` offers a local profile on the Local source from its stored `qualified_with_limits` row, and `OFFERED_FOR_NEW_RUNS` is unchanged.
  - US-23.7 makes `LoopbackClient` hold a required or named tool call to a JSON schema itself (Decision 0041 A18). Every tool stays in the request with `tool_choice` `none`, `tool_call_schema` admits one call of an allowed tool as a `response_format`, and the reply, asked for whole, is checked with `jsonschema` and turned into that call. A reply cut off by its cap keeps no text, and a mismatch raises `ProviderFailure` `other`, never retried. Migration `20261127000070` records Bonsai 2.5's route as `qualified_with_limits`, with only `schema_nested` disabled, so `local_offers` offers it on the Local source.
  - Profiles: `openrouter_terra`, `openrouter_sol` (`openai/gpt-6.1-sol`) and `openrouter_deepseek_flash`, in `domain/models.py`.
  - The client is built inside each attempt from a key resolved there, with at most 512 output tokens, 4,096 since Decision 0034 L1 after the analyzed revision.
  - Every call is streamed.
  - `/v1/models` adds the listed prices per 1M tokens, the supported parameters and `fetched_at`.
- **GitHub, on one configured repository** (`GITHUB_REPOSITORY`):
  - `adapters/github_reads.py`: four read-only tools, `github_list_pull_requests`, `github_list_workflow_runs`, `github_search_issues` (pinned to the repository) and `github_read_file` (private content, at most 1,048,576 bytes).
  - `adapters/github_issues.py`: `create_github_issue` versions 1 and 2; v2 takes up to 10 labels.
  - `adapters/github_pulls.py`: `github_open_pull_request`. It waits for approval with a per-file diff (`review_detail`), opens `autobots/<operation_id>` with a marker, reads back before a retry, and stops with `base_moved`.
- **Tavily** (`adapters/tavily.py`): `tavily_search` versions 1 and 2, `tavily_extract`, `tavily_map`, `tavily_crawl`. Read-only, metered, with Tavily's inference options off.
- **Jina** (`adapters/jina.py`): `search_web` versions 1 and 2, `extract_website_content` (reader mode).
- **Search paging** (`adapters/search_paging.py`, US-14.21, after the analyzed revision):
  - Version 2 of both search tools pages through `gather`: pages of 10, at most 3 a call, de-duplicated by canonical URL and ranked from 1. A call stops at `enough`, `no_more`, `page_limit` or `provider_error`, and a later page's typed failure is kept as `page_error` (Decision 0031).
  - `search_web` v2 sends `num` 10 and `page` n per page through one client per call, so the key is read once. It takes `max_results` up to 30, with a 70-second timeout.
  - Tavily has no next page, so `tavily_search` v2 asks once for up to 20.
  - Each call is one metered tool use whose public output records `pages`.
  - New grants take version 2 (`domain/tools.PROVIDER_TOOLS`, `domain/execution.TOOL_VERSIONS`). Version 1 stays registered for runs that pinned it.
- **Google through SerpApi** (`adapters/serpapi.py`, US-14.22, after the analyzed revision):
  - `google_search` v1, provider `serpapi`, pages through the same pager. It sends GET `/search.json` with `engine=google`, `start` 0/10/20, `hl=en`, `gl=us` and the key as `api_key`.
  - A page's `serpapi_pagination.next` says whether more exist (`search_paging.Page.more`), and a "Fully empty" reply is an empty page (Decision 0032).
  - Its key is the Keys & vars secret `serpapi` (`SERPAPI_API_KEY`), which migration 63 allows.
  - The concept seed's sixth Expert, Google bot, is granted it.
- **Google toolkit** (US-14.23, after the analyzed revision): the group `google` holds `google_search`, `google_map`, `google_extract` and `google_crawl` (Decision 0033).
  - `google_map` (`adapters/serpapi.py`) searches `site:<host><path>` and keeps the site's own links.
  - `adapters/google_reader.py` reads pages directly, provider `direct`, with no key:
    - the URL guard and robots.txt first, failing closed and checking the final host after redirects;
    - one request per page, at least a second apart per host, under the user agent `Autobots/1.0 (local research agent)`;
    - extraction by `trafilatura` 2.3.1, the only package added and pinned for it, which gets the bytes and no URL.
  - `google_extract` reads up to 5 pages, and `google_crawl` maps a site, then reads up to 10.
  - Google bot is granted all four.
- **Tool switches** (US-14.24, after the analyzed revision): the owner turns any Expert-grantable tool, or a whole group, on or off for the workspace on the Tools page (Decision 0033).
  - Switches live in `app_private.tool_switches` (migration 64). No row means on, and each switch carries an expected version.
  - `tool_keys.key_sources` puts them in the workspace view as `switches`, and `tool_catalog.describe` turns an off tool into `disabled_by_policy` with `turned_off` or `group_turned_off`. So admission and Expert saves refuse it.
  - The gateway refuses each call to an off tool with `tool_turned_off`, before approval or metering.
  - `PUT /v1/tools/{tool_id}/switch` and `PUT /v1/tools/groups/{group}/switch` are owner-only and versioned.
  - The page shows `role="switch"` controls to the owner and words to a member (`components/tools/tool-switch.tsx`).
- **Market data** (`adapters/market_data.py`): `market_history` (Yahoo chart endpoint over `httpx`), keyless. After the analyzed revision, US-18.1 removed `inflation_rates` and the `world_bank` provider (Decision 0036). `domain/tools.RETIRED_TOOLS` lists it:
  - `without_retired` leaves it out where a saved Expert version or routine becomes a grant (`application/experts.py`, `application/routines.py`, the run preview and the workflow overview), and where a revision is saved.
  - `domain/execution.incompatibility` lets a run whose recorded contract lists it continue. A call to it is refused with `tool_not_registered`.
- **Fetch guard:** `adapters/url_guard.py` admits only `https` URLs whose every DNS answer is global, requests the address it checked (R-62), revalidates up to 3 redirects, and caps size and time; a test keeps its public-address rule equal to the egress proxy's. `adapters/provider_http.py` reads a provider key per attempt. For Tavily and Jina, `application/tool_keys.py` resolves it from the run's workspace: the key saved in Settings, then the process environment, then the configuration root's `.env` files (US-14.17, after the analyzed revision). `make start` passes those two keys, the GitHub pair and an exact `enabled` browsing switch from the repository's `.env` through `scripts/tool_keys_env.py`. Since US-14.18 the GitHub adapters resolve their repository and token the same way, per attempt (`adapters/github_issues.py` `attempt_target`). The gateway refuses an approved write whose target now resolves differently, `approval_target_changed`. The worker binds `browse_goal` only when the run's workspace resolves the switch to `enabled`.
- **Browser:** `adapters/browser_executor.py` runs one hardened Chromium container per call behind `egress_proxy.py`, which allows only `CONNECT` to named hosts and gates DevTools with a token. `browser_page.py` reads pages over CDP.
- **browser-use (US-17.3, after the analyzed revision):**
  - **Its container.** For a YOLO call while browser-use is qualified, `adapters/browser_use_box.py` serves the run's admitted model endpoint and starts the session with the sidecar's relay. It then runs a third container, `autobots-browser-use:local` (`services/browser-use/` with its own `uv.lock`, browser-use 1.0.6), which drives the session's Chromium over CDP.
  - **Its outcome.** The worker keeps its own request guard on that Chromium, which logs top-frame navigations and cancels any download. It ends the call `refused_action` before admitting the next model request.
  - **Its qualification.** browser-use is qualified apart: `browser_use_qualified` reads its own report, fingerprint and image label, on top of the executor's.
  - **Typing and steps (US-17.4, after the analyzed revision).**
    - **Submits.** The guard of a browser-use session lets `POST` with a body and `OPTIONS` through on `https`, and records form submissions as host and path.
    - **Bot checks.** It recognises bot-check frames and pages (`browser_cdp.bot_check_host`), which end the call `bot_check`.
    - **Screenshots.** At each model request the worker captures the box's page into the run's private storage, beside a row in `app_private.browse_steps` (migration 66, `application/browse_steps.py`). Members read them through `GET /v1/runs/{run_id}/tool-uses/{use_id}/steps` and its screenshot route, and the run's tool row shows them (`components/runs/tool-uses/browse-steps.tsx`).
    - **The use id.** `ToolContext.use_id` carries the dispatch's tool-use row to a read.
    - **Version 3.** `browse_goal` version 3 adds `output_schema`, validated with `jsonschema` (`application/typed_results.py`), and outputs `result`, `submits` and `bot_check`.
    - **Version 4 (US-21.1, after the analyzed revision).** `save` has the worker render the validated result (`typed_results.rendered`) and write it through `run_files.write`, bound to the call's tool-use row, since a browse has no operation. The output names the file in place of `result`, or says why in `not_saved`.
    - **`append_to_file` (US-22.1, after the analyzed revision).** A Files tool in `application/tools.py`, Expert-only, that adds to a run file through `run_files.append`, which reads and writes under one lock, with a receipt and a readback by operation like `save_artifact`.
- **The stealth browser (US-20.1, after the analyzed revision):**
  - **The choice.** `ExpertConfig.browser` (`domain/browsing.BrowserKind`) is left out while `box`. `browsing_settings.expert_browser` reads it, with the workspace's time zone, from the Expert version the run was admitted with.
  - **The session.** `BrowserExecutor.start(stealth=Stealth(timezone))` starts `autobots-browser-stealth:local` with `TZ` and a 512-process cap. `browser-entrypoint.js` has both modes.
  - **The call.** `browsing_tool._stealth` refuses `stealth_browser_unqualified` before any container. `browser_qualification.stealth_qualified` reads its own report, fingerprint and image label.
  - **The guard.** `RequestGuard` refuses a request whose user agent isn't the browser's own, and counts a top-frame navigation under one.
  - **Checks (US-20.2, after the analyzed revision).** `browser_cdp.is_the_page` and `asks_a_person` tell checks apart for a guard with `Patience`. `RequestGuard.settle` is awaited by `browser_use_box.guarded` before admission. `Stealth.challenge_hosts` joins the sidecar's allowed hosts for browser-use on the stealth browser only.
  - **Quiet and paced (US-20.3, after the analyzed revision).** `RequestGuard._listen` keeps ten polls waiting in each page's `WATCH` world, and each step writes what they answered into `app_private.browse_steps.touched` (migration 67) and `BrowseStep.touched`. `application/browse_turns.py` has `Pace` and `turn`, used by `browsing_tool` for both engines on the stealth browser.
  - **The scoreboard (US-20.4, after the analyzed revision).** `scripts/browser_scoreboard.py` opens addresses the owner names once in each browser with the executor and the guard, and no model. No profile runs it.
- **Supabase:** Auth, Storage and PostgREST, self-hosted and loopback-bound.
- **MCP:** `langchain-mcp-adapters` is pinned but not imported under `src/`.
- **Tracing:** `forbid_remote_tracing` turns inherited LangSmith and OTLP settings off.

## Authentication and Authorization

- **Browser to web:** an HttpOnly SameSite=strict session cookie (`lib/session.ts`), with host, origin, fetch-site and CSRF checks (`lib/request-guard.ts`). The BFF adds the internal token on the server.
- **Web to API:** `api/security.py` requires `X-Autobots-Internal` (constant-time compare) and a Bearer JWT (HS256, audience `authenticated`). Membership comes from `public.workspace_members` (`api/membership.py`).
- **Workspace selection:** `current_workspace` (`api/dependencies.py`) uses a verified `X-Autobots-Workspace` header; without one it uses the user's only workspace and otherwise refuses with `403 workspace_required`. Since US-16.3, after the analyzed revision: `POST /api/workspace` (same origin, CSRF-checked, membership checked against the session) keeps the choice in the HttpOnly, SameSite=Strict `autobots.workspace` cookie (`lib/workspace-choice.ts`); `lib/bff.ts` and `lib/service-status.ts` send it as the header; sign-out deletes it; `components/workspace-chooser.tsx` in the account footer asks a member of several workspaces to choose, with no implicit default.
- **Owners:**
  - `require_owner` gates the owner routes: Expert writes, workflow draft writes, `/v1/operations/jobs`, retention changes, replays, policy reset, and others.
  - Workflow drafts are also owner-only in RLS.
  - Public signup is disabled ([local app runbook](docs/engineering/runbooks/local-app.md)).
- **Effects and approvals:**
  - `application/approvals.py` binds a proposal to its exact arguments before the wait.
  - Since R-50, after the analyzed revision, `domain/effects.py` holds the receipt and approval state machines, `application/receipts.py` is the only writer of receipt status and `approvals.py` the only writer of approval status, each guarding its write with the states its move starts from. The tables are in the [Option B contract](docs/engineering/option-b-contract.md) beside SP-010 (Decision 0029 F8). Adapters read an approved call from `ToolContext.approval` and send no SQL to these tables.
  - Effect rulings must carry the receipt's `generation`.
  - Requests store the requester, agent, scope snapshot and `APPROVAL_POLICY_VERSION`, immutable by trigger ([Decision 0015](docs/engineering/decisions/0015-approval-request-fields.md)).
  - `arbitrary_execution` is admitted only for a tool whose executor reports qualified.
- **Accepted single-owner limits:** memory is scoped to the workspace, not the user (Decision 0009). `authenticated` can read raw emissions within a workspace, and a rollback's actor isn't recorded ([Decision 0013](docs/engineering/decisions/0013-release-closure.md)).

## Current capabilities

- **Screens:**
  - Home, Runs (with the side panel), Run, Run inspector, Approvals;
  - Experts and the editor, Sessions;
  - Workflows, the editor, and the execution monitor (`app/workflow-executions/[id]`);
  - Tools and tool detail, Operations, Sign-in;
  - Settings: Appearance, Notifications, Account, Data on this Mac, Keyboard and Models.
  - Routines, memory and improvements have API routes and no screens.
- **Shell:**
  - The account footer shows the display name and role (`/v1/session`, `/v1/profile`).
  - The health line comes from `/v1/readiness`, which any member can read.
  - The approvals count badge comes from `/v1/approvals/count`.
  - After the skip link come New run (⇧⌘O, `new-run.tsx`) and Search (⌘K, `search/search-palette.tsx`).
  - `WaitingNotifier` polls every 4 s while `autobots.notify` is on and notification permission is granted.
- **Home:**
  - A greeting in the workspace's timezone, then "What should we work on?".
  - Needs you (pending approvals and `waiting_input` runs) and the five most recent runs (`home-activity.tsx`).
  - The composer has Model, Expert and Budget chips, preview chips (`GET /v1/run-preview`), and up to 5 text files of 1 MiB each as typed inputs.
  - `?new=1` focuses the goal.
- **Runs:**
  - `POST /v1/runs` admits atomically with idempotency receipts. It refuses with `503 not_ready`, when no key is usable, or for a budget outside `domain/budgets.py` or above the remaining daily cap.
  - `/v1/runs` returns the label, stop reason, plan progress, frozen profiles and ledger spend, with `group`, `q`, `profile` and keyset `cursor` filters and per-group counts.
  - `runs/panel/` opens under the list at `?run=<id>`. Its commands send the version it loaded.
  - `RunWorkspace` adds task markers, times from `plan_task_times`, wall seconds, used tools, `current_task_id`, and the metered-call count.
  - The controls are pause, resume, cancel, owner reconciliation of a call's charge, and Continue (a linked new run). Terminal runs don't resume. Since R-49, after the analyzed revision, `RunWorkspace.allowed_commands` lists the commands `domain.next_status` lets a person send from the run's status, and the page offers only those; the run views are folders under `components/runs/` with their pure rules in `lib/runs/`, and the stream's frames are declared in `contracts/run_workspace.py` (`StreamFrame`, `StreamCursor`, `StreamGap`) and parsed in one module, `lib/runs/stream.ts`.
- **Live result text:** while a run writes a result, the run view shows its text under Result until the published artifact replaces it. "Stream text as it's written" (`autobots.stream`) turns this off.
- **Model choice:**
  - New work can choose Terra or Sol.
  - New work naming DeepSeek is refused with `model_not_offered` and no substitute (`422` when the request names it, `409` for a saved choice or a workflow, `RoutineRefused` for a routine).
  - An already-admitted run keeps its frozen route.
  - Models shows the facts, binding sources, Discard, Reset all (`POST /v1/settings/model-policy/reset`), and the follow-the-default summary.
- **Goal execution:** versioned plans and evidence, required artifacts, verification from artifacts and checks, staged and verified publication, cursor replay, and a live SSE stream.
- **Tools:**
  - The catalog (`application/tool_catalog.py`) is derived from the registry, and availability is computed per request, for the request's workspace, with each key's source (US-14.17).
  - Registered tools:
    - plan tools, `calculate`, `read_run_file` v1 and v2, `read_csv`, `read_offload`;
    - `save_artifact`, `publish_artifact`, `search_memory`, `propose_improvement`;
    - `store_remote_file` (Expert-only);
    - the code tools (`search_files`, `read_code_file`, `write_code_file`, `patch_code_file`, which write under `outputs/` only);
    - the provider tools above.
  - `browse_goal` (`application/browsing_tool.py`) is registered only while `AUTOBOTS_BROWSER_EXECUTOR=enabled` and the executor's qualification is current, at versions 1 to 4 (version 2 since US-17.3, version 3 since US-17.4 and version 4 since US-21.1, all after the analyzed revision). A call runs on browser-use while it is YOLO and browser-use is qualified (`browser_use_box.py`), and otherwise on the read-only loop in `browsing_loop.py`, each on the `researcher` route. Version 2's limits resolve per engine: up to 40 steps and 600 s on browser-use, by default 25 and 300; the loop caps at 20 and 300.
    - **Since US-17.1** (after the analyzed revision): a call is YOLO while the run's frozen `runs.browsing_yolo` and the workspace's `app_private.browsing_settings` are both on (`application/browsing_settings.py`).
    - **A YOLO call** skips approval through `ApprovalPolicy.waived`, is refused before any container when a domain falls outside its Expert's `browse_domains`, and records `typing: on` in its tool row.
    - **Any other call** is approved on every call.
    - Settings → Browsing (`GET`/`PUT /v1/settings/browsing`) holds the setting, and Home shows a one-time notice.
    - **Since US-17.2** (after the analyzed revision): `adapters/model_endpoint.py` serves a per-browse, token-guarded OpenAI chat-completions endpoint on the Mac's loopback. Each request is one admitted call through the loop's middleware on the `researcher` route, with typed refusals. The egress sidecar relays to it from the box on port 9300 (`egress_proxy.handle_model`), and `BrowserExecutor.start` takes its `ModelLink`. A browse on browser-use uses it (US-17.3).
  - Every gateway dispatch writes a `tool_uses` row, and the API serves `GET /v1/runs/{id}/tool-uses`.
  - `/v1/tools/{id}/grants` lists the Experts and published workflows using a tool. The Tools page has group counts and a filter. Since US-14.20, after the analyzed revision, choosing a tool opens a native `dialog` modal (`components/tools/tool-dialog.tsx`, with the detail in `tool-detail.tsx`). It holds each tool's What, When and Why guide (`domain/tool_guides.py`, exposed as the descriptor's `guide`), its inputs and outputs, Granted to and Copy schema.
- **Approvals:** `/v1/approvals` lists pending or decided requests with goal, task, decider and argument size. The screen pairs a list with the selected request's detail (JSON or Fields view, a PR diff from `review_detail`), and decides with ⌘↵ or ⌘⌫ pressed twice.
- **Experts:**
  - Cards show the executor's profile, tools with "+N", `run_count` and `last_run_at`, an approval note, and Start run.
  - Filters come from the catalog.
  - Configs carry `tool_groups`, which a save expands. A save naming an unavailable tool is refused with `expert_tool_unavailable`.
- **Specialists:** `application/assignments.py` runs child runs synchronously, with the scope intersected from the parent and spend counted on the root.
- **Workflows:**
  - A typed subset with immutable versions. A run binds to a version and hash, and emissions are insert-only.
  - IR v2 adds an optional node `label`, and `ir_normalized` keeps v1 hashes.
  - Optional description.
  - Since US-19.1, after the analyzed revision, an owner renames a workflow through `PUT /v1/workflows/{id}/name` (`application/workflows.rename_workflow`) and the editor's Name field. The workspace's unique constraint refuses a taken name with `workflow_name_taken`, a lost race included. Nothing else changes, and a run's goal keeps the name its execution started under (Decision 0037). The concept seed adds a seeded workflow beside one renamed away rather than replaying its receipt onto it, and publishes under a key naming the workflow (N6).
  - One draft per workflow, which an owner can save, publish or discard. Executions and routines refuse `"draft"` with `draft_not_runnable`. Since R-56, after the analyzed revision, a draft that fails validation reads as absent with `draft_unreadable`, the list still loads, publishing it is refused, discard deletes it by key, and the editor says saving replaces it.
  - The list gives the Experts, step count, last execution and run count, with `/executions` and `/preview`.
  - Executions accept a D11 budget.
- **Concept seed:** `operations/concept_seed.py` creates five Experts and six workflows through the application layer, as the owner. After the analyzed revision it creates seven of each: Google bot (Decision 0032 G8), and the Deep research writer, whose seed carries instructions, and its Deep research content writer workflow (Decision 0034 E1 to F2). Its instructions were tuned from US-16.7's live runs: propose the plan once, keep the document to 1,800 to 2,400 words so it fits one reply, and never put it in a reply. `application/artifact_tool.read_tool` adds `read_artifact`, which reads a published text artifact of the run's workspace, so a workflow step can read an earlier one's work (Decision 0034 A1 to A4). Since Decision 0023 E7, after the analyzed revision, Market watcher and Research analyst also get `publish_artifact`. Since US-18.1, the Market watcher has no `inflation_rates`, and "Monthly FX and inflation note" is seeded as "Monthly FX note" (Decision 0036 R7). Since E8, `loop_prompts.SYSTEM_PROMPT`, the goal's opening and `PlanTask.criteria`'s description say a plan cites criterion IDs only.

  Since US-17.5, after the analyzed revision, it creates eight of each. The eighth Expert is the Transcript reader (Decision 0035 Y14), granted `browse_goal`, `save_artifact` and `publish_artifact` with no browse domains; its instructions make one browse_goal call with a transcript schema and, since US-21.1, a `save`. Since US-22.1 it grants `read_run_file` and `append_to_file` in place of `save_artifact`: the call saves `transcript-timed.md`, the model adds polished prose to `transcript.md` 60 lines at a time, and both are published. Its Transcript workflow, published only where `browse_goal` is available, takes a `video` input whose `pattern` admits only an https YouTube watch or youtu.be address. Since then a workflow's `string` input may declare a `pattern` (`domain/workflows.py`), and an execution whose value doesn't match is refused `workflow_inputs_invalid` with `input_pattern_mismatch` (Y17). The Experts page's card shows an Expert's browse domains, or that it has none yet (`lib/experts/card.browseDomainsLine`).
  - It keeps anything already named.
  - It strips unavailable tools and says so in the Expert's purpose.
  - It saves the GitHub-dependent workflows (while GitHub is unavailable) and Interview synthesis as drafts.
  - It writes no secret and admits no run.
- **Routines:** explicit, with immutable versions, admitted with a unique key by the maintenance step.
- **Memory and learning:**
  - Lexical search in Postgres.
  - Proposals go through regression and an owner's review with rollback.
  - `POST /v1/improvements/{id}/replay` admits the owner's held-out tasks, and promotion is refused with `replay_required`, `replay_running` or `replay_failed` ([Decision 0016](docs/engineering/decisions/0016-held-out-replay.md)).
- **Operations:**
  - The readiness sentence, "N of M checks pass", the worker count and the hold.
  - `LocalStatus.values`:
    - database p95 over the last 20 probes;
    - applied migrations, artifact bytes, disk;
    - leased and queued jobs, the checkpoint adapter release, the catalog check's duration;
    - a loopback-only bind check over the API's listening sockets (descriptors only);
    - live workers.
  - `GET /v1/operations/jobs` (owner) returns 24 hourly buckets from `run.status_changed` events, which `operations/jobs-chart.tsx` renders with a legend, tooltip and disclosed table.
  - Logs are redacted JSON lines, and retention is per workspace (`GET /v1/retention` for any member).
- **Search:** `GET /v1/search?q=` (`application/search.py`) returns up to five each of runs by goal and of Experts and workflows by name, scoped to the workspace in SQL, plus catalog tools. The palette is a modal combobox over a listbox using `aria-activedescendant`.
- **Appearance:**
  - System, Light and Dark (`theme-provider.tsx`, `enableSystem`, dark by default).
  - The before-paint script in `app/layout.tsx` applies `data-serif`, `data-density`, `data-motion` and `data-stream` from `autobots.*` keys.
  - `globals.css` adds `--document`, compact `--spacing: 0.2rem`, and a forced reduced-motion rule.
- **Server reads:** since R-67, after the analyzed revision, `lib/server-api.ts` (server-only) calls the generated operations with the request's session and chosen workspace, classifies failures with `lib/load-failure.ts` and caches each read for one request with React `cache()`, never across requests. The run inspector, the data summary, the session page, Home's activity, the run list's first page and the tool page's facts render on the server, a write that changes server data calls `router.refresh()`, and list filters and selection live in the URL on Runs, Experts and Approvals.
- **UI primitives:** since R-68, after the analyzed revision, `components/ui/` adds `Label` and `Field` (help and errors tied to their control with `aria-describedby`), a `Dialog` on the native `<dialog>` (Escape, outside-click close, focus return), `Card` with an `as` prop, and the shared `SegmentedControl`, `HairlineSection`, `SectionHeading`, `SettingsSection`, `InitialTile` and `StatusDot`. `globals.css` names the type scale (13 `--text-*` steps) and radius steps, `tests/harness/test_arbitrary_pixel_classes.py` holds the remaining arbitrary pixel classes to a baseline that only falls, and `lib/preferences.ts` is the one source for the appearance keys and the before-paint script.
- **Screen layout:** since R-43 to R-45 and R-59, after the analyzed revision, each large screen is a folder under `apps/web/components/` (`approvals/`, `composer/`, `workflow-editor/`, `operations/`, `model-policy/`, `provider-settings/`, `keys-and-vars/`, `search/`, `expert-editor/`, `experts/`, `workflows/`, `tools/`): a composing panel, a data hook on `lib/use-resource.ts`, an actions hook on `lib/use-submit.ts`, and presentational sections. Their pure rules are in `apps/web/lib/` with `node:test` cases. The Experts and Workflows lists share `components/list-detail/` and one filter, `lib/list-filter.ts`.
- **Design:** Luma tokens and the Studio presentation ([Decision 0021](docs/engineering/decisions/0021-studio-interface-redesign.md), [Decision 0022](docs/engineering/decisions/0022-studio-product-surfaces.md)), with a serif `PageHeader` and an attention tone. No workflow canvas component exists (grep for `canvas` in `apps/web/components` finds none). The model-assisted features stay out of scope under Decision 0022 D13.

## Product implementation status

These evidence classes aren't interchangeable, and later code doesn't inherit earlier live results.

| Class | What ran | Result and limit |
|---|---|---|
| Fake transport under the real SDK | `services/agent/tests`, `qualify_worker_inference.py`, `operations/fake_stream.py` for streamed replies | Credential failures, catalog outages, streaming, and the Tavily, Jina, market and GitHub tools in tests are mock-level |
| Disposable stack, scripted model | `db` and `operations` profiles, [the closing checks](docs/engineering/evidence/US-10.2/closing-checks.json) | Per-story records for US-15.20–15.25 report `db` exit 0, the latest at 2026-11-08T19:36Z (US-15.25). The newest recorded `operations` run found is at [US-12.8](docs/engineering/evidence/US-12.8/summary.md) |
| Real sleep, disposable stack | [US-12.5](docs/engineering/evidence/US-12.5/summary.md) | 988 s across 20 wakes, `succeeded`. No real provider across a sleep |
| Live, direct | US-3.4, US-7.2, US-11.2; US-14.15 (Sol route: 39 calls, US$0.011482 reported); US-15.16 (GitHub, `josoroma/bot-test`, 30 of 40 requests) | No worker or ledger around them. All predate streaming (US-15.24) except US-15.16, which makes no model calls |
| Live, disposable stack | LIVE-GOAL-1, US-10.1, US-12.4; US-14.16 (one `browse_goal` on Sol, US$0.00565) | Terra 5 of 5 and DeepSeek 0 of 5 on one repeated goal. **One US-12.4 round paused as `uncertain_acceptance` with no known cause** |
| Persistent install | US-11.3, [US-12.6](docs/engineering/evidence/US-12.6/summary.md) | Compose project `autobots-install`, ports 55321, 55322, 8001, 3000. Recorded stopped at migration 35 of 35. No later record found |

**Streamed calls against a live OpenRouter route aren't qualified.** The US-15.24 record says that needs its own capped authorization. Paid authority now exists only as per-decision, once-each grants (for example Decision 0019's S4 and S6). [Decision 0014](docs/engineering/decisions/0014-release-limits-accepted.md) ended general authority.

## Tests and Quality Gates

`scripts/verify.py` implements `harness`, `fast`, `full`, `db` and `operations` (`IMPLEMENTED_PROFILES`). It exits 0 passed, 1 a check failed, 2 unavailable, and it never installs.

- **`harness`:** configuration, backlog validation, deterministic harness tests.
- **`fast`:** adds the Python and web steps for what changed. Since R-07, after the analyzed revision, it also runs `repo_ruff_check` (root `ruff.toml`) and `repo_mypy` (strict, root `mypy.ini`, over the hook's six trust-boundary modules) when scripts, tests or hooks change.
- **`full`:** every static and unit step, `next build`, `contract_drift`, `qualify_faults.py`, the offline `tests/toolchain` modules (since R-01, after the analyzed revision) (scope, manifest pins and launchers), and `qualify_web.py`. Per-story records report 41 browser tests.
- **Selections:** since R-01, after the analyzed revision, `scripts/suites.py` names every step's tests: web and API-client unit tests by glob, the Playwright projects, and the manual files with their reasons. `tests/harness/test_suite_claims.py` fails on a test file nothing runs. `make check-fast` and `make check-full` run those profiles; `.githooks/pre-commit` is opt-in.
- **Profile registry:** since R-65, after the analyzed revision, `scripts/qualification/profiles.py` describes each profile's steps once (arguments, timeout, class, transport, scope, not-tested list), and `verify.py`, `toolchain.py`, `report_state` and `evidence.py` read it; the Stop hook derives a script's check domains from what those steps import. `disposable_db.disposable_project` owns every disposable stack's lifecycle and cleanup cases, the operations, backup and upgrade qualifiers run ordered `SCENARIOS`, `scripts/local_app.py` holds the Makefile's process supervision, and `harness_lib.parse_dotenv` is the one dotenv reader (with `stack.env` read verbatim, Decision 0029 F11). The disposable stack pins the install overlay's database and Storage images.
- **`db`:** disposable targets for `disposable_db`, `supabase_stack`, `app_db`, `qualify_identity` (including `tests/db/checks/*_check.py` such as `result_stream_check`, `task_timing_check`, `pull_request_check`, `concept_seed_check`) and `qualify_persistent_apply`.
- **`operations`:** `qualify_operations`, `qualify_backup`, `qualify_upgrade`, on disposable projects with a scripted model.

**Browser specs.** Since R-58, after the analyzed revision, `apps/web/tests/browser/projects.json` assigns the 41 spec files to seven Playwright projects, and each runner passes its own with `--project`:
- `qualify_identity.py` runs `main` (24 files, 131 tests), `arranged` (3 files, 8 tests, one at a time by title) and `slice` (8 files, 36 tests).
- `qualify_web.py` runs `web` (`appearance`, `boundary`, `tools`: 50 tests).
- `qualify_release.py --ui` runs `release`, `persistent_install.py screens` runs `install-current`, and `install` runs by hand.
- `support/state.ts` checks a shared state before a suite that needs it and restores it after one that changes it (provider key, retention, model policy, keys and values).

**In no profile:** `qualify_worker_inference.py`, `qualify_github_connector.py` (`--suite studio`, review then apply, ledger-capped), `qualify_browser_executor.py`, `qualify_browse_goal.py`, `browse_trial.py`, `qualify_mac_sleep.py`, `qualify_release.py`, `live_goal.py`, and `tests/toolchain` other than its offline modules. `scripts/suites.py` lists the manual test files with their reasons.

**Evidence and hooks.** `scripts/evidence.py` checks records for consistency, not correctness. The hook fixtures are in `tests/harness/test_hook_guard.py`, `test_hook_process.py`, `test_hook_diagnostics.py` and `test_hook_worktrees.py` (after the analyzed revision; `test_hooks.py` until R-66). Hooks are configured but not qualified ([Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md)).

## Common Commands

```sh
python3.12 scripts/specs.py validate             # also render, promote
python3.12 scripts/verify.py --profile harness   # also fast, full, db, operations
python3.12 scripts/toolchain.py versions         # also lock, bootstrap, check
python3.12 scripts/generate_contracts.py check   # or write
python3.12 scripts/evidence.py fingerprints
python3.12 scripts/qualify_worker_inference.py
make help                                        # persistent install: start, stop, status, migrate, check
```

Start, drain and stop are in [the operations runbook](docs/engineering/runbooks/operations.md). The other runbooks in `docs/engineering/runbooks/` are `backup-restore`, `upgrade`, `mac-sleep`, `local-supabase`, `local-app`, `first-slice`, `toolchains`, `development-harness` and `ohmyorch-delivery`.

## Conventions

- Stable `SP-*`, `EPIC-*`, `US-*` and requirement IDs. Code comments cite their source IDs, such as `PRD-Studio ST-01` and `Decision 0022 D5`.
- Routine delivery follows the OpenSpec lifecycle, and the archived change is the record ([Decision 0003](docs/engineering/decisions/0003-openspec-only-delivery.md)). Each archived `verification.md` ends with a "Not established" line. Since Decision 0030, after the analyzed revision, OhMyOrch 0.1.0's verify writes no file and `tasks.md` is a change's only tracker.
- Money is integer micro-USD. Errors reach clients as typed codes. Logs carry exception type names, never messages, with identifiers cut to 8 characters.
- Pydantic owns the public contracts and SQL owns the schema. Generated files aren't hand-edited. Migrations and seeds are separate.
- Versioned tools keep the old version registered beside the new one (`read_run_file`, `create_github_issue`).
- Browser preferences are `localStorage` keys `autobots.<name>`. Ports are loopback only. Disposable images are pinned by digest, and check projects are marked `autobots-disposable-*`.

## Constraints and Technical Debt

Accepted limits, by decision:
- Decision 0005: strict nested output is unsupported on DeepSeek.
- Decision 0008: US-10.1's limits.
- Decision 0010: WCAG 2.1 AA is the pass line.
- Decision 0013: PRD 8.3's empty `inputs` grant.
- Decision 0014: rare uncounted active time, paid calls during a drain, and Continue losing its key on reload.

Observed risks:
- **Input-size estimate:** a reservation's input size is a byte-based estimate, because no tokenizer is pinned.
- **Uncertain calls not logged:** `charge_not_reported`, `cancelled_after_dispatch` and a cut drain emit no `worker.call_uncertain`.
- **Duplicate issues:** `create_github_issue` has no idempotency key (Decision 0007). The PR connector uses a branch name and marker instead.
- **Fingerprint churn:** `input_manifest` in `scripts/harness_lib.py` hashes everything under `supabase/`, including ignored files such as `supabase/.temp/cli-latest`.

Repository text that differs from the code or tree:
- `README.md` says implementation remains pending and calls the product unimplemented.
- `SPECS.md` line 3 reads "development-harness work only, product unimplemented".
- `docs/engineering/runbooks/development-harness.md:47–48` counts 23 browser spec files. There are 38.
- `application/run_projection.py:1` says nothing there reads checkpoints, while line 642 reads their metadata.
- `docs/engineering/runbooks/mac-sleep.md` doesn't name `sleep_counted_as_work`.
- `services/agent/pyproject.toml:4` still says "minimal non-feature scaffold".

Hooks are guardrails, not OS confinement ([the harness runbook](docs/engineering/runbooks/development-harness.md)).

## Upstream evidence and local constraints

- `.claude/autobots.json` pins OhMyOrch at `fddfbf53…` for the spec-ingestor and, since Decision 0030 after the analyzed revision, `2bae070c…` (branch `main`, version 0.1.0, the sibling checkout `../OhMyOrch`) for the delivery plugin. The ignored clone at `research/upstream/OhMyOrch` stays at `9f384fa` (0.0.1, branch `openspec-only`) as the ingestor's provenance and the rollback source.
- The same file records assistant event delivery as `not_tested`, and the plugin's as `not_qualified_one_pretooluse_event_observed`.
- No local model runtime is part of the application. The `research/` material is historical.

## Gaps and evidence limits

- Passing any profile proves those checks only, not H1, product acceptance or anything about a persistent stack.
- No independent review ran on EPIC-14 or EPIC-15 stories (Decision 0003). Their scenarios were observed by the delivering session.
- `SPECS.md`, `CODEBASE.md`, work items and runbooks are excluded from the source fingerprint (`scripts/evidence.py`, `RECORD_FILES`). The US-12.8 binding predates 59 commits of source change.
- Raw reports under `.checks/`, including the US-15.16 qualification files, are ignored and local.

## Evidence Paths

- `services/agent/src/autobots/domain/models.py`: profiles, offered set, binding sources, output cap.
- `services/agent/src/autobots/adapters/loop_middleware.py`, `application/loop_admission.py`, `application/goal_loop.py`, `application/model_attempts.py`: admitted, streamed calls.
- `services/agent/src/autobots/adapters/result_stream.py`, `api/event_routes.py`: NOTIFY tap and live SSE frames.
- `services/agent/src/autobots/adapters/github_connector.py`, `github_reads.py`, `github_issues.py`, `github_pulls.py`: GitHub tools.
- `services/agent/src/autobots/adapters/tavily.py`, `jina.py`, `market_data.py`, `url_guard.py`, `browser_executor.py`, `egress_proxy.py`: other integrations.
- `services/agent/src/autobots/application/operations.py` (readiness), `backups.py`, `job_activity.py`, `operation_values.py`, `catalog_check.py`, `api/operation_routes.py`: readiness, values, jobs chart.
- `services/agent/src/autobots/api/dependencies.py`, `api/membership.py`, `apps/web/lib/bff.ts`: workspace and owner resolution.
- `services/agent/src/autobots/operations/concept_seed.py`, `operations/worker.py`: entry points.
- `services/agent/src/autobots/application/search.py`, `domain/budgets.py`, `domain/workflows.py`: search, budgets, workflow IR.
- `supabase/migrations/20261107000036_…` to `20261108000049_applied_migration_count.sql`: schema since the last refresh.
- `contracts/generated/openapi.json`: 66 `/v1` paths.
- `apps/web/components/` (`search/`, `new-run.tsx`, `waiting-notifier.tsx`, `operations/jobs-chart.tsx`, `runs/`, `settings-nav.tsx`, `sidebar-nav.tsx`, `appearance-control.tsx`), `apps/web/app/layout.tsx`, `apps/web/app/globals.css`: Studio surfaces.
- `scripts/verify.py`, `scripts/qualify_identity.py:276–335`, `scripts/qualify_web.py:169`, `scripts/harness_lib.py`: verifier and browser-spec mapping.
- `openspec/changes/archive/2026-11-07-us-14-*/`, `2026-11-08-us-15-*/verification.md`: per-story records (pointers only).
- `docs/engineering/decisions/0019-sol-profile-and-browser-use.md`, `0022-studio-product-surfaces.md`: paid authority, Studio scope.
- `docs/engineering/evidence/US-10.2/`, `US-12.8/`, `US-12.6/`: release record, Gate 0 binding, install.
- `Makefile`, `.env.example` (variable names only), `.claude/autobots.json`.

## Unknowns

- Whether the persistent install is still stopped at migration 35, or has had 36–49 applied. No record was found, and neither Docker nor `~/.local/share/autobots-install` was inspected. `make status` or `persistent_install.py status` would settle it.
- Current pass counts for each profile at HEAD. Only per-story exit codes are recorded, and no profile was run for this refresh. The newest `operations` run found predates EPIC-13.
- Behavior of streamed calls against live OpenRouter: not qualified, and settled only by a capped authorized run.
- How screens and admission behave on a database missing migrations 38–49, since the readiness lists don't cover them.
- Why US-12.4's round 1 paused (the record calls it unexplained).
- What Claude does when a hook crashes or times out, and whether live event delivery holds beyond the one observed event.
- Real OpenRouter credential-validation failures: MP-A02 and MP-A03 ran against a fake upstream.
- This refresh did not re-read `recovery`, `compaction`, `memory`, `workflow_runner`, `retention`, `improvements` or `scripts/local_backup.py` line by line. Their descriptions rest on the prior inventory.
- The exact tool count in the live registry at runtime, which depends on the keys and the executor flag.
