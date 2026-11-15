-- R-56 (SQLI-08): the run-scoped lookups are indexed. Retention's purge_run_content and
-- expire_idempotency_receipts (migration 27) find a run's tree, continuations, unresolved receipts and
-- open model calls, and each run view reads its receipts and artifacts by run. Each index matches one
-- of those filters, partial where the function's own predicate is.
-- Locks: SHARE on app_private.tool_receipts, public.artifacts, public.runs and
-- app_private.model_invocations from each index build until the file commits, which blocks their writes
-- but not their reads. The runner applies a file in one transaction, so CONCURRENTLY can't be used.
-- Expected duration: under 10 seconds in all for a local install with up to a few hundred thousand rows
-- in its largest table, tool_receipts; well under a second on a new one.
-- Data: none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
create index tool_receipts_run on app_private.tool_receipts (run_id, status);
create index artifacts_run on public.artifacts (run_id);
create index runs_continues on public.runs (continues_run_id) where continues_run_id is not null;
create index runs_tree on public.runs ((coalesce(root_run_id, id)));
create index model_invocations_open_run on app_private.model_invocations (run_id)
  where status = 'uncertain' and reconciled_at is null;
