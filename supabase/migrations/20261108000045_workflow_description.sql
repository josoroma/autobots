-- US-15.11, PRD-Studio WF-06: an optional description says what a workflow does. Versions and
-- their graphs aren't touched, so every published version keeps its hash.
alter table public.workflows add column description text
  check (description is null or char_length(description) between 1 and 500);
