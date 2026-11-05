-- PRD 8.5: a proposal is reviewed before it becomes a version, and every version can be rolled back.
create table public.improvement_candidates (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  kind text not null check (kind in ('memory', 'skill')),
  key text not null check (char_length(key) between 1 and 100),
  content text not null check (char_length(content) between 1 and 20000),
  evidence jsonb not null,
  regression_cases jsonb not null,
  source jsonb not null,
  status text not null default 'proposed'
    check (status in ('proposed', 'regression_failed', 'regression_passed', 'rejected', 'promoted')),
  regression_results jsonb,
  reviewed_by uuid,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.knowledge_versions (
  workspace_id uuid not null references public.workspaces (id),
  kind text not null check (kind in ('memory', 'skill')),
  key text not null,
  version integer not null check (version >= 1),
  content text not null,
  candidate_id uuid not null references public.improvement_candidates (id),
  provenance jsonb not null,
  created_at timestamptz not null default now(),
  primary key (workspace_id, kind, key, version)
);

create table public.knowledge_heads (
  workspace_id uuid not null references public.workspaces (id),
  kind text not null,
  key text not null,
  active_version integer not null,
  updated_at timestamptz not null default now(),
  primary key (workspace_id, kind, key)
);

alter table public.memory_items
  add column key text,
  add column version integer,
  add column retired_at timestamptz;
grant select (key, version, retired_at) on public.memory_items to authenticated;
grant update (retired_at) on public.memory_items to autobots_runtime;

alter table public.improvement_candidates enable row level security;
alter table public.knowledge_versions enable row level security;
alter table public.knowledge_heads enable row level security;
revoke all on public.improvement_candidates, public.knowledge_versions, public.knowledge_heads from public, anon, authenticated;
grant select on public.improvement_candidates, public.knowledge_versions, public.knowledge_heads to authenticated;
grant select, insert, update on public.improvement_candidates, public.knowledge_heads to autobots_runtime;
grant select, insert on public.knowledge_versions to autobots_runtime;

create policy members_read_candidates on public.improvement_candidates for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_knowledge on public.knowledge_versions for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy members_read_heads on public.knowledge_heads for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy runtime_candidates on public.improvement_candidates for all to autobots_runtime using (true) with check (true);
create policy runtime_knowledge on public.knowledge_versions for all to autobots_runtime using (true) with check (true);
create policy runtime_heads on public.knowledge_heads for all to autobots_runtime using (true) with check (true);
