-- Synthetic disposable fixtures with fixed identifiers. Repeatable, and never overwrites an edited row.
insert into app.workspaces (id, name) values
  ('a0000000-0000-4000-8000-000000000001', 'Workspace A'),
  ('b0000000-0000-4000-8000-000000000002', 'Workspace B')
on conflict (id) do nothing;

insert into app.workspace_members (workspace_id, user_id) values
  ('a0000000-0000-4000-8000-000000000001', 'a1111111-1111-4111-8111-111111111111'),
  ('b0000000-0000-4000-8000-000000000002', 'b2222222-2222-4222-8222-222222222222')
on conflict do nothing;

insert into app.notes (id, workspace_id, body) values
  ('a3333333-3333-4333-8333-333333333333', 'a0000000-0000-4000-8000-000000000001', 'A note'),
  ('b4444444-4444-4444-8444-444444444444', 'b0000000-0000-4000-8000-000000000002', 'B note')
on conflict (id) do nothing;

insert into app_private.credentials (workspace_id, ciphertext) values
  ('a0000000-0000-4000-8000-000000000001', 'synthetic-ciphertext')
on conflict (workspace_id) do nothing;
