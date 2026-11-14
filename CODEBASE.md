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

- **Intent:** `PRD-*.md` (10 files, including `PRD-Studio.md` and `PRD-Tool-Catalog.md`) and `SPECS.md`, mapped through `.claude/autobots.json`. The technical contract is `docs/engineering/option-b-contract.md`.
- **Source:**
  - `services/agent/src/autobots/`: the Python service (`domain/`, `contracts/`, `application/`, `adapters/`, `api/`, `operations/`, `persistence/`).
  - `apps/web/`: Next.js (`app/`, `components/`, `lib/`).
  - `packages/api-client/src/runtime.ts`: the client runtime.
  - SQL: `supabase/migrations/` (49 files), `supabase/seeds/`, `supabase/bootstrap/`.
  - `infra/`: Compose files, the vendored Supabase release in `infra/supabase/upstream/`, and the browser executor images in `infra/browser/`.
- **Generated:**
  - `contracts/generated/openapi.json`;
  - `packages/api-client/src/generated.ts`;
  - `packages/db-types/src/generated.ts`;
  - the backlog navigation in `SPECS.md`.
- **Tests:**
  - `services/agent/tests/`: 40 `test_*.py` modules, plus `conftest.py` and `fake_openrouter.py`.
  - `apps/web/tests/`: 38 browser specs and 2 unit tests.
  - `tests/db/`: disposable-stack checks and their workers.
  - `tests/harness/`, `tests/web/` (fixture API, upstream and worker), `tests/faults/`, `tests/toolchain/`, `tests/qualification/`.
  - `contracts/fixtures/`: shared cases.
- **Tooling:** `scripts/` (27 tracked files), `Makefile` (wraps the persistent install), and `.claude/` (7 agents, 13 skills, 9 rules, `hooks/dispatch.py`, `settings.json`, `ohmyorch/`).
- **Operator guides:** `README-SETUP-RUN.md` (set up, start, stop) and `README-QA.md` (runtime Q&A, which describes revision `ecb34900e46c`).
- **Delivery records:** `openspec/` (105 archived changes, 74 specs, `delivery/goal.md`), `SPEC-LOGS/`, `.claude/ohmyorch/project.json`.
- **Engineering records:** `docs/engineering/` holds:
  - `decisions/`: 0001–0022;
  - `runbooks/`: 9;
  - `evidence/`: 27 directories;
  - `work-items/`: 15;
  - `templates/` and `prerequisite-inventory.md`.
- **Design:** `docs/design/luma.css`, `docs/design/studio-extensions.css`, and the concept images in `docs/imagine/`.
- **Research:** `research/`. `research/upstream/` is git-ignored (`.gitignore:7`) and is not repository input.
- **No CI:** `.github/` has no tracked files, and no other CI configuration was found.

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
  - `infra/browser/browser.Dockerfile` uses the Playwright image by digest. `infra/browser/proxy.Dockerfile` runs the standard-library egress proxy on a Python base pinned by digest.
- **Makefile:** `make help`, `first-time`, `install`, `owner`, `build`, `migrate`, `start`/`stop` (stack, api, web, worker), `status`, `logs`, `check`.
  - It wraps `scripts/persistent_install.py`, and its header says it removes no container or volume.
  - Inference stays off unless `INFERENCE=enabled` is named on the command line.

## Architecture

Layers under `services/agent/src/autobots/`:

- **`domain/`:** pure rules.
  - `models.py`: three approved profiles, 14 roles, `BindingSource` (run override, workspace override, workspace default, built-in default), `OFFERED_FOR_NEW_RUNS = {Terra, Sol}`, and `MAX_OUTPUT_TOKENS = 512`.
  - `budgets.py`: US$0.25–US$5.00 in US$0.25 steps.
  - Also `runs.py`, `tools.py`, `tool_catalog.py`, `workflows.py` (`ir_normalized`), `workflow_execution.py`, `routines.py`, `execution.py`.
  - `secret_patterns.py`, added after the analyzed revision: the secret shapes that both log redaction and shown text (`public_text`) mask.
