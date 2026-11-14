-- R-17 (SQLI-01): the runtime role deletes only workflow drafts, which is all the service deletes.
-- Deleting a run cascades through 21 foreign keys into receipts, tool uses, approvals and evidence
-- that replay and reconciliation depend on, so no worker or API process may do it.
-- Locks: a brief catalog lock on each of the five tables; no table is rewritten or scanned.
-- Data: none. Rows and every other role's grants are unchanged.
-- Recovery: run it again; revoking a privilege the role no longer holds changes nothing.
revoke delete on public.runs, public.run_events, public.workspaces, public.workspace_members,
  public.user_profiles from autobots_runtime;
