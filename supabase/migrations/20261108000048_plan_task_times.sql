-- US-15.17, PRD-Studio RN-05: when each plan task started and finished, in database time.
-- Written only on the worker's fenced path: a task starts with the first tool use that serves it, in that
-- use's leased transaction, and finishes when complete_task records its evidence. Kept by task ID across
-- plan revisions, as a revision can't change or drop a completed task. A new, empty table: no backfill.
create table app_private.plan_task_times (
  run_id uuid not null references public.runs (id) on delete cascade,
  task_id text not null check (char_length(task_id) between 1 and 40),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  primary key (run_id, task_id),
  check (finished_at is null or finished_at >= started_at)
);

revoke all on app_private.plan_task_times from public, anon, authenticated;
grant select, insert, update on app_private.plan_task_times to autobots_runtime;
