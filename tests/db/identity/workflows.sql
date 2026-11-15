-- US-15.13: a workspace with a USD 10.00 daily cap and two Experts. "Weekly brief" has versions 1 and 2
-- (research, then write, then an approval gate), a draft and three executions: one reported, one failed
-- with an unreported charge and one still running. "Plain totals" has published versions only. Synthetic
-- rows for the disposable identity qualification only (DH-07). scripts/qualify_identity.py runs it as
-- the database superuser, with the flows-l owner's workspace and user, the Expert, workflow and run IDs,
-- and each graph as JSON.

insert into app_private.model_spend_limits (workspace_id, daily_limit_micro_usd) values (${workspace}, 10000000);
insert into public.experts (id, workspace_id, name, latest_version) values
  (${analyst}, ${workspace}, 'Research analyst', 1),
  (${writer}, ${workspace}, 'Brief writer', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values
  (${analyst}, 1, '{"tools": ["calculate", "read_csv"], "role_bindings": {"executor": "openrouter_sol"}}', ${user}),
  (${writer}, 1, '{"tools": ["save_artifact"]}', ${user});
insert into public.workflows (id, workspace_id, name, description, latest_version) values
  (${brief}, ${workspace}, 'Weekly brief', 'Research, then a brief for review', 2),
  (${plain}, ${workspace}, 'Plain totals', null, 2);
insert into public.workflow_versions (workflow_id, version, graph, graph_hash, block_versions, source, created_by) values
  (${brief}, 1, ${brief_1}, 'brief-1', '{}', 'user', ${user}),
  (${brief}, 2, ${brief_2}, 'brief-2', '{}', 'user', ${user}),
  (${plain}, 1, ${plain_graph}, 'plain-1', '{}', 'user', ${user}),
  (${plain}, 2, ${plain_graph}, 'plain-2', '{}', 'user', ${user});
insert into public.workflow_drafts (workflow_id, workspace_id, graph, saved_by) values (${brief}, ${workspace}, ${draft}, ${user});
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_1}, ${workspace}, 'succeeded', 'Workflow Weekly brief, version 1', 1000000, '{}', now() - interval '30 minutes',
   now() - interval '30 minutes' + interval '65 seconds');
insert into public.workflow_executions (id, workspace_id, workflow_id, workflow_version, graph_hash, block_versions, inputs, created_by, run_id, created_at)
  values (gen_random_uuid(), ${workspace}, ${brief}, 1, 'brief-1', '{}', '{}', ${user}, ${run_1}, now() - interval '30 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_2}, ${workspace}, 'failed', 'Workflow Weekly brief, version 2', 1000000, '{}', now() - interval '20 minutes',
   now() - interval '20 minutes' + interval '2 minutes');
insert into public.workflow_executions (id, workspace_id, workflow_id, workflow_version, graph_hash, block_versions, inputs, created_by, run_id, created_at)
  values (gen_random_uuid(), ${workspace}, ${brief}, 2, 'brief-2', '{}', '{}', ${user}, ${run_2}, now() - interval '20 minutes');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, created_at, updated_at) values
  (${run_3}, ${workspace}, 'running', 'Workflow Weekly brief, version 2', 1000000, '{}', now() - interval '10 minutes',
   now() - interval '10 minutes' + interval '0 seconds');
insert into public.workflow_executions (id, workspace_id, workflow_id, workflow_version, graph_hash, block_versions, inputs, created_by, run_id, created_at)
  values (gen_random_uuid(), ${workspace}, ${brief}, 2, 'brief-2', '{}', '{}', ${user}, ${run_3}, now() - interval '10 minutes');
insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day,
    reserved_micro_usd, charged_micro_usd, status, failure_class) values
  (gen_random_uuid(), ${workspace}, ${run_1}, ${run_1}, 'executor', 'openrouter_terra', 'w', 1, current_date - 1, 0, 120000, 'succeeded', null),
  (gen_random_uuid(), ${workspace}, ${run_2}, ${run_2}, 'executor', 'openrouter_terra', 'w', 1, current_date - 1, 40000, null, 'uncertain', 'charge_not_reported'),
  (gen_random_uuid(), ${workspace}, ${run_3}, ${run_3}, 'executor', 'openrouter_terra', 'w', 1, current_date - 1, 50000, null, 'reserved', null);
