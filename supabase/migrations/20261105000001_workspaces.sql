-- Workspace ownership and the private schema boundaries of LM-05.
create schema app_private;
create schema agent_runtime;
revoke all on schema app_private, agent_runtime from public, anon, authenticated;
grant usage on schema app_private, agent_runtime to autobots_runtime;

create table public.workspaces (
  id uuid primary key,
  name text not null check (char_length(name) between 1 and 200),
  timezone text not null default 'UTC',
  created_at timestamptz not null default now()
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null,
  role text not null default 'owner' check (role in ('owner', 'member')),
  primary key (workspace_id, user_id)
);

create index workspace_members_user_id on public.workspace_members (user_id);

create function public.is_workspace_member(target uuid) returns boolean
  language sql stable security definer set search_path = ''
  as $$ select exists (
    select 1 from public.workspace_members
    where workspace_id = target and user_id = auth.uid()
  ) $$;

revoke all on function public.is_workspace_member(uuid) from public;
grant execute on function public.is_workspace_member(uuid) to authenticated;

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;

revoke all on public.workspaces, public.workspace_members from public, anon, authenticated;
grant select on public.workspaces, public.workspace_members to authenticated;
grant select, insert, update, delete on public.workspaces, public.workspace_members to autobots_runtime;

create policy members_read_workspaces on public.workspaces for select to authenticated
  using (public.is_workspace_member(id));
create policy members_read_own_membership on public.workspace_members for select to authenticated
  using (user_id = auth.uid());
create policy runtime_workspaces on public.workspaces for all to autobots_runtime using (true) with check (true);
create policy runtime_memberships on public.workspace_members for all to autobots_runtime using (true) with check (true);
