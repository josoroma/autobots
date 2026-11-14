# Code-quality review metrics

Measurement step only. These are tool outputs, not findings or opinions.

## 1. Run

| Item | Value |
|---|---|
| Timestamp | 2026-11-12-09-52-30 |
| Revision | 156534da0bd5b19417f05d313077d767804b175b |
| Working tree | 2 porcelain entries, both untracked: `.claude/workflows/`, `docs/reviews/` |
| ruff | 0.17.3 (services/agent/.venv) |
| Python | 3.12.16 |
| Node | v22.23.2 |
| ESLint | v9.39.5 (apps/web) |
| Raw outputs | `.checks/reviews/review-2026-11-12-09-52-30/` (ignored) |

## 2. Size

In-scope files: 545 (listed in `files.txt` of the raw directory).

### Lines by area

| Area | Files | Lines |
|---|---|---|
| .claude | 1 | 243 |
| apps/web | 146 | 24477 |
| infra | 6 | 249 |
| Makefile | 1 | 234 |
| package.json | 1 | 13 |
| packages/api-client | 4 | 244 |
| packages/db-types | 1 | 9 |
| scripts | 28 | 10215 |
| services/agent | 186 | 35925 |
| supabase | 56 | 1565 |
| tests/db | 75 | 10793 |
| tests/faults | 15 | 142 |
| tests/harness | 15 | 3567 |
| tests/qualification | 2 | 66 |
| tests/toolchain | 5 | 673 |
| tests/web | 3 | 267 |

### 25 largest files

| Lines | File |
|---|---|
| 1149 | services/agent/tests/test_worker_inference.py |
| 1057 | apps/web/tests/browser/slice-visual.spec.ts |
| 864 | apps/web/components/run-workspace.tsx |
| 853 | apps/web/components/tool-catalog.tsx |
| 810 | scripts/persistent_install.py |
| 783 | tests/harness/test_assistant_assets.py |
| 782 | services/agent/src/autobots/application/goal_loop.py |
| 773 | apps/web/components/approvals-panel.tsx |
| 754 | scripts/qualify_identity.py |
| 739 | apps/web/components/workflow-editor.tsx |
| 732 | services/agent/src/autobots/operations/route_qualification.py |
| 721 | scripts/app_db.py |
| 703 | tests/harness/test_hooks.py |
| 674 | services/agent/src/autobots/adapters/loop_middleware.py |
| 664 | services/agent/src/autobots/application/run_projection.py |
| 660 | scripts/disposable_db.py |
| 653 | apps/web/components/goal-composer.tsx |
| 649 | apps/web/components/workflows-panel.tsx |
| 630 | scripts/specs.py |
| 624 | apps/web/tests/browser/experts.spec.ts |
| 594 | services/agent/src/autobots/application/tool_gateway.py |
| 550 | services/agent/src/autobots/application/workflows.py |
| 539 | apps/web/components/operations-panel.tsx |
| 533 | apps/web/tests/browser/appearance.spec.ts |
| 521 | services/agent/tests/test_route_qualification.py |

### Generated files (out of scope)

| Lines | File |
|---|---|
| 9604 | packages/api-client/src/generated.ts |
| 270 | packages/db-types/src/generated.ts |
| 14628 | contracts/generated/openapi.json |

## 3. Python functions and documentation

| Area | Files | Lines | Functions | Over 40 lines | Over 80 | Over 150 | Public functions documented | Files without module docstring | Broad except | type: ignore |
|---|---|---|---|---|---|---|---|---|---|---|
| .claude | 1 | 243 | 11 | 0 | 0 | 0 | 55% | 0 | 2 | 0 |
| scripts | 28 | 10215 | 433 | 39 | 17 | 10 | 30% | 0 | 3 | 15 |
| services/agent/src | 1 | 1 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 |
| services/agent/src/autobots/adapters | 22 | 4103 | 200 | 14 | 7 | 3 | 39% | 0 | 3 | 1 |
| services/agent/src/autobots/api | 21 | 3206 | 150 | 8 | 2 | 0 | 24% | 0 | 0 | 6 |
| services/agent/src/autobots/application | 46 | 11831 | 483 | 58 | 14 | 0 | 57% | 0 | 16 | 7 |
| services/agent/src/autobots/contracts | 27 | 3196 | 20 | 0 | 0 | 0 | 38% | 0 | 0 | 0 |
| services/agent/src/autobots/domain | 11 | 1568 | 46 | 2 | 0 | 0 | 53% | 0 | 0 | 0 |
| services/agent/src/autobots/operations | 9 | 2561 | 122 | 8 | 1 | 1 | 28% | 0 | 11 | 4 |
| services/agent/src/autobots/persistence | 2 | 21 | 0 | 0 | 0 | 0 | - | 0 | 0 | 0 |
| services/agent/tests | 46 | 9379 | 872 | 8 | 2 | 0 | 4% | 0 | 0 | 44 |
| tests/db | 67 | 10620 | 444 | 46 | 35 | 19 | 6% | 0 | 23 | 9 |
| tests/faults | 12 | 137 | 12 | 0 | 0 | 0 | 8% | 5 | 0 | 0 |
| tests/harness | 15 | 3567 | 395 | 0 | 0 | 0 | 4% | 0 | 0 | 0 |
| tests/qualification | 2 | 66 | 3 | 0 | 0 | 0 | 0% | 0 | 0 | 0 |
| tests/toolchain | 5 | 673 | 74 | 0 | 0 | 0 | 9% | 0 | 2 | 0 |
| tests/web | 3 | 267 | 17 | 1 | 0 | 0 | 23% | 0 | 0 | 1 |

### 40 longest Python functions

