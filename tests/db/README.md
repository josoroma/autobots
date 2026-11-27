# Database, worker and fault checks

Scripts and SQL that the disposable-stack qualifiers run against real Postgres, Storage and worker processes.
They act only on the disposable targets their invoker provides (AGENTS.md). Files are grouped by role
(refactor plan R-66, TDBC-09):

- `checks/`: each prints one JSON line of cases, `{"cases": [...]}`, which `scripts/qualification/children.py`
  replays into its qualifier's report (PRD-Development-Harness DH-W04). A check may add `browser_env` for the
  browser suites. New checks use `fixtures/checklib.py` and list their scenarios in a `SCENARIOS` tuple, run
  by `run_scenarios`: the first scenario to fail stops the rest, and the cases so far are still printed. Such a
  check passes `run_check` its parent's timeout, so it stops and prints before the parent would kill it, and
  starts its workers through `started_worker` or `run_worker`, which kill them however the scenario ends.
- `workers/`: processes a check or qualifier starts, and often kills on purpose.
- `arrange/`: arrangements and live actions. Each prints what its caller reads and no cases.
- `fixtures/`: modules the others import: the case protocol, scripted models, sinks and graphs.
- `sql/h1/`: the synthetic H1 stack's schema, seeds and fixtures. `sql/app/`: the application stack's fixtures.

Invokers name each script with its folder, such as `checks/memory_check.py`, and run it with the service's
interpreter, `services/agent/src` and `tests/db/fixtures` on `PYTHONPATH` (`children.service_env`). A worker or
browser helper that a script starts inherits that path. `scripts/qualify_upgrade.py` also runs the flat
`tests/db` of an older revision it archives, with that revision's own paths.

