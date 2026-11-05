-- PRD 7.3: each node instance has its own identity, and an emission is never overwritten.
alter table public.workflow_executions add column run_id uuid references public.runs (id);

create table public.workflow_node_instances (
  execution_id uuid not null references public.workflow_executions (id) on delete cascade,
  instance_key text not null,
  node_id text not null,
  iteration integer,
  status text not null check (status in ('running', 'succeeded', 'failed', 'skipped', 'blocked')),
  error_code text,
  updated_at timestamptz not null default now(),
  primary key (execution_id, instance_key)
);

create table public.workflow_emissions (
  execution_id uuid not null references public.workflow_executions (id) on delete cascade,
  instance_key text not null,
  port text not null,
  sequence integer not null,
  value jsonb not null,
  created_at timestamptz not null default now(),
  primary key (execution_id, instance_key, port, sequence)
);

alter table public.workflow_node_instances enable row level security;
alter table public.workflow_emissions enable row level security;
revoke all on public.workflow_node_instances, public.workflow_emissions from public, anon, authenticated;
grant select on public.workflow_node_instances, public.workflow_emissions to authenticated;
grant select, insert, update on public.workflow_node_instances to autobots_runtime;
grant select, insert on public.workflow_emissions to autobots_runtime;

create policy members_read_instances on public.workflow_node_instances for select to authenticated
  using (exists (select 1 from public.workflow_executions e
                 where e.id = execution_id and public.is_workspace_member(e.workspace_id)));
create policy members_read_emissions on public.workflow_emissions for select to authenticated
  using (exists (select 1 from public.workflow_executions e
                 where e.id = execution_id and public.is_workspace_member(e.workspace_id)));
create policy runtime_instances on public.workflow_node_instances for all to autobots_runtime using (true) with check (true);
create policy runtime_emissions on public.workflow_emissions for all to autobots_runtime using (true) with check (true);