| Lines | Function | Location | Parameters |
|---|---|---|---|
| 410 | qualify | scripts/qualify_worker_inference.py:65 | 1 |
| 326 | qualify | scripts/qualify_identity.py:414 | 1 |
| 316 | main | tests/db/verification_check.py:52 | 0 |
| 315 | attempt | scripts/qualify_release.py:76 | 3 |
| 290 | main | tests/db/assignment_check.py:49 | 0 |
| 270 | main | tests/db/recovery_check.py:46 | 0 |
| 254 | main | tests/db/tool_keys_check.py:86 | 0 |
| 250 | qualify | scripts/qualify_backup.py:43 | 1 |
| 247 | main | tests/db/workflow_run_check.py:75 | 0 |
| 243 | main | tests/db/improvement_check.py:42 | 0 |
| 240 | qualify | scripts/qualify_operations.py:136 | 1 |
| 227 | main | tests/db/blocker_check.py:51 | 0 |
| 226 | github_pull_request_tool | services/agent/src/autobots/adapters/github_pulls.py:68 | 2 |
| 221 | main | tests/db/web_tools_check.py:76 | 0 |
| 215 | qualify | scripts/qualify_upgrade.py:47 | 1 |
| 214 | main | tests/db/keys_and_vars_check.py:86 | 0 |
| 212 | github_read_tools | services/agent/src/autobots/adapters/github_reads.py:61 | 2 |
| 209 | main | tests/db/approval_check.py:63 | 0 |
| 196 | main | tests/db/goal_loop_check.py:38 | 0 |
| 196 | effects_and_assignments | tests/db/major_check.py:64 | 1 |
| 192 | run_trial | services/agent/src/autobots/operations/browse_trial.py:137 | 7 |
| 192 | main | tests/db/cronjob_check.py:51 | 0 |
| 190 | main | tests/db/review_check.py:73 | 0 |
| 189 | main | tests/db/worker_ownership_check.py:39 | 0 |
| 188 | tavily_tools | services/agent/src/autobots/adapters/tavily.py:42 | 3 |
| 165 | observe | scripts/qualify_mac_sleep.py:105 | 1 |
| 164 | examples | scripts/persistent_install.py:535 | 5 |
| 162 | main | tests/db/artifact_check.py:77 | 0 |
| 162 | main | tests/db/tool_gateway_check.py:61 | 0 |
| 160 | browser_cases | scripts/qualify_identity.py:252 | 14 |
| 159 | main | tests/db/connector_check.py:79 | 0 |
| 155 | main | tests/db/effect_check.py:41 | 0 |
| 153 | goal | scripts/persistent_install.py:324 | 8 |
| 145 | main | tests/db/run_list_check.py:30 | 0 |
| 144 | main | tests/db/browse_goal_check.py:70 | 0 |
| 140 | attempt | scripts/live_goal.py:49 | 4 |
| 134 | market_tools | services/agent/src/autobots/adapters/market_data.py:78 | 2 |
| 134 | assign_tool | services/agent/src/autobots/application/assignments.py:177 | 1 |
| 133 | main | tests/db/wake_check.py:64 | 0 |
| 131 | main | tests/db/routine_check.py:44 | 0 |

## 4. Python complexity and parameters

Scope: `services/agent/src`, rules C901 (max complexity 10), PLR0911, PLR0912, PLR0913, PLR0915, PLR0917.

| Rule | Hits |
|---|---|
| PLR0913 | 62 |
| PLR0917 | 38 |
| C901 | 24 |
| PLR0911 | 11 |
| PLR0912 | 6 |
| PLR0915 | 5 |