- **`contracts/`:** the public Pydantic DTOs, which are the source of OpenAPI. Row helpers are in `persistence/rows.py`.
- **`application/`:**
  - Admission: `runs.py`.
  - Goal loop: `goal_loop.py`, `plans.py`, `run_usage.py`, `verification.py`, `recovery.py`, `compaction.py`.
  - Model spend: `model_admission.py`, `model_attempts.py`, `worker_inference.py`, `profiles.py`.
  - Tools: `tool_gateway.py`, `tools.py`, `tool_catalog.py`, `tool_grants.py`, `tool_uses.py`, `code_tools.py`, `browsing_loop.py`, `browsing_tool.py`, `reconciliation.py`, `approvals.py`.
  - Product surfaces: `experts.py`, `assignments.py`, `workflows.py`, `workflow_overview.py`, `workflow_runner.py`, `routines.py`, `memory.py`, `improvements.py`, `artifacts.py`, `run_projection.py`, `search.py`.
  - Local operations: `operations.py`, `retention.py`, `worker_leases.py`, `provider_settings.py`, `credentials/`.
- **`adapters/`:**
  - Dispatch: `loop_middleware.py`, `tool_middleware.py`.
  - Storage and checkpoints: `checkpoints.py`, `object_storage.py`.
  - Live text: `result_stream.py`.
  - Outbound HTTP: `provider_http.py`, `url_guard.py`, `remote_files.py`, `tavily.py`, `jina.py`, `market_data.py`, `github_issues.py`, `github_reads.py`, `github_pulls.py`.
  - Browser: `browser_executor.py`, `browser_page.py`, `egress_proxy.py`.
  - Models: `models/` (`catalog.py`, `factory.py`, `openrouter_metadata.py`).
- **`api/`:** `app.py` (factory), `main.py` (configured entry), 14 route modules, `security.py`, `membership.py` and `errors.py`.
  - `contracts/generated/openapi.json` lists 66 paths under `/v1`.
  - Outside the schema (`include_in_schema=False`): artifact download and `/v1/runs/{id}/events/stream`.
- **`operations/`:** `worker.py`, `logs.py`, `bootstrap_owner.py`, `route_qualification.py`, `reasoning_trial.py`, `browse_trial.py`, `concept_seed.py`, `fake_stream.py`.

**The model path.** `goal_loop.py` builds the graph with `create_deep_agent` around `AdmittedModel`, which refuses any call outside an admitted dispatch. For each dispatch, `LoopMiddleware` (`adapters/loop_middleware.py`):
- rechecks ownership, parent status and active time;
- consumes the root's `model_calls` limit;
- bounds a call at 120 s and interrupts it on cancel;
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

**Ownership.** `worker_leases.py` claims jobs by database time with a rising generation. Triggers from `20261105000008_worker_ownership.sql` refuse checkpoint writes from any other generation. `WakeClock` and `goal_loop._keep_lease` handle sleep and wake ([US-12.5](docs/engineering/evidence/US-12.5/summary.md)).

**Live result text.** `goal_loop.py:350` creates a per-run `ResultTap` (`adapters/result_stream.py`).
- It reads only the growing `content` of `save_artifact` calls whose path is under `outputs/`.
- It coalesces it (0.15 s, 1,500-character pieces) and sends it with `NOTIFY` on `autobots_result_text`. A tap failure never stops the run.
- The stream route opens its own `LISTEN` connection (`api/event_routes.py`, `_listener`) and forwards this run's notes as `event: live` frames carrying a `result.text.delta` `RunEvent`, with no `id:`, so they never move the replay cursor and are never stored.

**Web.**
- Pages are under `apps/web/app/`. The same-origin BFF routes under `app/api/` (7 route files) forward through `lib/bff.ts`.
- `packages/api-client` is the generated client.
- Form controls come from `components/ui/field.tsx`, which `tests/harness/test_shared_form_controls.py` enforces.
- The shell is `components/app-shell.tsx` with `sidebar-nav.tsx` (Work: Home, Runs, Approvals; Build: Experts, Workflows, Tools; System: Operations, Models, Settings).

## Entry Points

