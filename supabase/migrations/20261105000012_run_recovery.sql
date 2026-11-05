-- SP-010 and SP-012: obligations that survive a pause, and a link instead of reopening a run.
alter table public.runs add column continues_run_id uuid references public.runs (id);
grant select (continues_run_id) on public.runs to authenticated;

create table app_private.run_obligations (
  id uuid primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  kind text not null check (kind in ('input', 'approval')),
  detail text not null,
  status text not null default 'open' check (status in ('open', 'met')),
  response text,
  created_at timestamptz not null default now(),
  met_at timestamptz
);

create unique index run_obligations_one_open on app_private.run_obligations (run_id, kind)
  where status = 'open';

revoke all on app_private.run_obligations from public, anon, authenticated;
grant select, insert, update on app_private.run_obligations to autobots_runtime;