| Rule | Measured | Message | Location |
|---|---|---|---|
| C901 | 37 | github_pull_request_tool is too complex (37 > 10) | services/agent/src/autobots/adapters/github_pulls.py:68 |
| C901 | 21 | validate_graph is too complex (21 > 10) | services/agent/src/autobots/domain/workflows.py:214 |
| C901 | 19 | _dispatch is too complex (19 > 10) | services/agent/src/autobots/application/tool_gateway.py:322 |
| C901 | 18 | github_read_tools is too complex (18 > 10) | services/agent/src/autobots/adapters/github_reads.py:61 |
| C901 | 17 | assign_tool is too complex (17 > 10) | services/agent/src/autobots/application/assignments.py:177 |
| C901 | 15 | github_issue_tool is too complex (15 > 10) | services/agent/src/autobots/adapters/github_issues.py:145 |
| C901 | 15 | _admitted_call is too complex (15 > 10) | services/agent/src/autobots/adapters/loop_middleware.py:491 |
| C901 | 15 | market_tools is too complex (15 > 10) | services/agent/src/autobots/adapters/market_data.py:78 |
| C901 | 14 | run_goal is too complex (14 > 10) | services/agent/src/autobots/application/goal_loop.py:291 |
| C901 | 14 | validate_proposal is too complex (14 > 10) | services/agent/src/autobots/application/plans.py:61 |
| C901 | 14 | next_steps is too complex (14 > 10) | services/agent/src/autobots/domain/workflow_execution.py:199 |
| C901 | 13 | browse is too complex (13 > 10) | services/agent/src/autobots/application/browsing_loop.py:217 |
| C901 | 13 | plan_tools is too complex (13 > 10) | services/agent/src/autobots/application/plans.py:177 |
| C901 | 13 | apply_command is too complex (13 > 10) | services/agent/src/autobots/application/runs.py:390 |
| C901 | 13 | _run_block is too complex (13 > 10) | services/agent/src/autobots/application/workflow_runner.py:163 |
| C901 | 12 | partial_object is too complex (12 > 10) | services/agent/src/autobots/adapters/result_stream.py:117 |
| C901 | 12 | tavily_tools is too complex (12 > 10) | services/agent/src/autobots/adapters/tavily.py:42 |
| C901 | 12 | post_run is too complex (12 > 10) | services/agent/src/autobots/api/run_routes.py:177 |
| C901 | 11 | _keep_lease is too complex (11 > 10) | services/agent/src/autobots/application/goal_loop.py:491 |
| C901 | 11 | _finish is too complex (11 > 10) | services/agent/src/autobots/application/goal_loop.py:697 |
| C901 | 11 | verify_candidate is too complex (11 > 10) | services/agent/src/autobots/application/verification.py:35 |
| C901 | 11 | _config_errors is too complex (11 > 10) | services/agent/src/autobots/domain/workflows.py:104 |
| C901 | 11 | _iteration_errors is too complex (11 > 10) | services/agent/src/autobots/domain/workflows.py:145 |
| C901 | 11 | run_trial is too complex (11 > 10) | services/agent/src/autobots/operations/reasoning_trial.py:202 |
| PLR0911 | 15 | Too many return statements (15 > 6) | services/agent/src/autobots/application/tool_gateway.py:322 |
| PLR0911 | 9 | Too many return statements (9 > 6) | services/agent/src/autobots/application/approvals.py:87 |
| PLR0911 | 9 | Too many return statements (9 > 6) | services/agent/src/autobots/application/browsing_loop.py:217 |
| PLR0911 | 9 | Too many return statements (9 > 6) | services/agent/src/autobots/application/workflow_runner.py:163 |
| PLR0911 | 9 | Too many return statements (9 > 6) | services/agent/src/autobots/domain/workflows.py:104 |
| PLR0911 | 8 | Too many return statements (8 > 6) | services/agent/src/autobots/adapters/egress_proxy.py:73 |
| PLR0911 | 8 | Too many return statements (8 > 6) | services/agent/src/autobots/adapters/result_stream.py:117 |
| PLR0911 | 8 | Too many return statements (8 > 6) | services/agent/src/autobots/operations/reasoning_trial.py:202 |
| PLR0911 | 7 | Too many return statements (7 > 6) | services/agent/src/autobots/api/workflow_routes.py:82 |
| PLR0911 | 7 | Too many return statements (7 > 6) | services/agent/src/autobots/application/goal_loop.py:291 |
| PLR0911 | 7 | Too many return statements (7 > 6) | services/agent/src/autobots/application/routines.py:408 |
| PLR0912 | 20 | Too many branches (20 > 12) | services/agent/src/autobots/domain/workflows.py:214 |
| PLR0912 | 18 | Too many branches (18 > 12) | services/agent/src/autobots/application/tool_gateway.py:322 |
| PLR0912 | 14 | Too many branches (14 > 12) | services/agent/src/autobots/application/goal_loop.py:291 |
| PLR0912 | 13 | Too many branches (13 > 12) | services/agent/src/autobots/application/browsing_loop.py:217 |
| PLR0912 | 13 | Too many branches (13 > 12) | services/agent/src/autobots/application/plans.py:61 |
| PLR0912 | 13 | Too many branches (13 > 12) | services/agent/src/autobots/domain/workflow_execution.py:199 |
| PLR0913 | 18 | Too many arguments in function definition (18 > 5) | services/agent/src/autobots/application/approvals.py:87 |
| PLR0913 | 15 | Too many arguments in function definition (15 > 5) | services/agent/src/autobots/application/runs.py:172 |
| PLR0913 | 12 | Too many arguments in function definition (12 > 5) | services/agent/src/autobots/application/workflows.py:325 |
| PLR0913 | 11 | Too many arguments in function definition (11 > 5) | services/agent/src/autobots/application/runs.py:390 |
| PLR0913 | 10 | Too many arguments in function definition (10 > 5) | services/agent/src/autobots/adapters/loop_middleware.py:350 |
| PLR0913 | 9 | Too many arguments in function definition (9 > 5) | services/agent/src/autobots/adapters/tavily.py:148 |
| PLR0913 | 9 | Too many arguments in function definition (9 > 5) | services/agent/src/autobots/application/goal_loop.py:208 |
| PLR0913 | 9 | Too many arguments in function definition (9 > 5) | services/agent/src/autobots/application/reconciliation.py:56 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/api/run_routes.py:299 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/application/assignments.py:244 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/application/browsing_loop.py:217 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/application/compaction.py:198 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/application/improvements.py:339 |
| PLR0913 | 8 | Too many arguments in function definition (8 > 5) | services/agent/src/autobots/application/workflows.py:251 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/api/event_routes.py:80 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/api/improvement_routes.py:86 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/api/run_routes.py:364 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/api/run_routes.py:401 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/api/workflow_routes.py:339 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/approvals.py:244 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/artifacts.py:68 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/experts.py:157 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/improvements.py:153 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/memory.py:33 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/memory.py:59 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/routines.py:150 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/routines.py:190 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/routines.py:312 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/run_projection.py:458 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/tool_uses.py:190 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/worker_inference.py:140 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/workflow_runner.py:124 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/application/workflow_runner.py:234 |
| PLR0913 | 7 | Too many arguments in function definition (7 > 5) | services/agent/src/autobots/operations/browse_trial.py:137 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/adapters/loop_middleware.py:459 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/adapters/url_guard.py:90 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/approval_routes.py:134 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/event_routes.py:185 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/expert_routes.py:110 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/routine_routes.py:98 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/run_routes.py:177 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/run_routes.py:338 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/run_routes.py:352 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/run_routes.py:438 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/run_routes.py:478 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/workflow_routes.py:256 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/api/workflow_routes.py:308 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/experts.py:119 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/experts.py:224 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/goal_loop.py:383 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/goal_loop.py:602 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/routines.py:329 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/tool_gateway.py:563 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/workflow_runner.py:163 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/workflow_runner.py:268 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/workflows.py:144 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/application/workflows.py:220 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/domain/workflows.py:76 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/operations/browse_trial.py:60 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/operations/reasoning_trial.py:202 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/operations/reasoning_trial.py:299 |
| PLR0913 | 6 | Too many arguments in function definition (6 > 5) | services/agent/src/autobots/operations/route_qualification.py:625 |
| PLR0915 | 92 | Too many statements (92 > 50) | services/agent/src/autobots/adapters/github_pulls.py:68 |
| PLR0915 | 67 | Too many statements (67 > 50) | services/agent/src/autobots/operations/browse_trial.py:137 |
| PLR0915 | 65 | Too many statements (65 > 50) | services/agent/src/autobots/adapters/loop_middleware.py:491 |
| PLR0915 | 53 | Too many statements (53 > 50) | services/agent/src/autobots/adapters/github_reads.py:61 |
| PLR0915 | 52 | Too many statements (52 > 50) | services/agent/src/autobots/application/goal_loop.py:291 |
| PLR0917 | 9 | Too many positional arguments (9 > 5) | services/agent/src/autobots/adapters/tavily.py:148 |
| PLR0917 | 9 | Too many positional arguments (9 > 5) | services/agent/src/autobots/application/goal_loop.py:208 |
| PLR0917 | 8 | Too many positional arguments (8 > 5) | services/agent/src/autobots/api/run_routes.py:299 |
| PLR0917 | 8 | Too many positional arguments (8 > 5) | services/agent/src/autobots/application/assignments.py:244 |
| PLR0917 | 8 | Too many positional arguments (8 > 5) | services/agent/src/autobots/application/compaction.py:198 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/api/event_routes.py:80 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/api/improvement_routes.py:86 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/api/run_routes.py:364 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/api/run_routes.py:401 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/api/workflow_routes.py:339 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/improvements.py:153 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/routines.py:312 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/tool_uses.py:190 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/worker_inference.py:140 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/workflow_runner.py:124 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/application/workflow_runner.py:234 |
| PLR0917 | 7 | Too many positional arguments (7 > 5) | services/agent/src/autobots/operations/browse_trial.py:137 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/adapters/loop_middleware.py:459 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/approval_routes.py:134 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/event_routes.py:185 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/expert_routes.py:110 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/routine_routes.py:98 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/run_routes.py:177 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/run_routes.py:338 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/run_routes.py:352 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/run_routes.py:438 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/run_routes.py:478 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/workflow_routes.py:256 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/api/workflow_routes.py:308 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/application/goal_loop.py:602 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/application/routines.py:329 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/application/tool_gateway.py:563 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/application/workflow_runner.py:163 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/domain/workflows.py:76 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/operations/browse_trial.py:60 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/operations/reasoning_trial.py:202 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/operations/reasoning_trial.py:299 |
| PLR0917 | 6 | Too many positional arguments (6 > 5) | services/agent/src/autobots/operations/route_qualification.py:625 |

