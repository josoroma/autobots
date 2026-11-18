-- US-15.9: a workspace with USD 2.10 left of its daily cap, as USD 2.90 was charged today, and one Expert
-- for the composer's Expert chip. It uses the installation key, which browser_cases grants it. Synthetic
-- rows for the disposable identity qualification only (DH-07). scripts/qualify_identity.py runs it as
-- the runtime role, with the composer-j owner's workspace and user and the Expert's ID.

insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  ('66666666-6666-4666-8666-000000000001', ${workspace}, 'succeeded', 'Spent earlier today', 5000000, '{}');
insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day,
    reserved_micro_usd, charged_micro_usd, status) values
  (gen_random_uuid(), ${workspace}, '66666666-6666-4666-8666-000000000001', '66666666-6666-4666-8666-000000000001', 'executor', 'openrouter_terra', 'w', 1,
   (now() at time zone 'utc')::date, 0, 2900000, 'succeeded');
insert into public.experts (id, workspace_id, name, latest_version) values (${expert}, ${workspace}, 'Composer helper', 1);
insert into public.expert_versions (expert_id, version, config, created_by) values (${expert}, 1,
  '{"tools": ["calculate", "read_csv"], "role_bindings": {"executor": "openrouter_sol"}}', ${user});
