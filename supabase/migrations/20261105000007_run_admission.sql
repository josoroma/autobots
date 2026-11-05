-- SP-010 and SP-014: versioned runs, a durable job row, and idempotency receipts.
alter table public.runs
  add column version integer not null default 1 check (version >= 1),
  add column goal_text text not null default '',
  add column policy_snapshot jsonb not null default '{}'::jsonb;

grant select (version, goal_text) on public.runs to authenticated;

create table app_private.run_jobs (
  run_id uuid primary key references public.runs (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id),
  status text not null default 'queued' check (status in ('queued', 'claimed', 'done')),
  available_at timestamptz not null default now(),
  attempts integer not null default 0 check (attempts >= 0),
  generation bigint not null default 0 check (generation >= 0),
  lease_owner text,
  lease_expires_at timestamptz
);

create index run_jobs_eligible on app_private.run_jobs (available_at) where status = 'queued';

create table app_private.idempotency_receipts (
  workspace_id uuid not null references public.workspaces (id),
  actor_id uuid not null,
  operation text not null,
  target text not null,
  idempotency_key text not null check (char_length(idempotency_key) between 1 and 200),
  request_hash text not null,
  result jsonb not null,
  created_at timestamptz not null default now(),
  primary key (workspace_id, actor_id, operation, target, idempotency_key)
);

revoke all on app_private.run_jobs, app_private.idempotency_receipts from public, anon, authenticated;
grant select, insert, update on app_private.run_jobs, app_private.idempotency_receipts to autobots_runtime;