## 5. Python rule superset (`--select ALL`, services/agent/src)

`ALL` is an exploratory superset of every ruff rule, used here only to show where signal concentrates. It is not a proposal to enable every rule. Totals for the whole run: 2846 hits, 497 fixable (434 more with unsafe fixes). Top 40 lines of `ruff_all_src.txt`:

```text
438	COM812 	[*] missing-trailing-comma
398	ANN401 	[ ] any-type
301	EM101  	[ ] raw-string-in-exception
274	D101   	[ ] undocumented-public-class
221	D103   	[ ] undocumented-public-function
175	D401   	[ ] non-imperative-mood
139	CPY001 	[ ] missing-copyright-notice
124	TRY003 	[ ] raise-vanilla-args
 94	D102   	[ ] undocumented-public-method
 78	FAST001	[ ] fast-api-redundant-response-model
 62	PLR0913	[ ] too-many-arguments
 61	D205   	[ ] missing-blank-line-after-summary
 55	D209   	[*] new-line-after-last-paragraph
 53	N818   	[ ] error-suffix-on-exception-name
 52	PLR2004	[ ] magic-value-comparison
 39	D107   	[ ] undocumented-public-init
 38	PLR0917	[ ] too-many-positional-arguments
 31	PLC0415	[ ] import-outside-top-level
 27	EM102  	[ ] f-string-in-exception
 24	C901   	[ ] complex-structure
 22	BLE001 	[ ] blind-except
 15	FBT003 	[ ] boolean-positional-value-in-call
 15	T201   	[ ] print
 11	PLR0911	[ ] too-many-return-statements
 11	ARG002 	[ ] unused-method-argument
 10	S608   	[ ] hardcoded-sql-expression
  8	D404   	[ ] docstring-starts-with-this
  6	S101   	[ ] assert
  6	PLR0912	[ ] too-many-branches
  5	FBT001 	[ ] boolean-type-hint-positional-argument
  5	PLR0915	[ ] too-many-statements
  4	TRY301 	[ ] raise-within-try
  4	D105   	[ ] undocumented-magic-method
  3	FBT002 	[ ] boolean-default-value-positional-argument
  3	PERF401	[ ] manual-list-comprehension
  3	TC006  	[*] runtime-cast-value
  2	S104   	[ ] hardcoded-bind-all-interfaces
  2	S105   	[ ] hardcoded-password-string
  2	ISC004 	[ ] implicit-string-concatenation-in-collection-literal
  2	SLF001 	[ ] private-member-access
```

## 6. Repository-level Python

`scripts/`, `tests/` and `.claude/hooks/` are outside the service's own ruff and mypy runs (which cover `services/agent/src` and `services/agent/tests`). They were checked here with `--isolated`, target py312, line length 100 and rules E, F, W, I, B, UP, ASYNC, RUF.

```text
5269	E501    	[ ] line-too-long
 295	RUF100  	[*] unused-noqa
 119	I001    	[*] unsorted-imports
  34	UP017   	[*] datetime-timezone-utc
   9	B023    	[ ] function-uses-loop-variable
   7	RUF012  	[ ] mutable-class-default
   7	F401    	[*] unused-import
   7	RUF059  	[ ] unused-unpacked-variable
   5	UP036   	[ ] outdated-version-block
   4	B905    	[ ] zip-without-explicit-strict
   3	ASYNC240	[ ] blocking-path-method-in-async-function
   3	RUF005  	[ ] collection-literal-concatenation
   2	RUF015  	[ ] unnecessary-iterable-allocation-for-first-element
   2	B007    	[ ] unused-loop-control-variable
   2	F841    	[ ] unused-variable
   2	RUF007  	[ ] zip-instead-of-pairwise
   1	F541    	[*] f-string-missing-placeholders
   1	E402    	[ ] module-import-not-at-top-of-file
   1	UP031   	[ ] printf-string-formatting
   1	UP037   	[*] quoted-annotation
   1	W291    	[*] trailing-whitespace
Found 5775 errors.
[*] 458 fixable with `--fix` (25 unsafe fixes available with `--fix --unsafe-fixes`).
```