- **API:** `uvicorn --factory autobots.api.main:create_configured_app`. It turns inherited tracing off first and logs JSON lines with no access lines (`operations/logs.py`).
- **Worker:** `python -m autobots.operations.worker`.
  - It always runs `maintenance_step`: expiring approvals, evaluating routines, and `retention.apply_all` hourly.
  - `AUTOBOTS_WORKER_INFERENCE=enabled` adds `inference_step` (`goal_loop.process_next`).
  - It exits on a partial configuration: `AUTOBOTS_DATABASE_URL`, an absolute `AUTOBOTS_CONFIG_ROOT`, and the Supabase URL and service key (`operations/worker.py:284–323`).
- **Web:** `next start` in `apps/web`, or `make start-web` ([local app runbook](docs/engineering/runbooks/local-app.md), `README-SETUP-RUN.md`).
- **Owner bootstrap:** `python -m autobots.operations.bootstrap_owner`.
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

- **Migrations:** `supabase/migrations/` holds 54 ordered files, from `20261105000001_workspaces.sql` to `20261114000054_runtime_cannot_delete_runs.sql` (US-14.17's Tavily and Jina providers and `app_private.tool_key_settings`, US-14.18's GitHub provider and saved values, US-14.19's `routines.removed_at` and `action_marked` approval rule, and R-17's revocation of the runtime role's DELETE on runs, run events, workspaces, members and profiles, after the analyzed revision), in the schemas `public`, `app_private` and `agent_runtime`. Since migration 35:

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

- **Seeds and bootstrap:** `supabase/seeds/reference.sql` is the repeatable model reference, and `supabase/bootstrap/` holds roles and Storage policies. The concept Experts and workflows are not in any seed or migration.
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
- **Schema readiness:** `application/operations.py` checks `REQUIRED_RELATIONS` and `REQUIRED_COLUMNS` (through migration 53), and compares `app_private.applied_migration_count()` with `SHIPPED_MIGRATIONS` in `application/schema_release.py`: fewer is `schema_behind` and blocks, more is `schema_ahead`, degraded and not blocking. A harness test (`tests/harness/test_app_db.py`) and `services/agent/tests/test_schema_release.py` fail unless that record matches `supabase/migrations`. Operations shows "N of M migrations applied" (`lib/schema-value.ts`). Changed by US-16.2, after the analyzed revision.
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
- **OpenRouter** is the only inference provider (`adapters/models/factory.py`, `openrouter_metadata.py`).
  - Profiles: `openrouter_terra`, `openrouter_sol` (`openai/gpt-6.1-sol`) and `openrouter_deepseek_flash`, in `domain/models.py`.
  - The client is built inside each attempt from a key resolved there, with at most 512 output tokens.
  - Every call is streamed.
  - `/v1/models` adds the listed prices per 1M tokens, the supported parameters and `fetched_at`.
- **GitHub, on one configured repository** (`GITHUB_REPOSITORY`):
  - `adapters/github_reads.py`: four read-only tools, `github_list_pull_requests`, `github_list_workflow_runs`, `github_search_issues` (pinned to the repository) and `github_read_file` (private content, at most 1,048,576 bytes).
  - `adapters/github_issues.py`: `create_github_issue` versions 1 and 2; v2 takes up to 10 labels.
  - `adapters/github_pulls.py`: `github_open_pull_request`. It waits for approval with a per-file diff (`review_detail`), opens `autobots/<operation_id>` with a marker, reads back before a retry, and stops with `base_moved`.
- **Tavily** (`adapters/tavily.py`): `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl`. Read-only, metered, with Tavily's inference options off.
- **Jina** (`adapters/jina.py`): `search_web`, `extract_website_content` (reader mode).
- **Market data** (`adapters/market_data.py`): `market_history` (Yahoo chart endpoint over `httpx`) and `inflation_rates` (World Bank `FP.CPI.TOTL.ZG`), both keyless.
- **Fetch guard:** `adapters/url_guard.py` admits only `https` URLs whose every DNS answer is global, revalidates up to 3 redirects, and caps size and time. `adapters/provider_http.py` reads a provider key per attempt. For Tavily and Jina, `application/tool_keys.py` resolves it from the run's workspace: the key saved in Settings, then the process environment, then the configuration root's `.env` files (US-14.17, after the analyzed revision). `make start` passes those two keys, the GitHub pair and an exact `enabled` browsing switch from the repository's `.env` through `scripts/tool_keys_env.py`. Since US-14.18 the GitHub adapters resolve their repository and token the same way, per attempt (`adapters/github_issues.py` `attempt_target`). The gateway refuses an approved write whose target now resolves differently, `approval_target_changed`. The worker binds `browse_goal` only when the run's workspace resolves the switch to `enabled`.
- **Browser:** `adapters/browser_executor.py` runs one hardened Chromium container per call behind `egress_proxy.py`, which allows only `CONNECT` to named hosts and gates DevTools with a token. `browser_page.py` reads pages over CDP.
- **Supabase:** Auth, Storage and PostgREST, self-hosted and loopback-bound.
- **MCP:** `langchain-mcp-adapters` is pinned but not imported under `src/`.
- **Tracing:** `forbid_remote_tracing` turns inherited LangSmith and OTLP settings off.

## Authentication and Authorization

- **Browser to web:** an HttpOnly SameSite=strict session cookie (`lib/session.ts`), with host, origin, fetch-site and CSRF checks (`lib/request-guard.ts`). The BFF adds the internal token on the server.
- **Web to API:** `api/security.py` requires `X-Autobots-Internal` (constant-time compare) and a Bearer JWT (HS256, audience `authenticated`). Membership comes from `public.workspace_members` (`api/membership.py`).
- **Workspace selection:** `current_workspace` (`api/settings_routes.py`) uses a verified `X-Autobots-Workspace` header; without one it uses the user's only workspace and otherwise refuses with `403 workspace_required`. Since US-16.3, after the analyzed revision: `POST /api/workspace` (same origin, CSRF-checked, membership checked against the session) keeps the choice in the HttpOnly, SameSite=Strict `autobots.workspace` cookie (`lib/workspace-choice.ts`); `lib/bff.ts` and `lib/service-status.ts` send it as the header; sign-out deletes it; `components/workspace-chooser.tsx` in the account footer asks a member of several workspaces to choose, with no implicit default.
- **Owners:**
  - `require_owner` gates the owner routes: Expert writes, workflow draft writes, `/v1/operations/jobs`, retention changes, replays, policy reset, and others.
  - Workflow drafts are also owner-only in RLS.
  - Public signup is disabled ([local app runbook](docs/engineering/runbooks/local-app.md)).
- **Effects and approvals:**
  - `application/approvals.py` binds a proposal to its exact arguments before the wait.
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
  - After the skip link come New run (⇧⌘O, `new-run.tsx`) and Search (⌘K, `search-palette.tsx`).
  - `WaitingNotifier` polls every 4 s while `autobots.notify` is on and notification permission is granted.
- **Home:**
  - A greeting in the workspace's timezone, then "What should we work on?".
  - Needs you (pending approvals and `waiting_input` runs) and the five most recent runs (`home-activity.tsx`).
  - The composer has Model, Expert and Budget chips, preview chips (`GET /v1/run-preview`), and up to 5 text files of 1 MiB each as typed inputs.
  - `?new=1` focuses the goal.
- **Runs:**
  - `POST /v1/runs` admits atomically with idempotency receipts. It refuses with `503 not_ready`, when no key is usable, or for a budget outside `domain/budgets.py` or above the remaining daily cap.
  - `/v1/runs` returns the label, stop reason, plan progress, frozen profiles and ledger spend, with `group`, `q`, `profile` and keyset `cursor` filters and per-group counts.
  - `run-panel.tsx` opens under the list at `?run=<id>`. Its commands send the version it loaded.
  - `RunWorkspace` adds task markers, times from `plan_task_times`, wall seconds, used tools, `current_task_id`, and the metered-call count.
  - The controls are pause, resume, cancel, owner reconciliation of a call's charge, and Continue (a linked new run). Terminal runs don't resume.
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
  - `browse_goal` (`application/browsing_tool.py`) is registered only while `AUTOBOTS_BROWSER_EXECUTOR=enabled` and the executor's qualification is current. It is approved on every call and runs the read-only loop in `browsing_loop.py` on the `researcher` route.
  - Every gateway dispatch writes a `tool_uses` row, and the API serves `GET /v1/runs/{id}/tool-uses`.
  - `/v1/tools/{id}/grants` lists the Experts and published workflows using a tool. The Tools page has group counts and a filter. Since US-14.20, after the analyzed revision, choosing a tool opens a native `dialog` modal (`components/tool-catalog.tsx` `ToolDialog`). It holds each tool's What, When and Why guide (`domain/tool_guides.py`, exposed as the descriptor's `guide`), its inputs and outputs, Granted to and Copy schema.
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
  - One draft per workflow, which an owner can save, publish or discard. Executions and routines refuse `"draft"` with `draft_not_runnable`.
  - The list gives the Experts, step count, last execution and run count, with `/executions` and `/preview`.
  - Executions accept a D11 budget.
