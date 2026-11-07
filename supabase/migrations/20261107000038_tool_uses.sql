-- US-14.3, PRD-Tool-Catalog TU-01 to TU-07, Decision 0017 Q3, Q4 and Q13: every tool dispatch is
-- recorded, whatever its class and including denials. Receipts stay the effect ledger, and a use
-- links to one by operation ID. Content never lands here: only the fields a tool's definition lists
-- as public, digests and sizes.
create table app_private.tool_uses (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  root_run_id uuid not null references public.runs (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id),
  sequence_in_run integer not null check (sequence_in_run >= 1),
  tool_id text not null check (char_length(tool_id) between 1 and 100),
  tool_version integer check (tool_version >= 1),
  tool_group text,
  provider text,
  cost_class text,
  plan_version integer,
  task_id text,
  requested_at timestamptz not null default clock_timestamp(),
  finished_at timestamptz,
  outcome text check (outcome in ('succeeded', 'failed', 'unknown', 'denied')),
  code text,
  input_digest text not null,
  input_public jsonb not null default '{}'::jsonb check (jsonb_typeof(input_public) = 'object'),
  output_public jsonb check (output_public is null or jsonb_typeof(output_public) = 'object'),
  output_bytes integer check (output_bytes >= 0),
  operation_id text,
  provider_units numeric,
  -- Set when a metered call was admitted under the run tree's limit, so a count can't race.
  metered boolean not null default false,
  generation bigint not null,
  unique (run_id, sequence_in_run),
  check ((outcome is null) = (finished_at is null))
);

create index tool_uses_tree on app_private.tool_uses (root_run_id, id);
create index tool_uses_metered on app_private.tool_uses (root_run_id) where metered;

-- Private: no PostgREST, no Realtime and no browser role. The API reads it in a projection.
revoke all on app_private.tool_uses from public, anon, authenticated;
grant select, insert, update on app_private.tool_uses to autobots_runtime;