Format check (`ruff format --isolated --check --line-length 100`): 121 files would be reformatted, 13 files already formatted.

## 7. TypeScript and React

Scope: `apps/web` `app`, `components`, `lib`, `tests`. The extra rules were passed on the command line and only warn.

| ESLint rule (extra rules warn only) | Hits |
|---|---|
| @typescript-eslint/consistent-type-assertions | 94 |
| max-lines-per-function | 83 |
| max-statements | 43 |
| react/no-multi-comp | 38 |
| complexity | 31 |
| max-lines | 22 |
| @typescript-eslint/no-non-null-assertion | 10 |
| max-params | 1 |

### Longest functions (non-test)

| Lines (no blanks or comments) | Function | Location |
|---|---|---|
| 677 | Function 'RunWorkspaceView' | apps/web/components/run-workspace.tsx:152 |
| 617 | Function 'WorkflowEditor' | apps/web/components/workflow-editor.tsx:106 |
| 527 | Function 'GoalComposer' | apps/web/components/goal-composer.tsx:113 |
| 393 | Function 'ExpertEditor' | apps/web/components/expert-editor.tsx:70 |
| 377 | Function 'OperationsPanel' | apps/web/components/operations-panel.tsx:158 |
| 350 | Function 'ModelPolicyPanel' | apps/web/components/model-policy-panel.tsx:118 |
| 341 | Function 'WorkflowsPanel' | apps/web/components/workflows-panel.tsx:83 |
| 308 | Function 'ApprovalsPanel' | apps/web/components/approvals-panel.tsx:117 |
| 263 | Function 'RunInspectorView' | apps/web/components/run-inspector.tsx:18 |
| 260 | Function 'RunList' | apps/web/components/run-list.tsx:160 |
| 255 | Function 'ExpertsPanel' | apps/web/components/experts-panel.tsx:22 |
| 252 | Function 'JobsPlot' | apps/web/components/jobs-chart.tsx:133 |
| 249 | Function 'ToolCatalogPanel' | apps/web/components/tool-catalog.tsx:183 |
| 245 | Function 'ApprovalDetail' | apps/web/components/approvals-panel.tsx:436 |
| 228 | Function 'RunPanel' | apps/web/components/run-panel.tsx:47 |
| 222 | Function 'ProviderSettingsPanel' | apps/web/components/provider-settings-panel.tsx:155 |
| 220 | Function 'RunDisclosure' | apps/web/components/run-disclosure.tsx:22 |
| 213 | Function 'WorkflowPreviewPanel' | apps/web/components/workflows-panel.tsx:429 |
| 204 | Function 'WorkflowMonitor' | apps/web/components/workflow-monitor.tsx:27 |
| 194 | Function 'SessionPanel' | apps/web/components/session-panel.tsx:15 |
| 189 | Function 'SearchPalette' | apps/web/components/search-palette.tsx:24 |
| 174 | Function 'ToolDetail' | apps/web/components/tool-catalog.tsx:581 |
| 170 | Function 'RunControls' | apps/web/components/run-controls.tsx:45 |
| 165 | Function 'HomeActivity' | apps/web/components/home-activity.tsx:56 |
| 115 | Function 'KeysAndVarsPanel' | apps/web/components/keys-and-vars-panel.tsx:162 |
| 115 | Function 'ExpertCard' | apps/web/components/experts-panel.tsx:317 |
| 115 | Function 'AppearanceControl' | apps/web/components/appearance-control.tsx:142 |
| 109 | Function 'ItemCard' | apps/web/components/keys-and-vars-panel.tsx:51 |
| 108 | Function 'ContinueRun' | apps/web/components/continue-run.tsx:12 |
| 107 | Function 'UnknownEffects' | apps/web/components/unknown-effects.tsx:22 |

### Most complex functions (non-test)

| Complexity | Function | Location |
|---|---|---|
| 39 | Function 'RunWorkspaceView' | apps/web/components/run-workspace.tsx:152 |
| 37 | Function 'GoalComposer' | apps/web/components/goal-composer.tsx:113 |
| 28 | Function 'OperationsPanel' | apps/web/components/operations-panel.tsx:158 |
| 27 | Function 'ExpertCard' | apps/web/components/experts-panel.tsx:317 |
| 27 | Function 'onKey' | apps/web/components/approvals-panel.tsx:229 |
| 25 | Function 'RunDisclosure' | apps/web/components/run-disclosure.tsx:22 |
| 20 | Function 'WorkflowEditor' | apps/web/components/workflow-editor.tsx:106 |
| 19 | Async function 'save' | apps/web/components/expert-editor.tsx:130 |
| 18 | Function 'ToolDetail' | apps/web/components/tool-catalog.tsx:581 |
| 18 | Async function 'run' | apps/web/components/goal-composer.tsx:276 |
| 17 | Function 'valueFor' | apps/web/components/operations-panel.tsx:121 |
| 15 | Async function 'poll' | apps/web/components/waiting-notifier.tsx:35 |
| 15 | Function 'ItemCard' | apps/web/components/keys-and-vars-panel.tsx:51 |
| 14 | Async function 'run' | apps/web/components/session-panel.tsx:45 |
| 14 | Function 'RunPanel' | apps/web/components/run-panel.tsx:47 |
| 14 | Function 'ExpertEditor' | apps/web/components/expert-editor.tsx:70 |
| 13 | Function 'guardRequest' | apps/web/lib/request-guard.ts:34 |
| 13 | Async function 'forward' | apps/web/lib/bff.ts:71 |
| 13 | Function 'draftOf' | apps/web/components/expert-editor.tsx:59 |
| 13 | Function 'ApprovalDetail' | apps/web/components/approvals-panel.tsx:436 |

### Type assertions, non-null assertions and components per file (non-test)