- **Concept seed:** `operations/concept_seed.py` creates five Experts and six workflows through the application layer, as the owner. Since Decision 0023 E7, after the analyzed revision, Market watcher and Research analyst also get `publish_artifact`. Since E8, `goal_loop.SYSTEM_PROMPT`, the goal's opening and `PlanTask.criteria`'s description say a plan cites criterion IDs only.
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
  - `GET /v1/operations/jobs` (owner) returns 24 hourly buckets from `run.status_changed` events, which `jobs-chart.tsx` renders with a legend, tooltip and disclosed table.
  - Logs are redacted JSON lines, and retention is per workspace (`GET /v1/retention` for any member).
- **Search:** `GET /v1/search?q=` (`application/search.py`) returns up to five each of runs by goal and of Experts and workflows by name, scoped to the workspace in SQL, plus catalog tools. The palette is a modal combobox over a listbox using `aria-activedescendant`.
- **Appearance:**
  - System, Light and Dark (`theme-provider.tsx`, `enableSystem`, dark by default).
  - The before-paint script in `app/layout.tsx` applies `data-serif`, `data-density`, `data-motion` and `data-stream` from `autobots.*` keys.
  - `globals.css` adds `--document`, compact `--spacing: 0.2rem`, and a forced reduced-motion rule.
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
- **Selections:** since R-01, after the analyzed revision, `scripts/suites.py` names every step's tests: web and API-client unit tests by glob, the db and operations qualifiers, the Playwright filters, and the manual files with their reasons. `tests/harness/test_suite_claims.py` fails on a test file nothing runs. `make check-fast` and `make check-full` run those profiles; `.githooks/pre-commit` is opt-in.
- **`db`:** disposable targets for `disposable_db`, `supabase_stack`, `app_db`, `qualify_identity` (including `tests/db/*_check.py` such as `result_stream_check`, `task_timing_check`, `pull_request_check`, `concept_seed_check`) and `qualify_persistent_apply`.
- **`operations`:** `qualify_operations`, `qualify_backup`, `qualify_upgrade`, on disposable projects with a scripted model.

