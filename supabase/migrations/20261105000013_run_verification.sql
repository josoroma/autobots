-- LC-12: a run's completion is decided from recorded checks, kept for inspection.
create table app_private.run_verifications (
  id uuid primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  passed boolean not null,
  unmet jsonb not null,
  checks integer not null,
  created_at timestamptz not null default now()
);

create index run_verifications_run on app_private.run_verifications (run_id, created_at);

revoke all on app_private.run_verifications from public, anon, authenticated;
grant select, insert on app_private.run_verifications to autobots_runtime;
