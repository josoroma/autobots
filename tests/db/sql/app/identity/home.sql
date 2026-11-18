-- US-15.10: a Costa Rica workspace whose owner is named Ada, with seven runs a minute apart. The newest
-- waits for input, the next is paused and the third waits on two pending approvals. The fourth has a
-- plan with one of two tasks done, and the fifth was charged USD 0.07. Synthetic rows for the disposable
-- identity qualification only (DH-07). scripts/qualify_identity.py runs it as the database superuser,
-- since the runtime role can't change a workspace's zone or write a profile, with the home-k owner's
-- workspace and user, the seven run IDs and the two approval IDs.

update public.workspaces set timezone = 'America/Costa_Rica' where id = ${workspace};
insert into public.user_profiles (user_id, display_name) values (${user}, 'Ada');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_1}, ${workspace}, 'waiting_input', 'Answer the rate question', 1000000, '{}', now() - interval '1 minutes', now() - interval '1 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_2}, ${workspace}, 'paused', 'Compare paused rates', 1000000, '{}', now() - interval '2 minutes', now() - interval '2 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_3}, ${workspace}, 'waiting_approval', 'Send the brief', 1000000, '{}', now() - interval '3 minutes', now() - interval '3 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_4}, ${workspace}, 'running', 'Plan two tasks', 1000000, '{}', now() - interval '4 minutes', now() - interval '4 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_5}, ${workspace}, 'succeeded', 'Spent seven cents', 1000000, '{}', now() - interval '5 minutes', now() - interval '5 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_6}, ${workspace}, 'succeeded', 'Older sixth run', 1000000, '{}', now() - interval '6 minutes', now() - interval '6 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_7}, ${workspace}, 'failed', 'Oldest seventh run', 1000000, '{}', now() - interval '7 minutes', now() - interval '7 minutes');
insert into public.approval_requests (id, workspace_id, run_id, operation_id, tool_id, tool_version, operation_class, argument_hash, arguments,
    scope_hash, expires_at, created_at) values
  (${approval_1}, ${workspace}, ${run_3}, 'home-k-1', 'create_github_issue', 1, 'consequential_external_write', 'hash-1',
   '{"title": "Brief 1"}', 'scope', now() + interval '1 day', now() - interval '2 minutes');
insert into public.approval_requests (id, workspace_id, run_id, operation_id, tool_id, tool_version, operation_class, argument_hash, arguments,
    scope_hash, expires_at, created_at) values
  (${approval_2}, ${workspace}, ${run_3}, 'home-k-2', 'create_github_issue', 1, 'consequential_external_write', 'hash-2',
   '{"title": "Brief 2"}', 'scope', now() + interval '1 day', now() - interval '1 minutes');
insert into app_private.plan_versions (run_id, version, tasks) values (${run_4}, 1,
  '[{"id": "t1", "title": "One", "criteria": []}, {"id": "t2", "title": "Two", "criteria": []}]');
insert into app_private.plan_evidence (run_id, task_id, evidence, summary) values (${run_4}, 't1', '[]', 'done');
insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day, reserved_micro_usd,
    charged_micro_usd, status) values
  (gen_random_uuid(), ${workspace}, ${run_5}, ${run_5}, 'executor', 'openrouter_terra', 'w', 1, current_date, 0, 70000, 'succeeded');