| File | Type assertions | Non-null assertions | Components in file |
|---|---|---|---|
| apps/web/components/workflow-editor.tsx | 6 | 1 | 1 |
| apps/web/components/model-policy-panel.tsx | 5 | 0 | 2 |
| apps/web/components/run-workspace.tsx | 5 | 0 | 2 |
| apps/web/components/experts-panel.tsx | 4 | 0 | 2 |
| apps/web/components/expert-editor.tsx | 3 | 0 | 1 |
| apps/web/components/goal-composer.tsx | 3 | 0 | 1 |
| apps/web/components/approvals-panel.tsx | 2 | 0 | 4 |
| apps/web/components/continue-run.tsx | 2 | 0 | 1 |
| apps/web/components/session-panel.tsx | 2 | 0 | 1 |
| apps/web/components/workflows-panel.tsx | 2 | 0 | 2 |
| apps/web/app/api/session/route.ts | 1 | 0 | 1 |
| apps/web/app/api/workspace/route.ts | 1 | 0 | 1 |
| apps/web/components/account-form.tsx | 1 | 0 | 1 |
| apps/web/components/keys-and-vars-panel.tsx | 1 | 0 | 2 |
| apps/web/components/provider-settings-panel.tsx | 1 | 0 | 3 |
| apps/web/components/run-controls.tsx | 1 | 0 | 1 |
| apps/web/components/run-panel.tsx | 1 | 0 | 1 |
| apps/web/components/unknown-effects.tsx | 1 | 0 | 1 |
| apps/web/lib/csrf-fetch.ts | 1 | 0 | 1 |
| apps/web/lib/service-status.ts | 1 | 0 | 1 |
| apps/web/components/app-shell.tsx | 0 | 0 | 3 |
| apps/web/components/appearance-control.tsx | 0 | 0 | 3 |
| apps/web/components/home-activity.tsx | 0 | 3 | 1 |
| apps/web/components/jobs-chart.tsx | 0 | 0 | 3 |
| apps/web/components/readiness.tsx | 0 | 0 | 2 |
| apps/web/components/run-inspector.tsx | 0 | 0 | 2 |
| apps/web/components/run-list.tsx | 0 | 0 | 3 |
| apps/web/components/tool-catalog.tsx | 0 | 0 | 8 |
| apps/web/components/tool-uses.tsx | 0 | 0 | 3 |
| apps/web/components/ui/card.tsx | 0 | 0 | 5 |
| apps/web/components/ui/field.tsx | 0 | 0 | 4 |
| apps/web/components/ui/page-header.tsx | 0 | 0 | 2 |
| apps/web/components/workflow-monitor.tsx | 0 | 0 | 2 |

210 files have leads, written to `file_metrics.json` in the raw directory.

## 8. Baseline checks

From this run:

| Check | Exit code |
|---|---|
| Project ruff (`services/agent`, `src tests`, project config) | 0 |
| ESLint (`apps/web`, project config plus extra warn-only rules) | 0 |

Latest verification reports, read from `.checks/<profile>/latest.json`, not rerun:

| Profile | Status | Completed (UTC) | Checks passed |
|---|---|---|---|
| harness | passed | 2026-11-12T15:53:26 | 3 of 3 |
| fast | passed | 2026-11-09T02:58:38 | 11 of 24 |
| full | passed | 2026-11-08T19:20:30 | 24 of 24 |
| db | passed | 2026-11-09T03:08:50 | 9 of 9 |
| operations | passed | 2026-11-07T02:40:37 | 7 of 7 |

The fast report counts 11 of 24 checks as `passed`; the remaining entries carry another status (the report was not inspected further). These reports predate or are independent of this measurement and bind to whatever revision they recorded.

## 9. Commands

Step 1:

```sh
TS=2026-11-12-09-52-30
[ -n "$TS" ] || TS=$(date +%Y-%m-%d-%H-%M-%S)
OUT=docs/reviews/review-$TS; RAW=.checks/reviews/review-$TS
if [ -d "$OUT" ] && [ -n "$(ls -A "$OUT")" ]; then echo "STOP: $OUT already holds files"; exit 0; fi
mkdir -p "$OUT/findings" "$RAW" && echo "TS=$TS"
git rev-parse HEAD
git status --porcelain | wc -l
services/agent/.venv/bin/ruff --version; python3.12 --version
"$HOME/.nvm/versions/node/v$(cat .node-version)/bin/node" --version
(cd apps/web && PATH="$HOME/.nvm/versions/node/v$(cat ../../.node-version)/bin:$PATH" node_modules/.bin/eslint --version)
```

Step 2:

```sh
TS=2026-11-12-09-52-30; RAW=.checks/reviews/review-$TS
git ls-files | grep -E '\.(ts|tsx|mjs|js|py|sql|sh|css)$|Dockerfile|Makefile$|compose[^/]*\.ya?ml$|(^|/)(package\.json|tsconfig\.json|pyproject\.toml)$' \
  | grep -v -E '^(openspec|docs|research)/|^packages/api-client/src/generated\.ts$|^packages/db-types/src/generated\.ts$|^contracts/generated/|^infra/supabase/upstream/|^\.claude/(worktrees|ohmyorch|workflows|skills|agents|rules)/' > "$RAW/files.txt"
wc -l < "$RAW/files.txt"
tr '\n' '\0' < "$RAW/files.txt" | xargs -0 wc -l | grep -v ' total$' | sort -rn > "$RAW/loc.txt"
head -25 "$RAW/loc.txt"
awk '{split($2, p, "/"); top = (p[1] == "services" || p[1] == "apps" || p[1] == "packages" || p[1] == "tests") ? p[1] "/" p[2] : p[1]; lines[top] += $1; count[top] += 1} END {for (t in lines) printf "%s: %d files, %d lines\n", t, count[t], lines[t]}' "$RAW/loc.txt" | sort
wc -l packages/api-client/src/generated.ts packages/db-types/src/generated.ts contracts/generated/openapi.json
```

Step 3:

