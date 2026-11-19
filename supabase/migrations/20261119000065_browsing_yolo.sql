-- US-17.1, Decision 0035 Y1 to Y4: the workspace's "Let browsing type and submit (YOLO)" setting, and the value each run
-- froze at admission. No settings row means on, so every workspace, new or existing, starts on (Y1). A run admitted before
-- this migration reads false, so it never skips approval. Direct server SQL only: no PostgREST, Realtime or browser role.
-- Locks: none on existing data for the new table; `runs` takes a brief ACCESS EXCLUSIVE lock to add a column with a
--   constant default, a catalog-only change that rewrites no rows, however large the table.
-- Data: none rewritten.
-- Recovery: it applies in one transaction with its history row, so a failure leaves neither change; apply it again.
create table app_private.browsing_settings (
  workspace_id uuid primary key references public.workspaces (id),
  yolo boolean not null default true,
  version integer not null default 1 check (version >= 1),
  notice_seen_at timestamptz,
  updated_at timestamptz not null default now()
);

revoke all on app_private.browsing_settings from public, anon, authenticated;
grant select, insert, update on app_private.browsing_settings to autobots_runtime;

alter table public.runs add column browsing_yolo boolean not null default false;
