-- SP-013 and PRD 9.2: a proposal is stored before the wait, and bound to its exact arguments.
create table public.approval_requests (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  run_id uuid not null references public.runs (id) on delete cascade,
  operation_id text not null unique,
  tool_id text not null,
  tool_version integer not null,
  operation_class text not null,
  argument_hash text not null,
  arguments jsonb not null,
  scope_hash text not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'expired', 'withdrawn')),
  expires_at timestamptz not null,
  decided_by uuid,
  decided_at timestamptz,
  created_at timestamptz not null default now()
);

create index approval_requests_pending on public.approval_requests (workspace_id, created_at)
  where status = 'pending';

alter table public.approval_requests enable row level security;
revoke all on public.approval_requests from public, anon, authenticated;
grant select (id, workspace_id, run_id, tool_id, tool_version, operation_class, argument_hash, status, expires_at, decided_at, created_at)
  on public.approval_requests to authenticated;
grant select, insert, update on public.approval_requests to autobots_runtime;
create policy members_read_approvals on public.approval_requests for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy runtime_approvals on public.approval_requests for all to autobots_runtime
  using (true) with check (true);
