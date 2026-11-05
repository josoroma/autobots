-- Runs and their sanitized event log. States are SP-010's. Lease and checkpoint columns stay private.
create table public.runs (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  parent_run_id uuid references public.runs (id),
  status text not null default 'queued' check (status in (
    'queued', 'running', 'waiting_input', 'waiting_approval', 'paused', 'verifying',
    'cancelling', 'succeeded', 'failed', 'cancelled'
  )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  spent_micro_usd bigint not null default 0 check (spent_micro_usd >= 0),
  reserved_micro_usd bigint not null default 0 check (reserved_micro_usd >= 0),
  limit_micro_usd bigint not null check (limit_micro_usd >= 0),
  lease_generation bigint not null default 0 check (lease_generation >= 0),
  checkpoint_thread_id text
);

create index runs_workspace_id on public.runs (workspace_id);

create table public.run_events (
  run_id uuid not null references public.runs (id) on delete cascade,
  sequence bigint not null check (sequence >= 1),
  schema_version integer not null check (schema_version >= 1),
  payload jsonb not null,
  occurred_at timestamptz not null,
  primary key (run_id, sequence)
);

alter table public.runs enable row level security;
alter table public.run_events enable row level security;

revoke all on public.runs, public.run_events from public, anon, authenticated;
grant select (id, workspace_id, parent_run_id, status, created_at, updated_at,
              spent_micro_usd, reserved_micro_usd, limit_micro_usd) on public.runs to authenticated;
grant select on public.run_events to authenticated;
grant select, insert, update, delete on public.runs, public.run_events to autobots_runtime;

create policy members_read_runs on public.runs for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_events on public.run_events for select to authenticated
  using (exists (
    select 1 from public.runs where runs.id = run_events.run_id and public.is_workspace_member(runs.workspace_id)
  ));
create policy runtime_runs on public.runs for all to autobots_runtime using (true) with check (true);
create policy runtime_events on public.run_events for all to autobots_runtime using (true) with check (true);
