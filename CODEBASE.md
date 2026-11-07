# Autobots codebase context

**Inspected:** 2026-11-06. **Scope:** descriptive inventory of what the repository currently is. This file supplies no product requirements.

Analyzed revision: 4315944bf8dc34300360e4a4cec2cf8c3937e7b6
Working tree: dirty. Modified: `.env.example`. Untracked and not described here: `README-QA.md`, `docs/diagrams/`, `docs/engineering/evidence/DOC-QA-001/`, `docs/engineering/work-items/DOC-QA-001.md`.

## System Summary

The repository holds product PRDs, a source-traceable backlog, local delivery and verification tooling, and a local application: a Next.js web app, a FastAPI API, a Python worker running goals through Deep Agents and LangGraph, self-hosted Supabase in Docker, and inference through OpenRouter only. `SPECS.md` has 13 epics and 64 stories: 62 `DONE` and 2 `BLOCKED` (US-13.1 and US-13.2, each with an `External:` dependency on the owner scheduling it).

The worker claims and runs admitted jobs only when `AUTOBOTS_WORKER_INFERENCE=enabled`; by default it does maintenance only. That path has run on fake transports, on disposable stacks with a real provider, and on one persistent install on this Mac, which its latest record leaves stopped.

[The US-10.2 release record](docs/engineering/evidence/US-10.2/summary.md) reads H1 as "met, with its stated limits" and product acceptance as "supported by this record, with the limits the owner accepted", leaving release to the owner. Passing a verification profile establishes neither.

## Repository Map

- **Intent:** `PRD-*.md` and `SPECS.md`, mapped through `.claude/autobots.json`. `docs/engineering/option-b-contract.md` is the technical contract.
- **Source:**
  - `services/agent/src/autobots/`: Python service.
  - `apps/web/`: Next.js.
  - `packages/api-client/src/runtime.ts`: client runtime.
  - `supabase/migrations/`, `supabase/seeds/`, `supabase/bootstrap/`: SQL.
  - `infra/`: Compose, including a vendored Supabase release in `infra/supabase/upstream/`.
- **Generated:** `contracts/generated/openapi.json`, `packages/api-client/src/generated.ts`, `packages/db-types/src/generated.ts`. Backlog navigation in `SPECS.md` is also generated.
- **Tests:** `services/agent/tests/` (24 test modules plus a fake OpenRouter), `apps/web/tests/` (25 browser specs, 2 unit tests), `packages/api-client/tests/`, `tests/harness/`, `tests/db/`, `tests/web/`, `tests/faults/`, `tests/toolchain/`, `tests/qualification/`. `contracts/fixtures/` holds shared cases.
- **Tooling:** `scripts/`, with `.claude/` (agents, skills, rules, hooks, `settings.json`).
- **Delivery records:** `openspec/` (63 archived changes, 63 specs, `delivery/goal.md`), `SPEC-LOGS/`, `.claude/ohmyorch/project.json`.
- **Engineering records:** under `docs/engineering/`: `decisions/` (0001 to 0014), `runbooks/` (10), `evidence/`, `work-items/` (12 tracked), `templates/`, `prerequisite-inventory.md`.
- **Design:** `docs/design/luma.css` and concept art in `docs/imagine/`.
- **Research:** `research/`. `research/upstream/` is ignored and isn't repository input.
- **No CI:** `.github/` has no tracked files, and no other CI configuration was found at the top level.

## Runtime and Tooling

Probed with `--version` on 2026-11-06, on this Mac. Presence isn't qualification.

- **Probed tools:** Python 3.12.16, uv 0.13.6, Docker 29.9.2, Supabase CLI 2.98.2, OpenSpec 1.13.2, jq 1.7.1-apple, Bash 3.2.57, Claude Code 2.1.314.
- **Node:** the shell default is 26.13.0. The repository pins 22.23.2 (`.node-version`, `package.json`), and `scripts/toolchain.py` selects it per process. pnpm 12.16.1 is pinned through Corepack.
- **Python service:** `services/agent/pyproject.toml` requires `==3.12.*` and uses `uv.lock`. It pins `deepagents` 0.7.32, `langgraph` 1.2.19, `langgraph-checkpoint-postgres` 3.2.0, `langchain` 1.4.8, `langchain-openrouter` 0.2.9, `openrouter` 0.11.46, `fastapi` 0.162.0, `psycopg` 3.3.8 and `cryptography` 50.0.2. Dev tools are ruff, mypy (strict) and pytest.
- **Web:** `apps/web/package.json` pins Next 16.4.5, React 19.3.1, TypeScript 6.0.3, Tailwind 4.3.4, `@supabase/ssr` 0.12.7, Playwright 1.64.1 and axe. `pnpm-lock.yaml` is the lock.
- **Infrastructure:** `infra/disposable/compose.yaml` pins images by digest. `infra/supabase/compose.overlay.yaml` binds gateway and database to `127.0.0.1` and puts Realtime, Edge Functions and Supavisor in a `removed` profile.

