-- US-16.3: a member of two workspaces, their own P and the runs-g owner's G, with a run only in P.
-- Synthetic rows for the disposable identity qualification only (DH-07). scripts/qualify_identity.py
-- runs it as the database superuser, with workspace G, the multi-p owner's user and workspace P.

insert into public.workspace_members (workspace_id, user_id, role) values (${shared}, ${user}, 'member');
insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) values
  (gen_random_uuid(), ${workspace}, 'succeeded', 'Only in workspace P', 1000000, '{}');
