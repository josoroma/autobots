-- US-15.18: a workspace with one job that lost its worker, one leased and one queued, none of which any
-- worker may take for 30 days, and two published artifacts of 1,000 and 2,345 bytes beside a staged one.
-- The operations spec adds two live worker heartbeats while it looks, and stops them. Synthetic rows for
-- the disposable identity qualification only (DH-07). scripts/qualify_identity.py runs it as the
-- database superuser, with the ops-n owner's workspace.

insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  ('99999999-9999-4999-8999-000000000001', ${workspace}, 'running', 'Operations job 1', 1000000, '{}');
insert into app_private.run_jobs (run_id, workspace_id, status, available_at, generation, lease_owner, lease_expires_at) values
  ('99999999-9999-4999-8999-000000000001', ${workspace}, 'claimed', now() + interval '30 days', 1, 'arranged-ops', now() - interval '1 minute');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  ('99999999-9999-4999-8999-000000000002', ${workspace}, 'running', 'Operations job 2', 1000000, '{}');
insert into app_private.run_jobs (run_id, workspace_id, status, available_at, generation, lease_owner, lease_expires_at) values
  ('99999999-9999-4999-8999-000000000002', ${workspace}, 'claimed', now() + interval '30 days', 1, 'arranged-ops', now() + interval '1 day');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  ('99999999-9999-4999-8999-000000000003', ${workspace}, 'queued', 'Operations job 3', 1000000, '{}');
insert into app_private.run_jobs (run_id, workspace_id, status, available_at, generation, lease_owner, lease_expires_at) values
  ('99999999-9999-4999-8999-000000000003', ${workspace}, 'queued', now() + interval '30 days', 1, null, null);
insert into public.artifacts (id, workspace_id, run_id, operation_id, name, object_path, media_type, size_bytes, sha256, status) values
  (gen_random_uuid(), ${workspace}, '99999999-9999-4999-8999-000000000001', 'ops-n-0', 'file-0.md', 'ops-n/0', 'text/markdown', 1000,
   '0000000000000000000000000000000000000000000000000000000000000000', 'published'),
  (gen_random_uuid(), ${workspace}, '99999999-9999-4999-8999-000000000001', 'ops-n-1', 'file-1.md', 'ops-n/1', 'text/markdown', 2345,
   '0000000000000000000000000000000000000000000000000000000000000001', 'published'),
  (gen_random_uuid(), ${workspace}, '99999999-9999-4999-8999-000000000001', 'ops-n-2', 'file-2.md', 'ops-n/2', 'text/markdown', 999,
   '0000000000000000000000000000000000000000000000000000000000000002', 'staged');