| File | Role | Invoker |
|---|---|---|
| `checks/admission_check.py` | check | `scripts/app_db.py` |
| `checks/admission_replay_check.py` | check | `scripts/app_db.py` |
| `checks/approval_check.py` | check, with `browser_env` for `approvals.spec.ts` | `scripts/qualify_identity.py` |
| `checks/artifact_check.py` | check | `scripts/qualify_identity.py` |
| `checks/assignment_check.py` | check; starts `workers/assignment_worker.py` | `scripts/qualify_identity.py` |
| `checks/browse_goal_check.py` | check, live | `scripts/qualify_browse_goal.py` (manual, `scripts/suites.py`) |
| `checks/browser_executor_check.py` | check, live | `scripts/qualify_browser_executor.py` (manual, `scripts/suites.py`) |
| `checks/browser_use_check.py` | check, live | `scripts/qualify_browser_executor.py` (manual, `scripts/suites.py`) |
| `checks/browsing_loop_check.py` | check | `scripts/app_db.py` |
| `checks/child_run_records_check.py` | check | `scripts/qualify_identity.py` |
| `checks/concept_seed_check.py` | check | `scripts/qualify_identity.py` |
| `checks/connector_check.py` | check | `scripts/qualify_identity.py` |
| `checks/credential_store_check.py` | check | `scripts/app_db.py` |
| `checks/cronjob_check.py` | check | `scripts/app_db.py` |
| `checks/effect_check.py` | check, with `browser_env`; starts `workers/effect_worker.py` | `scripts/qualify_identity.py` |
| `checks/effects_routines_and_retention_check.py` | check | `scripts/qualify_identity.py` |
| `checks/expert_check.py` | check | `scripts/app_db.py` |
| `checks/goal_loop_check.py` | check; starts `workers/goal_loop_worker.py` | `scripts/app_db.py` |
| `checks/improvement_check.py` | check | `scripts/qualify_identity.py` |
| `checks/keys_and_vars_check.py` | check | `scripts/app_db.py` |
| `checks/browse_steps_check.py` | check | `scripts/app_db.py` |
| `checks/browse_turn_check.py` | check | `scripts/app_db.py` |
| `checks/local_offering_check.py` | check | `scripts/app_db.py` |
| `checks/stealth_check.py` | check, live | `scripts/qualify_browser_executor.py` (manual, `scripts/suites.py`) |
| `checks/transcript_check.py` | check | `scripts/app_db.py` |
| `checks/retired_tools_check.py` | check | `scripts/app_db.py` |
| `checks/browsing_yolo_check.py` | check | `scripts/app_db.py` |
| `checks/memory_check.py` | check | `scripts/app_db.py` |
| `checks/model_endpoint_check.py` | check | `scripts/app_db.py` |
| `checks/operations_check.py` | check: `retention` | `scripts/qualify_operations.py` |
| `checks/pause_cancel_and_fencing_check.py` | check | `scripts/qualify_identity.py` |
| `checks/provider_key_check.py` | check, with `browser_env` for `experts.spec.ts` | `scripts/qualify_identity.py` |
| `checks/pull_request_check.py` | check | `scripts/qualify_identity.py` |
| `checks/recovery_check.py` | check; starts `workers/sleeping_worker.py` | `scripts/app_db.py` |
| `checks/restore_check.py` | check: `verify`; `seed` arranges its credential | `scripts/qualify_backup.py` |
| `checks/result_stream_check.py` | check, with `browser_env` for `stream-result.spec.ts` | `scripts/qualify_identity.py` |
| `checks/routine_check.py` | check | `scripts/app_db.py` |
| `checks/run_admission_check.py` | check | `scripts/app_db.py` |
| `checks/run_list_check.py` | check | `scripts/app_db.py` |
| `checks/schema_release_check.py` | check | `scripts/qualify_identity.py` |
| `checks/sol_profile_check.py` | check | `scripts/app_db.py` |
| `checks/task_timing_check.py` | check, with `browser_env` for `run-panel.spec.ts` | `scripts/qualify_identity.py` |
| `checks/tool_gateway_check.py` | check | `scripts/app_db.py` |
| `checks/tool_keys_check.py` | check | `scripts/app_db.py` |
| `checks/tool_use_check.py` | check | `scripts/app_db.py` |
| `checks/tool_use_view_check.py` | check, with `browser_env` for `run-workspace.spec.ts` | `scripts/qualify_identity.py` |
| `checks/unreadable_draft_check.py` | check | `scripts/app_db.py` |
| `checks/upgrade_check.py` | check: `upgrade` and `adapter` | `scripts/qualify_upgrade.py`; `adapter` by hand (`docs/engineering/runbooks/upgrade.md`) |
| `checks/verification_check.py` | check | `scripts/qualify_identity.py` |
| `checks/wake_check.py` | check | `scripts/qualify_identity.py` |
| `checks/web_tools_check.py` | check | `scripts/app_db.py` |
| `checks/worker_failure_check.py` | check | `scripts/app_db.py` |
| `checks/worker_ownership_check.py` | check; starts `workers/ownership_worker.py` | `scripts/app_db.py` |
| `checks/workflow_check.py` | check | `scripts/app_db.py` |
| `checks/workflow_run_check.py` | check; starts `workers/workflow_worker.py` | `scripts/qualify_identity.py` |
| `workers/assignment_worker.py` | worker, killed inside a model call | `checks/assignment_check.py` |
| `workers/effect_worker.py` | worker, killed after an effect | `checks/effect_check.py` |
| `workers/goal_loop_worker.py` | worker, killed mid-loop | `checks/goal_loop_check.py` |
| `workers/operations_worker.py` | fixture worker that serves jobs | `scripts/qualification/ops.py` (operations and backup), `scripts/qualify_upgrade.py` |
| `workers/ownership_worker.py` | worker, killed after a commit | `checks/worker_ownership_check.py` |
| `workers/product_inference_worker.py` | the product worker over a fake transport | `scripts/qualify_worker_inference.py` (manual) |
| `workers/sleep_inference_worker.py` | the product worker for a real Mac sleep | `scripts/qualify_mac_sleep.py` (manual) |
| `workers/sleeping_worker.py` | worker stopped past its lease | `checks/recovery_check.py` |
| `workers/workflow_worker.py` | worker, killed inside a workflow node | `checks/workflow_run_check.py` |
| `arrange/browser_runs.py` | runs no screen reaches by itself | `scripts/qualify_identity.py` |
| `arrange/model_sources.py` | a run with recorded binding sources | `scripts/qualify_identity.py` |
| `arrange/notify_live.py` | live: runs start waiting while a page watches | `settings-sections.spec.ts` |
| `arrange/operations_live.py` | live: worker heartbeats and jobs | `operations-values.spec.ts`, `operations-jobs.spec.ts` |
| `arrange/product_inference.py` | what the worker inference qualifiers arrange or read back | `scripts/qualify_worker_inference.py`, `scripts/qualify_mac_sleep.py` (manual) |
| `arrange/result_stream_live.py` | live: a streamed result | `stream-result.spec.ts` |
| `arrange/run_commands.py` | `admit`, `cancel` and `resume` | `scripts/qualification/ops.py`, `scripts/qualify_operations.py`, `scripts/qualify_backup.py`, `scripts/qualify_upgrade.py` |
| `arrange/run_files_probe.py` | reads a run's input files | `run-workspace.spec.ts` |
| `arrange/task_timing_live.py` | live: task times | `run-panel.spec.ts` |
| `arrange/tool_use_live.py` | live: tool uses | `run-workspace.spec.ts` |
| `fixtures/browse_rig.py` | the real gateway and executor with a scripted model, and an Expert for each browser | `checks/stealth_check.py` |
| `fixtures/checklib.py` | the case protocol and shared arrangements | the checks; `tests/harness/test_db_case_protocol.py` |
| `fixtures/effect_tools.py` | tools that deliver to a sink | `checks/effect_check.py`, `workers/effect_worker.py`, `arrange/browser_runs.py` |
| `fixtures/goal_loop_script.py` | the scripted model, with a planted key | the checks, workers and arrangements that drive a loop |
| `fixtures/mock_sink.py` | a destination that records deliveries | `fixtures/effect_tools.py` and its users |
| `fixtures/stream_script.py` | the scripted model, streaming | `checks/result_stream_check.py`, `arrange/result_stream_live.py` |
| `fixtures/worker_graph.py` | a graph that writes an effect log | `checks/worker_ownership_check.py`, `workers/ownership_worker.py` |
| `sql/h1/migrations/`, `sql/h1/bad_migrations/`, `sql/h1/seeds/` | the synthetic H1 stack's history, a failing migration and seeds | `scripts/disposable_db.py` |
| `sql/h1/storage_policies.sql`, `sql/h1/worker_fixture.sql` | Storage policies and the stub worker's tables | `scripts/disposable_db.py` |
| `sql/app/fixture.sql`, `sql/app/bad_migrations/` | the application stack's fixture and a failing migration | `scripts/app_db.py` |
| `sql/app/identity/` | each identity arrangement's SQL | `scripts/qualify_identity.py` |

Browser specs live in `apps/web/tests/browser/` and reach `arrange/` through `support/db-helpers.ts`.
