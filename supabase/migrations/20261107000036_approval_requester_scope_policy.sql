-- US-13.1, Decision 0015: who asked, under what scope and under which policy version, PRD 9.2.
-- Nullable, as a run or request saved before this has none of them, and nothing fills them in.

-- The person who started the run. A child takes its parent's, and a routine's run has none.
alter table public.runs
  add column started_by uuid;

alter table public.approval_requests
  add column requested_by uuid,
  add column requested_by_agent jsonb
    check (requested_by_agent is null or requested_by_agent ->> 'kind' in ('expert', 'coordinator')),
  add column scope_snapshot jsonb
    check (scope_snapshot is null or (
      jsonb_typeof(scope_snapshot -> 'tools') = 'object'
      and jsonb_typeof(scope_snapshot -> 'paths') = 'array')),
  add column policy_version text,
  add column policy_rule text
    check (policy_rule is null or policy_rule in ('consequential_external_write', 'tool_marked'));

-- Stored once with the proposal. A later change, filling in an older request included, is refused.
create function app_private.keep_approval_record() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.requested_by is distinct from old.requested_by
     or new.requested_by_agent is distinct from old.requested_by_agent
     or new.scope_snapshot is distinct from old.scope_snapshot
     or new.policy_version is distinct from old.policy_version
     or new.policy_rule is distinct from old.policy_rule then
    raise exception 'an approval request''s requester, scope and policy are immutable'
      using errcode = 'AB002';
  end if;
  return new;
end;
$$;

create trigger approval_requests_immutable before update on public.approval_requests
  for each row execute function app_private.keep_approval_record();
