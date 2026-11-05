-- Synthetic rows for a prior-version upgrade and authorization cases, in disposable targets only.
insert into public.workspaces (id, name) values
  ('a0000000-0000-4000-8000-000000000001', 'Workspace A'),
  ('b0000000-0000-4000-8000-000000000002', 'Workspace B');
insert into public.workspace_members (workspace_id, user_id) values
  ('a0000000-0000-4000-8000-000000000001', 'a1111111-1111-4111-8111-111111111111'),
  ('b0000000-0000-4000-8000-000000000002', 'b2222222-2222-4222-8222-222222222222');
insert into public.runs (id, workspace_id, limit_micro_usd) values
  ('a3333333-3333-4333-8333-333333333333', 'a0000000-0000-4000-8000-000000000001', 1000),
  ('b4444444-4444-4444-8444-444444444444', 'b0000000-0000-4000-8000-000000000002', 1000);
