-- SP-012 and SP-013: durable identity for tool effects, and virtual run files.
create table app_private.tool_receipts (
  operation_id text primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id),
  tool_id text not null,
  tool_version integer not null check (tool_version >= 1),
  argument_hash text not null,
  status text not null check (status in ('started', 'succeeded', 'failed', 'unknown')),
  result jsonb,
  generation bigint not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table app_private.run_files (
  run_id uuid not null references public.runs (id) on delete cascade,
  path text not null check (char_length(path) between 1 and 500),
  version integer not null check (version >= 1),
  content text not null,
  sha256 text not null,
  media_type text not null,
  operation_id text not null unique,
  created_at timestamptz not null default now(),
  primary key (run_id, path, version)
);

revoke all on app_private.tool_receipts, app_private.run_files from public, anon, authenticated;
grant select, insert, update on app_private.tool_receipts to autobots_runtime;
grant select, insert on app_private.run_files to autobots_runtime;
