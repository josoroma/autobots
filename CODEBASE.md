# Autobots codebase context

**Inspected:** 2026-11-04. **Scope:** descriptive inventory; this file supplies no product requirements.

Analyzed revision: 5587a9f80ed1fcbed06e60e7105b948b6625ff85

This describes that revision, which includes the OhMyOrch delivery setup in [HARNESS-OHMYORCH-001](docs/engineering/work-items/HARNESS-OHMYORCH-001.md), US-1.1's inventory and five added cache ignore rules, US-1.2's rule mapping checks, derived `assistant_adapter` status and forward ingestion runbook, and US-1.3's locked toolchains and scaffold, plus the US-1.4 verification profiles and hook changes committed on top of it. The bullets added by each later delivered story describe that story's working tree, not a re-analysis of the whole repository, so this revision line is older than they are.

## System Summary

A repository of product PRDs, a source-traceable backlog, local tooling to plan, deliver and verify work, and a partial product application: the web app, the API, SQL migrations and the model layer below. It has run admission, and nothing runs a run yet.

## Repository Map

- `PRD-*.md`, `SPECS.md`: product and harness intent, and the execution backlog.
- `docs/engineering/`: technical contract, decisions, work items, runbooks and evidence. `prerequisite-inventory.md` there is the point-in-time inventory of repository assets and local tools.
- `docs/design/`, `docs/imagine/`: Luma tokens and generated interface concepts.
- `.claude/`: project skills, agents, rules, hooks and the document map in `autobots.json`.
- `scripts/`, `tests/harness/`: backlog tooling, harness verifier and their tests.
- `openspec/`, `SPEC-LOGS/`, `.claude/ohmyorch/`: OhMyOrch delivery state, per [Decision 0002](docs/engineering/decisions/0002-ohmyorch-delivery-loop.md).
- `research/`: research material. `research/upstream/` is ignored and not repository input.

## Runtime and Tooling

Observed on 2026-11-04, on this Mac. Presence is not qualification of an application environment.

- Python 3.12.16 at `/opt/homebrew/bin/python3.12`, used by project scripts and hooks.
- OpenSpec 1.13.2, jq 1.7.1, Bash 3.2.57 and Claude Code 2.1.314, used by OhMyOrch delivery.
- Node 26.13.0 is the shell default and 22.23.2 is under nvm; `scripts/toolchain.py` selects the pinned 22.23.2 per process. uv 0.13.6, Supabase CLI 2.98.2 and Docker 29.9.2 are present. pnpm is not installed globally; it runs repo-local through Corepack.

## Evidence Paths

- `scripts/verify.py` writes its local report to `.checks/<profile>/latest.json` (ignored).
- Reviewed summaries are under `docs/engineering/evidence/<work-item-id>/`.
- Work records are under `docs/engineering/work-items/`.

## Unknowns

- Whether the OhMyOrch role identity and full story lifecycle hold in a live session; upstream 0.0.1 lists these as unproven.
- Whether installed tool versions satisfy the toolchain US-1.3 will lock.

## Current capabilities

The workspace contains the research PRDs, historical model evidence and an Option B technical contract. The technical contract preserves SP-001–SP-021 at `docs/engineering/option-b-contract.md`; root `SPECS.md` now contains a source-traceable backlog with 10 epics, 42 stories and generated navigation.

The current adaptation adds project-local `.claude` skills, specialist agents, scoped rules, command-hook configuration, a standalone backlog validator/navigation renderer, and a deterministic harness verifier. They are development tooling, not a product API or worker. Verification details belong to the adaptation evidence record; code existence is not proof a check passed.

The design artifacts include `PRD-Design-System.md`, the user-supplied light/dark token definitions at `docs/design/luma.css`, and generated interface concepts with a local gallery under `docs/imagine`. The design source is mapped into the harness and frontend guidance. These files document shadcn Luma with dark as the default; they do not implement an app theme provider or qualify browser behavior.

## Product implementation status

The Next.js application, FastAPI service, LangGraph goal loop and application migrations and seeds exist, as the bullets below describe, and have run only on disposable stacks with a scripted model. No persistent project Supabase stack is configured. No worker has called a real model: by default the product worker runs maintenance only, and its inference step, off unless `AUTOBOTS_WORKER_INFERENCE=enabled`, has only run over a fake HTTP transport. No local model runtime is part of the selected design. Public OpenRouter catalog research does not establish authenticated live model qualification.

