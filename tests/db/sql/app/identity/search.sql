-- US-15.22: "read" names a run's goal, an Expert and a workflow in the ops-n workspace, and a run and an
-- Expert in the flows-l workspace, which a search from ops-n must not return. Synthetic rows for the
-- disposable identity qualification only (DH-07). scripts/qualify_identity.py runs it as the database
-- superuser, with each record's ID and both owners' workspaces and users.

insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  (${run}, ${workspace}, 'succeeded', 'Read the quarter notes', 1000000, '{}'),
  (${other_run}, ${other_workspace}, 'succeeded', 'Read another workspace plan', 1000000, '{}');
insert into public.experts (id, workspace_id, name, latest_version) values
  (${expert}, ${workspace}, 'Reading analyst', 1),
  (${other_expert}, ${other_workspace}, 'Reader elsewhere', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values
  (${expert}, 1, '{"tools": ["calculate"]}', ${user}),
  (${other_expert}, 1, '{"tools": ["calculate"]}', ${other_user});
insert into public.workflows (id, workspace_id, name, description, latest_version) values (${workflow}, ${workspace}, 'Read and summarize', null, 0);
