-- MP-07: a private ledger. Every attempt is a row, and a reservation stays until it is settled or reconciled.
create table app_private.model_spend_limits (
  workspace_id uuid primary key references public.workspaces (id),
  run_limit_micro_usd bigint not null default 1000000 check (run_limit_micro_usd >= 0),
  daily_limit_micro_usd bigint not null default 5000000 check (daily_limit_micro_usd >= 0),
  slots integer not null default 2 check (slots >= 1)
);

create table app_private.model_invocations (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  root_run_id uuid not null,
  run_id uuid not null,
  role text not null,
  profile text not null check (profile in ('openrouter_deepseek_flash', 'openrouter_astra')),
  wire_id text not null,
  attempt integer not null check (attempt >= 1),
  credential_version integer,
  spend_day date not null,
  reserved_micro_usd bigint not null check (reserved_micro_usd >= 0),
  charged_micro_usd bigint check (charged_micro_usd >= 0),
  status text not null check (status in (
    'reserved', 'dispatched', 'succeeded', 'failed_before_acceptance', 'uncertain', 'cancelled'
  )),
  failure_class text,
  accumulated_output text,
  upstream_provider text,
  reconciled_at timestamptz,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create index model_invocations_workspace_day on app_private.model_invocations (workspace_id, spend_day);
create index model_invocations_root on app_private.model_invocations (root_run_id);

revoke all on app_private.model_spend_limits, app_private.model_invocations from public, anon, authenticated;
grant select, insert, update on app_private.model_spend_limits, app_private.model_invocations to autobots_runtime;
