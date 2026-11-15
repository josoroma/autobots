-- R-56 (SQLI-14): a run, an assignment, a routine occurrence and a knowledge head each name a version
-- that exists, as a workflow execution already does (migration 18). MATCH SIMPLE leaves a pair with a
-- null unchecked: a run with no Expert, and a knowledge head rolled back to no version (migration 28).
-- They are added NOT VALID, so every new write is checked at once; migration 61 validates the existing rows.
-- Locks: SHARE ROW EXCLUSIVE on public.runs, app_private.assignments, public.routine_occurrences and
-- public.knowledge_heads, and on public.expert_versions, public.routine_versions and
-- public.knowledge_versions, for the catalog change only: milliseconds, since NOT VALID reads no row.
-- Data: none.
-- Recovery: it applies in one transaction with its history row, so a failure leaves nothing; apply it again.
alter table public.runs add constraint runs_expert_version_fk
  foreign key (expert_id, expert_version) references public.expert_versions (expert_id, version) not valid;
alter table app_private.assignments add constraint assignments_expert_version_fk
  foreign key (expert_id, expert_version) references public.expert_versions (expert_id, version) not valid;
alter table public.routine_occurrences add constraint routine_occurrences_version_fk
  foreign key (routine_id, routine_version) references public.routine_versions (routine_id, version) not valid;
alter table public.knowledge_heads add constraint knowledge_heads_active_version_fk
  foreign key (workspace_id, kind, key, active_version)
  references public.knowledge_versions (workspace_id, kind, key, version) not valid;
