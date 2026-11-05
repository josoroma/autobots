-- PRD 7.3: a published graph is immutable, and an execution binds to its exact version and hash.
create table public.workflows (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  name text not null check (char_length(name) between 1 and 100),
  latest_version integer not null default 0 check (latest_version >= 0),
  created_at timestamptz not null default now(),
  unique (workspace_id, name)
);

create table public.workflow_versions (
  workflow_id uuid not null references public.workflows (id) on delete cascade,
  version integer not null check (version >= 1),
  graph jsonb not null,
  graph_hash text not null,
  block_versions jsonb not null,
  source text not null check (source in ('user', 'model_proposal')),
  created_by uuid not null,
  created_at timestamptz not null default now(),
  primary key (workflow_id, version)
);

create table public.workflow_executions (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  workflow_id uuid not null,
  workflow_version integer not null,
  graph_hash text not null,
  block_versions jsonb not null,
  inputs jsonb not null,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  foreign key (workflow_id, workflow_version) references public.workflow_versions (workflow_id, version)
);

alter table public.workflows enable row level security;
alter table public.workflow_versions enable row level security;
alter table public.workflow_executions enable row level security;
revoke all on public.workflows, public.workflow_versions, public.workflow_executions from public, anon, authenticated;
grant select on public.workflows, public.workflow_versions, public.workflow_executions to authenticated;
grant select, insert, update on public.workflows to autobots_runtime;
grant select, insert on public.workflow_versions, public.workflow_executions to autobots_runtime;

create policy members_read_workflows on public.workflows for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_workflow_versions on public.workflow_versions for select to authenticated
  using (exists (select 1 from public.workflows w
                 where w.id = workflow_id and public.is_workspace_member(w.workspace_id)));
create policy members_read_workflow_executions on public.workflow_executions for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy runtime_workflows on public.workflows for all to autobots_runtime using (true) with check (true);
create policy runtime_workflow_versions on public.workflow_versions for all to autobots_runtime using (true) with check (true);
create policy runtime_workflow_executions on public.workflow_executions for all to autobots_runtime using (true) with check (true);
