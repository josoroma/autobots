-- Decision 0028 E4 (R-35, PRUN-14, XERR-10): a job counts its run's consecutive failed passes and keeps
-- the last one's module-qualified exception type, so the worker bounds their retries (SP-012). The
-- check admits only a qualified name, never a message. The columns stay private through the table's
-- grants: autobots_runtime writes them, and anon and authenticated hold nothing on run_jobs.
-- Locks: ACCESS EXCLUSIVE on app_private.run_jobs while the columns are added and one scan checks
-- them; no rewrite, as both defaults are constants, and one row per run keeps it under a second.
-- Data: none. Existing jobs read 0 failures and no type.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table app_private.run_jobs
  add column failed_attempts integer not null default 0 check (failed_attempts >= 0),
  add column last_failure_type text check (last_failure_type ~ '^[A-Za-z0-9_.<>]{1,200}$');
