# SQL, infrastructure and Makefile

The SQL and infrastructure layer is small, consistent and well explained. Its 53 migrations are short (the largest is 136 lines). None was edited after it was added, and the installer enforces names and checksums. All 24 public tables enable RLS, the private schemas are closed to browser roles, and all nine functions pin search_path. Fencing and approval immutability raise typed SQLSTATEs, the reference seed is version-guarded and proven repeatable, and the Compose overlay is digest-pinned, loopback-only and checked on its merged result. The Makefile states its safety rules. The weaknesses are privilege gaps the tests can't see and coordination costs that grow with every migration. The runtime role keeps an unused DELETE on runs, and deleting a run cascades into the receipt ledger that migration 23 says is never removed. Browser images are qualified by a hash of their sources, while the image that actually runs is whatever `:local` tag exists. Each profile change restates the approved profiles in three CHECK constraints, and the Storage policies sit in a frozen superuser file with no forward path. Route limits are prose concatenated across migrations, and that has already dropped a shared caveat for Sol. The generated db-types have no consumer and don't reflect grants. RLS and grant conventions are checked one case at a time rather than from the catalog. Few migrations that rewrite data state their locks or a recovery path, although database.md requires it. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 4 | Most DH-07 and DH-08 rules hold and several are enforced in code. The disposable images aren't from the install's pinned family, and lock notes, resource limits and .dockerignore are missing. |
| modules | 3 | The public, app_private and agent_runtime schemas and the role split are clean, but unused runtime DELETE grants and a PostgREST write path for drafts blur those boundaries. |
| size | 4 | No SQL file exceeds 136 lines and function bodies stay near 60 lines; the Makefile packs logic into one-liners of up to 187 characters. |
| functions | 4 | SQL functions are single-purpose and refuse early. The terminal-state predicate is repeated, and each Makefile macro does several jobs. |
| structure | 3 | The layout matches DH-03, but there is no view of the current schema, the Storage bootstrap has no forward path and the browser image build is not codified. |
| approach | 3 | RLS, fencing triggers and pinned overlays are sound. CHECK-list vocabularies, prose limits, unindexed run lookups and unverified image provenance add friction and risk. |
| comments | 4 | Every SQL file opens with a traceable why-header; lock, backfill and recovery notes are missing where data is rewritten. |
| types | 3 | CHECK and jsonb shape constraints are rich, but the generated row types ignore grants and have no consumer, and four version references lack a composite key. |
| errors | 4 | The code uses typed SQLSTATEs AB001 and AB002, coded purge refusals and actionable Makefile messages; the browser entrypoint fails opaquely. |
| tests | 3 | Per-story RLS and seed cases are thorough, but nothing sweeps the catalog, the run-delete cascade is untested and the Makefile's process supervision has no tests. |
| maintainability | 3 | Files are small and well explained, but common changes need hidden coordinated edits: three profile checks, the reset list, a frozen Storage file and prose limits. |

## Strengths

