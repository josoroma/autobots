-- PRD 10.4: an explicit routine, immutable versions, and one row per occurrence.
create table public.routines (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  name text not null check (char_length(name) between 1 and 100),
  latest_version integer not null default 1,
  enabled boolean not null default true,
  evaluated_until timestamptz not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, name)
);

create table public.routine_versions (
  routine_id uuid not null references public.routines (id) on delete cascade,
  version integer not null check (version >= 1),
  config jsonb not null,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  primary key (routine_id, version)
);

create table public.routine_occurrences (
  routine_id uuid not null references public.routines (id) on delete cascade,
  occurrence_time timestamptz not null,
  routine_version integer not null,
  status text not null check (status in ('admitted', 'missed', 'skipped_overlap', 'blocked')),
  reason text,
  run_id uuid references public.runs (id),
  created_at timestamptz not null default now(),
  primary key (routine_id, occurrence_time)
);

alter table public.routines enable row level security;
alter table public.routine_versions enable row level security;
alter table public.routine_occurrences enable row level security;
revoke all on public.routines, public.routine_versions, public.routine_occurrences from public, anon, authenticated;
grant select on public.routines, public.routine_versions, public.routine_occurrences to authenticated;
grant select, insert, update on public.routines to autobots_runtime;
grant select, insert on public.routine_versions, public.routine_occurrences to autobots_runtime;

create policy members_read_routines on public.routines for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_routine_versions on public.routine_versions for select to authenticated
  using (exists (select 1 from public.routines r
                 where r.id = routine_id and public.is_workspace_member(r.workspace_id)));
create policy members_read_occurrences on public.routine_occurrences for select to authenticated
  using (exists (select 1 from public.routines r
                 where r.id = routine_id and public.is_workspace_member(r.workspace_id)));
create policy runtime_routines on public.routines for all to autobots_runtime using (true) with check (true);
create policy runtime_routine_versions on public.routine_versions for all to autobots_runtime using (true) with check (true);
create policy runtime_occurrences on public.routine_occurrences for all to autobots_runtime using (true) with check (true);
