-- US-13.2, Decision 0016: a held-out replay gates promotion. An owner's tasks become ordinary runs
-- with the proposal applied to them alone. Its state is read from those runs, never stored.
create table app_private.improvement_replays (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  candidate_id uuid not null references public.improvement_candidates (id) on delete cascade,
  requested_by uuid not null,
  created_at timestamptz not null default now()
);

create index improvement_replays_latest on app_private.improvement_replays (candidate_id, created_at desc);

create table app_private.improvement_replay_runs (
  replay_id uuid not null references app_private.improvement_replays (id) on delete cascade,
  run_id uuid not null unique references public.runs (id) on delete cascade,
  position integer not null check (position >= 0),
  task jsonb not null check (jsonb_typeof(task -> 'goal_text') = 'string'),
  primary key (replay_id, position)
);

-- A replay is a record of what was run. Nothing rewrites it.
revoke all on app_private.improvement_replays, app_private.improvement_replay_runs from public, anon, authenticated;
grant select, insert on app_private.improvement_replays, app_private.improvement_replay_runs to autobots_runtime;
