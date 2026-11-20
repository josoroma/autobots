-- US-17.4, Decision 0035 Y11: one row per browser-use step of a browse_goal tool use, with the page it ended on as host and
-- path, the host and path of each form it submitted, and its screenshot's object in the run's private storage. Never a typed
-- value or a query. Direct server SQL only: no PostgREST, Realtime or browser role.
-- Locks: none on existing data; the foreign keys take brief SHARE ROW EXCLUSIVE locks on `tool_uses`, `runs` and
--   `workspaces` to add their triggers, which scan no rows.
-- Data: none rewritten.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
create table app_private.browse_steps (
  id bigint generated always as identity primary key,
  tool_use_id bigint not null references app_private.tool_uses (id) on delete cascade,
  run_id uuid not null references public.runs (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id),
  step integer not null check (step between 1 and 100),
  page text check (page is null or char_length(page) <= 2048),
  submits jsonb not null default '[]'::jsonb check (jsonb_typeof(submits) = 'array'),
  object_path text check (object_path is null or char_length(object_path) <= 512),
  bytes integer check (bytes is null or bytes >= 0),
  sha256 text check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (tool_use_id, step),
  check ((object_path is null) = (bytes is null) and (object_path is null) = (sha256 is null))
);

create index browse_steps_run on app_private.browse_steps (run_id);

revoke all on app_private.browse_steps from public, anon, authenticated;
grant select, insert on app_private.browse_steps to autobots_runtime;
