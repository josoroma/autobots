-- US-15.4: a workspace with 101 runs, so the run list has a second page, and three with spend: one
-- reserved, one with an unreported charge and one fully reported. Synthetic rows for the disposable
-- identity qualification only (DH-07). scripts/qualify_identity.py runs it as the runtime role, with
-- the runs-g owner's workspace.

insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, created_at, policy_snapshot)
  select gen_random_uuid(), ${workspace}, (array['queued','succeeded','paused','waiting_input'])[1 + n % 4],
    'Filler run ' || n, 1000000, now() - make_interval(mins => 200 + n),
    '{"bindings": {"executor": "openrouter_terra"}}'::jsonb from generate_series(1, 98) n;
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, created_at, policy_snapshot) values
  ('44444444-4444-4444-8444-000000000001', ${workspace}, 'running', 'Spend held in reserve', 1000000, now() - interval '3 minutes', '{"bindings": {"researcher": "openrouter_sol"}}'),
  ('44444444-4444-4444-8444-000000000002', ${workspace}, 'failed', 'Spend never reported', 1000000, now() - interval '2 minutes', '{}'),
  ('44444444-4444-4444-8444-000000000003', ${workspace}, 'succeeded', 'Spend fully reported', 1000000, now() - interval '1 minute', '{}');
insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day,
    reserved_micro_usd, charged_micro_usd, status, failure_class) values
  (gen_random_uuid(), ${workspace}, '44444444-4444-4444-8444-000000000001', '44444444-4444-4444-8444-000000000001', 'executor', 'openrouter_terra', 'w', 1, current_date, 180000, null, 'reserved', null),
  (gen_random_uuid(), ${workspace}, '44444444-4444-4444-8444-000000000002', '44444444-4444-4444-8444-000000000002', 'executor', 'openrouter_terra', 'w', 1, current_date, 30000, null, 'uncertain', 'charge_not_reported'),
  (gen_random_uuid(), ${workspace}, '44444444-4444-4444-8444-000000000003', '44444444-4444-4444-8444-000000000003', 'executor', 'openrouter_terra', 'w', 1, current_date, 0, 70000, 'succeeded', null);
