-- US-14.19, Decision 0026 C7: a routine can be removed without deleting anything. A removed
-- routine is disabled, hidden from lists and never evaluated, while its versions, occurrences and
-- runs stay. Its name is free again, so the name is unique only among routines still in use.
alter table public.routines
  add column removed_at timestamptz,
  drop constraint routines_workspace_id_name_key;

create unique index routines_live_name on public.routines (workspace_id, name) where removed_at is null;

-- Decision 0026 C3: a tool can ask for approval on some calls only, recorded as `action_marked`
-- under approval-policy/2. Existing rows keep their rule.
alter table public.approval_requests
  drop constraint approval_requests_policy_rule_check,
  add constraint approval_requests_policy_rule_check
    check (policy_rule is null or policy_rule in ('consequential_external_write', 'tool_marked', 'action_marked'));