## Architecture

Layers under `services/agent/src/autobots/`:

- **`domain/`:** pure rules.
  - `models.py`: two approved profiles, 14 roles, the policy order, `OFFERED_FOR_NEW_RUNS`.
  - `runs.py`: run states and commands.
  - `tools.py`: operation classes and tool grants.
  - `workflows.py` and `workflow_execution.py`: the workflow subset and readiness.
  - `routines.py`, and `execution.py`: the versions a run records.
- **`contracts/`:** public Pydantic DTOs, the source of OpenAPI. `persistence/rows.py` holds row helpers.
- **`application/`:**
  - Admission: `runs.py`.
  - Goal loop: `goal_loop.py`, `plans.py`, `run_usage.py`, `verification.py`, `recovery.py`, `compaction.py`.
  - Model spend: `model_admission.py`, `model_attempts.py`, `worker_inference.py`.
  - Tools: `tool_gateway.py`, `tools.py`, `reconciliation.py`, `approvals.py`.
  - Product surfaces: `experts.py`, `assignments.py`, `workflows.py`, `workflow_runner.py`, `routines.py`, `memory.py`, `improvements.py`, `artifacts.py`, `run_projection.py`.
  - Local operations: `operations.py`, `retention.py`, `worker_leases.py`, `provider_settings.py`, `credentials/`.
- **`adapters/`:**
  - `loop_middleware.py`: limits and admission around every dispatch.
  - `tool_middleware.py`: answers tool calls from the gateway.
  - `checkpoints.py`, `object_storage.py`, `github_issues.py`.
  - `models/`: catalog, client factory, OpenRouter metadata.
- **`api/`:** the factory in `app.py`, the configured entry in `main.py`, 12 route modules, and safe errors. `contracts/generated/openapi.json` lists 48 paths under `/v1`. Artifact download and the event stream are outside the schema.
- **`operations/`:** the worker, structured logs, owner bootstrap, route qualification and the reasoning trial.

**The model path.** `goal_loop.py` builds the graph with `create_deep_agent`, wrapping the client in `AdmittedModel`, which refuses any call outside an admitted dispatch, so an SDK-initiated call can't spend unseen. `LoopMiddleware` in `adapters/loop_middleware.py` does the following for each dispatch:

- Rechecks ownership, parent status and active time.
- Consumes the root's `model_calls` limit.
- Bounds a call at 120 seconds and interrupts it on cancel.
- Compacts the model's view, with summaries through the same admission.
- Allows one shorter retry after a `length` cut-off.
- Records reply facts with no message content.
- Reserves the route's worst case plus an amount for prompt bytes beyond the assumed 32,000 tokens.
- Stops with `cost_unavailable` if a request could reach a higher long-prompt tier, or if a fresh catalog price exceeds what was reserved (the latter check is in `worker_inference.py`).
- Stops with `request_unencodable` on text that can't be encoded.
- Reconciles a late reply on a lost lease as `source="provider"`.

**Uncertain calls.** When a call's failure class is uncertain, `_log_uncertain` writes a `worker.call_uncertain` WARNING to the worker's log. It holds the shortened invocation and run, the failure class, the exception's and cause's type names, any HTTP status, and a `reason` of `call_time_limit` or `run_interrupted`. It holds no message text and no charge, there is no column for it, and no screen shows it ([Decision 0014](docs/engineering/decisions/0014-release-limits-accepted.md)).

**Routes.** All 14 role bindings resolve and freeze at admission, and a run dispatches through its `executor` binding. A `summarizer` binding that differs pauses a run needing compaction with `route_not_bound` ([Decision 0009](docs/engineering/decisions/0009-release-scope-from-blocking-findings.md)).

**Ownership.** `worker_leases.py` claims jobs by database time with a rising generation, and triggers from `20261105000008_worker_ownership.sql` refuse checkpoint writes from any other generation. `WakeClock` detects a real sleep from two clocks. `goal_loop._keep_lease` reconnects after a dropped connection, revives an unclaimed lease after a wake, and discounts time asleep through `run_usage.discount_sleep`, deliberately uncapped by the database clock ([US-12.5](docs/engineering/evidence/US-12.5/summary.md)).