No application lockfile/toolchain qualification or persistent database operation has been performed by this harness adaptation. The `harness` profile is limited to the delivered development tooling. `fast` and `full` add the scaffold's static checks, tests and build. `db` runs synthetic fixtures on a disposable Docker target. `operations` runs `scripts/qualify_operations.py`, `scripts/qualify_backup.py` and `scripts/qualify_upgrade.py` on disposable Compose projects with a scripted model, which is disposable evidence and not H1, product acceptance or proof about a persistent stack.

## Integration points

- `.claude/autobots.json` maps source documents, backlog, technical contract and this inventory.
- `.claude/agents/autobots-spec-ingestor.md` reads sources and returns a proposed backlog; its caller writes approved changes.
- `scripts/specs.py` checks backlog structure, local source references, Gherkin, statuses and dependencies; it generates navigation from story bodies and promotes dependency-blocked stories whose dependencies are DONE. It cannot prove semantic source entailment.
- The `ohmyorch` plugin, on a local OpenSpec-only branch, provides `/ohmyorch:deliver`; `.claude/rules/ohmyorch-delivery.md` holds the project's delivery rule.
- `scripts/verify.py` runs the `harness`, `fast` and `full` profiles, with exit codes 0, 1 and 2, and records current input fingerprints/results locally. `fast` chooses Python and web steps from what differs since the last passing report, and records the rest as `not_run`.
- `services/agent/src/autobots/contracts/` holds the initial public Pydantic contracts, separate from `domain/` and `persistence/`. `scripts/generate_contracts.py` generates `contracts/generated/openapi.json` and the TypeScript client in `packages/api-client/`, offline, and detects drift.
- `supabase/migrations/` holds the ordered application schema, `supabase/seeds/` its reference rows and `supabase/bootstrap/` the migration and runtime roles. `scripts/app_db.py` qualifies them on a disposable database and generates `packages/db-types`. It has no persistent path.
- `services/agent/src/autobots/api/` holds the FastAPI factory, lifespan, settings, safe errors, internal and session checks, and two routes. `apps/web` is a Next.js shell with exact Luma tokens, dark default, a guarded same-origin BFF and a generated client. `scripts/qualify_web.py` drives both with a real browser. `scripts/qualify_identity.py` qualifies real Auth, membership in the database, PostgREST and Storage on a disposable stack.
- `services/agent/src/autobots/domain/models.py` holds the two approved profiles and role precedence, and `adapters/models/` the catalog association check and the only factory that builds an inference client. Tests use a fake transport. No model has been called and no real catalog fetch exists yet.
- `services/agent/src/autobots/application/credentials/` holds source precedence, AES-256-GCM sealing, master key handling and the encrypted store, and `apps/web/lib/credential-precedence.ts` the same precedence for Next.js. `application/provider_settings.py` and `api/settings_routes.py` expose the MP-05 routes, with a write-only form in `apps/web`. Validation has only been run against a fake upstream.
- `application/model_admission.py` holds slot and spend reservation under a lock, in the private `app_private.model_invocations` ledger, and `application/model_attempts.py` failure classes and bounded retries. The goal loop dispatches through them, and each reply's finish reason, token counts and tool names are recorded in the ledger, with no message content.
- `application/runs.py` and `api/run_routes.py` admit runs atomically with idempotency receipts, and apply SP-010's commands with version and actor guards. A queued run has a job row.
- `application/worker_leases.py` claims jobs by database time with a rising generation, and `adapters/checkpoints.py` gives a worker a direct checkpointer. Triggers in `20261105000008_worker_ownership.sql` refuse a checkpoint write from any generation but the current one. There is no worker loop yet, so nothing claims a job in the running product.
- `application/tool_gateway.py` is the one place a tool runs, with receipts in `app_private.tool_receipts`, and `application/tools.py` holds the first three tools. `adapters/tool_middleware.py` answers every tool call inside a Deep Agents loop from the gateway, because the SDK attaches file, shell and subagent tools of its own.
- `application/goal_loop.py` runs one bounded pass over an admitted goal in a Deep Agents graph, with `application/plans.py` and `application/run_usage.py` keeping versioned plans, evidence and root limits in the database. Only tests call it: no worker process exists, and no real model has run it.
- `application/artifacts.py` stages, uploads, verifies and then publishes private artifacts, and reconciles interrupted ones. `adapters/object_storage.py` reaches Supabase Storage with the service key, so the workspace check comes from `public.artifacts` rows. `api/artifact_routes.py` serves listing and downloads.
- `application/run_projection.py` builds the public view of a run from typed records, and `api/event_routes.py` serves cursor replay, a live stream and a snapshot. `app/runs/[id]` shows them. Nothing reads checkpoints for display.
- `application/recovery.py` classifies what an interrupted owner left before anything else is dispatched, and `run_goal` checks obligations, uncertain calls and the frozen policy first. `process_next` claims a job, runs it and settles it, and `application/verification.py` decides completion from required artifacts and checks. Test fixtures call it with a scripted model, and the product worker calls it only when inference is switched on, as below. No real model has run this.
- `application/experts.py` holds Experts, immutable revisions, sessions and routing, and `api/expert_routes.py` and `app/experts` expose them. A run freezes its Expert's tools, instructions and model bindings at admission. Skills are stored as references, and nothing loads them yet.
- `application/assignments.py` runs specialists synchronously as child runs, with scope intersected from the parent, the parent's policy, and calls, tools and spend counted on the root.
- `application/approvals.py` stores a proposal bound to its exact arguments before the wait, and validates decisions against it. `app/approvals` is the inbox. The worker's tool step runs again after a decision, and only then can the effect happen.
- `application/reconciliation.py` keeps unknown effects visible until a tool's readback or an owner's report resolves them. No real external tool exists yet: only fixtures over a controlled sink use this.
- `domain/workflows.py` holds the documented workflow subset and its typed validation, and `application/workflows.py` publishes immutable versions and binds executions to an exact version and hash. `domain/workflow_execution.py` decides readiness, and `application/workflow_runner.py` runs a bound execution under a lease with insert-only emissions. Only tests run a worker. `app/workflows` edits, validates, publishes and runs a graph as JSON, and `app/workflow-executions` monitors saved state.
- `application/routines.py` holds explicit routines with immutable versions, and `evaluate_routines` admits due occurrences with a unique key. No process calls it yet.
- `application/memory.py` holds scoped memory and lexical search in Postgres, with no embedding service, and `application/compaction.py` bounds what a model sees while keeping the goal, permissions and open waits out of any summary.
- `application/improvements.py` takes a memory or skill proposal through regression and an owner's review to a new version, with rollback. A promoted skill reaches a new run's instructions as reference, and nothing there can change a grant or a model.
- `infra/supabase/` vendors the pinned self-hosted release with a local overlay; `scripts/supabase_stack.py` runs port preflight and disposable qualification. No persistent stack start exists.
- `operations/worker.py` is the worker process: heartbeat, bounded drain and reconnection around whatever step it's given. Its own entry runs maintenance (approvals, routines, retention) and claims no job, unless `AUTOBOTS_WORKER_INFERENCE=enabled` adds `application/worker_inference.py`'s step: `process_next` binds each claimed job's route from its frozen `policy_snapshot`, reserves from catalog prices, and builds a client from `adapters/models/factory.py` inside each attempt from a key resolved there, pausing the run when no usable key or catalog exists. That path is qualified over a fake transport by `scripts/qualify_worker_inference.py`, and `scripts/live_goal.py` runs it live on a disposable stack, where [a batch of one repeated goal went Terra 5 of 5 and DeepSeek 0 of 5](docs/engineering/evidence/LIVE-GOAL-1/summary.md). `tool_receipts` records each failed tool call's code and category, never what the model wrote, and tool replies carry the `operation_id` that receipt evidence cites. `application/operations.py` and `api/operation_routes.py` report local status and gate admission on database, schema, Storage and disk. `operations/logs.py` holds redacted JSON logs and turns inherited tracing off at bootstrap. `application/retention.py` applies per-workspace windows through two security-definer functions. `scripts/qualify_operations.py` exercises `docs/engineering/runbooks/operations.md` on a disposable stack.
- `scripts/local_backup.py` takes a cold, encrypted backup of a Compose project's named volumes and configuration with a signed manifest, keeps the provider key apart, and restores only into a new disposable project under a hold (`app_private.installation_holds`), which stops claims, admission, routines and retention until an operator releases it. `scripts/qualify_backup.py` exercises it between two disposable stacks.
- `domain/execution.py` holds the versions a run records at admission, and `goal_loop.execution_block` pauses a saved run they no longer match, before any model or checkpoint. `adapters/checkpoints.py` fingerprints the installed checkpoint adapter, and `agent_runtime.adapter_qualifications` records which fingerprints may continue saved work. `scripts/qualify_upgrade.py` exercises `docs/engineering/runbooks/upgrade.md` from a prior release read out of git history.
- Review round 1's blockers are fixed: `tool_gateway` admits effects under the lease and only moves a receipt forward, `goal_loop` keeps a cancelled parent queued until its children are terminal at any depth, `assignments` answers a replay from a finished child, `workflow_runner` treats pauses as stops and fails a stalled or newly invalid graph, `approvals` refuses to approve what can't be shown whole, `compaction` and `memory` read stored evidence back in pages, and an Expert can name `propose_improvement`. `tests/db/blocker_check.py` holds the arranged cases.
- `agent_runtime.route_qualifications` holds each route's live result with its date, configuration and limits, added by migration. `ProviderSettings.route_qualifications` reads it into the provider status, and a route with no record for its own canonical model reads as not qualified.
- The two approved profiles in `domain/models.py` are DeepSeek and Terra, by [Decision 0004](docs/engineering/decisions/0004-terra-replaces-astra.md), and Terra is the default for all 14 roles by [Decision 0006](docs/engineering/decisions/0006-terra-is-the-default.md). Migration `20261105000026` removes Astra from what can be selected and keeps it in invocation history. `operations/route_qualification.py` runs capped paid qualifications of named routes, with results in `docs/engineering/evidence/US-3.4/`. DeepSeek's strict nested output is unsupported by [Decision 0005](docs/engineering/decisions/0005-deepseek-strict-nested-unsupported.md), and `tests/test_route_qualification.py` fails if application code asks for strict output or an approved profile has no route to qualify. `adapters/models/factory.py` gives model calls a 130-second client timeout, above the goal loop's 120-second bound. `adapters/github_issues.py` is the one consequential connector, by [Decision 0007](docs/engineering/decisions/0007-first-connector-github-issues.md): it creates an issue in one configured repository, an owner grants it per Expert, and `scripts/qualify_github_connector.py` has run it against the owner's throwaway private repository. That run found GitHub's issue list lagging a create by about 9 seconds, so its readback waits up to 15 seconds before saying not delivered. `scripts/qualify_release.py` measures US-10.1's protocol cases, held-out tasks in `tests/qualification/tasks.json`, local benchmark and resources on a disposable stack, under a spending cap each run must state. With `--ui` it also times events in a real browser through `apps/web/tests/browser/release-latency.spec.ts`, which no other suite runs. [Results are in `docs/engineering/evidence/US-10.1/`](docs/engineering/evidence/US-10.1/summary.md).
- Review round 1's majors are recorded in `docs/engineering/evidence/REVIEW-US-5.1-to-US-9.3/fixes-majors.md`, with arranged cases in `tests/db/major_check.py`. `workflow_executions.current_instance` lets the monitor name the node in progress, `memory_items.expert_id` scopes memory, and `knowledge_heads.active_version` can be null after undoing a first promotion.
- `scripts/disposable_db.py` holds target-guarded `reset`, `cleanup` and `migrate` wrappers and the `db` profile's qualification, including a synthetic stub worker, using `infra/disposable/compose.yaml` and synthetic SQL in `tests/db/`. No persistent stack or product migration exists.
- `scripts/qualify_faults.py` runs the pinned tools on known-good and known-bad fixtures in `tests/faults/`, and `full` includes it. `services/agent/tests` has a fake OpenRouter transport; its tests make no real model call.
- `scripts/evidence.py` validates DH-W01–06 completion evidence from the templates in `docs/engineering/templates/`, under the contract in `docs/engineering/evidence/README.md`. US-1.8's Gate 0 record is the first work item validated with it.
- `.claude/hooks/dispatch.py` integrates selected events with bounded local checks: a deadline, fail-closed errors, path validation, affected check domains and a `ruff` diagnostic. An event's `cwd` selects its root only among worktrees Git has registered under `.claude/worktrees/`, otherwise the root is the dispatcher's own checkout. If Git fails there, file edits are denied and `Stop` blocks once per turn, while `Bash` carries on. Script fixture tests and actual Claude event delivery have separate evidence.

## Upstream evidence and local constraints

OhMyOrch is cloned at `research/upstream/OhMyOrch`, pinned to `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. The spec-ingestion adaptation does not depend on running its plugin, shell/JQ tooling or OpenSpec lifecycle. Epic delivery does, per [Decision 0002](docs/engineering/decisions/0002-ohmyorch-delivery-loop.md): the plugin is installed from this checkout at local scope. The clone stays excluded from repository verification input and future commits.

Read-only local probes found Python 3.15.2, Python 3.12.16 at /opt/homebrew/bin/python3.12, and Claude Code 2.1.314 available. A separate process resolved plain python3 to macOS 3.9.6, so project hooks explicitly select the available 3.12 executable and scripts reject unsupported versions. The application Python baseline remains 3.12 as specified; the local interpreter probe is not a changed product requirement or a qualified application environment. No assistant model conversation was started to perform those probes.

## Gaps and evidence limits

H0/H1 and product work remain separately tracked in SPECS. Installed project files and synthetic hook tests do not establish an active, authenticated Claude/OpenRouter integration, a complete engineering baseline, or a working application. Update this inventory from actual observed changes and evidence; never derive new requirements from it.