- **Append-only, checksum-guarded migration history.** No migration file was modified after it was added (git log --diff-filter=M lists only supabase/seeds/reference.sql). The installer refuses a misnamed, missing or changed file and applies each pending file in one transaction together with its history row (scripts/persistent_install.py:251-270). Sources: [scripts/persistent_install.py:251-270](../../../../scripts/persistent_install.py#L251).
- **SECURITY DEFINER hygiene everywhere.** All nine functions set search_path = '' and schema-qualify every name: supabase/migrations/20261105000001_workspaces.sql:24, 20261105000008_worker_ownership.sql:48, 20261105000023_operations.sql:47 and 114, 20261107000036_approval_requester_scope_policy.sql:22, 20261107000042_user_profiles.sql:12, 20261108000046_workflow_drafts.sql:4, 20261108000049_applied_migration_count.sql:7 and supabase/bootstrap/storage.sql:6. Private functions are granted only to autobots_runtime (20261105000023_operations.sql:133-136). Sources: [supabase/migrations/20261105000001_workspaces.sql:24](../../../../supabase/migrations/20261105000001_workspaces.sql#L24), [supabase/migrations/20261105000008_worker_ownership.sql:48](../../../../supabase/migrations/20261105000008_worker_ownership.sql#L48), [supabase/migrations/20261105000023_operations.sql:47](../../../../supabase/migrations/20261105000023_operations.sql#L47), [supabase/migrations/20261105000023_operations.sql:114](../../../../supabase/migrations/20261105000023_operations.sql#L114), [supabase/migrations/20261107000036_approval_requester_scope_policy.sql:22](../../../../supabase/migrations/20261107000036_approval_requester_scope_policy.sql#L22), [supabase/migrations/20261107000042_user_profiles.sql:12](../../../../supabase/migrations/20261107000042_user_profiles.sql#L12), [supabase/migrations/20261108000046_workflow_drafts.sql:4](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L4), [supabase/migrations/20261108000049_applied_migration_count.sql:7](../../../../supabase/migrations/20261108000049_applied_migration_count.sql#L7), [supabase/bootstrap/storage.sql:6](../../../../supabase/bootstrap/storage.sql#L6), [supabase/migrations/20261105000023_operations.sql:133-136](../../../../supabase/migrations/20261105000023_operations.sql#L133).
- **Schema boundaries and column-level exposure.** All 24 public tables enable RLS and revoke before granting. app_private and agent_runtime are closed to browser roles (20261105000001_workspaces.sql:4, 20261105000004_provider_credentials.sql:24, 20261105000008_worker_ownership.sql:70). Column grants keep the lease, checkpoint and policy columns private (20261105000002_runs.sql:34-35), and scripts/app_db.py:209 and :389 prove it. Sources: [supabase/migrations/20261105000001_workspaces.sql:4](../../../../supabase/migrations/20261105000001_workspaces.sql#L4), [supabase/migrations/20261105000004_provider_credentials.sql:24](../../../../supabase/migrations/20261105000004_provider_credentials.sql#L24), [supabase/migrations/20261105000008_worker_ownership.sql:70](../../../../supabase/migrations/20261105000008_worker_ownership.sql#L70), [supabase/migrations/20261105000002_runs.sql:34-35](../../../../supabase/migrations/20261105000002_runs.sql#L34), [scripts/app_db.py:209](../../../../scripts/app_db.py#L209), [scripts/app_db.py:389](../../../../scripts/app_db.py#L389).
- **Invariants enforced where the write happens, with typed errors.** The checkpoint fence trigger raises SQLSTATE AB001 (20261105000008_worker_ownership.sql:46-68), which services/agent/src/autobots/adapters/checkpoints.py:18 consumes as STALE_OWNER_SQLSTATE. The approval immutability trigger raises AB002 (20261107000036_approval_requester_scope_policy.sql:21-37). Further guards are the jsonb shape checks (20261107000038_tool_uses.sql:23-24, 32) and a composite FK that keeps each draft in its workflow's workspace (20261108000046_workflow_drafts.sql:13, 21). Sources: [supabase/migrations/20261105000008_worker_ownership.sql:46-68](../../../../supabase/migrations/20261105000008_worker_ownership.sql#L46), [services/agent/src/autobots/adapters/checkpoints.py:18](../../../../services/agent/src/autobots/adapters/checkpoints.py#L18), [supabase/migrations/20261107000036_approval_requester_scope_policy.sql:21-37](../../../../supabase/migrations/20261107000036_approval_requester_scope_policy.sql#L21), [supabase/migrations/20261107000038_tool_uses.sql:23-24](../../../../supabase/migrations/20261107000038_tool_uses.sql#L23), [supabase/migrations/20261107000038_tool_uses.sql:32](../../../../supabase/migrations/20261107000038_tool_uses.sql#L32), [supabase/migrations/20261108000046_workflow_drafts.sql:13](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L13), [supabase/migrations/20261108000046_workflow_drafts.sql:21](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L21).
- **Why-comments with traceability.** Every SQL file opens with a header, and 50 of the 53 migrations cite a story, decision or PRD ID. Comments state invariants rather than syntax (20261105000008_worker_ownership.sql:46, 20261105000023_operations.sql:10 and 43-44, 20261108000044_chosen_run_budget.sql:1-5). 20261105000029_call_diagnostics.sql:1-3 and 20261105000030_tool_failure_diagnostics.sql:1-3 state lock behavior, the pattern to spread. Sources: [supabase/migrations/20261105000008_worker_ownership.sql:46](../../../../supabase/migrations/20261105000008_worker_ownership.sql#L46), [supabase/migrations/20261105000023_operations.sql:10](../../../../supabase/migrations/20261105000023_operations.sql#L10), [supabase/migrations/20261105000023_operations.sql:43-44](../../../../supabase/migrations/20261105000023_operations.sql#L43), [supabase/migrations/20261108000044_chosen_run_budget.sql:1-5](../../../../supabase/migrations/20261108000044_chosen_run_budget.sql#L1), [supabase/migrations/20261105000029_call_diagnostics.sql:1-3](../../../../supabase/migrations/20261105000029_call_diagnostics.sql#L1), [supabase/migrations/20261105000030_tool_failure_diagnostics.sql:1-3](../../../../supabase/migrations/20261105000030_tool_failure_diagnostics.sql#L1).
- **Repeatable, edit-preserving reference seed.** supabase/seeds/reference.sql:1-10 upserts rows by stable ID under a seed_version guard and keeps labels users have edited. The installer runs it after every apply (scripts/persistent_install.py:271-273), and scripts/app_db.py:175-189 proves that a second run changes nothing. Sources: [supabase/seeds/reference.sql:1-10](../../../../supabase/seeds/reference.sql#L1), [scripts/persistent_install.py:271-273](../../../../scripts/persistent_install.py#L271), [scripts/app_db.py:175-189](../../../../scripts/app_db.py#L175).
- **Compose overlay discipline, checked on the merged result.** Images are pinned by tag and digest with pull_policy never, and ports are loopback-only, with the reason for !override explained (infra/supabase/compose.overlay.yaml:2, 21-22, 58-59). Unused services are parked in a profile that is never selected (71-78), and Studio AI is disabled (10-11). scripts/supabase_stack.py:137-152 validates labels and mounts on the rendered configuration. Sources: [infra/supabase/compose.overlay.yaml:2](../../../../infra/supabase/compose.overlay.yaml#L2), [infra/supabase/compose.overlay.yaml:21-22](../../../../infra/supabase/compose.overlay.yaml#L21), [infra/supabase/compose.overlay.yaml:58-59](../../../../infra/supabase/compose.overlay.yaml#L58), [infra/supabase/compose.overlay.yaml:71-78](../../../../infra/supabase/compose.overlay.yaml#L71), [infra/supabase/compose.overlay.yaml:10-11](../../../../infra/supabase/compose.overlay.yaml#L10), [scripts/supabase_stack.py:137-152](../../../../scripts/supabase_stack.py#L137).
- **Operational safety rules written next to the code.** The Makefile explains why it uses := against environment overrides (Makefile:5-8) and .NOTPARALLEL (29-30). It checks pid plus start time (93-98), never sends KILL to a worker that may be in a paid call (176-177), and makes stop-stack check the recorded project (213-219). infra/browser/browser-entrypoint.js:1-7, 13-14 and 30 likewise explain each group of Chromium flags. Sources: [Makefile:5-8](../../../../Makefile#L5), [Makefile:29-30](../../../../Makefile#L29), [Makefile:93-98](../../../../Makefile#L93), [Makefile:176-177](../../../../Makefile#L176), [Makefile:213-219](../../../../Makefile#L213), [infra/browser/browser-entrypoint.js:1-7](../../../../infra/browser/browser-entrypoint.js#L1), [infra/browser/browser-entrypoint.js:13-14](../../../../infra/browser/browser-entrypoint.js#L13), [infra/browser/browser-entrypoint.js:30](../../../../infra/browser/browser-entrypoint.js#L30).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [SQLI-01](#sqli-01) | high | modules | Runtime role can delete runs, and the cascade reaches the receipt ledger | S | high |
| [SQLI-02](#sqli-02) | high | approach | Browser images are qualified by source hash, not by the image that runs | M | medium |
| [SQLI-03](#sqli-03) | medium | duplication | Approved profiles are restated in three CHECK constraints at every change | M | high |
| [SQLI-04](#sqli-04) | medium | comments | Migrations that rewrite data or rebuild constraints say nothing about locks or recovery | S | low |
| [SQLI-05](#sqli-05) | medium | tests | RLS and grant conventions are checked case by case, never from the catalog | M | low |
| [SQLI-06](#sqli-06) | medium | types | Generated DB row types list columns the browser role can't read, and nothing imports them | S | low |
| [SQLI-07](#sqli-07) | medium | structure | Storage policies live in one frozen superuser file with no forward path | M | high |
| [SQLI-08](#sqli-08) | medium | approach | Run-scoped lookups and retention guards scan unindexed columns | S | medium |
| [SQLI-09](#sqli-09) | medium | structure | No current-schema view: live definitions hide in the last migration that touched them | M | low |
| [SQLI-10](#sqli-10) | medium | approach | Makefile process supervision is untested shell inside Make macros | M | medium |
| [SQLI-11](#sqli-11) | medium | duplication | The Makefile re-derives Node, images and install.json, which scripts already handle | S | low |
| [SQLI-12](#sqli-12) | medium | approach | Route limits are prose stitched across migrations, and Sol lacks a shared caveat | M | medium |
| [SQLI-13](#sqli-13) | medium | approach | Draft graphs written through PostgREST skip the API's validation, and one bad draft breaks the workflow list | S | high |
| [SQLI-14](#sqli-14) | medium | types | Version references are enforced by a composite key in one table and by nothing in four | S | medium |
| [SQLI-15](#sqli-15) | low | standards | The synthetic H1 stack runs on images the install doesn't use, and nothing pulls them | S | medium |
| [SQLI-16](#sqli-16) | low | duplication | The disposable reset names every public table and function by hand | S | low |
| [SQLI-17](#sqli-17) | low | duplication | The terminal-state predicate is spelled out nine times in SQL | S | medium |
| [SQLI-18](#sqli-18) | low | naming | Some migrations are named for a review round and bundle unrelated changes | S | low |
| [SQLI-19](#sqli-19) | low | standards | The install overlay sets no resource limits, and its list overrides can drop upstream mounts | S | medium |
| [SQLI-20](#sqli-20) | low | errors | The browser entrypoint fails opaquely when Chromium can't be found or started | S | low |

### <a id="sqli-01"></a>SQLI-01: Runtime role can delete runs, and the cascade reaches the receipt ledger

- **Severity** high · **Dimension** modules · **Effort** S · **Risk** high · **Occurrences** 5
- **Where:**
  - [supabase/migrations/20261105000002_runs.sql:37](../../../../supabase/migrations/20261105000002_runs.sql#L37): DELETE on runs and run_events for autobots_runtime
  - [supabase/migrations/20261105000001_workspaces.sql:38](../../../../supabase/migrations/20261105000001_workspaces.sql#L38): DELETE on workspaces and workspace_members
  - [supabase/migrations/20261107000042_user_profiles.sql:27](../../../../supabase/migrations/20261107000042_user_profiles.sql#L27): DELETE on user_profiles
  - [supabase/migrations/20261105000009_tool_gateway.sql:4](../../../../supabase/migrations/20261105000009_tool_gateway.sql#L4): tool_receipts are deleted along with their run
  - [supabase/migrations/20261107000038_tool_uses.sql:7-8](../../../../supabase/migrations/20261107000038_tool_uses.sql#L7): the tool-use ledger cascades too
  - [supabase/migrations/20261105000023_operations.sql:43-44](../../../../supabase/migrations/20261105000023_operations.sql#L43): states that the runtime role can't delete and that every receipt is kept
  - [tests/db/operations_check.py:170-175](../../../../tests/db/operations_check.py#L170): only a direct delete of run_files is tested
  - [scripts/qualify_identity.py:245](../../../../scripts/qualify_identity.py#L245): an arrangement deletes run_events as the runtime role
- **Evidence:** Migration 02:37 grants `select, insert, update, delete on public.runs, public.run_events to autobots_runtime`, and 01:38 and 42:27 grant DELETE on workspaces, workspace_members and user_profiles. The service deletes only from workflow_drafts (services/agent/src/autobots/application/workflows.py:214 and 245; found with a grep for `delete from` under services/agent/src). Eighteen tables reference public.runs with ON DELETE CASCADE through 21 foreign keys, among them tool_receipts, tool_uses, run_files, approval_requests and artifacts. Cascades run as the table owner, so neither grants nor RLS stop them, and no trigger blocks deletes on those tables. Five references have no cascade (parent_run_id, continues_run_id, root_run_id, workflow_executions.run_id and routine_occurrences.run_id), so a delete fails only for a run with a child, a continuation, a workflow execution or a routine occurrence. Migration 23:43-44 says the runtime role can't delete and that every tool receipt is kept, but the tests check only direct deletes (app_db.py:405, 496, 517 and 519; operations_check.py:170-175). Only two test arrangements use the grants, at qualify_identity.py:245 and 472.
- **Why it matters:** One mistaken or injected `delete from public.runs` in the API or worker would silently erase that run's receipts, tool uses, approvals and evidence. Replay and reconciliation depend on those records, and no check would notice. The documented invariant holds only for direct deletes.
- **Recommendation:** Write a forward migration that revokes DELETE on public.runs, run_events, workspaces, workspace_members and user_profiles from autobots_runtime. Move the arranged deletes in qualify_identity.py (lines 245 and 472) to the admin connection. Add db cases asserting that the runtime role cannot delete a run or an event, and record the runtime's allowed DELETE grants (workflow_drafts only) in the catalog check proposed below. Optionally, switch tool_receipts and tool_uses to ON DELETE RESTRICT in the same migration.
- **Rule check:** DH-07 asks for least-privilege grants, and DH-06 says replay must preserve operation receipts. The change narrows privileges in a forward migration and edits no applied file.
- **Verification:** revised. Grants, 21 cascading foreign keys from 18 tables and the 23:43-44 comment confirmed. Added that five references without a cascade block only some deletes, and that only two test arrangements use the grant.

```sql
-- 20261112000054_runtime_cannot_delete_runs.sql
-- Locks: catalog only. Data: none. Recovery: grant again in a later migration if a path proves it needs it.
revoke delete on public.runs, public.run_events, public.workspaces,
  public.workspace_members, public.user_profiles from autobots_runtime;
-- scripts/app_db.py: runtime 'delete from public.runs' and 'delete from public.run_events' -> permission denied
-- scripts/qualify_identity.py:245 and 472: arrange through stack.sql (supabase_admin), not stack.runtime
```

### <a id="sqli-02"></a>SQLI-02: Browser images are qualified by source hash, not by the image that runs

- **Severity** high · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 2
- **Where:**
  - [infra/browser/proxy.Dockerfile:1-6](../../../../infra/browser/proxy.Dockerfile#L1): the build context is the whole adapters package, and the base digest names no Python version
  - [infra/browser/browser.Dockerfile:1-6](../../../../infra/browser/browser.Dockerfile#L1): tagged autobots-browser:local by hand
  - [docs/engineering/runbooks/operations.md:107-108](../../../../docs/engineering/runbooks/operations.md#L107): the only place the build is written down
  - [scripts/qualify_browser_executor.py:45-47](../../../../scripts/qualify_browser_executor.py#L45): checks only that the :local tags exist
  - [services/agent/src/autobots/adapters/browser_executor.py:427-438](../../../../services/agent/src/autobots/adapters/browser_executor.py#L427): the fingerprint hashes source files
  - [services/agent/src/autobots/adapters/browser_executor.py:489-500](../../../../services/agent/src/autobots/adapters/browser_executor.py#L489): reported qualified when the report's fingerprint matches the sources
- **Evidence:** The qualifier accepts whatever images are tagged `autobots-browser:local` and `autobots-egress:local`; it only runs `docker image inspect` (qualify_browser_executor.py:45-47). It then records images_fingerprint, a hash of both Dockerfiles, the entrypoint and the proxy and executor sources (browser_executor.py:427-438), and executor_qualified trusts that hash alone (489-500). The two `docker build` commands appear only in operations.md:107-108. There is no make target, no label on either image and no .dockerignore anywhere in the repository, and the proxy's build context is services/agent/src/autobots/adapters.
- **Why it matters:** Suppose someone edits egress_proxy.py or a Chromium flag, skips the rebuild and requalifies. The old image passes, the report carries the new fingerprint, and browse_goal runs the old egress sandbox while reporting that it is qualified at the current code.
- **Recommendation:** Codify the build and bind each image to its inputs. Give the build one entry point, a make target that calls a small script. It builds both images with `--label autobots.fingerprint=<digest of images_fingerprint>`, from build contexts narrowed by Dockerfile-specific ignore files. The qualifier refuses images whose label differs from the current fingerprint, and executor_qualified checks the label on the images it will start. Name the proxy base image's Python version next to its digest, as the browser image names Playwright 1.64.1.
- **Rule check:** DH-08 (reviewed images, .dockerignore, non-root) and infrastructure.md (pin and qualify images). The change adds a binding check and removes no egress rule, sandbox flag or qualification case.
- **Verification:** confirmed. qualify_browser_executor.py:45-47 only inspects the :local tags, images_fingerprint hashes five source files, and executor_qualified compares only that hash. The repository has no make target, image label or .dockerignore for these images.

```text
make browser-images  ->  scripts/browser_images.py build
  fp = sha256(json.dumps(images_fingerprint(root), sort_keys=True))
  docker build --label autobots.fingerprint=$fp -t autobots-browser:local -f infra/browser/browser.Dockerfile infra/browser
  docker build --label autobots.fingerprint=$fp -t autobots-egress:local -f infra/browser/proxy.Dockerfile services/agent/src/autobots/adapters
infra/browser/proxy.Dockerfile.dockerignore: '*' then '!egress_proxy.py'
browser_executor.images_match(root) -> bool   # both image labels equal fp
qualify_browser_executor: Unavailable unless images_match; executor_qualified(): ... and images_match(root)
```

### <a id="sqli-03"></a>SQLI-03: Approved profiles are restated in three CHECK constraints at every change

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** high · **Occurrences** 9
- **Where:**
  - [supabase/migrations/20261105000003_model_profiles.sql:3](../../../../supabase/migrations/20261105000003_model_profiles.sql#L3)
  - [supabase/migrations/20261105000005_provider_settings.sql:13](../../../../supabase/migrations/20261105000005_provider_settings.sql#L13)
  - [supabase/migrations/20261105000006_model_invocations.sql:15](../../../../supabase/migrations/20261105000006_model_invocations.sql#L15)
  - [supabase/migrations/20261105000026_terra_replaces_astra.sql:6-28](../../../../supabase/migrations/20261105000026_terra_replaces_astra.sql#L6): three drops and re-adds, plus a row insert
  - [supabase/migrations/20261107000040_sol_profile.sql:4-19](../../../../supabase/migrations/20261107000040_sol_profile.sql#L4): the same three again, plus a row insert
  - [supabase/seeds/reference.sql:3-5](../../../../supabase/seeds/reference.sql#L3): the same rows, owned by the seed
  - [tests/db/sol_profile_check.py:63-67](../../../../tests/db/sol_profile_check.py#L63): a test exists to prove all three checks were updated
- **Evidence:** Each change to the approved set drops and re-adds model_profiles_profile_id_check, model_policies_default_profile_check and model_invocations_profile_check, each with the full list (26:6-28, 40:4-19). This relies on the constraint names Postgres generates. public.model_profiles already holds the vocabulary as rows, but no column references it, and 26:11-13 and 40:9-11 insert the same rows that the seed upserts. sol_profile_check.py:63-67 reads pg_constraint by name to prove that all three checks admit Sol. Counted with a grep for profile IDs inside check lists.
- **Why it matters:** Adding or retiring a profile touches three constraints, a migration insert, the seed and a route qualification row. A missed one is caught only by a story-specific test, and the next profile change will need its own test.
- **Recommendation:** The next time the approved set changes, replace model_policies_default_profile_check with a named foreign key to public.model_profiles, and insert every approved row in that migration, as 26 and 40 did for theirs (DeepSeek's row comes only from the seed today). model_profiles' own CHECK stays the one approved list, which is Decision 0019's guard, and the table keeps only approved rows, so the key admits exactly what the CHECK did. Retiring a profile then has to rewrite the policies that name it before its row can be deleted, the order migration 26 followed by hand. Keep model_invocations' own CHECK, under a name the migration chooses, because the ledger must still accept retired profiles such as Astra. Do not add retired rows to model_profiles: a foreign key would then let a policy choose a retired profile again. A change then touches one profile CHECK, one invocation CHECK, a seed row and a qualification row, and no longer depends on generated constraint names.
- **Rule check:** Decision 0019 and model-gateway.md (exactly three approved profiles) keep their guard in model_profiles' own CHECK. DH-07: forward migrations only, and no applied file is edited.
- **Verification:** revised. Nine restated lists confirmed (3 originals, and 3 swaps each in 26 and 40). Revised the recommendation: a foreign key to a table holding retired rows would let a policy choose Astra again, which today's CHECK refuses.

```sql
-- the next migration that changes the approved set
insert into public.model_profiles (profile_id, canonical_id, wire_id, label, seed_version)
  values ('openrouter_deepseek_flash', 'deepseek/deepseek-v4.1-flash-20261017', 'deepseek/deepseek-v4.1-flash-1017', 'DeepSeek Flash', 1)
  on conflict (profile_id) do nothing;   -- likewise each approved row
alter table app_private.model_policies
  drop constraint model_policies_default_profile_check,
  add constraint model_policies_default_profile_fk foreign key (default_profile) references public.model_profiles (profile_id);
-- kept: model_profiles' CHECK (approved only) and model_invocations' CHECK (approved plus retired)
```

### <a id="sqli-04"></a>SQLI-04: Migrations that rewrite data or rebuild constraints say nothing about locks or recovery

- **Severity** medium · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 15
- **Where:**
  - [supabase/migrations/20261105000011_artifacts.sql:2-4](../../../../supabase/migrations/20261105000011_artifacts.sql#L2): backfills every run with no note
  - [supabase/migrations/20261105000025_execution_contracts.sql:4-6](../../../../supabase/migrations/20261105000025_execution_contracts.sql#L4): explains why, but not what it locks or how to undo it
  - [supabase/migrations/20261105000026_terra_replaces_astra.sql:5-28](../../../../supabase/migrations/20261105000026_terra_replaces_astra.sql#L5): irreversible rewrite of policies and three constraint swaps
  - [supabase/migrations/20261105000023_operations.sql:32-34](../../../../supabase/migrations/20261105000023_operations.sql#L32): constraint swap on a populated table
  - [supabase/migrations/20261108000046_workflow_drafts.sql:13](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L13): builds a unique index on workflows
  - [supabase/migrations/20261108000053_routine_removal.sql:4-15](../../../../supabase/migrations/20261108000053_routine_removal.sql#L4)
  - [supabase/migrations/20261105000029_call_diagnostics.sql:1-3](../../../../supabase/migrations/20261105000029_call_diagnostics.sql#L1): the pattern to copy
- **Evidence:** Fifteen migrations (11, 23, 25, 26, 27, 28, 32, 34, 40, 44, 46, 50, 51, 52 and 53) update or delete existing rows, swap CHECK constraints or build an index on an existing table; 32, 34 and 50 rewrite only a few route_qualifications rows. Their headers explain intent and cite stories, but none says which lock it takes, which rows it rewrites or how to undo it. Only 29:1-3, 30:1-3 and 48:4 describe lock or backfill behavior, and no migration mentions recovery. Counted by reading each file for UPDATE or DELETE statements outside function bodies, constraint swaps and index builds on existing tables.
- **Why it matters:** Step 1 of upgrade.md tells the operator to read the new migrations before applying them to the persistent install. Without notes in each file they can't judge how long writes will be blocked, or see that 26's policy rewrite can be undone only by restoring the pre-upgrade backup.
- **Recommendation:** Give new migrations three header lines after the traceability line: Locks, Data and Recovery. Describe that convention in a short supabase/README.md, together with the conventions that are now only implicit: names made of a date plus a global sequence, one transaction per file owned by the runner, a runtime policy on every public table, and the AB0xx SQLSTATE codes. Add a harness check that fails for migrations sorted after 20261108000053_routine_removal.sql that lack the three lines. Leave applied files untouched.
- **Rule check:** database.md ('Document locks/backfills and forward recovery') and DH-07. Only new migrations change; applied files stay byte-identical, as the installer's checksum requires.
- **Verification:** revised. Recounted 15 migrations, adding 32, 34 and 50, which update existing route_qualifications rows. Only 29, 30 and 48 describe locks or backfills, and upgrade.md:19 does tell the operator to read new migrations first.

```sql
-- US-x.y, Decision NNNN: what changes and why.
-- Locks: ACCESS EXCLUSIVE on public.runs while the new check scans it; brief on a local install.
-- Data: rewrites runs.foo where ...; none otherwise.
-- Recovery: fix forward; reverting needs the pre-upgrade backup (upgrade.md).
# harness check: every migration after 20261108000053 has lines starting -- Locks:, -- Data: and -- Recovery:
```

### <a id="sqli-05"></a>SQLI-05: RLS and grant conventions are checked case by case, never from the catalog

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 33
- **Where:**
  - [scripts/app_db.py:206-216](../../../../scripts/app_db.py#L206): named cases such as 'anonymous cannot read runs'
  - [supabase/migrations/20261105000002_runs.sql:44-46](../../../../supabase/migrations/20261105000002_runs.sql#L44): member policy plus runtime allow-all policy, repeated for each table
  - [supabase/migrations/20261105000001_workspaces.sql:30](../../../../supabase/migrations/20261105000001_workspaces.sql#L30): EXECUTE revoked from PUBLIC only
  - [supabase/bootstrap/storage.sql:13](../../../../supabase/bootstrap/storage.sql#L13): definer function created by supabase_admin, with a PUBLIC-only revoke
  - [supabase/migrations/20261105000023_operations.sql:133-136](../../../../supabase/migrations/20261105000023_operations.sql#L133): app_private functions also revoke from anon and authenticated
  - [supabase/migrations/20261106000033_approval_reason_target.sql:3-5](../../../../supabase/migrations/20261106000033_approval_reason_target.sql#L3): new public columns whose exposure is decided by omission
- **Evidence:** All 24 public tables enable RLS and carry a member SELECT policy and a runtime policy (24 identical `for all ... using (true) with check (true)`), and all 9 functions pin search_path. Tests and scripts contain no catalog query: no has_table_privilege, has_function_privilege, pg_policies, relrowsecurity or column_privileges. app_db.py checks named cases instead. The four public helper functions revoke EXECUTE only from PUBLIC (01:30, 42:20, 46:9, storage.sql:13), while the app_private functions revoke it from public, anon and authenticated (23:133-134, 49:26). That is enough for the three helpers the migrator owns. can_access_artifact, though, is created by supabase_admin, whose Supabase default privileges grant EXECUTE on new public functions to anon, so anon most likely keeps it (not observed).
- **Why it matters:** Today's checks can't catch a new table without RLS or its runtime policy, a table-level grant that exposes a withheld column, or a definer function that anon can call, unless someone thinks to add a case for it. Today's helpers return false without auth.uid(), so nothing leaks yet.
- **Recommendation:** Add one catalog check to the db profile, run on the disposable stack after migrations and bootstrap. It asserts invariants over all objects: RLS on every public table; a member SELECT policy and a runtime policy on each; no INSERT, UPDATE or DELETE for authenticated outside an allowlist; and no anon privilege on tables, columns or functions in public, app_private or agent_runtime. It also checks that every definer function pins search_path, that authenticated's SELECT columns and the runtime's DELETE grants each equal a checked-in allowlist, and that status CHECK vocabularies equal the Python enums. Revoke anon's EXECUTE wherever the check fails; for can_access_artifact that needs the superuser path SQLI-07 proposes, since the migration role does not own it.
- **Rule check:** DH-07 (least-privilege grants, RLS isolation, exclusion of private schemas) and database.md. The check adds verification and changes no grant except revoking what it finds.
- **Verification:** revised. 24 public tables with RLS and member and runtime policies, all 24 runtime policies identical (not 23), 9 pinned functions and no catalog-privilege query in scripts or tests. Anon's EXECUTE on can_access_artifact stays reasoned, not observed.

```text
tests/db/catalog_check.py, db profile, after migrations and bootstrap:
  no_rls    = public tables where not relrowsecurity -> expect none
  anon_exec = pg_proc in public and app_private where has_function_privilege('anon', oid, 'execute') -> none
  unpinned  = pg_proc where prosecdef and proconfig is null -> none
  exposed   = public columns where has_column_privilege('authenticated', table, column, 'SELECT') -> equals allowlist
  deletes   = tables where has_table_privilege('autobots_runtime', oid, 'DELETE') -> {workflow_drafts}
  vocab     = values in pg_get_constraintdef(runs_status_check) == set(RunStatus)
```

### <a id="sqli-06"></a>SQLI-06: Generated DB row types list columns the browser role can't read, and nothing imports them

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 24
- **Where:**
  - [packages/db-types/package.json:6-8](../../../../packages/db-types/package.json#L6): exports a module that no package imports
  - [packages/db-types/README.md:3](../../../../packages/db-types/README.md#L3): describes the exposed public schema
  - [packages/db-types/src/generated.ts:156-181](../../../../packages/db-types/src/generated.ts#L156): RunsRow includes lease_generation, checkpoint_thread_id, policy_snapshot and execution_contract
  - [supabase/migrations/20261105000002_runs.sql:1](../../../../supabase/migrations/20261105000002_runs.sql#L1): lease and checkpoint columns stay private
  - [supabase/migrations/20261105000002_runs.sql:34-35](../../../../supabase/migrations/20261105000002_runs.sql#L34): column-level SELECT grant
  - [scripts/app_db.py:126-129](../../../../scripts/app_db.py#L126): the generator reads every public column
  - [tests/harness/test_verify_profiles.py:112](../../../../tests/harness/test_verify_profiles.py#L112): the fast profile runs nothing when this file changes
- **Evidence:** The README calls generated.ts the row types for the exposed public schema, but the generator selects every column of every public table from information_schema.columns (app_db.py:127-128). 02:34-35 withholds lease_generation and checkpoint_thread_id from authenticated, yet RunsRow lists both (generated.ts:166-167). In all, 24 columns that authenticated cannot select appear in the types: 7 in runs, 12 in approval_requests, 3 in artifacts and 2 in memory_items. Counted by checking the column grants in migrations 02, 11, 16, 21, 22 and 28 against columns added later. git grep finds no import of @autobots/db-types; the db profile only compares the file for drift (app_db.py:632-640).
- **Why it matters:** The only generated artifact for database exposure can't show a change in exposure. A table-level `grant select on public.runs to authenticated` would reveal policy_snapshot and produce no diff. A future consumer would be typed for columns that fail with 'permission denied'.
- **Recommendation:** Generate the row types from the columns authenticated can actually select, checked with has_column_privilege per column, so any grant change shows up as drift in review. Regenerate generated.ts rather than editing it. State in the README that the package is an exposure snapshot checked by the db profile, and drop the exports entry until something imports it.
- **Rule check:** DH-06 and DH-07 ('generated Supabase types limited to intended exposed schemas'; 'Verify generated public DB types'). generated.ts is regenerated, never edited by hand, and SQL keeps owning the schema.
- **Verification:** confirmed. Recomputed the 24 withheld columns (7 runs, 12 approval_requests, 3 artifacts, 2 memory_items) from the column grants and generated.ts, and git grep finds no import of @autobots/db-types.

```text
scripts/app_db.py
def exposed_columns(stack) -> list[Column]:
    select table_name, column_name, data_type, is_nullable from information_schema.columns
    where table_schema = 'public'
      and has_column_privilege('authenticated', format('public.%I', table_name), column_name, 'SELECT')
    order by table_name, ordinal_position
type_cases(): compare row_types(exposed_columns(stack)) with packages/db-types/src/generated.ts
```

### <a id="sqli-07"></a>SQLI-07: Storage policies live in one frozen superuser file with no forward path

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** high · **Occurrences** 1
- **Where:**
  - [supabase/bootstrap/storage.sql:1](../../../../supabase/bootstrap/storage.sql#L1): superuser only, since the migration role can't alter Storage
  - [supabase/bootstrap/storage.sql:22-27](../../../../supabase/bootstrap/storage.sql#L22): members may insert, update and delete in their workspace folder
  - [scripts/persistent_install.py:254-256](../../../../scripts/persistent_install.py#L254): a changed storage.sql is refused
  - [scripts/persistent_install.py:274-277](../../../../scripts/persistent_install.py#L274): applied once, as a single history row
  - [services/agent/src/autobots/adapters/object_storage.py:1-5](../../../../services/agent/src/autobots/adapters/object_storage.py#L1): the product writes with the service key
  - [services/agent/src/autobots/adapters/object_storage.py:55-61](../../../../services/agent/src/autobots/adapters/object_storage.py#L55): objects are never overwritten (x-upsert false)
  - [services/agent/src/autobots/application/artifacts.py:231-233](../../../../services/agent/src/autobots/application/artifacts.py#L231): reads check the hash, so a replaced object reads as missing
- **Evidence:** The Storage policies and can_access_artifact are owned by supabase_admin and live only in bootstrap/storage.sql. The installer records that file once, as a single history row, and refuses it if its digest changes (persistent_install.py:254-256, 274-277). Migrations run as autobots_migrator, which cannot alter storage.objects or functions it doesn't own. The policies let any member insert, overwrite or delete objects under their own workspace folder. That folder includes <workspace>/<run>/, where the API writes artifacts with the service key and x-upsert false; no product path uploads as a member.
- **Why it matters:** Any change to Storage authorization has nowhere to go, such as keeping members out of run folders or revoking anon's EXECUTE on can_access_artifact. Editing the file is refused, and a migration lacks the privilege. Meanwhile, a member who overwrites an object turns a published artifact into artifact_missing.
- **Recommendation:** Give superuser-owned objects the same append-only history as migrations. Use ordered supabase/bootstrap/<14 digits>_<description>.sql files, applied as supabase_admin after migrations by both persistent_install.py and app_db.py, each with its own checksum row; storage.sql stays first and unchanged. Then record a decision on whether members need Storage insert, update or delete at all, and narrow the policies in the next bootstrap file.
- **Rule check:** DH-07 and database.md: never edit an applied file, and never introduce competing history. The ordered bootstrap files would be recorded in the same autobots_install.migrations table that already holds storage.sql's row, and would hold only objects the migration role cannot own. LM-05 says Storage authorization covers upload and deletion. Persistent apply stays the guarded installer's job, as infrastructure.md requires.
- **Verification:** revised. Confirmed the digest refusal (persistent_install.py:254-256), the single history row (274-277) and member write policies (storage.sql:22-27) that no product path uses. The rule check now explains why ordered bootstrap files don't compete with supabase/migrations.

```text
supabase/bootstrap/storage.sql                                (applied, frozen)
supabase/bootstrap/20261112000001_storage_run_folders.sql      (the next change)
persistent_install.guarded_apply(): after migrations and the seed,
  for path in sorted(BOOTSTRAP.glob('[0-9]*_*.sql')): same name, checksum and refusal rules; run via stack.sql
app_db.qualify(): apply the same ordered list on the disposable target
```

### <a id="sqli-08"></a>SQLI-08: Run-scoped lookups and retention guards scan unindexed columns

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [supabase/migrations/20261105000009_tool_gateway.sql:2-14](../../../../supabase/migrations/20261105000009_tool_gateway.sql#L2): tool_receipts is indexed by operation_id only
  - [supabase/migrations/20261105000011_artifacts.sql:6-19](../../../../supabase/migrations/20261105000011_artifacts.sql#L6): no index on artifacts.run_id
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:69-80](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L69): coalesce(root_run_id, id), continues_run_id and tool_receipts.run_id
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:19-30](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L19): r.id::text matches and model_invocations.run_id
  - [services/agent/src/autobots/application/retention.py:122-130](../../../../services/agent/src/autobots/application/retention.py#L122): one purge call per candidate run
  - [services/agent/src/autobots/application/run_projection.py:626](../../../../services/agent/src/autobots/application/run_projection.py#L626): reads receipts by run_id for every projection
- **Evidence:** purge_run_content filters runs by coalesce(root_run_id, id) and by continues_run_id, and filters tool_receipts and artifacts by run_id (27:69-80, 93). None of these columns is covered by any of the 23 indexes the migrations define. The retention pass calls the function once per candidate, in up to 20 batches of 100 (retention.py:14-15, 122-130). expire_idempotency_receipts compares r.id::text for each receipt and filters model_invocations by run_id (27:22, 28-29). The run projection also reads receipts by run_id (run_projection.py:626).
- **Why it matters:** Each purge scans runs twice, plus the receipt and artifact tables, so the cost of a retention pass grows with the number of candidates times table size. Every run view also grows with the receipt ledger. The effect is invisible on fixtures but will show after months of local use.
- **Recommendation:** Write one forward migration that adds the indexes below. Its header should say that the runner's per-file transaction rules out CONCURRENTLY, so each build briefly blocks writes on its table. In the next migration that replaces expire_idempotency_receipts, compare uuids instead of id::text where target holds a uuid.
- **Rule check:** DH-07 (document indexes and locks; use follow-up migrations only).
- **Verification:** confirmed. The migrations define 23 indexes, none on tool_receipts.run_id, artifacts.run_id, runs.continues_run_id, coalesce(root_run_id, id) or model_invocations.run_id. Retention calls the function once per candidate, in up to 20 batches of 100.

```sql
create index tool_receipts_run on app_private.tool_receipts (run_id, status);
create index artifacts_run on public.artifacts (run_id);
create index runs_continues on public.runs (continues_run_id) where continues_run_id is not null;
create index runs_tree on public.runs ((coalesce(root_run_id, id)));
create index model_invocations_open_run on app_private.model_invocations (run_id) where status = 'uncertain' and reconciled_at is null;
```

### <a id="sqli-09"></a>SQLI-09: No current-schema view: live definitions hide in the last migration that touched them

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** low · **Occurrences** 10
- **Where:**
  - [supabase/migrations/20261105000023_operations.sql:45-109](../../../../supabase/migrations/20261105000023_operations.sql#L45): the first purge_run_content, which still shows an open-obligation refusal at 84-86
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:10-103](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L10): both functions restated in full
  - [supabase/migrations/20261107000040_sol_profile.sql:4-19](../../../../supabase/migrations/20261107000040_sol_profile.sql#L4): current profile checks
  - [supabase/migrations/20261108000052_keys_and_vars.sql:4-20](../../../../supabase/migrations/20261108000052_keys_and_vars.sql#L4): current provider checks
  - [supabase/migrations/20261108000053_routine_removal.sql:12-15](../../../../supabase/migrations/20261108000053_routine_removal.sql#L12): current policy_rule check
- **Evidence:** To learn the live retention rules, a reader must know that 27 replaced both functions from 23. File 23, which can't be edited, still shows the open-obligation refusal that 27 removed. Eight named constraints were later dropped and re-created or replaced, so their current text sits in whichever of 23, 26, 40, 51, 52 or 53 ran last. The only generated view of the schema is the public row types.
- **Why it matters:** Reviewing a change to a grant, function or vocabulary means replaying 53 files mentally, and the count grows by several a day. Stale function bodies in early files invite edits based on the wrong version.
- **Recommendation:** Generate a normalized schema snapshot in the db profile with pg_dump --schema-only --no-owner of public, app_private and agent_runtime, including grants and policies. Commit it beside the migrations and check it for drift like the row types. Migrations stay the only history; the snapshot is derived and never applied. When a migration replaces a function, its header should say what changed from the previous body.
- **Rule check:** DH-07 keeps a single schema history. The snapshot is produced by replaying migrations and is never applied, so it doesn't compete with that history, and it is regenerated rather than edited by hand.
- **Verification:** confirmed. Eight distinct constraints are re-created across 23, 26, 40, 51, 52 and 53, and 27 restates both retention functions, while 23's first body still shows the open_obligation refusal at 84-86.

```text
scripts/app_db.py schema   -> supabase/schema.snapshot.sql (generated, Do not edit)
  docker compose exec db pg_dump --schema-only --no-owner -n public -n app_private -n agent_runtime | normalize (drop SET lines, sort grants)
type_cases(): also compare the snapshot; drift fails the db profile
```

### <a id="sqli-10"></a>SQLI-10: Makefile process supervision is untested shell inside Make macros

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [Makefile:93-98](../../../../Makefile#L93): pid and start-time identity; line 98 is 187 characters
  - [Makefile:100-107](../../../../Makefile#L100): stray detection
  - [Makefile:118-138](../../../../Makefile#L118): launch
  - [Makefile:140-150](../../../../Makefile#L140): await
  - [Makefile:176-195](../../../../Makefile#L176): halt
  - [tests/harness/test_tool_keys_env.py:1-23](../../../../tests/harness/test_tool_keys_env.py#L1): only TOOL_KEYS and BROWSER_SWITCH are exercised
- **Evidence:** The macros running, stray_pids, launch, await and halt hold the install's process safety rules. They handle pid reuse after a reboot, refuse to start beside an untracked copy, wait out a drain and never send KILL to a worker that may be in a paid call. They are about 50 lines of $$-escaped shell in define blocks and one-line variables, 66 with their comments. No test or qualifier runs a make target; test_tool_keys_env.py extracts only the TOOL_KEYS and BROWSER_SWITCH lines.
- **Why it matters:** A quoting or escaping slip could start a second paid worker or report a live one as stopped, and only manual use would reveal it. Changing a rule means editing escaped shell that nothing exercises.
- **Recommendation:** Move the supervision into a small Python script with unit tests on a fake process table: a reused pid, a stray copy, a drain timeout, and pinned locale and time zone. Keep today's messages and rules, and make each target a one-line call. The Makefile stays the documented entry point.
- **Rule check:** infrastructure.md and the Makefile's own header (persistent_install.py stays the only path that changes the database, and nothing removes containers or volumes). The rules move unchanged.
- **Verification:** revised. Macros and their rules confirmed, and line 98 is 187 characters. Corrected the size to about 50 lines of shell, 66 with comments, rather than 85.

```text
scripts/local_app.py
  start NAME [--keys] -- CMD...   refuse when tracked or stray; nohup; write pid and lstart
  await NAME PORT URL             our pid holds the port and answers HTTP, 30 tries
  stop NAME                       TERM, wait 45 s, never KILL; report strays
  status
tests/harness/test_local_app.py
Makefile: start-api: ; $(LOCAL_APP) start api --keys -- $(PY) -m uvicorn ...
```

### <a id="sqli-11"></a>SQLI-11: The Makefile re-derives Node, images and install.json, which scripts already handle

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [Makefile:20](../../../../Makefile#L20): nvm path only; the version is never checked
  - [scripts/toolchain.py:160-163](../../../../scripts/toolchain.py#L160): verified search for the pinned Node
  - [Makefile:69-70](../../../../Makefile#L69): grep and sed over the raw overlay
  - [scripts/supabase_stack.py:184-193](../../../../scripts/supabase_stack.py#L184): images from the rendered, merged config
  - [Makefile:12](../../../../Makefile#L12): inline JSON reader
  - [Makefile:215](../../../../Makefile#L215): a second inline JSON reader
- **Evidence:** NODE_BIN prepends ~/.nvm/versions/node/v<.node-version>/bin without checking that it exists. toolchain.find_tools, by contrast, searches PATH and then nvm and accepts only the pinned version (toolchain.py:141-163). `make images` greps image lines out of compose.overlay.yaml, while require_images reads the merged configuration. install.json is parsed by two separate python3.12 -c snippets.
- **Why it matters:** If Node 22.23.2 is installed outside nvm, toolchain bootstrap passes, but make build and start-web run whatever node comes first on PATH, possibly another major version, without any message. A service that upstream adds without an overlay image line is skipped by `make images` and only reported later by the stack check.
- **Recommendation:** Use the scripts that already own these jobs. Add a toolchain.py verb that prints the verified Node directory, and use it for NODE_BIN, with build and start-web failing hard when it is empty. Add a persistent_install.py verb that pulls the rendered stack's images, and use one install.json reader for both lines.
- **Rule check:** The toolchain rules in AGENTS.md (prepared, pinned environments with nothing installed implicitly) still hold, since the new verbs only locate and verify.
- **Verification:** confirmed. Makefile:20 prepends an unchecked nvm path while toolchain.find_tools verifies the version, make images greps the raw overlay while require_images reads the rendered configuration, and install.json has two inline readers (12 and 215).

```text
NODE_BIN = $(shell python3.12 scripts/toolchain.py node-bin)   # verified pinned Node, empty when absent
build and start-web begin with: test -n '$(NODE_BIN)' || { echo 'pinned Node not found, run make toolchain'; exit 1; }
images: ; $(INSTALL) images --project $(PROJECT)   # pulls each rendered service's image
recorded = one reader, e.g. a persistent_install.py show FIELD verb
```

### <a id="sqli-12"></a>SQLI-12: Route limits are prose stitched across migrations, and Sol lacks a shared caveat

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [supabase/migrations/20261106000031_route_qualifications.sql:4-12](../../../../supabase/migrations/20261106000031_route_qualifications.sql#L4): limits is one free-text column
  - [supabase/migrations/20261106000032_terra_reasoning_limit.sql:2-4](../../../../supabase/migrations/20261106000032_terra_reasoning_limit.sql#L2): appended with ||
  - [supabase/migrations/20261106000034_route_limits_from_review.sql:2-3](../../../../supabase/migrations/20261106000034_route_limits_from_review.sql#L2): concurrency caveat appended to every row that existed then
  - [supabase/migrations/20261107000041_sol_route_qualified.sql:1-6](../../../../supabase/migrations/20261107000041_sol_route_qualified.sql#L1): Sol, with the same runner and suite, inserted without it
  - [supabase/migrations/20261108000050_sol_route_requalified.sql:7](../../../../supabase/migrations/20261108000050_sol_route_requalified.sql#L7): rewritten, still without it
  - [docs/engineering/evidence/US-3.4/summary.md:45](../../../../docs/engineering/evidence/US-3.4/summary.md#L45): the runner never touched MP-A09's concurrent admission
- **Evidence:** Each route's limits are one prose string, and migrations 32 and 34 extend it with `limits = limits || ...`. 34:2-3 appends a sentence saying that concurrent admission on a live route wasn't tested to every row that existed then. Sol was qualified with US-3.4's runner and suite (41:1-2), and that story's summary says MP-A09's concurrent admission wasn't touched. Yet 41:6 and 50:7 write Sol's limits without the sentence, the same omission that US-11.12's review found for the first two routes.
- **Why it matters:** Settings shows Sol with fewer stated limits than its evidence supports. A route's current text can only be known by replaying several migrations, and each new route repeats the copy-and-edit step that lost the caveat.
- **Recommendation:** After confirming against the US-14.15 and US-16.4 evidence, add the MP-A09 caveat to Sol's row in a forward migration. US-14.15's verification lists what the runner exercised, and concurrent admission is not among it. When the next route is qualified, consider storing limits as coded items, in a child table or a jsonb array, so that a caveat shared by every route comes from one list, with a check that each qualified route carries the shared codes unless its evidence says otherwise.
- **Rule check:** DH-07: forward migrations only. 31:2-3 still has qualification results recorded by migration once a round has run. Adding a caveat states more limits and never claims a qualification that didn't happen.
- **Verification:** revised. 34:2-3 appended the caveat to the two rows that existed, and 41 and 50 wrote Sol's without it, although Sol was qualified with the US-3.4 runner that never touched MP-A09. Made the structural change optional, since three routes don't yet need it.

```sql
create table agent_runtime.route_qualification_limits (
  profile text not null references agent_runtime.route_qualifications (profile),
  code text not null,   -- mp_a09_concurrent_admission, strict_nested_unsupported, ...
  body text not null,
  primary key (profile, code));
read_route_qualifications(): joins and orders the items; Settings renders the same text
```

### <a id="sqli-13"></a>SQLI-13: Draft graphs written through PostgREST skip the API's validation, and one bad draft breaks the workflow list

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** high · **Occurrences** 1
- **Where:**
  - [supabase/migrations/20261108000046_workflow_drafts.sql:18](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L18): graph is jsonb with no shape check
  - [supabase/migrations/20261108000046_workflow_drafts.sql:26-36](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L26): member write grants and owner policies, which US-15.12#1 asks for
  - [supabase/migrations/20261107000042_user_profiles.sql:6-7](../../../../supabase/migrations/20261107000042_user_profiles.sql#L6): user_profiles repeats the API's bounds in SQL
  - [services/agent/src/autobots/application/workflows.py:192-205](../../../../services/agent/src/autobots/application/workflows.py#L192): the product writes as autobots_runtime
  - [services/agent/src/autobots/application/workflows.py:59-69](../../../../services/agent/src/autobots/application/workflows.py#L59): every view validates the stored draft
  - [services/agent/src/autobots/application/workflows.py:135-141](../../../../services/agent/src/autobots/application/workflows.py#L135): list_workflows builds a view for every workflow
  - [services/agent/src/autobots/application/workflows.py:210](../../../../services/agent/src/autobots/application/workflows.py#L210): discard_draft reads the view before deleting
  - [scripts/app_db.py:250-283](../../../../scripts/app_db.py#L250): cases assert the owner's write as authenticated
- **Evidence:** Of the 24 public tables, only workflow_drafts and user_profiles grant writes to authenticated (46:26, 42:26), guarded by policies built on is_workspace_owner and auth.uid(). The API writes both as autobots_runtime after its own checks (workflows.py:192-205; profiles.py:45), and no web code queries Supabase tables. user_profiles repeats the API's bounds in SQL (42:6-7), but workflow_drafts.graph is any jsonb (46:18). _draft validates the stored graph with WorkflowGraph.model_validate (workflows.py:67-69), list_workflows builds a view for every workflow (135-141), and discard_draft reads the view before deleting (210). US-15.12#1 asks for RLS that lets only the owner write a draft, and US-15.2's RLS scenario has users updating their own names, so both write grants are accepted behavior.
- **Why it matters:** An owner session can store any JSON as a draft graph through PostgREST. From then on, the workspace's workflow list fails validation for every member, and so does the API's discard of that draft, until the row is removed outside the API.
- **Recommendation:** Keep the owner write path that US-15.12 and US-15.2 accept, and make the API survive what it lets through. Have the list and discard paths tolerate a draft that fails WorkflowGraph validation, for example by reporting it as unreadable and deleting it by key. Add a forward-migration CHECK that graph is an object holding nodes and links arrays, added NOT VALID and then validated. Removing the member write grants instead would overturn those accepted scenarios, so it needs a product decision first. user_profiles needs no change.
- **Rule check:** AGENTS.md (Pydantic/OpenAPI owns public API contracts) and database.md (public tables keep RLS). US-15.12#1 and US-15.2's RLS scenario accept the owner and self writes, so they stay. The CHECK arrives in a forward migration, and any change to the view's contract regenerates the API client rather than editing it.
- **Verification:** revised. Grants, policies and the failing read path confirmed. Revised the recommendation because SPECS accepts these RLS writes (US-15.12#1, US-15.2), and dropped user_profiles, whose SQL check already matches the API's bounds.

```sql
alter table public.workflow_drafts add constraint workflow_drafts_graph_shape
  check (jsonb_typeof(graph) = 'object' and jsonb_typeof(graph -> 'nodes') = 'array'
         and jsonb_typeof(graph -> 'links') = 'array') not valid;
alter table public.workflow_drafts validate constraint workflow_drafts_graph_shape;
-- workflows._draft(): on ValidationError, report the draft as unreadable instead of raising
-- discard_draft(): delete by (workflow_id, workspace_id) without building the view first
```

### <a id="sqli-14"></a>SQLI-14: Version references are enforced by a composite key in one table and by nothing in four

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** medium · **Occurrences** 4
- **Where:**
  - [supabase/migrations/20261105000018_workflows.sql:33](../../../../supabase/migrations/20261105000018_workflows.sql#L33): workflow_executions references the exact version
  - [supabase/migrations/20261105000014_experts.sql:30-33](../../../../supabase/migrations/20261105000014_experts.sql#L30): runs.expert_version is a bare integer
  - [supabase/migrations/20261105000015_assignments.sql:12-13](../../../../supabase/migrations/20261105000015_assignments.sql#L12)
  - [supabase/migrations/20261105000020_routines.sql:25](../../../../supabase/migrations/20261105000020_routines.sql#L25): routine_occurrences.routine_version
  - [supabase/migrations/20261105000022_improvements.sql:31-37](../../../../supabase/migrations/20261105000022_improvements.sql#L31): knowledge_heads.active_version
- **Evidence:** workflow_executions declares `foreign key (workflow_id, workflow_version) references public.workflow_versions (workflow_id, version)` (18:33). By contrast, runs.expert_version (14:33), assignments.expert_version (15:13), routine_occurrences.routine_version (20:25) and knowledge_heads.active_version (22:35) are plain integers next to a foreign key on the parent id only. Counted by reading every *_version column that names a row of a versioned table.
- **Why it matters:** Immutable versions are central here (14:1, 18:1, 20:1). Yet a run, assignment, occurrence or knowledge head can name a version that never existed, and only application code prevents it.
- **Recommendation:** Write one forward migration that adds the composite foreign keys as NOT VALID and then runs VALIDATE CONSTRAINT. Try it first on a restored copy, as upgrade.md describes; a validation failure reveals drift worth finding. MATCH SIMPLE keeps the nullable pairs in runs and knowledge_heads valid when either column is null.
- **Rule check:** DH-07 (constraints and foreign keys are part of database acceptance; forward migrations only).
- **Verification:** confirmed. Only workflow_executions has a composite version key. runs, assignments, routine_occurrences and knowledge_heads hold bare integers, while expert_versions, routine_versions and knowledge_versions have the composite keys these foreign keys need.

```sql
alter table public.runs add constraint runs_expert_version_fk
  foreign key (expert_id, expert_version) references public.expert_versions (expert_id, version) not valid;
alter table public.runs validate constraint runs_expert_version_fk;
-- likewise app_private.assignments, public.routine_occurrences (routine_id, routine_version),
-- public.knowledge_heads (workspace_id, kind, key, active_version) -> public.knowledge_versions
```

### <a id="sqli-15"></a>SQLI-15: The synthetic H1 stack runs on images the install doesn't use, and nothing pulls them

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** medium · **Occurrences** 2
- **Where:**
  - [infra/disposable/compose.yaml:3](../../../../infra/disposable/compose.yaml#L3): not the coordinated self-hosted release
  - [infra/disposable/compose.yaml:12](../../../../infra/disposable/compose.yaml#L12): postgres 17.6.1.106
  - [infra/disposable/compose.yaml:31](../../../../infra/disposable/compose.yaml#L31): storage-api v1.35.3
  - [infra/supabase/compose.overlay.yaml:35](../../../../infra/supabase/compose.overlay.yaml#L35): storage-api v1.81.0
  - [infra/supabase/compose.overlay.yaml:54](../../../../infra/supabase/compose.overlay.yaml#L54): postgres 17.6.1.136
  - [scripts/verify.py:133](../../../../scripts/verify.py#L133): the db profile's first step uses it
  - [scripts/supabase_stack.py:32-33](../../../../scripts/supabase_stack.py#L32): the application checks run on the overlay's family
- **Evidence:** infra/disposable/compose.yaml pins public.ecr.aws/supabase/postgres:17.6.1.106 and storage-api v1.35.3, while the install overlay pins supabase/postgres:17.6.1.136 and storage-api v1.81.0. US-1.7's verification records that these images were already on the machine for unrelated projects, and it left DH-07's same-family requirement to US-2.1. The application checks in the same profile (supabase_stack, app_db and identity) now run on the overlay's family through supabase_stack.py:32-33, so the gap is the first step only: disposable_db.py's guard, synthetic migration and Storage fixture qualification. No make target, script or runbook pulls the two older images.
- **Why it matters:** On a fresh machine, the db profile stops at a prerequisite until someone pulls two images named only in an error message, and the H1 guard evidence runs on images the install never runs.
- **Recommendation:** Re-pin the db and storage services in infra/disposable/compose.yaml to the overlay's digests, which make images already pulls. Adjust the storage environment variables as v1.81 needs, then requalify the db profile. Alternatively, read both images from the rendered overlay so the two sets can't drift.
- **Rule check:** DH-07 ('Use the same pinned Compose family for integration coverage') and infrastructure.md (pin and qualify images).
- **Verification:** revised. Pins confirmed, but app_db and qualify_identity run on the overlay's family (supabase_stack.py:32-33), so only the synthetic H1 step differs. Lowered the severity to low.

### <a id="sqli-16"></a>SQLI-16: The disposable reset names every public table and function by hand

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 27
- **Where:**
  - [scripts/app_db.py:114-123](../../../../scripts/app_db.py#L114): 24 tables and 3 functions listed in one string
  - [supabase/migrations/20261108000046_workflow_drafts.sql:3](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L3): a migration's new public function...
  - [supabase/migrations/20261108000046_workflow_drafts.sql:15](../../../../supabase/migrations/20261108000046_workflow_drafts.sql#L15): ...and table, both also added to the reset
  - [supabase/migrations/20261107000042_user_profiles.sql:4-11](../../../../supabase/migrations/20261107000042_user_profiles.sql#L4)
- **Evidence:** reset() drops app_private and agent_runtime by schema but drops public objects by name: a 24-table `drop table if exists public.workflow_drafts, public.user_profiles, ... public.workspaces cascade`, followed by three `drop function if exists` lines. Every migration that adds a public table or function must also edit this string.
- **Why it matters:** This is a hidden second edit in the area's most common change. Forgetting it shows up later as an 'already exists' failure when the disposable target replays from clean.
- **Recommendation:** Derive the drop list from the catalog on the marker-checked disposable target: the tables and functions in schema public owned by autobots_migrator. Keep the marker check first.
- **Rule check:** DH-07 and database.md: the reset still requires the disposable-target marker and never reaches the persistent instance.
- **Verification:** confirmed. reset() lists exactly the 24 public tables the migrations create, plus three functions, so each new public table or function needs a second edit here.

```python
def reset(stack):
    require_marker(stack)
    stack.sql(do-block: drop each pg_class table in public owned by 'autobots_migrator'::regrole with cascade;
              drop each pg_proc function in public owned by 'autobots_migrator'::regrole;
              drop schema if exists app_private, agent_runtime cascade; truncate autobots_disposable.migrations)
```

### <a id="sqli-17"></a>SQLI-17: The terminal-state predicate is spelled out nine times in SQL

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 9
- **Where:**
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:24](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L24)
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:62](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L62)
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:70](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L70)
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:74](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L74)
  - [supabase/migrations/20261105000023_operations.sql:65-122](../../../../supabase/migrations/20261105000023_operations.sql#L65): four copies in the superseded bodies
  - [services/agent/src/autobots/domain/runs.py:22](../../../../services/agent/src/autobots/domain/runs.py#L22): Python's TERMINAL
  - [services/agent/src/autobots/application/retention.py:107](../../../../services/agent/src/autobots/application/retention.py#L107): a Python query repeats it
- **Evidence:** `status not in ('succeeded', 'failed', 'cancelled')` appears four times in the live bodies of purge_run_content and expire_idempotency_receipts (27:24, 62, 70, 74), four times in 23's superseded bodies and once at 27:8. Python defines TERMINAL once (domain/runs.py:22), and retention.py:107 repeats the list in a query. Counted with a grep for the literal list.
- **Why it matters:** The Option B contract owns run states, but SQL keeps its own unlinked copies, so reviewing a state change means finding them by grep.
- **Recommendation:** The next migration that replaces these functions should add app_private.run_is_terminal(status text) and use it, and the catalog check should compare its set with TERMINAL.
- **Rule check:** option-b-contract.md owns the canonical states. The helper arrives in a forward migration and changes no state.
- **Verification:** confirmed. Nine SQL copies recounted: 4 live in 27, 4 superseded in 23 and 1 in 27's data update. In Python the list also repeats at retention.py:107, routines.py:306 and runs.py:346.

```sql
create function app_private.run_is_terminal(status text) returns boolean
  language sql immutable set search_path = ''
  as $$ select status in ('succeeded', 'failed', 'cancelled') $$;
```

### <a id="sqli-18"></a>SQLI-18: Some migrations are named for a review round and bundle unrelated changes

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [supabase/migrations/20261105000028_review_majors.sql:1-10](../../../../supabase/migrations/20261105000028_review_majors.sql#L1): three unrelated changes
  - [supabase/migrations/20261105000027_retention_and_adapter_rules.sql:1-2](../../../../supabase/migrations/20261105000027_retention_and_adapter_rules.sql#L1)
  - [supabase/migrations/20261106000034_route_limits_from_review.sql:1](../../../../supabase/migrations/20261106000034_route_limits_from_review.sql#L1)
  - [supabase/migrations/20261108000053_routine_removal.sql:10-15](../../../../supabase/migrations/20261108000053_routine_removal.sql#L10): approval policy rule inside routine removal
  - [scripts/persistent_install.py:251-253](../../../../scripts/persistent_install.py#L251): applied names can't change
- **Evidence:** Migration 28, named review_majors, adds workflow_executions.current_instance and memory_items.expert_id and makes knowledge heads nullable. Migration 27 mixes retention keys, obligation cleanup, two function replacements and adapter qualification evidence. Migration 53 adds the action_marked rule for approval_requests inside routine_removal.
- **Why it matters:** File names are the index of the schema history. Finding where memory_items.expert_id came from takes a grep, and a review-round name says nothing about the schema.
- **Recommendation:** For new migrations, put one concern in each file and name it for the object and the change, for example memory_items_expert_link. Applied names stay as they are, because the installer refuses when an applied name is missing.
- **Rule check:** DH-07 (<timestamp>_<description>.sql). Applied files are never renamed or edited.
- **Verification:** confirmed. 28, 27, 34 and 53 confirmed. Their headers name each bundled change, so the cost is in the file names, which the installer forbids changing once applied.

### <a id="sqli-19"></a>SQLI-19: The install overlay sets no resource limits, and its list overrides can drop upstream mounts

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** medium · **Occurrences** 8
- **Where:**
  - [infra/supabase/compose.overlay.yaml:4-69](../../../../infra/supabase/compose.overlay.yaml#L4): no mem_limit or cpus on any service
  - [infra/supabase/compose.overlay.yaml:60-69](../../../../infra/supabase/compose.overlay.yaml#L60): db volumes restated with !override
  - [infra/supabase/upstream/docker-compose.yml:482-499](../../../../infra/supabase/upstream/docker-compose.yml#L482): the upstream list the override copies
  - [scripts/supabase_stack.py:146-152](../../../../scripts/supabase_stack.py#L146): the mount check covers safety, not completeness
- **Evidence:** No service in the overlay or upstream sets mem_limit or cpus. DH-08 asks to check resource limits, and the deployment PRD says to begin with bounded containers, noting that no capacity result exists yet (PRD-Local-Mac-Deployment.md:119). The db volume list restates upstream's seven init scripts under !override. The merged-config check verifies that mounts are read-only and inside upstream/volumes, but not that every upstream init script is still mounted.
- **Why it matters:** A runaway Studio or imgproxy container can take the Mac's memory away from the database. An upstream upgrade that adds an init script would be dropped silently by the override.
- **Recommendation:** Measure first, then add per-service limits, starting with studio, imgproxy and meta and leaving db for last with headroom. Add a check in supabase_stack.py that every upstream /docker-entrypoint-initdb.d target stays mounted in the merged db service.
- **Rule check:** DH-08 and infrastructure.md ('inspect health/resource limits and persistent mounts'). The limits follow a measurement, as the deployment PRD says.
- **Verification:** confirmed. No mem_limit or cpus in the overlay, upstream or disposable files, the db volume list restates upstream's seven init scripts under !override, and supabase_stack.py:146-150 checks only mount safety.

### <a id="sqli-20"></a>SQLI-20: The browser entrypoint fails opaquely when Chromium can't be found or started

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [infra/browser/browser-entrypoint.js:15-17](../../../../infra/browser/browser-entrypoint.js#L15): find() results used unchecked
  - [infra/browser/browser-entrypoint.js:20](../../../../infra/browser/browser-entrypoint.js#L20): spawn without an error listener
  - [infra/browser/browser-entrypoint.js:53](../../../../infra/browser/browser-entrypoint.js#L53): only exit is handled
  - [infra/browser/browser-entrypoint.js:55-66](../../../../infra/browser/browser-entrypoint.js#L55): no server error listener
- **Evidence:** root and platform come from Array.find and are interpolated straight into paths. If the Playwright layout differs after a re-pin, readdirSync throws ENOENT on /ms-playwright/undefined. A failed spawn emits an 'error' event that nothing handles, so Node crashes with a stack trace, and the DevTools forwarder has no 'error' listener either.
- **Why it matters:** The executor sees only a dead container. The reason sits in a stack trace in the container logs instead of a one-line cause.
- **Recommendation:** Exit with a one-line reason when either lookup fails. Handle Chromium's 'error' event by logging and exiting with status 1, and handle the server's 'error' event the same way.
- **Rule check:** DH-06 (errors carry their cause). The sandbox flags and egress rules are unchanged.
- **Verification:** confirmed. find() results are used unchecked at 15-17, and neither the spawn at 20 nor the server at 55-66 has an 'error' listener; per-connection errors are handled at 63-64.

## Rejected during verification

None. Every finding survived verification, some with corrections noted under Verification.

## Not covered

This was a static review. No database, Compose stack or image build was run, so two claims are reasoned from code and catalog rules rather than observed: that anon keeps EXECUTE on can_access_artifact through Supabase's default privileges for supabase_admin, and what the unindexed lookups cost. Several files outside this area were read only at the cited lines to confirm couplings: scripts/app_db.py, scripts/persistent_install.py, scripts/supabase_stack.py, scripts/toolchain.py, scripts/qualify_identity.py, scripts/qualify_browser_executor.py, tests/db/operations_check.py, tests/db/sol_profile_check.py, and the service modules for artifacts, workflows, retention and the browser executor. Their own quality is left to their areas. The vendored infra/supabase/upstream files were read only to compare the overlay's overrides. packages/db-types/src/generated.ts was read only to judge whether it reflects grants, not for its style. PRD-Development-Harness.md DH-03, DH-06, DH-07 and DH-08, and metrics.md, were read in the relevant sections, not in full. No earlier review exists to compare against.
