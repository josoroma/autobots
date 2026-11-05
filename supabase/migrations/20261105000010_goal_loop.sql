-- SP-008 and SP-011: the admitted goal, versioned plans, kept evidence and root usage.
create table app_private.goal_specs (
  run_id uuid primary key references public.runs (id) on delete cascade,
  spec jsonb not null
);

create table app_private.plan_versions (
  run_id uuid not null references public.runs (id) on delete cascade,
  version integer not null check (version >= 1),
  tasks jsonb not null,
  revision_reason text,
  created_at timestamptz not null default now(),
  primary key (run_id, version),
  check (version = 1 or revision_reason is not null)
);

create table app_private.plan_evidence (
  run_id uuid not null references public.runs (id) on delete cascade,
  task_id text not null,
  evidence jsonb not null,
  summary text not null,
  completed_at timestamptz not null default now(),
  primary key (run_id, task_id)
);

create table app_private.run_usage (
  run_id uuid primary key references public.runs (id) on delete cascade,
  model_calls integer not null default 0,
  tool_dispatches integer not null default 0,
  repairs integer not null default 0,
  plan_revisions integer not null default 0,
  children integer not null default 0,
  active_seconds double precision not null default 0,
  segment_started_at timestamptz,
  stop_reason text
);

revoke all on app_private.goal_specs, app_private.plan_versions, app_private.plan_evidence,
  app_private.run_usage from public, anon, authenticated;
grant select, insert on app_private.goal_specs, app_private.plan_versions, app_private.plan_evidence
  to autobots_runtime;
grant select, insert, update on app_private.run_usage to autobots_runtime;
