-- Synthetic H1 fixture, not product schema.
create schema app;
create schema app_private;

create table app.workspaces (
  id uuid primary key,
  name text not null
);

create table app.workspace_members (
  workspace_id uuid not null references app.workspaces (id),
  user_id uuid not null,
  primary key (workspace_id, user_id)
);

create table app.notes (
  id uuid primary key,
  workspace_id uuid not null references app.workspaces (id),
  body text not null
);

create table app_private.credentials (
  workspace_id uuid primary key references app.workspaces (id),
  ciphertext text not null
);

create function app.is_member(target uuid) returns boolean
  language sql stable security definer set search_path = ''
  as $$ select exists (
    select 1 from app.workspace_members
    where workspace_id = target and user_id = auth.uid()
  ) $$;

alter table app.workspaces enable row level security;
alter table app.workspace_members enable row level security;
alter table app.notes enable row level security;

grant usage on schema app to authenticated;
grant select on app.workspaces, app.workspace_members to authenticated;
grant select, insert, update, delete on app.notes to authenticated;
grant execute on function app.is_member(uuid) to authenticated;
revoke all on schema app from anon;
revoke all on schema app_private from public, anon, authenticated;
revoke all on all tables in schema app_private from public, anon, authenticated;

create policy member_workspaces on app.workspaces for select to authenticated using (app.is_member(id));
create policy own_membership on app.workspace_members for select to authenticated using (user_id = auth.uid());
create policy member_notes on app.notes for all to authenticated
  using (app.is_member(workspace_id)) with check (app.is_member(workspace_id));