```sh
TS=2026-11-12-09-52-30; RAW=.checks/reviews/review-$TS
python3.12 -I - "$RAW" <<'PY'
import ast, json, sys
from collections import defaultdict
from pathlib import Path
raw = Path(sys.argv[1])
files = [f for f in (raw / 'files.txt').read_text().split() if f.endswith('.py')]
def area(f):
    parts = f.split('/')
    if f.startswith('services/agent/src/autobots/') and len(parts) > 5:
        return '/'.join(parts[:5])
    if f.startswith('services/agent/'):
        return '/'.join(parts[:3])
    if f.startswith('tests/') and len(parts) > 2:
        return '/'.join(parts[:2])
    return parts[0] if len(parts) > 1 else '(root)'
funcs, per_file = [], {}
for f in files:
    src = Path(f).read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    s = dict(lines=len(lines), public=0, documented=0, module_docstring=ast.get_docstring(tree) is not None,
             broad_except=0, type_ignores=src.count('type: ignore'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and (node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {'Exception', 'BaseException'})):
            s['broad_except'] += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                s['public'] += 1
                s['documented'] += ast.get_docstring(node) is not None
            a = node.args
            funcs.append(dict(file=f, name=node.name, line=node.lineno, length=node.end_lineno - node.lineno + 1,
                              args=len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)))
    per_file[f] = s
funcs.sort(key=lambda x: -x['length'])
(raw / 'py_functions.json').write_text(json.dumps(funcs))
(raw / 'py_files.json').write_text(json.dumps(per_file))
agg = defaultdict(lambda: defaultdict(int))
for f, s in per_file.items():
    g = agg[area(f)]
    g['files'] += 1; g['lines'] += s['lines']; g['public'] += s['public']; g['documented'] += s['documented']
    g['no_module_doc'] += not s['module_docstring']; g['broad_except'] += s['broad_except']; g['type_ignores'] += s['type_ignores']
for fn in funcs:
    g = agg[area(fn['file'])]
    g['functions'] += 1
    for t in (40, 80, 150):
        g['over' + str(t)] += fn['length'] > t
print('| Area | Files | Lines | Functions | Over 40 lines | Over 80 | Over 150 | Public functions documented | Files without module docstring | Broad except | type: ignore |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for k in sorted(agg):
    g = agg[k]
    pct = str(round(100 * g['documented'] / g['public'])) + '%' if g['public'] else '-'
    print(f"| {k} | {g['files']} | {g['lines']} | {g['functions']} | {g['over40']} | {g['over80']} | {g['over150']} | {pct} | {g['no_module_doc']} | {g['broad_except']} | {g['type_ignores']} |")
print()
print('| Lines | Function | Location | Parameters |')
print('|---|---|---|---|')
for fn in funcs[:40]:
    print(f"| {fn['length']} | {fn['name']} | {fn['file']}:{fn['line']} | {fn['args']} |")
PY
```

Step 4:

```sh
TS=2026-11-12-09-52-30; RAW=.checks/reviews/review-$TS
(cd services/agent && .venv/bin/ruff check --no-cache --quiet src tests; echo "project ruff exit=$?")
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --statistics --select ALL src) > "$RAW/ruff_all_src.txt" 2>/dev/null; head -45 "$RAW/ruff_all_src.txt"
(cd services/agent && .venv/bin/ruff check --no-cache --exit-zero --select C901,PLR0911,PLR0912,PLR0913,PLR0915,PLR0917 --config 'lint.mccabe.max-complexity = 10' --output-format json src) > "$RAW/ruff_complexity.json" 2>/dev/null
services/agent/.venv/bin/ruff check --no-cache --isolated --exit-zero --statistics --target-version py312 --line-length 100 --select E,F,W,I,B,UP,ASYNC,RUF scripts tests .claude/hooks > "$RAW/ruff_root.txt" 2>/dev/null; head -25 "$RAW/ruff_root.txt"
services/agent/.venv/bin/ruff format --no-cache --isolated --check --line-length 100 scripts tests .claude/hooks 2>/dev/null | tail -1
python3.12 -I - "$RAW/ruff_complexity.json" <<'PY'
import json, re, sys
from collections import Counter
from pathlib import Path
root = Path.cwd().resolve()
data = json.loads(Path(sys.argv[1]).read_text() or '[]')
def measured(d):
    found = re.search(r'\((\d+) >', d['message'])
    return int(found.group(1)) if found else 0
print('| Rule | Hits |')
print('|---|---|')
for code, n in Counter(d['code'] for d in data).most_common():
    print(f'| {code} | {n} |')
print()
print('| Rule | Measured | Message | Location |')
print('|---|---|---|---|')
for d in sorted(data, key=lambda d: (d['code'], -measured(d))):
    where = Path(d['filename']).resolve().relative_to(root)
    print(f"| {d['code']} | {measured(d)} | {d['message'].replace(chr(96), '')} | {where}:{d['location']['row']} |")
PY
```

Step 5:

```sh
TS=2026-11-12-09-52-30; RAW=.checks/reviews/review-$TS; REPORT="$PWD/$RAW/eslint.json"
(cd apps/web && PATH="$HOME/.nvm/versions/node/v$(cat ../../.node-version)/bin:$PATH" node_modules/.bin/eslint --no-cache \
  --rule 'max-lines-per-function: [warn, {max: 60, skipBlankLines: true, skipComments: true}]' \
  --rule 'max-lines: [warn, {max: 300, skipBlankLines: true, skipComments: true}]' \
  --rule 'complexity: [warn, 10]' --rule 'max-depth: [warn, 4]' --rule 'max-params: [warn, 4]' --rule 'max-statements: [warn, 25]' \
  --rule 'react/no-multi-comp: [warn, {ignoreStateless: false}]' \
  --rule '@typescript-eslint/no-non-null-assertion: warn' --rule '@typescript-eslint/no-explicit-any: warn' \
  --rule '@typescript-eslint/consistent-type-assertions: [warn, {assertionStyle: never}]' \
  --format json -o "$REPORT" app components lib tests; echo "eslint exit=$? (0 means the project's own rules pass; the extra rules only warn)")
```

Step 6:

