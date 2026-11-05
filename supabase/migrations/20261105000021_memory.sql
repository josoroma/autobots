-- PRD 8.4: scoped durable memory and lexical evidence in local Postgres, with no vector store.
create table public.memory_items (
  id uuid primary key,
  workspace_id uuid not null references public.workspaces (id),
  title text not null check (char_length(title) between 1 and 200),
  content text not null check (char_length(content) <= 20000),
  source jsonb not null,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  search tsvector generated always as (to_tsvector('english', title || ' ' || content)) stored
);

create index memory_items_search on public.memory_items using gin (search);
create index memory_items_workspace on public.memory_items (workspace_id);

alter table public.memory_items enable row level security;
revoke all on public.memory_items from public, anon, authenticated;
grant select (id, workspace_id, title, content, source, created_at) on public.memory_items to authenticated;
grant select, insert on public.memory_items to autobots_runtime;
create policy members_read_memory on public.memory_items for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy runtime_memory on public.memory_items for all to autobots_runtime using (true) with check (true);

alter table app_private.run_files
  add column search tsvector generated always as (to_tsvector('english', path || ' ' || content)) stored;
create index run_files_search on app_private.run_files using gin (search);

-- Long tool output, kept whole so a summary can cite it.
create table app_private.run_offloads (
  id uuid primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  tool_call_id text not null,
  tool_name text not null,
  content text not null,
  sha256 text not null,
  created_at timestamptz not null default now(),
  unique (run_id, tool_call_id)
);

create table app_private.run_summaries (
  id uuid primary key,
  run_id uuid not null references public.runs (id) on delete cascade,
  covers integer not null check (covers >= 1),
  summary text not null,
  sources jsonb not null,
  role text not null,
  profile text not null,
  created_at timestamptz not null default now()
);

create index run_summaries_run on app_private.run_summaries (run_id, covers desc);

revoke all on app_private.run_offloads, app_private.run_summaries from public, anon, authenticated;
grant select, insert on app_private.run_offloads, app_private.run_summaries to autobots_runtime;