**Browser specs.** This mapping of the 38 spec files is inferred from the Playwright filters in `scripts/`:
- 33 run through `qualify_identity.py`: 22 in the main list, 3 by title (`qualification`, `saved-choice`, `readiness`) and 8 `slice*`.
- 3 run through `qualify_web.py`: `appearance`, `boundary`, `tools`.
- `release-latency` runs only under `qualify_release.py --ui`.
- `install.spec.ts` runs by hand, and `install-current` through `persistent_install.py screens`.

**In no profile:** `qualify_worker_inference.py`, `qualify_github_connector.py` (`--suite studio`, review then apply, ledger-capped), `qualify_browser_executor.py`, `qualify_browse_goal.py`, `browse_trial.py`, `qualify_mac_sleep.py`, `qualify_release.py`, `live_goal.py`, and `tests/toolchain` other than its offline modules. `scripts/suites.py` lists the manual test files with their reasons.

**Evidence and hooks.** `scripts/evidence.py` checks records for consistency, not correctness. The hook fixtures are in `tests/harness/test_hooks.py`. Hooks are configured but not qualified ([Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md)).

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

Start, drain and stop are in [the operations runbook](docs/engineering/runbooks/operations.md) and `README-SETUP-RUN.md`. The other runbooks in `docs/engineering/runbooks/` are `backup-restore`, `upgrade`, `mac-sleep`, `local-supabase`, `local-app`, `first-slice`, `toolchains`, `development-harness` and `ohmyorch-delivery`.

## Conventions