**Web.** `apps/web/app/` holds the pages. Same-origin BFF routes under `app/api/` forward through `lib/bff.ts`. `packages/api-client` is the generated client. Form controls come from `components/ui/field.tsx`, which `tests/harness/test_shared_form_controls.py` enforces.

## Entry Points

- **API:** `uvicorn --factory autobots.api.main:create_configured_app`. It turns inherited tracing off first. uvicorn's own lines go through the JSON format, and access lines aren't logged (`operations/logs.py`).
- **Worker:** `python -m autobots.operations.worker`.
  - It always runs `maintenance_step`: expiring approvals, `evaluate_routines`, and `retention.apply_all` hourly.
  - `AUTOBOTS_WORKER_INFERENCE=enabled` adds `inference_step`, which calls `goal_loop.process_next` with `InferenceSource.bind`. The worker refuses to start half configured.
  - `_drive` routes a workflow's run to `workflow_runner.run_workflow`.
- **Web:** `next start apps/web` ([local app runbook](docs/engineering/runbooks/local-app.md)).
- **Owner bootstrap:** `python -m autobots.operations.bootstrap_owner`.
- **Paid operations modules:** `operations/route_qualification.py` and `operations/reasoning_trial.py`.
- **Install and data:** `scripts/persistent_install.py` (`init`, `up`, `setup`, `status`, `apply`, `goal`; `reset` and `apply --reset` exist only to refuse), `scripts/local_backup.py` (`keygen`, `backup`, `restore`, `verify`).
- **Verification and generation:** see [Common Commands](#common-commands).
- **Paid or real-world runners, in no profile:** `scripts/live_goal.py`, `scripts/qualify_release.py`, `scripts/qualify_github_connector.py`. `scripts/qualify_mac_sleep.py` needs a person to sleep the Mac.
- **Hooks:** `.claude/hooks/dispatch.py`, for `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop` and `SubagentStop` in `.claude/settings.json`.

## Data and Persistence

- **Migrations:** `supabase/migrations/` holds 35 ordered files, `20261105000001_workspaces.sql` to `20261106000035_charge_source.sql`, in the schemas `public`, `app_private` and `agent_runtime`. The newest two:
  - `20261106000034_route_limits_from_review.sql` appends stored limits text to `agent_runtime.route_qualifications`: concurrent admission on a live route wasn't tested, and per profile, one real goal repeated on disposable stacks went 0 of 5 for DeepSeek and 5 of 5 for Terra.
  - `20261106000035_charge_source.sql` adds nullable `app_private.model_invocations.charge_source`, checked to `provider` or `owner`. `ModelAdmission.reconcile` writes it. `RunInspector`'s `ModelCallView` exposes `reconciled`, `outcome_unknown` and `charge_source_unknown`.
- **Seeds and bootstrap:** `supabase/seeds/reference.sql` is the repeatable model reference. `supabase/bootstrap/` holds roles and Storage policies.
- **Public tables:** workspaces and members, runs and `run_events`, `artifacts`, `approval_requests`, Experts and versions, `sessions`, workflows with versions, executions, node instances and emissions, routines with versions and occurrences, `memory_items`, improvement and knowledge tables, `model_profiles`.
- **Private tables:** jobs, goal specs, plans, usage, verifications, `model_invocations`, `tool_receipts`, assignments, credentials, policies and spend limits, idempotency receipts, heartbeats, retention, `installation_holds`.
- **`agent_runtime`:** LangGraph checkpoints, `adapter_qualifications`, `route_qualifications`.
- **Schema readiness:** `application/operations.py` checks required relations and also `REQUIRED_COLUMNS`, including `charge_source`, so a column-only migration not yet applied reads as a schema problem and gates admission.
- **Install-only schema:** `autobots_install`, holding identity and applied-migration digests (`scripts/persistent_install.py`). [US-12.6](docs/engineering/evidence/US-12.6/summary.md) records 36 history rows: 35 migrations and the Storage policies.
- **Objects and files:**
  - Artifacts are in private Supabase Storage through `adapters/object_storage.py`.
  - Provider keys are AES-256-GCM sealed under a master key file (`application/credentials/`).
  - Backups are cold and encrypted, with a signed manifest, and restore only into a new held disposable project.
  - The shared spending ledger is `.checks/decision-0009/ledger.json` (ignored).
  - The install's record, secrets and logs are recorded at `~/.local/share/autobots-install` by [the operations runbook](docs/engineering/runbooks/operations.md); this analysis didn't read them.

## Integration points

**Internal.**
- `.claude/autobots.json` maps documents, the verifier report and upstream pins. `.claude/ohmyorch/project.json` activates OhMyOrch.
- `scripts/specs.py` (`validate`, `render`, `promote`) checks structure, sources, Gherkin, statuses and dependencies. It can't prove semantic entailment.
- `scripts/generate_contracts.py` (`write`, `check`) generates OpenAPI and the TypeScript client offline. `scripts/app_db.py types` generates row types for `public`.

**External.**
- **OpenRouter:** the only inference provider, through `adapters/models/factory.py` and `openrouter_metadata.py` (key check and real catalog fetch). Profiles are `openrouter_terra` and `openrouter_deepseek_flash`. A client is built inside each attempt from a key resolved there, and requests ask for at most 512 output tokens.
- **GitHub:** `adapters/github_issues.py`, tool `create_github_issue`, one operation on one configured repository, granted per Expert ([Decision 0007](docs/engineering/decisions/0007-first-connector-github-issues.md)). Readback waits up to 15 seconds, after one measured lag of about 9 seconds.
- **Supabase:** Auth, Storage and PostgREST, self-hosted and loopback-bound.
- **MCP:** `langchain-mcp-adapters` is pinned but not imported under `src/` (grep), and the release record says no MCP adapter exists.
- **Tracing:** `forbid_remote_tracing` turns inherited LangSmith and OTLP settings off.

## Authentication and Authorization

- **Browser to web:** an HttpOnly, SameSite=strict session cookie (`lib/session.ts`), with host, origin, fetch-site and CSRF checks in `lib/request-guard.ts`. The BFF adds the internal token on the server.
- **Web to API:** `api/security.py` requires `X-Autobots-Internal` (compared in constant time) and a Bearer JWT verified as HS256 with audience `authenticated`. Membership comes from `public.workspace_members` (`api/membership.py`). Client-supplied user or workspace IDs aren't trusted.
- **Owners:** owner-only routes include Expert writes. A non-owner naming an Expert version gets `403 owner_required` ([Decision 0011](docs/engineering/decisions/0011-review-dispositions.md)). Public signup is disabled ([local app runbook](docs/engineering/runbooks/local-app.md)).
- **Effects:** `application/approvals.py` binds a proposal to its exact arguments before the wait. Effect rulings must carry the receipt's `generation`, and a stale one is refused.
- **Approval record (US-13.1, after this analysis):** migration `20261107000036_approval_requester_scope_policy.sql` adds `runs.started_by` and, on `approval_requests`, `requested_by`, `requested_by_agent`, `scope_snapshot`, `policy_version` and `policy_rule`. A trigger refuses any later change to them. `admit_run` takes an explicit `started_by`, a child copies its parent's, and a routine's run has none. The gateway stores `APPROVAL_POLICY_VERSION` (`approval-policy/1`), and the inbox shows all three, or not recorded on older requests ([Decision 0015](docs/engineering/decisions/0015-approval-request-fields.md)).
- **Held-out replay (US-13.2, after this analysis):** migration `20261107000037_improvement_replays.sql` adds `app_private.improvement_replays` and `improvement_replay_runs`. `POST /v1/improvements/{id}/replay` (owner-only) admits each owner-written task as an ordinary run with the proposal applied to it alone: a skill in its instructions, a memory in its `search_memory` results. `decide` refuses promotion with `replay_required`, `replay_running` or `replay_failed` until every run of the latest replay succeeded. Text cases became optional. `tests/db/improvement_check.py` now runs in `scripts/qualify_identity.py`, because replay runs are verified from Storage ([Decision 0016](docs/engineering/decisions/0016-held-out-replay.md)).
- **Accepted single-owner limits:** memory is scoped to the workspace, not to a user (Decision 0009). `authenticated` can read raw emissions within a workspace, and a rollback's actor and a promoted memory's `created_by` aren't recorded ([Decision 0013](docs/engineering/decisions/0013-release-closure.md)).

## Current capabilities

- **Screens:** Home, Runs, Run, Run inspector, Experts and editor, Sessions, Workflows, editor and monitor, Approvals, Operations, Settings, Models, Sign-in. Routines, memory and improvements have API routes and no screens (Decision 0009).
- **Runs:**
  - `POST /v1/runs` admits atomically with idempotency receipts and refuses when not ready (`503 not_ready`) or with no usable key.
  - `components/run-controls.tsx` exposes pause, resume, cancel and owner reconciliation of a model call's charge.
  - `components/continue-run.tsx` starts a linked new run. With `goal_text` omitted, the server repeats the stored goal, and `RunWorkspace.can_continue` says whether a run qualifies. Terminal runs don't resume.
  - A rate limit or provider error ends a run after its retries (Decision 0011).
- **New-run model choice:**
  - `OFFERED_FOR_NEW_RUNS` is Terra alone, by Decision 0013. DeepSeek stays approved in `PROFILES`, the seed and the catalog list, where `ModelAvailability.offered` is false.
  - New work naming it is refused with `model_not_offered` and no substitute: `422` when the request names it, including Experts and settings; `409` for a saved choice or a workflow; `RoutineRefused` for a routine. A workflow is checked only if it needs a model. `/v1/runs/intent` returns the same code.
  - A run already admitted keeps its frozen route, so `worker_inference.py` can still serve one.
  - The web panels keep a saved choice visible and unselectable.
- **Goal execution:** versioned plans and evidence, required artifacts, verification from artifacts and checks, staged and verified artifact publication, cursor replay and a live event stream.
- **Tools:** plan tools, `calculate`, `read_run_file`, `save_artifact`, `publish_artifact`, `search_memory`, and optionally `propose_improvement`, `create_github_issue` and the provider tools below. `assign_specialist` is for coordinator sessions only. Receipts are in `app_private.tool_receipts`.
- **Tool catalog (US-14.1, after the analyzed revision):** `application/tool_catalog.py` derives descriptors from the worker's registry, and `GET /v1/tools`, `/v1/tools/{tool_id}` and `/v1/tools/{tool_id}/versions/{version}` serve them to members. Availability is computed per request from whether key variables are set. `browse_goal` is catalogued as `disabled_by_policy` and never registered.
- **Tools screen and group grants (US-14.2, after the analyzed revision):** `/tools` and `/tools/{tool_id}` in the web app, with a sidebar entry before Settings. Expert configs carry `tool_groups`, which a save expands into explicit tools, and a save naming an unavailable tool is refused `expert_tool_unavailable`.
- **Tool-use record (US-14.3, after the analyzed revision):** `app_private.tool_uses` (migration 38) holds one row per gateway dispatch, denials included, with the served plan task, public fields, digests and sizes. `tool.use.started` and `tool.use.completed` join the event union. `GET /v1/runs/{run_id}/tool-uses` lists a run or a root's tree. A root run tree may make 20 metered tool calls.
- **Tool-use views (US-14.4, after the analyzed revision):** the run workspace's Tools used and the workflow monitor's Tool uses by node read the listing; migration 39 records each use's workflow node instance.
- **Tool-provider keys (US-14.5, after the analyzed revision):** `adapters/provider_http.py` reads a provider's key per attempt for that attempt's HTTP client only. Run creation through a session and routine occurrences are refused `tool_unavailable` when a granted tool's key is missing. Log redaction and the evidence scan recognize Tavily, Jina and GitHub key shapes.
- **URL guard (US-14.8, after the analyzed revision):** `adapters/url_guard.py` admits only `https` URLs whose every DNS answer is globally routable, revalidates each redirect (at most three) and caps size and time, with typed refusals.
- **Tavily tools (US-14.6, after the analyzed revision):** `adapters/tavily.py` registers `tavily_search`, `tavily_extract`, `tavily_map` and `tavily_crawl`, read-only and metered, Expert-grantable, with Tavily's inference options always off. Tested with fake transports only.
- **Specialists:** `application/assignments.py` runs child runs synchronously, with scope intersected from the parent and spend counted on the root.
- **Unknown effects:** these stay visible until a tool's readback or an owner's report resolves them.
- **Workflows:** a typed subset, immutable versions, a run bound to version and hash, and insert-only emissions.
- **Routines:** explicit, with immutable versions, admitted with a unique key by the maintenance step when readiness allows.
- **Memory and learning:** lexical search in Postgres, and proposals through regression and an owner's review with rollback. A promoted skill reaches a new run's instructions as reference (`experts.py`, `improvements.py`). Promotion gates on a reviewer's text checks (Decision 0011).
- **Operations:** the status page reports database, schema, Storage, disk, queue, delayed routines, catalog availability, restore history and each route's qualification. Logs are redacted JSON lines. Retention is per workspace.
- **Evidence-limited behavior:** the inspector reads typed columns and checkpoint metadata (ID, parent, step, source), never checkpoint content, tool arguments or partial output (`run_projection.py`).
- **Design:** Luma tokens, dark by default, with `components/theme-provider.tsx`. Eight named surfaces, such as charts and a workflow canvas, don't exist in the app, and the owner confirmed reading the requirement as not reaching them yet ([US-10.2, DS-03](docs/engineering/evidence/US-10.2/summary.md#ds-design-system)).

## Product implementation status

What has run how. These classes aren't interchangeable, and later code doesn't inherit earlier live results. Most live evidence predates US-12.8's bound fingerprint `51212ae1…`, and **nothing live ran at that fingerprint** ([record](docs/engineering/evidence/US-10.2/summary.md#revisions)).

| Class | What ran | Result and limit |
|---|---|---|
| Fake transport under the real SDK | `services/agent/tests`, `scripts/qualify_worker_inference.py` on a disposable stack | 55 of 55 cases at the bound fingerprint. Credential failures, catalog outages and compaction through the worker are mock-level |
| Disposable stack, scripted model | `db` and `operations` profiles, [closing checks](docs/engineering/evidence/US-10.2/closing-checks.json), [the screen walk](docs/engineering/evidence/US-12.2/summary.md) | [US-12.8](docs/engineering/evidence/US-12.8/summary.md): all exit 0. Closing checks: 12 of 12 cancels on running runs, at most 13.5 ms; a stream cut by TCP reset 4 times and rebuilt; 9 secrets found nowhere scanned |
| Real sleep, disposable stack, scripted model | [US-12.5](docs/engineering/evidence/US-12.5/summary.md) | 988 s across 20 wakes ended `succeeded`, at `05916d5e…`. An earlier attempt found a defect, since fixed. No real provider across a sleep |
| Live, direct | [US-3.4](docs/engineering/evidence/US-3.4/summary.md), US-7.2 against GitHub, US-11.2's reasoning trial | No worker or ledger around them. Terra's reasoning `id` is removed by the pinned SDK, accepted in Decision 0013 |
| Live, disposable stack | [LIVE-GOAL-1](docs/engineering/evidence/LIVE-GOAL-1/summary.md), [US-10.1](docs/engineering/evidence/US-10.1/summary.md), [US-12.4](docs/engineering/evidence/US-12.4/summary.md) | One repeated goal: Terra 5 of 5, DeepSeek 0 of 5. Corpus: 104 of 120 (86.7%), scored by string checks on an assistant-written corpus. Two calls at once: 9 of 10 goals, and **one of five rounds paused as `uncertain_acceptance` with no known cause** |
| Persistent install | US-11.3 and [US-12.6](docs/engineering/evidence/US-12.6/summary.md) | Compose project `autobots-install`, gateway `127.0.0.1:55321`, database `55322`, API `8001`, web `3000`. Two real goals in total, both succeeded, on Terra. Recorded stopped, data kept, at migration 35 of 35, at `05916d5e…` |

**Release record ([US-10.2](docs/engineering/evidence/US-10.2/summary.md)).**
- It maps LC, MP, LM, DS and DH items to evidence or a decision, and says nothing mandatory is open.
- It states that partial rows stand on owner decisions and don't meet their text, and that PRD 13.1's stability target is "not met, not revised, accepted as a limit".
- Open in substance:
  - The owner's call on whether to release.
  - The pause's cause stays unexplained, and `worker.call_uncertain` hasn't caught a real one.
  - No person new to the app has used it, and no person has judged task quality.
  - No screen reader has been used.
  - No real network loss or real provider across a sleep has been observed.
  - Docker or Mac restart wasn't run.
- EPIC-13 waits for the owner to schedule it.
- PRD 12.2's timing metrics are later scope, and routine screens are later scope.

**Spending.** The shared ledger read US$0.315650 of US$1 after US-12.6, including US$0.25 held from US-12.4's paused round. [Decision 0014](docs/engineering/decisions/0014-release-limits-accepted.md) says the authority for paid calls and persistent changes has ended.

## Tests and Quality Gates

`scripts/verify.py` has five profiles and exits 0 passed, 1 a check failed, 2 unavailable. It never installs.

- **`harness`:** configuration, backlog validation, deterministic harness tests.
- **`fast`:** adds Python and web steps for what changed, and records the rest `not_run`.
- **`full`:** every static and unit step, `next build`, `contract_drift`, the fault qualification (`scripts/qualify_faults.py`), the toolchain scope test, and `qualify_web.py`.
- **`db`:** disposable targets for `disposable_db`, `supabase_stack`, `app_db`, `qualify_identity` and `qualify_persistent_apply`.
- **`operations`:** `qualify_operations`, `qualify_backup` and `qualify_upgrade`, on disposable projects with a scripted model.

Last recorded at [US-12.8](docs/engineering/evidence/US-12.8/summary.md), on 2026-11-06: `harness` 284 tests; `full` 24 checks, 554 Python tests and 32 browser tests; `db` 44, 18, 449, 447 and 29 cases; `operations` 69, 50 and 45 cases. Only `harness` was re-run for this document.

**Browser specs.** By this analysis of Playwright filters (inference from `scripts/`), of 25 spec files:
- 21 run through `qualify_identity.py`.
- 2 through `qualify_web.py`.
- `release-latency` runs only under `qualify_release.py --ui`.
- `install.spec.ts` runs by hand on the install.

**In no profile:** `qualify_worker_inference.py`, `qualify_mac_sleep.py`, `qualify_release.py`, `qualify_github_connector.py`, `live_goal.py`, and `tests/toolchain` other than its scope test.

**Evidence and hooks.** `scripts/evidence.py` (`fingerprints`, `validate`, `complete`, `record`) checks work-item records for consistency, not correctness. Hook script fixtures are in `tests/harness/test_hooks.py`. Hooks are configured and not qualified: nothing shows Claude's own crash, timeout or Stop recursion behavior ([Decision 0012](docs/engineering/decisions/0012-unqualified-hooks-in-h1.md)).

## Common Commands

```sh
python3.12 scripts/specs.py validate
python3.12 scripts/specs.py render
python3.12 scripts/verify.py --profile harness   # also fast, full, db, operations
python3.12 scripts/toolchain.py versions         # also lock, bootstrap, check
python3.12 scripts/generate_contracts.py check   # or write
python3.12 scripts/evidence.py fingerprints
python3.12 scripts/qualify_worker_inference.py
```

Start, drain and stop are in [the operations runbook](docs/engineering/runbooks/operations.md). Other procedures are in `docs/engineering/runbooks/`: `backup-restore`, `upgrade`, `mac-sleep`, `local-supabase`, `local-app`, `first-slice`, `toolchains`, `development-harness`, `ohmyorch-delivery`.

## Conventions

- Stable `SP-*`, `EPIC-*`, `US-*` and requirement IDs. Revisions keep IDs and are recorded in decisions.
- Routine delivery follows the OpenSpec lifecycle, with the archived change as its record ([Decision 0003](docs/engineering/decisions/0003-openspec-only-delivery.md), `.claude/rules/ohmyorch-delivery.md`). Final reviews and Gate 0 have fuller records under `docs/engineering/evidence/`.
- Money is integer micro-USD. Errors reach clients as typed codes. Logs carry exception type names, never messages, and identifiers are cut to eight characters.
- Pydantic owns public contracts and SQL owns schema. Generated files aren't hand-edited. Migrations and seeds are separate. Each migration is applied once and digest-checked on the install.
- Loopback-only ports, digest-pinned disposable images, and marked `autobots-disposable-*` projects for checks.
- Runners that a change under `scripts/` would void a binding for are kept beside their evidence, such as `docs/engineering/evidence/US-12.4/measure_two_calls.py`.

## Constraints and Technical Debt

Accepted limits, by decision:
- [Decision 0005](docs/engineering/decisions/0005-deepseek-strict-nested-unsupported.md): DeepSeek strict nested output is unsupported.
- [Decision 0008](docs/engineering/decisions/0008-us-10-1-limits-accepted.md): US-10.1's limits.
- [Decision 0010](docs/engineering/decisions/0010-contrast-pass-line.md): WCAG 2.1 AA as the pass line.
- Decision 0013: PRD 8.3's empty `inputs` grant, and routines reading policy and skill text at each occurrence.
- Decision 0014: active time can go uncounted in rare clock cases; a running step can send further paid calls during a drain; a page reload loses Continue's kept key, so a later press can start a second paid run.

Observed risks:
- A reservation's input size is a byte-based estimate, as no tokenizer is pinned.
- `charge_not_reported`, `cancelled_after_dispatch` and a call left by a cut drain emit no `worker.call_uncertain` (US-10.2).
- GitHub issue creation has no idempotency key, and a failure after acceptance can create a duplicate (Decision 0007).
- `input_manifest` in `scripts/harness_lib.py` hashes everything under `supabase/`, including git-ignored files. Run from this repository, even `supabase --version` writes `supabase/.temp/cli-latest`, which changes the source fingerprint and makes `scripts/evidence.py validate` fail until the file is removed. Observed once during this refresh.

Text in the repository that differs from the code or tree:
- `README.md` says implementation and release qualification remain pending, and calls the product unimplemented.
- `SPECS.md`'s `CODEBASE Context` line reads "development-harness work only, product unimplemented".
- `docs/engineering/runbooks/development-harness.md` counts 23 browser spec files; 25 are tracked.
- `application/run_projection.py:1` says nothing there reads checkpoints, while line 447 reads their metadata.
- `check_run_intent`'s docstring in `api/settings_routes.py` calls run admission a later story.
- `docs/engineering/runbooks/mac-sleep.md` doesn't name `sleep_counted_as_work`, which `scripts/qualify_mac_sleep.py` reports.
- `services/agent/pyproject.toml` still describes a "minimal non-feature scaffold".

Hooks are guardrails and not OS confinement. [The harness runbook](docs/engineering/runbooks/development-harness.md) lists Bash forms that get past the secret patterns.

## Upstream evidence and local constraints

- `.claude/autobots.json` records two OhMyOrch pins: `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07` for the spec-ingestor agent, and `9f384fa97ea9bf43d46c2a19770bb580697ccf14`, branch `openspec-only`, for the delivery plugin. The clone at `research/upstream/OhMyOrch` is ignored and its HEAD is `9f384fa`; `fddfbf5` is present in its history. The plugin reports version 0.0.1.
- The same file records assistant event delivery as `not_tested`, and the plugin's as `not_qualified_one_pretooluse_event_observed`.
- Local model research under `research/` is historical, per `README.md`. No local model runtime is part of the application.

## Gaps and evidence limits

- Passing `harness`, `fast`, `full`, `db` or `operations` proves those checks, not H1, product acceptance or anything about a persistent stack. The H1 reading belongs to the release record, and a later source change voids its binding.
- `SPECS.md`, `CODEBASE.md`, work items and runbooks are excluded from the source fingerprint (`scripts/evidence.py`, `RECORD_FILES`), as are evidence directories. `scripts/evidence.py validate US-12.8` passed at this refresh, so the source inputs matched `51212ae1…` then.
- US-10.1's figures predate EPIC-11 and EPIC-12 and stand by Decision 0014 without repetition. US-3.4, US-7.2 and LIVE-GOAL-1 predate later admission changes.
- Raw reports under `.checks/` are ignored and local, so committed summaries are what a reader of this repository can check.

## Evidence Paths

- [`docs/engineering/evidence/US-10.2/`](docs/engineering/evidence/US-10.2/summary.md): release record, three reviews, closing checks and their runner.
- [`docs/engineering/evidence/US-12.8/`](docs/engineering/evidence/US-12.8/summary.md): the current Gate 0 binding, manifest and reviews. US-12.3 and US-11.12 are replaced and kept as history.
- `docs/engineering/evidence/US-12.2/`, `US-12.4/`, `US-12.5/`, `US-12.6/`, `US-11.11/`: screen walk, two-call workload, real sleep, install, visual captures.
- `docs/engineering/evidence/LIVE-GOAL-1/`, `US-10.1/`, `US-3.4/`, `WORKER-INFERENCE-001/`: live and mock inference.
- `docs/engineering/evidence/README.md`, `docs/engineering/templates/`: the evidence contract.
- `docs/engineering/decisions/`: Decisions 0001 to 0014.
- `openspec/changes/archive/*/verification.md`: per-story records, mostly written by the session that built the story.
- `services/agent/src/autobots/adapters/loop_middleware.py`, `domain/models.py`, `operations/worker.py`, `application/worker_inference.py`, `application/goal_loop.py`: the inference path.
- `supabase/migrations/`, `contracts/generated/openapi.json`, `scripts/verify.py`, `scripts/harness_lib.py`: schema, public contract and verifier.

## Unknowns

- Whether the install is stopped and at migration 35 now. Records say so, and neither Docker nor its directory was inspected. `persistent_install.py status` would settle it.
- Why US-12.4's round 1 paused. The record calls it unexplained.
- Whether the OhMyOrch role identity and full lifecycle hold in a live session beyond what this delivery did, and what Claude does when a hook crashes or times out.
- Real behavior of provider credential validation against OpenRouter's own failures: MP-A02 and MP-A03 ran against a fake upstream.
- This refresh didn't re-read every module line by line. The descriptions of `recovery`, `approvals`, `memory`, `compaction`, `workflow_runner` internals, `retention` and `scripts/local_backup.py` rest on the prior inventory, with no contradicting change found in the diff. Reading them would settle it. The diffs of `improvements`, `model_attempts`, `reconciliation`, `reasoning_trial` and `route_qualification` weren't read.
