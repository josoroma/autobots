-- R-56 (SQLI-13, SQLI-14): migration 59's draft shape check and migration 60's four version keys hold for
-- every existing row, not only new ones. This is the one file of 57 to 61 that a drifted row can stop.
-- Before applying it to an existing install, run each query below on it; each must return no row:
--   select workflow_id from public.workflow_drafts where not ((jsonb_typeof(graph) = 'object' and jsonb_typeof(graph -> 'nodes') = 'array' and jsonb_typeof(graph -> 'links') = 'array') is true);
--   select r.id from public.runs r where r.expert_id is not null and r.expert_version is not null and not exists (select 1 from public.expert_versions v where v.expert_id = r.expert_id and v.version = r.expert_version);
--   select a.id from app_private.assignments a where not exists (select 1 from public.expert_versions v where v.expert_id = a.expert_id and v.version = a.expert_version);
--   select o.routine_id, o.occurrence_time from public.routine_occurrences o where not exists (select 1 from public.routine_versions v where v.routine_id = o.routine_id and v.version = o.routine_version);
--   select h.workspace_id, h.kind, h.key from public.knowledge_heads h where h.active_version is not null and not exists (select 1 from public.knowledge_versions v where (v.workspace_id, v.kind, v.key, v.version) = (h.workspace_id, h.kind, h.key, h.active_version));
-- Locks: SHARE UPDATE EXCLUSIVE on public.workflow_drafts, public.runs, app_private.assignments,
-- public.routine_occurrences and public.knowledge_heads, and ROW SHARE on the version tables they name,
-- while each is read once; reads and writes go on. Expected duration: a few seconds at most on a local
-- install, most of it reading public.runs.
-- Data: none. A row that breaks a constraint stops the file; nothing is rewritten.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; 57 to 60 stay
-- applied, and readiness reads schema_behind until it applies. No later migration can repair the rows, since
-- this one fails first. The queries above name the offending rows. The owner corrects them with a reviewed
-- data change against the install, as supabase_admin over the database container's socket
-- (docs/engineering/runbooks/local-supabase.md, "Before make migrate"); a misshapen draft can also be
-- discarded with DELETE /v1/workflows/{id}/draft. Then the guarded apply runs again and applies 61 and the
-- files after it. The pre-upgrade backup holds the rows as they were.
alter table public.workflow_drafts validate constraint workflow_drafts_graph_shape;
alter table public.runs validate constraint runs_expert_version_fk;
alter table app_private.assignments validate constraint assignments_expert_version_fk;
alter table public.routine_occurrences validate constraint routine_occurrences_version_fk;
alter table public.knowledge_heads validate constraint knowledge_heads_active_version_fk;
