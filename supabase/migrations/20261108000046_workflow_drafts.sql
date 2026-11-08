-- US-15.12, PRD-Studio WF-02 and Decision 0022 D8: one saved draft graph per workflow. A member reads
-- it, only an owner writes it, and nothing runs it: runs and routines bind published versions only.
create function public.is_workspace_owner(target uuid) returns boolean
  language sql stable security definer set search_path = ''
  as $$ select exists (
    select 1 from public.workspace_members
    where workspace_id = target and user_id = auth.uid() and role = 'owner'
  ) $$;
revoke all on function public.is_workspace_owner(uuid) from public;
grant execute on function public.is_workspace_owner(uuid) to authenticated;

-- So a draft's workspace is always its workflow's.
alter table public.workflows add constraint workflows_id_workspace unique (id, workspace_id);

create table public.workflow_drafts (
  workflow_id uuid primary key,
  workspace_id uuid not null,
  graph jsonb not null,
  saved_by uuid not null,
  saved_at timestamptz not null default now(),
  foreign key (workflow_id, workspace_id) references public.workflows (id, workspace_id) on delete cascade
);

alter table public.workflow_drafts enable row level security;
revoke all on public.workflow_drafts from public, anon, authenticated;
grant select, insert, update, delete on public.workflow_drafts to authenticated;
grant select, insert, update, delete on public.workflow_drafts to autobots_runtime;
create policy members_read_drafts on public.workflow_drafts for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy owners_add_drafts on public.workflow_drafts for insert to authenticated
  with check (public.is_workspace_owner(workspace_id) and saved_by = auth.uid());
create policy owners_change_drafts on public.workflow_drafts for update to authenticated
  using (public.is_workspace_owner(workspace_id))
  with check (public.is_workspace_owner(workspace_id) and saved_by = auth.uid());
create policy owners_discard_drafts on public.workflow_drafts for delete to authenticated
  using (public.is_workspace_owner(workspace_id));
create policy runtime_drafts on public.workflow_drafts for all to autobots_runtime
  using (true) with check (true);
