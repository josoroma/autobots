-- US-15.2, PRD-Studio ID-01: one editable display name per user. A user writes only their own; the
-- user and members of a workspace they share may read it. Without a row, the app falls back to the
-- local part of the sign-in email.
create table public.user_profiles (
  user_id uuid primary key,
  display_name text not null
    check (char_length(display_name) between 1 and 60 and display_name = btrim(display_name)),
  updated_at timestamptz not null default now()
);

create function public.shares_workspace_with(target uuid) returns boolean
  language sql stable security definer set search_path = ''
  as $$ select exists (
    select 1
    from public.workspace_members mine
    join public.workspace_members theirs on theirs.workspace_id = mine.workspace_id
    where mine.user_id = auth.uid() and theirs.user_id = target
  ) $$;

revoke all on function public.shares_workspace_with(uuid) from public;
grant execute on function public.shares_workspace_with(uuid) to authenticated;

alter table public.user_profiles enable row level security;

revoke all on public.user_profiles from public, anon, authenticated;
grant select, insert, update on public.user_profiles to authenticated;
grant select, insert, update, delete on public.user_profiles to autobots_runtime;

create policy read_own_or_shared_profiles on public.user_profiles for select to authenticated
  using (user_id = auth.uid() or public.shares_workspace_with(user_id));
create policy insert_own_profile on public.user_profiles for insert to authenticated
  with check (user_id = auth.uid());
create policy update_own_profile on public.user_profiles for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy runtime_profiles on public.user_profiles for all to autobots_runtime
  using (true) with check (true);
