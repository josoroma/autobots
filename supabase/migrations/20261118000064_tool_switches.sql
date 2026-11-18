-- US-14.24, Decision 0033 W1 to W5 and PRD-Tool-Catalog TW-01 to TW-03: the owner turns a tool, or a whole group, on or
-- off for the workspace. No row means on. Each switch keeps its own optimistic version, like Keys & vars. Direct server
-- SQL only: no PostgREST, Realtime or browser role.
-- Locks: none on existing tables; it creates one new, empty table.
-- Data: none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves no table; apply it again.
create table app_private.tool_switches (
  workspace_id uuid not null references public.workspaces (id),
  kind text not null check (kind in ('tool', 'group')),
  target text not null check (target ~ '^[a-z][a-z0-9_]{2,63}$'),
  enabled boolean not null default true,
  version integer not null default 1 check (version >= 1),
  updated_at timestamptz not null default now(),
  primary key (workspace_id, kind, target)
);

revoke all on app_private.tool_switches from public, anon, authenticated;
grant select, insert, update on app_private.tool_switches to autobots_runtime;
