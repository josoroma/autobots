-- PRD 8.3: an assignment is created before dispatch, and deduplicated by the parent's operation.
alter table public.runs add column root_run_id uuid references public.runs (id);

create table app_private.assignments (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  parent_run_id uuid not null references public.runs (id) on delete cascade,
  child_run_id uuid not null unique references public.runs (id) on delete cascade,
  root_run_id uuid not null references public.runs (id) on delete cascade,
  operation_id text not null unique,
  depth integer not null check (depth >= 1),
  expert_id uuid not null references public.experts (id),
  expert_version integer not null,
  status text not null default 'open' check (status in ('open', 'finished')),
  outcome text,
  result jsonb,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create index assignments_parent on app_private.assignments (parent_run_id);
create index assignments_root on app_private.assignments (root_run_id, status);

revoke all on app_private.assignments from public, anon, authenticated;
grant select, insert, update on app_private.assignments to autobots_runtime;