```sh
TS=2026-11-12-09-52-30; RAW=.checks/reviews/review-$TS
python3.12 -I - "$RAW" <<'PY'
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
raw = Path(sys.argv[1])
root = Path.cwd().resolve()
def rel(p):
    return str(Path(p).resolve().relative_to(root))
eslint = json.loads((raw / 'eslint.json').read_text())
totals, sizes, complexity, per_file = Counter(), [], [], defaultdict(Counter)
for f in eslint:
    name = rel(f['filePath'])
    for m in f['messages']:
        rule = m.get('ruleId') or 'parse-error'
        totals[rule] += 1
        per_file[name][rule] += 1
        what = re.match(r"^(.*?) has (too many lines|a complexity)", m['message'])
        label = what.group(1) if what else '?'
        count = re.search(r'\((\d+)\)', m['message'])
        if rule == 'max-lines-per-function' and count:
            sizes.append((int(count.group(1)), name, m['line'], label))
        score = re.search(r'complexity of (\d+)', m['message'])
        if rule == 'complexity' and score:
            complexity.append((int(score.group(1)), name, m['line'], label))
print('| ESLint rule (extra rules warn only) | Hits |')
print('|---|---|')
for rule, n in totals.most_common():
    print(f'| {rule} | {n} |')
sizes.sort(reverse=True)
complexity.sort(reverse=True)
print()
print('| Lines (no blanks or comments) | Function | Location |')
print('|---|---|---|')
for n, name, line, label in [s for s in sizes if '/tests/' not in s[1]][:30]:
    print(f'| {n} | {label} | {name}:{line} |')
print()
print('| Complexity | Function | Location |')
print('|---|---|---|')
for n, name, line, label in [c for c in complexity if '/tests/' not in c[1]][:20]:
    print(f'| {n} | {label} | {name}:{line} |')
print()
print('| File | Type assertions | Non-null assertions | Components in file |')
print('|---|---|---|---|')
for name, c in sorted(per_file.items(), key=lambda kv: -kv[1]['@typescript-eslint/consistent-type-assertions']):
    a, nn, mc = c['@typescript-eslint/consistent-type-assertions'], c['@typescript-eslint/no-non-null-assertion'], c['react/no-multi-comp']
    if '/tests/' not in name and (a or nn or mc):
        print(f'| {name} | {a} | {nn} | {mc + 1 if mc else 1} |')
loc = {}
for line in (raw / 'loc.txt').read_text().splitlines():
    parts = line.split(None, 1)
    if len(parts) == 2:
        loc[parts[1]] = int(parts[0])
notes = defaultdict(list)
for fn in json.loads((raw / 'py_functions.json').read_text()):
    if fn['length'] >= 60:
        notes[fn['file']].append(f"{fn['name']}@{fn['line']} is {fn['length']} lines")
for d in json.loads((raw / 'ruff_complexity.json').read_text() or '[]'):
    notes[rel(d['filename'])].append(f"{d['code']}@{d['location']['row']}: {d['message'].replace(chr(96), '')}")
for f in eslint:
    name = rel(f['filePath'])
    for m in f['messages']:
        if m.get('ruleId') in ('max-lines-per-function', 'complexity', 'max-depth', 'max-params'):
            notes[name].append(f"{m['ruleId']}@{m['line']}: {m['message']}")
    c = per_file[name]
    if c['@typescript-eslint/consistent-type-assertions']:
        notes[name].append(f"{c['@typescript-eslint/consistent-type-assertions']} type assertions")
    if c['react/no-multi-comp']:
        notes[name].append(f"{c['react/no-multi-comp'] + 1} components in the file")
files = (raw / 'files.txt').read_text().split()
leads = [{'file': f, 'loc': loc.get(f, 0), 'notes': '; '.join(notes.get(f, []))[:1500]}
         for f in files if loc.get(f, 0) >= 300 or notes.get(f)]
(raw / 'file_metrics.json').write_text(json.dumps(leads, indent=1))
print()
print(f'{len(leads)} files have leads, written to file_metrics.json')
PY
```

Step 7:

```sh
for p in harness fast full db operations; do f=.checks/$p/latest.json; [ -f "$f" ] && python3.12 -I -c 'import json, sys; d = json.load(open(sys.argv[1])); c = d.get("checks", []); print(sys.argv[2], d.get("status"), d.get("completed_at_utc"), sum(1 for x in c if x.get("status") == "passed"), "of", len(c), "checks passed")' "$f" "$p"; done
```

Supporting commands run while writing this file (read-only):

```sh
wc -l .checks/reviews/review-2026-11-12-09-52-30/ruff_all_src.txt .checks/reviews/review-2026-11-12-09-52-30/ruff_root.txt; tail -3 .checks/reviews/review-2026-11-12-09-52-30/ruff_all_src.txt
head -40 .checks/reviews/review-2026-11-12-09-52-30/ruff_all_src.txt | tail -1
git status --porcelain
```

## 10. Limitations

- No step failed or was refused. One supporting read-only command (`cat -A`) failed because macOS `cat` lacks `-A`; it affected nothing.
- In step 4, `ruff_all_src.txt` and `ruff_root.txt` outputs printed back to back; the section 5 and 6 blocks were separated from the files themselves (`ruff_all_src.txt` has 61 lines, `ruff_root.txt` 23).
- Line counts are approximate measures of size. ESLint function line counts skip blank and comment lines, while the Python function and file counts include them. File line counts come from `wc -l`.
- Python function lengths include nested functions separately and also inside their parent, so nested functions are counted twice in area totals.
- "Public functions documented" counts any function or method whose name lacks a leading underscore, including nested and test functions; `type: ignore` is a plain substring count.
- Broad except counts only bare `except`, `except Exception` and `except BaseException`, not tuples containing them.
- The `ALL` ruff run is an exploratory superset, not the project configuration. The repository-level ruff run uses `--isolated` with chosen settings, not a project configuration, because `scripts/`, `tests/` and `.claude/hooks/` have none.
- ESLint extra rules were applied ad hoc on the command line; components per file is a `react/no-multi-comp` count plus one.
- Verification reports were read, not rerun, and none was produced by this measurement step. Their revisions were not compared with this run's revision.