- Stable `SP-*`, `EPIC-*`, `US-*` and requirement IDs. Code comments cite their source IDs, such as `PRD-Studio ST-01` and `Decision 0022 D5`.
- Routine delivery follows the OpenSpec lifecycle, and the archived change is the record ([Decision 0003](docs/engineering/decisions/0003-openspec-only-delivery.md)). Each `verification.md` ends with a "Not established" line.
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
- `check_run_intent` (`api/settings_routes.py:296`) calls run admission "a later story".
- `docs/engineering/runbooks/mac-sleep.md` doesn't name `sleep_counted_as_work`.
- `services/agent/pyproject.toml:4` still says "minimal non-feature scaffold".
- `README-QA.md` describes revision `ecb34900e46c`.

Hooks are guardrails, not OS confinement ([the harness runbook](docs/engineering/runbooks/development-harness.md)).

## Upstream evidence and local constraints

- `.claude/autobots.json` pins OhMyOrch at `fddfbf53…` for the spec-ingestor and `9f384fa9…` (branch `openspec-only`) for the delivery plugin. The ignored clone's HEAD is `9f384fa`, and the plugin reports version 0.0.1.
- The same file records assistant event delivery as `not_tested`, and the plugin's as `not_qualified_one_pretooluse_event_observed`.
- No local model runtime is part of the application. The `research/` material is historical.

## Gaps and evidence limits

- Passing any profile proves those checks only, not H1, product acceptance or anything about a persistent stack.
- No independent review ran on EPIC-14 or EPIC-15 stories (Decision 0003). Their scenarios were observed by the delivering session.
- `SPECS.md`, `CODEBASE.md`, work items and runbooks are excluded from the source fingerprint (`scripts/evidence.py`, `RECORD_FILES`). The US-12.8 binding predates 59 commits of source change.
- Raw reports under `.checks/`, including the US-15.16 qualification files, are ignored and local.

## Evidence Paths

- `services/agent/src/autobots/domain/models.py`: profiles, offered set, binding sources, output cap.
- `services/agent/src/autobots/adapters/loop_middleware.py`, `application/goal_loop.py`, `application/model_attempts.py`: admitted, streamed calls.
- `services/agent/src/autobots/adapters/result_stream.py`, `api/event_routes.py`: NOTIFY tap and live SSE frames.
- `services/agent/src/autobots/adapters/github_reads.py`, `github_issues.py`, `github_pulls.py`: GitHub tools.
- `services/agent/src/autobots/adapters/tavily.py`, `jina.py`, `market_data.py`, `url_guard.py`, `browser_executor.py`, `egress_proxy.py`: other integrations.
- `services/agent/src/autobots/application/operations.py`, `api/operation_routes.py`: readiness, values, jobs chart.
- `services/agent/src/autobots/api/settings_routes.py:46–70`, `api/membership.py`, `apps/web/lib/bff.ts`: workspace and owner resolution.
- `services/agent/src/autobots/operations/concept_seed.py`, `operations/worker.py`: entry points.
- `services/agent/src/autobots/application/search.py`, `domain/budgets.py`, `domain/workflows.py`: search, budgets, workflow IR.
- `supabase/migrations/20261107000036_…` to `20261108000049_applied_migration_count.sql`: schema since the last refresh.
- `contracts/generated/openapi.json`: 66 `/v1` paths.
- `apps/web/components/` (`search-palette.tsx`, `new-run.tsx`, `waiting-notifier.tsx`, `jobs-chart.tsx`, `run-panel.tsx`, `settings-nav.tsx`, `sidebar-nav.tsx`, `appearance-control.tsx`), `apps/web/app/layout.tsx`, `apps/web/app/globals.css`: Studio surfaces.
- `scripts/verify.py`, `scripts/qualify_identity.py:276–335`, `scripts/qualify_web.py:169`, `scripts/harness_lib.py`: verifier and browser-spec mapping.
- `openspec/changes/archive/2026-11-07-us-14-*/`, `2026-11-08-us-15-*/verification.md`: per-story records (pointers only).
- `docs/engineering/decisions/0019-sol-profile-and-browser-use.md`, `0022-studio-product-surfaces.md`: paid authority, Studio scope.
- `docs/engineering/evidence/US-10.2/`, `US-12.8/`, `US-12.6/`: release record, Gate 0 binding, install.
- `Makefile`, `README-SETUP-RUN.md`, `.env.example` (variable names only), `.claude/autobots.json`.

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
