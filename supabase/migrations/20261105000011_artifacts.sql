-- SP-013 and LM-05: artifact metadata, staged before bytes and published only after verification.
alter table public.runs add column event_sequence bigint not null default 0;
update public.runs r set event_sequence =
  coalesce((select max(e.sequence) from public.run_events e where e.run_id = r.id), 0);

create table public.artifacts (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  run_id uuid not null references public.runs (id) on delete cascade,
  operation_id text not null unique,
  name text not null check (char_length(name) between 1 and 200),
  object_path text not null unique,
  media_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('staged', 'published', 'failed', 'missing')),
  created_at timestamptz not null default now(),
  published_at timestamptz
);

alter table public.artifacts enable row level security;
revoke all on public.artifacts from public, anon, authenticated;
grant select (id, workspace_id, run_id, name, media_type, size_bytes, sha256, status, created_at, published_at)
  on public.artifacts to authenticated;
grant select, insert, update on public.artifacts to autobots_runtime;
create policy members_read_artifacts on public.artifacts for select to authenticated
  using (public.is_workspace_member(workspace_id) and status in ('published', 'missing'));
create policy runtime_artifacts on public.artifacts for all to autobots_runtime
  using (true) with check (true);
