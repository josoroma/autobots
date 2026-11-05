-- PRD 8.2: an Expert is a durable product object, and each revision of it is immutable.
create table public.experts (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  name text not null check (char_length(name) between 1 and 100),
  latest_version integer not null default 1 check (latest_version >= 1),
  created_at timestamptz not null default now(),
  unique (workspace_id, name)
);

create table public.expert_versions (
  expert_id uuid not null references public.experts (id) on delete cascade,
  version integer not null check (version >= 1),
  config jsonb not null,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  primary key (expert_id, version)
);

create table public.sessions (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  kind text not null check (kind in ('direct', 'coordinator')),
  -- For a direct session one entry, and for a coordinator the Experts it may route to.
  experts jsonb not null,
  created_by uuid not null,
  created_at timestamptz not null default now()
);

alter table public.runs
  add column session_id uuid references public.sessions (id),
  add column expert_id uuid references public.experts (id),
  add column expert_version integer;
grant select (session_id, expert_id, expert_version) on public.runs to authenticated;

alter table public.experts enable row level security;
alter table public.expert_versions enable row level security;
alter table public.sessions enable row level security;
revoke all on public.experts, public.expert_versions, public.sessions from public, anon, authenticated;
grant select on public.experts, public.expert_versions, public.sessions to authenticated;
grant select, insert, update on public.experts to autobots_runtime;
grant select, insert on public.expert_versions, public.sessions to autobots_runtime;

create policy members_read_experts on public.experts for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_expert_versions on public.expert_versions for select to authenticated
  using (exists (select 1 from public.experts e
                 where e.id = expert_id and public.is_workspace_member(e.workspace_id)));
create policy members_read_sessions on public.sessions for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy runtime_experts on public.experts for all to autobots_runtime using (true) with check (true);
create policy runtime_expert_versions on public.expert_versions for all to autobots_runtime using (true) with check (true);
create policy runtime_sessions on public.sessions for all to autobots_runtime using (true) with check (true);
